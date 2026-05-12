"""BCP Dev v0.2 read-only process tools.

PR 2 adds two LLM-facing tools that answer process questions grounded in the
six state/process_rules/*.json files. Neither tool computes allocations or
posts entries; both return markdown with citations and provenance.

Tools:
    query_bcp_dev_process      — route NL questions to the relevant rule file(s)
    explain_allocation_logic   — explain a method by cost_type or event

Both depend on `BcpDevContext` for state loading; PR 4 wires them to the MCP
server. PR 3 will add the readiness tools (`validate_crosswalk_readiness`,
`check_allocation_readiness`).
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from core.agent.bcp_dev_context import BcpDevContext
from core.tools.base import Tool


# ---------------------------------------------------------------------------
# Routing — maps keywords in a question to the rule files that may answer it.
# Each file's entries are evaluated in order; first-matching wins for an answer
# headline, but ALL matching routes are cited in the provenance block.
# ---------------------------------------------------------------------------


_ROUTE_TABLE: tuple[tuple[str, tuple[str, ...]], ...] = (
    # (route_id, keywords). Order = priority for the headline answer. The
    # status_taxonomy route is first because lifecycle questions are most
    # frequent; allocation_methods is checked before account_prefix_matrix so
    # that "allocation method for indirect costs" is routed to the method file,
    # not the prefix file (where "ind" would otherwise win on substring match).
    ("status_taxonomy", (
        "status", "lifecycle", "lnd_", "transition", "raw land", "entitled",
        "developing", "recorded", "sih", "3rdy", "cancelled", "on hold",
    )),
    ("event_map", (
        "event", "trigger", "fire", "post", "journal entry", "je ", "gl entry",
        "closing", "mda", "pre-con", "precon", "water letter", "lot sale",
        "final plat", "cancellation",
    )),
    ("allocation_methods", (
        "allocate", "allocation", "method", "land at mda", "direct per phase",
        "indirect cost", "indirect alloc", "warranty", "water by letter",
        "range row", "range-row", "shell", "ratified", "unratified",
        "cost pool", "sales basis",
    )),
    ("account_prefix_matrix", (
        "account", "prefix", "lnd", "mpl", " ind ", " dir ", " wtr ", " cpi ",
        "131-100", "131-200", "131-300", "131-010", "132-500", "132-510",
        "132-600", "132-610", "132-700", "132-710", "240-102", "240-112",
        "145-100", "posting", "validity", "chart of accounts",
    )),
    ("monthly_review_checks", (
        "monthly review", "monthly check", "reconcil", "aging", "drainage",
        "tie-out", "tie out", "three-way tie", "three way tie", "audit",
        "inventory by job", "wip balance", "stale crosswalk",
    )),
    ("exception_rules", (
        "exception", "refuse", "refusal", "cancel", "duplicate", "impair",
        "wip aging", "intercompany anomaly", "stale source", "partial tie",
        "off happy path",
    )),
)


_FILE_PATHS = {
    "status_taxonomy": "state/process_rules/status_taxonomy_v1.json",
    "event_map": "state/process_rules/clickup_gl_event_map_v1.json",
    "account_prefix_matrix": "state/process_rules/account_prefix_matrix_v1.json",
    "allocation_methods": "state/process_rules/allocation_methods_v1.json",
    "monthly_review_checks": "state/process_rules/monthly_review_checks_v1.json",
    "exception_rules": "state/process_rules/exception_rules_v1.json",
}


def _route(question: str) -> list[str]:
    """Return the list of route_ids whose keywords appear in `question`.

    A question may route to multiple files (e.g., 'allocation method for MDA'
    hits both allocation_methods and event_map). Order preserved from the
    route table for deterministic output.
    """
    q = question.lower()
    hits: list[str] = []
    for route_id, keywords in _ROUTE_TABLE:
        for kw in keywords:
            if kw in q:
                hits.append(route_id)
                break
    return hits


def _scope_header() -> str:
    return (
        "_[BCP Dev v0.2 — forward-looking accounting process; rules authored "
        "from briefing extracts pending source-doc recovery.]_\n\n"
    )


def _provenance_block(
    ctx: BcpDevContext,
    routes: Iterable[str],
    extra_notes: Optional[list[str]] = None,
) -> str:
    """Emit a provenance block listing every rule file consulted and its
    verification status (taken from the file's `source.doc_status` and
    rule-level `verification_status` markers)."""
    routes = list(routes)
    lines = ["## Provenance\n"]
    seen_paths: set[str] = set()
    for route in routes:
        path = _FILE_PATHS.get(route)
        if not path or path in seen_paths:
            continue
        seen_paths.add(path)
        doc = _load_route_doc(ctx, route)
        doc_status = ((doc.get("source") or {}).get("doc_status")) or "no doc_status declared"
        lines.append(f"- `{path}` — doc_status: {doc_status}")
    if extra_notes:
        for note in extra_notes:
            lines.append(f"- {note}")
    return "\n".join(lines) + "\n"


def _load_route_doc(ctx: BcpDevContext, route_id: str) -> Any:
    if route_id == "status_taxonomy":
        return ctx.status_taxonomy()
    if route_id == "event_map":
        return ctx.event_map()
    if route_id == "account_prefix_matrix":
        return ctx.account_prefix_matrix()
    if route_id == "allocation_methods":
        return ctx.allocation_methods()
    if route_id == "monthly_review_checks":
        return ctx.monthly_review_checks()
    if route_id == "exception_rules":
        return ctx.exception_rules()
    raise KeyError(route_id)


# ---------------------------------------------------------------------------
# Detection helpers used by routed answers
# ---------------------------------------------------------------------------


def _find_status(ctx: BcpDevContext, question: str) -> Optional[dict]:
    q = question.upper()
    for status in ctx.status_taxonomy()["statuses"]:
        code = str(status.get("status_code") or "")
        if code and code in q:
            return status
        label = str(status.get("status_label") or "")
        if label and label.upper() in q:
            return status
    return None


def _find_event(ctx: BcpDevContext, question: str) -> Optional[dict]:
    q = question.lower()
    for event in ctx.event_map()["events"]:
        eid = str(event.get("event_id") or "")
        if eid and eid in q:
            return event
        name = str(event.get("name") or "")
        if name and name.lower() in q:
            return event
    return None


def _find_method(ctx: BcpDevContext, question: str) -> Optional[dict]:
    q = question.lower()
    methods = list(ctx.allocation_methods()["methods"])
    # First, direct id / name match
    for method in methods:
        mid = str(method.get("method_id") or "")
        if mid and mid in q:
            return method
        name = str(method.get("name") or "")
        if name and name.lower() in q:
            return method
    # Second, cost_type fallback ("warranty", "water", etc.). Skip "land" and
    # "direct" because they collide with lifecycle / status phrasing.
    cost_to_method = {
        str((m.get("applies_to") or {}).get("cost_type", "")).lower(): m
        for m in methods
    }
    for ct in ("warranty", "water", "indirect"):
        if ct in q and ct in cost_to_method:
            return cost_to_method[ct]
    # "shell_range_row" / "range row" → unratified method
    if "range row" in q or "range-row" in q or "shell" in q:
        return cost_to_method.get("shell_range_row")
    return None


def _verification_caveat(verification_status: str | None) -> str | None:
    if not verification_status:
        return None
    if verification_status == "source_doc_extracted":
        return None
    return (
        f"Caveat: rule verification_status = `{verification_status}` — "
        "answer is pending source-doc recovery / ratification."
    )


# ---------------------------------------------------------------------------
# Tool 1: query_bcp_dev_process
# ---------------------------------------------------------------------------


class QueryBcpDevProcessTool(Tool):
    """Process Q&A grounded in state/process_rules/*.json."""

    output_format = "markdown"
    name = "query_bcp_dev_process"
    description = (
        "[BCP Dev v0.2 — forward-looking accounting process] Answer process "
        "questions about ClickUp lifecycle statuses, accounting events / GL "
        "triggers, account-prefix matrix, allocation methods, monthly review "
        "checks, and exception/refusal rules. Cites rule IDs and rule files. "
        "Refuses to invent rules or unratified allocation methods."
    )

    def __init__(self, context: BcpDevContext | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._ctx = context or BcpDevContext()

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": (
                        "Natural-language question about BCP Dev v0.2 "
                        "accounting / allocation / lifecycle process."
                    ),
                }
            },
            "required": ["question"],
        }

    def run(self, data: Any = None, question: str = "", **kwargs: Any) -> str:
        if isinstance(data, dict) and "question" in data:
            question = data["question"]
        question = (question or kwargs.get("question") or "").strip()
        if not question:
            return "**ERROR**: question is required."

        routes = _route(question)
        # Always cite at least one file — fall back to process-ontology pointer
        # rather than fabricating an answer if nothing routes.
        out: list[str] = [_scope_header()]

        if not routes:
            out.append(
                "## Answer\n\n"
                "This question does not route to any of the six v0.2 process "
                "rule files. The v0.2 substrate covers: status taxonomy, "
                "ClickUp→GL event map, account/prefix matrix, allocation "
                "methods, monthly review checks, and exception rules. Rephrase "
                "or scope to one of those areas.\n\n"
            )
            out.append(_provenance_block(self._ctx, ()))
            return "".join(out)

        # Compose answer per-route. First route gets the headline section;
        # additional routes append cross-references.
        out.append("## Answer\n\n")
        extra_notes: list[str] = []
        primary = routes[0]
        out.append(self._answer_for_route(primary, question, extra_notes))
        for r in routes[1:]:
            section = self._answer_for_route(r, question, extra_notes, is_secondary=True)
            if section:
                out.append("\n" + section)

        out.append("\n" + _provenance_block(self._ctx, routes, extra_notes))
        return "".join(out)

    # ------------------------------------------------------------------
    # Per-route answer composers
    # ------------------------------------------------------------------

    def _answer_for_route(
        self,
        route: str,
        question: str,
        extra_notes: list[str],
        is_secondary: bool = False,
    ) -> str:
        if route == "status_taxonomy":
            return self._answer_status(question, extra_notes, is_secondary)
        if route == "event_map":
            return self._answer_event(question, extra_notes, is_secondary)
        if route == "account_prefix_matrix":
            return self._answer_accounts(question, extra_notes, is_secondary)
        if route == "allocation_methods":
            return self._answer_methods(question, extra_notes, is_secondary)
        if route == "monthly_review_checks":
            return self._answer_monthly(question, extra_notes, is_secondary)
        if route == "exception_rules":
            return self._answer_exceptions(question, extra_notes, is_secondary)
        return ""

    def _answer_status(
        self, question: str, extra_notes: list[str], is_secondary: bool
    ) -> str:
        status = _find_status(self._ctx, question)
        header = "### Status lifecycle\n\n" if is_secondary else ""
        if status is None:
            return (
                header
                + "Status lifecycle answer requires a specific status code "
                "(e.g., `LND_RECORDED_SIH`). All 14 statuses live in "
                "`status_taxonomy_v1.json`.\n"
            )
        code = status.get("status_code")
        rule_id = status.get("rule_id")
        et = status.get("event_trigger_id")
        gl = status.get("gl_relevance")
        req_in = list(status.get("required_fields_for_transition_in") or [])
        req_out = list(status.get("required_fields_for_transition_out") or [])
        vstat = status.get("verification_status")

        lines = [
            header,
            f"**Status `{code}`** ([{rule_id} from status_taxonomy_v1.json])\n\n",
            f"- {status.get('description', '')}\n",
            f"- GL relevance: `{gl}`\n",
        ]
        if et:
            lines.append(
                f"- Event trigger: `{et}` "
                f"(see `clickup_gl_event_map_v1.json` for the JE).\n"
            )
        if req_in:
            lines.append(f"- Required fields to enter status: {', '.join(req_in)}\n")
        if req_out:
            lines.append(f"- Required fields to exit status: {', '.join(req_out)}\n")
        caveat = _verification_caveat(vstat)
        if caveat:
            extra_notes.append(caveat)
        return "".join(lines)

    def _answer_event(
        self, question: str, extra_notes: list[str], is_secondary: bool
    ) -> str:
        event = _find_event(self._ctx, question)
        header = "### Accounting event\n\n" if is_secondary else ""

        if event is None:
            # Generic event-map summary
            events = self._ctx.event_map()["events"]
            lines = [header, "ClickUp status changes that trigger DevCo GL entries:\n\n"]
            for e in events:
                trig = e.get("trigger") or {}
                target = trig.get("status_change_to") or "(non-status trigger)"
                rid = e.get("rule_id")
                lines.append(
                    f"- `{e['event_id']}` ← `{target}` "
                    f"([{rid} from clickup_gl_event_map_v1.json])\n"
                )
            return "".join(lines)

        eid = event.get("event_id")
        rule_id = event.get("rule_id")
        trig = event.get("trigger") or {}
        gl_entries = list(event.get("gl_entries") or ())
        gates = list(event.get("hard_gates") or ())
        vstat = event.get("verification_status")

        lines = [
            header,
            f"**Event `{eid}`** ([{rule_id} from clickup_gl_event_map_v1.json])\n\n",
            f"- {event.get('name', '')}\n",
            f"- Trigger: `{trig.get('source_system', '?')}` "
            f"→ status `{trig.get('status_change_to') or trig.get('trigger_doc') or '(see rule)'}`\n",
        ]
        required = list(event.get("required_inputs") or ())
        if required:
            lines.append("- Required inputs:\n")
            for r in required:
                blocks = r.get("blocks_event_if_missing")
                mark = "**blocks if missing**" if blocks else "optional"
                lines.append(f"  - `{r.get('field')}` ({r.get('system')}) — {mark}\n")
        if gl_entries:
            lines.append("- GL entries (recommended JEs — detection only, never posts):\n")
            for entry in gl_entries:
                desc = self._describe_gl_entry(entry, extra_notes)
                lines.append(f"  - {desc}\n")
        if gates:
            lines.append("- Hard gates:\n")
            for g in gates:
                lines.append(
                    f"  - `{g.get('gate_id')}` — {g.get('description', '')}\n"
                )
        caveat = _verification_caveat(vstat)
        if caveat:
            extra_notes.append(caveat)
        return "".join(lines)

    def _describe_gl_entry(self, entry: Any, extra_notes: list[str]) -> str:
        eid = entry.get("entry_id")
        debit = entry.get("debit_account") or entry.get("debit_account_options")
        credit = entry.get("credit_account") or entry.get("credit_account_options")
        # Sentinel detection
        sentinels = {
            "intercompany_revenue_or_transfer_clearing",
            "land_sale_revenue",
        }
        sentinel_hit = (
            (isinstance(credit, str) and credit in sentinels)
            or (isinstance(debit, str) and debit in sentinels)
        )
        if sentinel_hit:
            extra_notes.append(
                "Caveat: this event surfaces a credit-side sentinel "
                "(`intercompany_revenue_or_transfer_clearing` or "
                "`land_sale_revenue`) pending source-doc ratification (Q17/Q18). "
                "Tools must not fabricate a chart code."
            )
        amount = entry.get("amount_source", "")
        return (
            f"`{eid}`: debit {debit}, credit {credit}"
            + (f" — {amount}" if amount else "")
        )

    def _answer_accounts(
        self, question: str, extra_notes: list[str], is_secondary: bool
    ) -> str:
        apm = self._ctx.account_prefix_matrix()
        header = "### Account / prefix\n\n" if is_secondary else ""
        q = question.lower()
        prefix_targets = {"lnd", "mpl", "ind", "dir", "wtr", "cpi"}
        wanted_prefix = next((p for p in prefix_targets if f" {p}" in q or q.endswith(p) or q.startswith(p + " ")), None)
        # Code lookup
        code_match = None
        for entry in list(apm.get("posting_accounts") or ()) + list(apm.get("alloc_accounts") or ()):
            code = entry.get("code")
            if code and code in question:
                code_match = entry
                break

        if code_match is not None:
            return (
                header
                + f"**Account `{code_match.get('code')}` — {code_match.get('name')}** "
                f"([{code_match.get('rule_id')} from account_prefix_matrix_v1.json])\n\n"
                f"- Category: `{code_match.get('category', '')}`\n"
                f"- Valid prefixes: {', '.join(code_match.get('valid_prefixes') or ('—',))}\n"
            )
        if wanted_prefix:
            for entry in apm.get("job_prefixes") or ():
                if str(entry.get("code", "")).lower() == wanted_prefix:
                    return (
                        header
                        + f"**Prefix `{entry.get('code')}` ({entry.get('name')})** "
                        f"([{entry.get('rule_id')} from account_prefix_matrix_v1.json])\n\n"
                        f"- Owns cost type: {entry.get('owns_cost_type', '—')}\n"
                        f"- Valid posting accounts: "
                        f"{', '.join(entry.get('valid_posting_accounts') or ('—',))}\n"
                    )

        # Validity-matrix summary
        valid_pairs = list((apm.get("validity_matrix") or {}).get("valid_combinations") or ())
        lines = [
            header,
            "Account/prefix matrix overview "
            "([ACCT-* rules from account_prefix_matrix_v1.json]):\n\n",
            "- 8 posting accounts (145-100, 131-100, 131-200, 131-300, "
            "132-500, 132-600, 132-700, 240-102).\n",
            "- 5 alloc accounts (131-010, 132-510, 132-610, 132-710, 240-112).\n",
            "- 6 job prefixes (LND, MPL, IND, DIR, WTR, CPI).\n",
            f"- {len(valid_pairs)} ratified (prefix, account) combinations in "
            "`validity_matrix.valid_combinations`.\n",
        ]
        return "".join(lines)

    def _answer_methods(
        self, question: str, extra_notes: list[str], is_secondary: bool
    ) -> str:
        method = _find_method(self._ctx, question)
        header = "### Allocation method\n\n" if is_secondary else ""

        if method is not None:
            mid = method.get("method_id")
            rid = method.get("rule_id")
            ratified = bool(method.get("ratified"))
            applies = method.get("applies_to") or {}
            trig = method.get("trigger_event")
            vstat = method.get("verification_status")
            lines = [
                header,
                f"**Method `{mid}`** ([{rid} from allocation_methods_v1.json])\n\n",
                f"- {method.get('name', '')}\n",
                f"- Cost type: `{applies.get('cost_type', '—')}` / "
                f"scope: `{applies.get('scope', '—')}`\n",
                f"- Trigger event: `{trig}`\n",
                f"- Ratified: **{ratified}**\n",
            ]
            if not ratified:
                refusal = method.get("refusal_reason", "Method is unratified; tools refuse to compute.")
                lines.append(f"- **Refusal**: {refusal}\n")
                extra_notes.append(
                    f"Caveat: method `{mid}` is unratified — see "
                    "`exception_rules_v1.json#EXC-007` for refusal posture."
                )
            else:
                inputs = list(method.get("inputs_required") or ())
                if inputs:
                    lines.append("- Required inputs:\n")
                    for i in inputs:
                        lines.append(
                            f"  - `{i.get('input')}` "
                            f"(source: `{i.get('system')}`, type: `{i.get('type')}`)\n"
                        )
                calc = method.get("calculation") or {}
                if calc:
                    lines.append("- Calculation:\n")
                    for k, v in calc.items():
                        lines.append(f"  - `{k}`: {v}\n")
                if mid == "warranty_at_sale":
                    extra_notes.append(
                        "Caveat: warranty rate is an open question (Agent C Q5) "
                        "— tools refuse to populate `warranty_per_lot` until rate "
                        "and scope are source-owner ratified."
                    )
            caveat = _verification_caveat(vstat)
            if caveat:
                extra_notes.append(caveat)
            return "".join(lines)

        # Generic method-summary
        methods = list(self._ctx.allocation_methods()["methods"])
        lines = [
            header,
            "Allocation methods registered in v0.2 "
            "([ALLOC-* rules from allocation_methods_v1.json]):\n\n",
        ]
        for m in methods:
            mark = "ratified" if m.get("ratified") else "**unratified — refuse**"
            lines.append(
                f"- `{m.get('method_id')}` "
                f"({(m.get('applies_to') or {}).get('cost_type', '—')}) — {mark}\n"
            )
        return "".join(lines)

    def _answer_monthly(
        self, question: str, extra_notes: list[str], is_secondary: bool
    ) -> str:
        header = "### Monthly review\n\n" if is_secondary else ""
        checks = list(self._ctx.monthly_review_checks()["checks"])
        lines = [
            header,
            "Monthly review checks "
            "([CHK-* rules from monthly_review_checks_v1.json]):\n\n",
        ]
        for c in checks:
            lines.append(
                f"- `{c.get('check_id')}` — {c.get('name')} "
                f"(severity: `{c.get('severity')}`, "
                f"verification: `{c.get('verification_status')}`)\n"
            )
        return "".join(lines)

    def _answer_exceptions(
        self, question: str, extra_notes: list[str], is_secondary: bool
    ) -> str:
        header = "### Exception / refusal\n\n" if is_secondary else ""
        q = question.lower()
        # Range-row refusal specifically — common ask
        if "range" in q or "shell" in q or "unratified" in q:
            for r in self._ctx.exception_rules()["rules"]:
                if r.get("exception_id") == "unratified_method_refusal":
                    extra_notes.append(
                        "Caveat: range-row allocation is refused per "
                        "`exception_rules.unratified_method_refusal` until "
                        "Agent C Q6 is closed by the source owner."
                    )
                    return (
                        header
                        + f"**Range-row / shell allocation is refused** "
                        f"([{r.get('rule_id')} from exception_rules_v1.json]).\n\n"
                        f"- Reason: {r.get('action', {}).get('rule', '')}\n"
                        f"- Currently unratified methods: "
                        f"{', '.join((r.get('action') or {}).get('currently_unratified') or ('—',))}\n"
                    )
        # General exception list
        rules = list(self._ctx.exception_rules()["rules"])
        lines = [
            header,
            "Exception rules "
            "([EXC-* rules from exception_rules_v1.json]):\n\n",
        ]
        for r in rules:
            lines.append(
                f"- `{r.get('exception_id')}` — {r.get('name')} "
                f"(verification: `{r.get('verification_status')}`)\n"
            )
        return "".join(lines)


# ---------------------------------------------------------------------------
# Tool 2: explain_allocation_logic
# ---------------------------------------------------------------------------


class ExplainAllocationLogicTool(Tool):
    """For a given cost_type or event, explain which AllocationMethod applies."""

    output_format = "markdown"
    name = "explain_allocation_logic"
    description = (
        "[BCP Dev v0.2 — forward-looking accounting process] Explain the "
        "allocation method that applies for a given cost_type (Land, Direct, "
        "Indirect, Water, Warranty, shell_range_row) or accounting event "
        "(closing, mda_execution, pre_con, water_letter_received, "
        "lot_sale_sih, lot_sale_3rdy, etc.). Returns trigger, required inputs, "
        "calculation formula, ratified status, and GL accounts touched. "
        "Refuses to fabricate methods for unratified cases."
    )

    def __init__(self, context: BcpDevContext | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._ctx = context or BcpDevContext()

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "cost_type": {
                    "type": "string",
                    "description": (
                        "One of Land, Direct, Indirect, Water, Warranty, "
                        "shell_range_row."
                    ),
                },
                "event": {
                    "type": "string",
                    "description": (
                        "Optional event_id (closing, mda_execution, pre_con, "
                        "water_letter_received, final_plat, lot_sale_sih, "
                        "lot_sale_3rdy, cancellation)."
                    ),
                },
            },
            "required": [],
        }

    def run(
        self,
        data: Any = None,
        cost_type: str = "",
        event: str = "",
        **kwargs: Any,
    ) -> str:
        if isinstance(data, dict):
            cost_type = cost_type or data.get("cost_type", "")
            event = event or data.get("event", "")
        cost_type = (cost_type or kwargs.get("cost_type") or "").strip()
        event = (event or kwargs.get("event") or "").strip()

        if not cost_type and not event:
            return (
                "**ERROR**: provide at least one of `cost_type` or `event`. "
                "cost_type ∈ {Land, Direct, Indirect, Water, Warranty, "
                "shell_range_row}; event ∈ {closing, mda_execution, pre_con, "
                "water_letter_received, final_plat, lot_sale_sih, "
                "lot_sale_3rdy, cancellation}."
            )

        out: list[str] = [_scope_header()]
        extra_notes: list[str] = []

        # Resolve to one or more methods
        if event:
            methods = self._methods_for_event(event)
            event_doc = self._event_doc(event)
            if event_doc is None and not methods:
                out.append(
                    f"## Refusal\n\nEvent `{event}` is not in "
                    "`clickup_gl_event_map_v1.json`. Tools refuse to fabricate "
                    "an allocation method for an unknown event.\n\n"
                )
                out.append(_provenance_block(self._ctx, ("event_map",)))
                return "".join(out)
        else:
            methods = self._methods_for_cost_type(cost_type)
            event_doc = None

        if not methods:
            out.append(
                f"## Refusal\n\nNo allocation method ratified for "
                f"cost_type=`{cost_type or '—'}` event=`{event or '—'}`. "
                "Tools refuse to fabricate methods.\n\n"
            )
            out.append(_provenance_block(self._ctx, ("allocation_methods",)))
            return "".join(out)

        out.append("## Allocation method(s)\n\n")
        for method in methods:
            out.append(self._render_method(method, extra_notes))

        if event_doc is not None:
            out.append(self._render_event_gl(event_doc, extra_notes))

        out.append(
            _provenance_block(
                self._ctx,
                ("allocation_methods", "account_prefix_matrix", "event_map"),
                extra_notes,
            )
        )
        return "".join(out)

    # ------------------------------------------------------------------

    def _methods_for_cost_type(self, cost_type: str) -> list[dict]:
        if not cost_type:
            return []
        ct = cost_type.strip().lower()
        out: list[dict] = []
        for m in self._ctx.allocation_methods()["methods"]:
            applies = m.get("applies_to") or {}
            if str(applies.get("cost_type", "")).lower() == ct:
                out.append(dict(m))
        return out

    def _methods_for_event(self, event_id: str) -> list[dict]:
        eid = event_id.strip()
        matrix = (
            (self._ctx.allocation_methods().get("method_event_matrix") or {}).get("rows")
            or ()
        )
        method_ids: tuple[str, ...] = ()
        for row in matrix:
            if str(row.get("event_id", "")) == eid:
                method_ids = tuple(row.get("methods") or ())
                break
        methods_by_id = {
            m["method_id"]: dict(m) for m in self._ctx.allocation_methods()["methods"]
        }
        return [methods_by_id[mid] for mid in method_ids if mid in methods_by_id]

    def _event_doc(self, event_id: str) -> Optional[dict]:
        for e in self._ctx.event_map()["events"]:
            if e.get("event_id") == event_id:
                return dict(e)
        return None

    def _render_method(self, method: dict, extra_notes: list[str]) -> str:
        mid = method.get("method_id")
        rid = method.get("rule_id")
        applies = method.get("applies_to") or {}
        ratified = bool(method.get("ratified"))
        vstat = method.get("verification_status")

        lines = [
            f"### Method `{mid}` "
            f"([{rid} from allocation_methods_v1.json])\n\n",
            f"- Name: {method.get('name', '')}\n",
            f"- Cost type: `{applies.get('cost_type', '—')}` / "
            f"scope: `{applies.get('scope', '—')}`\n",
            f"- Trigger event: `{method.get('trigger_event')}`\n",
            f"- Ratified: **{ratified}**\n",
            f"- Verification: `{vstat}`\n",
        ]

        if not ratified:
            lines.append(
                f"\n**Refusal:** {method.get('refusal_reason', 'Method unratified.')}\n"
                "Tools must not approximate this method with a ratified one "
                "(see `exception_rules_v1.json#EXC-007`).\n\n"
            )
            extra_notes.append(
                f"Caveat: method `{mid}` is unratified — see "
                "`exception_rules_v1.json#unratified_method_refusal`."
            )
            return "".join(lines)

        inputs = list(method.get("inputs_required") or ())
        if inputs:
            lines.append("\n**Inputs required:**\n\n")
            for i in inputs:
                lines.append(
                    f"- `{i.get('input')}` (source: `{i.get('system')}`, "
                    f"type: `{i.get('type')}`)\n"
                )
        calc = method.get("calculation") or {}
        if calc:
            lines.append("\n**Calculation:**\n\n")
            for k, v in calc.items():
                lines.append(f"- `{k}`: {v}\n")

        # GL pair from account_prefix_matrix via the alloc_pair string on the method
        pair = applies.get("alloc_pair")
        if pair:
            lines.append(f"\n**GL pair:** {pair}\n")

        if mid == "warranty_at_sale":
            extra_notes.append(
                "Caveat: warranty rate value is unratified (Agent C Q5) and "
                "the warranty pool source is unresolved (Agent D UNRES-07). "
                "Tools must not populate a numeric warranty accrual until both "
                "are closed."
            )
            lines.append(
                "\n**Refusal on numeric example:** the warranty rate is not yet "
                "ratified; this tool surfaces the formula and refuses to substitute "
                "a numeric default.\n"
            )

        # Worked example: PF Phase E1 for direct_per_phase only (cheap, deterministic).
        if mid == "direct_per_phase":
            lines.append(
                "\n**Worked example (illustrative, Parkway Fields E1):** if "
                "`direct_cost_pool_usd_phase = $4,500,000` and "
                "`phase_lot_count = 198`, then "
                "`per_lot_share_usd ≈ $22,727`. Replace inputs from the PF "
                "satellite at runtime; values shown are illustrative only.\n"
            )

        return "".join(lines)

    def _render_event_gl(self, event_doc: dict, extra_notes: list[str]) -> str:
        eid = event_doc.get("event_id")
        rid = event_doc.get("rule_id")
        entries = list(event_doc.get("gl_entries") or ())
        if not entries:
            return ""
        lines = [
            f"\n### GL entries at `{eid}` "
            f"([{rid} from clickup_gl_event_map_v1.json])\n\n",
        ]
        sentinels = {
            "intercompany_revenue_or_transfer_clearing",
            "land_sale_revenue",
        }
        for entry in entries:
            debit = entry.get("debit_account") or entry.get("debit_account_options")
            credit = entry.get("credit_account") or entry.get("credit_account_options")
            line = (
                f"- `{entry.get('entry_id')}`: debit `{debit}`, credit `{credit}`"
            )
            amt = entry.get("amount_source")
            if amt:
                line += f" — amount: {amt}"
            sentinel = (
                (isinstance(credit, str) and credit in sentinels)
                or (isinstance(debit, str) and debit in sentinels)
            )
            if sentinel:
                line += " — **credit-side account pending source-doc ratification (Q17/Q18)**"
                extra_notes.append(
                    "Caveat: credit-side account on this event is a sentinel "
                    "(`intercompany_revenue_or_transfer_clearing` or "
                    "`land_sale_revenue`). Tools never fabricate a chart code "
                    "for these — they surface as `pending_source_doc_review`."
                )
            lines.append(line + "\n")
        return "".join(lines)


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


def register_bcp_dev_workflow_tools(registry, context: BcpDevContext | None = None):
    """Register the PR-2 BCP Dev tools on a ToolRegistry. Returns the registry."""
    ctx = context or BcpDevContext()
    registry.register(QueryBcpDevProcessTool(context=ctx))
    registry.register(ExplainAllocationLogicTool(context=ctx))
    return registry


BCP_DEV_WORKFLOW_TOOLS = (
    QueryBcpDevProcessTool,
    ExplainAllocationLogicTool,
)


__all__ = [
    "QueryBcpDevProcessTool",
    "ExplainAllocationLogicTool",
    "BCP_DEV_WORKFLOW_TOOLS",
    "register_bcp_dev_workflow_tools",
]
