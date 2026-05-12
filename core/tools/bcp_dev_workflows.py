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

from pathlib import Path
from typing import Any, Iterable, Optional

from core.agent.bcp_dev_context import BcpDevContext, OUT_OF_SCOPE_COMMUNITIES
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


# ---------------------------------------------------------------------------
# Tool 3: validate_crosswalk_readiness
# ---------------------------------------------------------------------------


class ValidateCrosswalkReadinessTool(Tool):
    """Report unmapped, ambiguous, or stale crosswalk entries."""

    output_format = "markdown"
    name = "validate_crosswalk_readiness"
    description = (
        "[BCP Dev v0.2 — forward-looking accounting process] Report "
        "crosswalk readiness across the 13 v0.2 crosswalk tables: resolved "
        "counts, unresolved-in-table rows (canonical_value=null), "
        "UNRES-* unresolved mappings, stale source files, and monitored-"
        "field drift alerts. Scope filter by community / DevCo / 'all'."
    )

    def __init__(self, context: BcpDevContext | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._ctx = context or BcpDevContext()

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "description": (
                        "Optional filter: a community name, a DevCo entity "
                        "code (BCPD, BCPBL, ASD, BCPI), or 'all'. Default 'all'."
                    ),
                }
            },
            "required": [],
        }

    def run(self, data: Any = None, scope: str = "all", **kwargs: Any) -> str:
        if isinstance(data, dict) and "scope" in data:
            scope = data["scope"]
        scope = (scope or kwargs.get("scope") or "all").strip() or "all"

        crosswalks = self._ctx.source_crosswalks()
        tables = list(crosswalks.get("tables") or ())
        unresolved = list(crosswalks.get("unresolved_mappings") or ())

        out: list[str] = [_scope_header()]
        out.append(f"# Crosswalk readiness — scope `{scope}`\n\n")

        # --- Resolved counts per table ---
        out.append("## Resolved counts per table\n\n")
        for t in tables:
            tid = t.get("table_id")
            name = t.get("name")
            rows = list(t.get("rows") or ())
            resolved = sum(1 for r in rows if r.get("canonical_value") is not None)
            null_rows = len(rows) - resolved
            out.append(
                f"- `{tid}` {name}: {resolved} resolved / "
                f"{null_rows} held / {len(rows)} total\n"
            )

        # --- Unresolved-in-table rows (canonical_value=null) ---
        out.append("\n## Unresolved rows (`canonical_value: null` — explicitly unmapped)\n\n")
        unresolved_rows_found = False
        for t in tables:
            for row in t.get("rows") or ():
                if row.get("canonical_value") is None:
                    if not _scope_matches(scope, row, tables):
                        continue
                    unresolved_rows_found = True
                    out.append(
                        f"- `{t.get('table_id')}` "
                        f"source `{row.get('source_system')}` → "
                        f"`{row.get('source_value')}` "
                        f"(confidence: `{row.get('confidence')}`) — "
                        f"{row.get('notes', '')}\n"
                    )
        if not unresolved_rows_found:
            out.append("- (none in scope)\n")

        # --- UNRES-* unresolved mappings ---
        out.append("\n## UNRES-* unresolved mappings (held for source-owner review)\n\n")
        for entry in unresolved:
            out.append(
                f"- `{entry.get('id')}` — {entry.get('topic')} "
                f"(confidence: `inferred-unknown`)\n  - {entry.get('details', '')}\n"
            )

        # --- Stale sources ---
        out.append("\n## Stale source files\n\n")
        warnings = self._ctx.check_source_freshness()
        if not warnings:
            out.append("- (none; all source files are `current`)\n")
        else:
            for w in warnings:
                out.append(
                    f"- `{w.file_id}` (`{w.path}`) — "
                    f"freshness_caveat=`{w.freshness_caveat}`, "
                    f"last_modified=`{w.last_modified}`\n"
                )

        # --- Monitored field drift expectations ---
        monitored = crosswalks.get("monitored_fields_summary") or {}
        out.append("\n## Monitored-field drift alerts\n\n")
        for category in ("must_alert_on_new_value", "must_alert_on_value_change"):
            items = list(monitored.get(category) or ())
            if items:
                out.append(f"**{category}:**\n")
                for it in items:
                    out.append(f"- {it}\n")

        out.append("\n" + _provenance_block(
            self._ctx,
            (),
            extra_notes=[
                "Crosswalk readiness uses `state/bcp_dev/source_crosswalks_v1.json` "
                "and `state/bcp_dev/source_file_manifest_v1.json`. "
                "Tools must never guess a mapping — `canonical_value: null` is "
                "explicitly unmapped.",
            ],
        ))
        return "".join(out)


def _scope_matches(scope: str, row: Any, tables: Iterable[Any]) -> bool:
    """Best-effort scope filter: 'all' passes everything; otherwise the row
    passes if its canonical_value contains the scope token, or if any other
    cell mentions it. Soft filter — readiness output should err on the side
    of showing rows when in doubt."""
    if scope == "all":
        return True
    needle = scope.lower()
    for key in ("canonical_value", "source_value", "notes", "evidence"):
        val = row.get(key)
        if isinstance(val, str) and needle in val.lower():
            return True
    return False


# ---------------------------------------------------------------------------
# Tool 4: check_allocation_readiness
# ---------------------------------------------------------------------------


class CheckAllocationReadinessTool(Tool):
    """Per (community, phase) readiness check using BcpDevContext.compute_status_for()."""

    output_format = "markdown"
    name = "check_allocation_readiness"
    description = (
        "[BCP Dev v0.2 — forward-looking accounting process] Given a "
        "(community, phase?) pair, report whether allocation can run today: "
        "compute_status decision, MDA Day tie-status, input checklist, "
        "crosswalk readiness, blocker list. Refuses to claim 'ready' for "
        "out-of-scope DevCos, LH (AAJ #ERROR cascade), range-row methods, "
        "or master communities with no pricing."
    )

    def __init__(self, context: BcpDevContext | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._ctx = context or BcpDevContext()

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "community": {
                    "type": "string",
                    "description": "Canonical community name.",
                },
                "phase": {
                    "type": "string",
                    "description": "Optional phase identifier (e.g. 'E1').",
                },
            },
            "required": ["community"],
        }

    def run(
        self,
        data: Any = None,
        community: str = "",
        phase: str = "",
        **kwargs: Any,
    ) -> str:
        if isinstance(data, dict):
            community = community or data.get("community", "")
            phase = phase or data.get("phase", "")
        community = (community or kwargs.get("community") or "").strip()
        phase = (phase or kwargs.get("phase") or "").strip() or None

        if not community:
            return "**ERROR**: `community` is required."

        out: list[str] = [_scope_header()]
        out.append(f"# Allocation readiness — {community}"
                   + (f" / {phase}" if phase else "") + "\n\n")

        status_result = self._ctx.compute_status_for(community, phase)
        out.append(
            f"**Decision:** `{status_result.decision}`"
            + (f" — reason: `{status_result.reason}`" if status_result.reason else "")
            + "\n\n"
        )

        if status_result.blockers:
            out.append("**Blockers:**\n\n")
            for b in status_result.blockers:
                out.append(f"- {b}\n")
            out.append("\n")
        if status_result.caveats:
            out.append("**Caveats:**\n\n")
            for c in status_result.caveats:
                out.append(f"- {c}\n")
            out.append("\n")

        # MDA Day tie status — best-effort, PR-1 skeleton (no count overrides in this path).
        if phase:
            mda = self._ctx.mda_day_check(community, phase)
            out.append(
                f"**MDA Day three-way tie:** `{mda.status}` — {mda.note}\n\n"
            )

        # Input checklist (always show — drives operator awareness even on blocked).
        reqs = self._ctx.allocation_input_requirements()
        global_inputs = list(reqs.get("global_required_inputs") or ())
        out.append("## Required inputs (from allocation_input_requirements_v1.json)\n\n")
        out.append("| Input | Category | Grain | Source | Today |\n")
        out.append("|---|---|---|---|---|\n")
        for r in global_inputs:
            out.append(
                f"| `{r.get('input_id')}` | {r.get('category')} | {r.get('grain')} | "
                f"{r.get('source_system_authoritative')} | "
                f"{r.get('default_status_today', '—')} |\n"
            )

        # Crosswalk readiness — summary line + UNRES count.
        cw = self._ctx.source_crosswalks()
        unres_count = len(list(cw.get("unresolved_mappings") or ()))
        out.append(
            f"\n## Crosswalk readiness summary\n\n"
            f"- {unres_count} UNRES-* unresolved mappings open "
            "(see `validate_crosswalk_readiness` for the full list).\n"
        )

        # Refusal-pattern cross-references.
        if status_result.decision == "blocked":
            out.append(
                "\n## Refusal\n\n"
                "Tool refuses to claim 'ready'. "
                f"Reason: `{status_result.reason}`. "
                "See `exception_rules_v1.json` for the canonical refusal "
                "patterns: `EXC-002` (missing required input), "
                "`EXC-007` (unratified method).\n"
            )

        out.append("\n" + _provenance_block(
            self._ctx,
            ("allocation_methods", "event_map", "exception_rules", "monthly_review_checks"),
            extra_notes=[
                "Decision tree lives in `BcpDevContext.compute_status_for()` "
                "(plan §4). MDA Day partial-tie returns `partial`, not `fail`.",
            ],
        ))
        return "".join(out)


# ---------------------------------------------------------------------------
# Tool 5: detect_accounting_events
# ---------------------------------------------------------------------------


class DetectAccountingEventsTool(Tool):
    """Surface AccountingEvents from ClickUp status changes. Detection only."""

    output_format = "markdown"
    name = "detect_accounting_events"
    description = (
        "[BCP Dev v0.2 — forward-looking accounting process] Given a "
        "ClickUp export CSV path or an explicit list of status changes, "
        "surface the AccountingEvents that should fire under "
        "clickup_gl_event_map_v1.json. Detection only — never posts "
        "entries. Surfaces missing required inputs, sentinel SIH/3RDY "
        "credit codes, unresolved crosswalks, and MDA Day partial-tie."
    )

    def __init__(self, context: BcpDevContext | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._ctx = context or BcpDevContext()

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "clickup_export_path": {
                    "type": "string",
                    "description": "Path to a ClickUp CSV export.",
                },
                "status_changes": {
                    "type": "array",
                    "description": (
                        "List of dicts: "
                        "{task_id, community, phase?, lot_number?, status_from, "
                        "status_to, fields?}"
                    ),
                    "items": {"type": "object"},
                },
            },
            "required": [],
        }

    def run(
        self,
        data: Any = None,
        clickup_export_path: str = "",
        status_changes: Optional[list] = None,
        **kwargs: Any,
    ) -> str:
        if isinstance(data, dict):
            clickup_export_path = clickup_export_path or data.get("clickup_export_path", "")
            status_changes = status_changes if status_changes is not None else data.get("status_changes")
        clickup_export_path = (
            clickup_export_path or kwargs.get("clickup_export_path") or ""
        ).strip()
        if status_changes is None:
            status_changes = kwargs.get("status_changes")

        if not clickup_export_path and not status_changes:
            return (
                "**ERROR**: provide either `clickup_export_path` or `status_changes`."
            )

        changes: list[dict] = []
        if isinstance(status_changes, list):
            changes.extend(dict(c) for c in status_changes)
        if clickup_export_path:
            try:
                changes.extend(self._load_export(clickup_export_path))
            except FileNotFoundError:
                return (
                    f"**ERROR**: clickup_export_path `{clickup_export_path}` not found."
                )

        out: list[str] = [_scope_header()]
        out.append("# Detected accounting events (detection only — does not post)\n\n")
        out.append(
            "_This tool **never posts** GL entries. The `gl_entries` field "
            "below is the recommended JE shape from "
            "`clickup_gl_event_map_v1.json`._\n\n"
        )

        if not changes:
            out.append("No status changes supplied or extracted from export.\n")
            out.append("\n" + _provenance_block(self._ctx, ("event_map",)))
            return "".join(out)

        events_by_target = self._events_by_status_target()
        extra_notes: list[str] = []
        detected_count = 0
        blocked_count = 0

        for change in changes:
            block = self._evaluate_change(change, events_by_target, extra_notes)
            if block is None:
                continue
            detected_count += 1
            if "blocker" in block.lower() or "missing" in block.lower():
                blocked_count += 1
            out.append(block)
            out.append("\n")

        if detected_count == 0:
            out.append("(no status changes matched any event in event_map.)\n")

        out.append(
            f"\n**Summary:** {detected_count} events detected; "
            f"{blocked_count} with blocking caveats.\n"
        )

        out.append("\n" + _provenance_block(
            self._ctx,
            ("event_map", "status_taxonomy", "exception_rules"),
            extra_notes=extra_notes,
        ))
        return "".join(out)

    # ------------------------------------------------------------------

    def _load_export(self, path_str: str) -> list[dict]:
        import csv
        path = Path(path_str)
        if not path.is_absolute():
            path = self._ctx.repo_root / path_str
        if not path.exists():
            raise FileNotFoundError(path_str)
        rows: list[dict] = []
        with open(path, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Heuristic: status field; community + phase + lot from
                # subdivision / phase / lot_num. We cannot infer from-status
                # without a delta export, so emit current-state inference rows
                # with an inferred-unknown caveat.
                rows.append({
                    "task_id": row.get("id"),
                    "community": row.get("subdivision"),
                    "phase": row.get("phase"),
                    "lot_number": row.get("lot_num"),
                    "status_from": None,  # unknown in single-snapshot export
                    "status_to": row.get("status"),
                    "fields": {
                        "FMV at Transfer": row.get("FMV at Transfer"),
                        "Sale Price": row.get("Sale Price"),
                        "Sale Date": row.get("sold_date") or row.get("close_date"),
                    },
                    "_inferred_from_snapshot": True,
                })
        return rows

    def _events_by_status_target(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for event in self._ctx.event_map()["events"]:
            trig = event.get("trigger") or {}
            tgt = trig.get("status_change_to")
            if tgt:
                out[tgt] = dict(event)
        return out

    def _evaluate_change(
        self,
        change: dict,
        events_by_target: dict[str, dict],
        extra_notes: list[str],
    ) -> Optional[str]:
        target = change.get("status_to")
        if not target:
            return None
        event = events_by_target.get(target)
        if event is None:
            return (
                f"### Change `{change.get('task_id', '?')}` — "
                f"status `{target}` not in event_map\n\n"
                "- No accounting event fires for this status change.\n"
            )

        eid = event.get("event_id")
        rid = event.get("rule_id")
        required = list(event.get("required_inputs") or ())
        fields = dict(change.get("fields") or {})

        # Required-field check
        missing_blocking: list[str] = []
        for r in required:
            if not r.get("blocks_event_if_missing"):
                continue
            fname = r.get("field")
            val = fields.get(fname)
            if val in (None, "", "null"):
                missing_blocking.append(str(fname))

        # Crosswalk resolution for community
        cw_status: list[str] = []
        community = change.get("community")
        if community:
            res = self._ctx.resolve_canonical(
                source_system="ClickUp",
                source_value=community,
                canonical_type="community",
            )
            if res.canonical_value is None:
                held_or_missing = (
                    "explicitly unmapped — held for source-owner review"
                    if res.found
                    else "no crosswalk row"
                )
                extra_notes.append(
                    f"Caveat: ClickUp subdivision `{community}` did not resolve "
                    f"to a canonical community ({held_or_missing}) — "
                    "confidence `inferred-unknown`."
                )
                cw_status.append(
                    f"community resolution: **inferred-unknown** "
                    f"(source `{community}`, {held_or_missing})"
                )
            else:
                cw_status.append(
                    f"community resolution: `{res.canonical_value}` "
                    f"(confidence `{res.confidence}`)"
                )

        # GL entries + sentinel detection
        sentinels = {
            "intercompany_revenue_or_transfer_clearing",
            "land_sale_revenue",
        }
        gl_lines: list[str] = []
        sentinel_hit = False
        for entry in event.get("gl_entries") or ():
            debit = entry.get("debit_account") or entry.get("debit_account_options")
            credit = entry.get("credit_account") or entry.get("credit_account_options")
            if (isinstance(credit, str) and credit in sentinels) or (
                isinstance(debit, str) and debit in sentinels
            ):
                sentinel_hit = True
            gl_lines.append(
                f"  - `{entry.get('entry_id')}`: debit `{debit}`, credit `{credit}`"
                + (f" — {entry.get('amount_source')}" if entry.get("amount_source") else "")
            )
        if sentinel_hit:
            extra_notes.append(
                "Caveat: this event references a sentinel credit account "
                "(`intercompany_revenue_or_transfer_clearing` / "
                "`land_sale_revenue`); tools must never fabricate a chart code "
                "— surfaced as `pending_source_doc_review` (Q17/Q18)."
            )

        # MDA Day partial-tie wording for mda_execution
        mda_line = ""
        if eid == "mda_execution":
            mda_line = (
                "- `mda_day_check`: requires three-way tie of "
                "`clickup_lot_count == mda_lot_count == workbook_lot_count`. "
                "If only two of three are available and they agree, "
                "emit `partial`, not `fail` "
                "(per `exception_rules.mda_day_partial_tie_handling`).\n"
            )

        # Overall confidence (worst-link)
        worst: list[str] = []
        if missing_blocking:
            worst.append("blocker: missing_required_input")
        if sentinel_hit:
            worst.append("pending_source_doc_review (credit code)")
        if any("inferred-unknown" in s for s in cw_status):
            worst.append("inferred-unknown (crosswalk)")
        confidence_line = "high" if not worst else " / ".join(worst)

        lines = [
            f"### `{event.get('name')}` — event `{eid}` "
            f"([{rid} from clickup_gl_event_map_v1.json])\n\n",
            f"- Task: `{change.get('task_id', '?')}` "
            f"({change.get('community') or '—'} / "
            f"{change.get('phase') or '—'} / "
            f"lot {change.get('lot_number') or '—'})\n",
            f"- Status change: `{change.get('status_from') or '?'}` → `{target}`\n",
        ]
        if change.get("_inferred_from_snapshot"):
            lines.append(
                "- ⚠ Inferred from single-snapshot ClickUp export "
                "(status_from unknown); confidence reduced accordingly.\n"
            )
        if cw_status:
            for s in cw_status:
                lines.append(f"- {s}\n")
        if missing_blocking:
            lines.append(
                f"- **Blocker:** missing required input(s): "
                f"`{', '.join(missing_blocking)}` — "
                "see `exception_rules.missing_required_input_refusal`.\n"
            )
        else:
            lines.append("- Required inputs present: yes (for this change)\n")
        if mda_line:
            lines.append(mda_line)
        if gl_lines:
            lines.append("- Recommended JE shape (not posted):\n")
            lines.extend(line + "\n" for line in gl_lines)
        lines.append(f"- Confidence (worst-link): `{confidence_line}`\n")
        return "".join(lines)


# ---------------------------------------------------------------------------
# Tool 6: generate_per_lot_output_spec
# ---------------------------------------------------------------------------


class GeneratePerLotOutputSpecTool(Tool):
    """Spec-only Per-Lot Output for any (community, phase). Never emits values."""

    output_format = "markdown"
    name = "generate_per_lot_output_spec"
    description = (
        "[BCP Dev v0.2 — forward-looking accounting process] For a given "
        "(community, phase?), return the canonical Per-Lot Output shape "
        "with per-field compute_status and blocker list. SPEC ONLY — never "
        "emits computed dollar values. Cites refusal patterns from "
        "`per_lot_output_schema_v1.json` for warranty, range-row, missing "
        "pricing, LH AAJ #ERROR, unresolved crosswalks, and PF negative-"
        "Indirects sign convention."
    )

    def __init__(self, context: BcpDevContext | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._ctx = context or BcpDevContext()

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "community": {"type": "string"},
                "phase": {"type": "string"},
            },
            "required": ["community"],
        }

    def run(
        self,
        data: Any = None,
        community: str = "",
        phase: str = "",
        **kwargs: Any,
    ) -> str:
        if isinstance(data, dict):
            community = community or data.get("community", "")
            phase = phase or data.get("phase", "")
        community = (community or kwargs.get("community") or "").strip()
        phase = (phase or kwargs.get("phase") or "").strip() or None

        if not community:
            return "**ERROR**: `community` is required."

        schema = self._ctx.per_lot_output_schema()
        fields = list(schema.get("fields") or ())
        refusal_patterns = list(schema.get("refusal_patterns") or ())

        status_result = self._ctx.compute_status_for(community, phase)
        is_pf = community == "Parkway Fields"
        is_lh = community == "Lomond Heights"
        is_eagle = community == "Eagle Vista"
        is_range_row = phase is not None and self._is_range_row_phase(phase)

        out: list[str] = [_scope_header()]
        out.append(
            f"# Per-Lot Output Spec — {community}"
            + (f" / {phase}" if phase else "") + "\n\n"
        )
        out.append("_Spec only. No numeric values are emitted by this tool._\n\n")
        out.append(
            f"**Scope decision:** `{status_result.decision}`"
            + (f" — `{status_result.reason}`" if status_result.reason else "")
            + "\n\n"
        )

        # Per-field table
        out.append("## Fields\n\n")
        out.append("| Field | method_id_ref | grain | compute_status | source | blocker |\n")
        out.append("|---|---|---|---|---|---|\n")
        for f in fields:
            field_status, blocker = self._field_status(
                f, status_result.decision, is_pf, is_lh, is_eagle, is_range_row
            )
            method_ref = f.get("method_id_ref") or "—"
            grain = f.get("grain") or "—"
            source = (
                f.get("source_today")
                or f.get("formula")
                or f.get("source_eventually")
                or "—"
            )
            out.append(
                f"| `{f.get('field_id')}` | `{method_ref}` | {grain} | "
                f"`{field_status}` | {source} | {blocker or '—'} |\n"
            )

        # Refusal-pattern citations
        out.append("\n## Refusal patterns cited (from per_lot_output_schema_v1.json)\n\n")
        for pat in refusal_patterns:
            applies = False
            pid = pat.get("pattern_id", "")
            trigger = pat.get("trigger", "")
            if pid == "refuse_range_row" and is_range_row:
                applies = True
            if pid == "refuse_zero_basis" and status_result.decision == "spec_only":
                applies = True
            if pid == "refuse_org_wide" and community in OUT_OF_SCOPE_COMMUNITIES:
                applies = True
            if pid == "refuse_unmapped_phase":
                # Always cite as available
                applies = True
            if pid == "refuse_mda_gate_failure":
                applies = True
            mark = "**applies**" if applies else "available"
            out.append(
                f"- `{pid}` ({mark}) — trigger: {trigger}\n"
                f"  - {pat.get('behavior', '')}\n"
            )

        # Scope-specific notes
        if is_pf:
            out.append(
                "\n## PF-specific notes\n\n"
                "- **Indirect sign convention:** PF satellite shows the Indirect pool as "
                "negative ($-1,249,493.54); workbook treats this as a credit. "
                "Tools that later compute values must flag this caveat.\n"
                "- **Previous-section refusal:** Phases B2, D1, G1 Church are "
                "historical/closed. The future `generate_per_lot_output` tool "
                "refuses to re-allocate these.\n"
            )
        if is_lh:
            out.append(
                "\n## LH-specific blocker\n\n"
                "- AAJ Capitalized Interest cell is `#ERROR!`, cascading through "
                "Indirects total. Tool emits blocker; no values produced.\n"
            )
        if is_eagle:
            out.append(
                "\n## Eagle Vista blocker\n\n"
                "- Not present in master Allocation Engine. Spec emitted; values "
                "blocked until community is added to the workbook.\n"
            )

        extra_notes = []
        if any("warranty" in (f.get("field_id") or "") for f in fields):
            extra_notes.append(
                "Caveat: `warranty_allocated` and `warranty_per_lot` are spec-only "
                "until warranty rate (Q5) and pool source (UNRES-07) are ratified."
            )
        if is_range_row:
            extra_notes.append(
                "Caveat: range-row phases refuse per "
                "`allocation_methods.range_row_unratified` + `exception_rules.EXC-007`."
            )

        out.append("\n" + _provenance_block(
            self._ctx,
            (),
            extra_notes=[
                "Spec sourced from `state/bcp_dev/per_lot_output_schema_v1.json`. "
                "No values computed; per-field statuses derived from "
                "BcpDevContext.compute_status_for and per_lot_output_schema."
                + (f" | {' | '.join(extra_notes)}" if extra_notes else "")
            ],
        ))
        return "".join(out)

    @staticmethod
    def _is_range_row_phase(phase: str) -> bool:
        import re
        return bool(re.match(r"^[A-Za-z]+\s?\d+\s?-\s?\d+$", phase.strip()))

    def _field_status(
        self,
        field: dict,
        scope_decision: str,
        is_pf: bool,
        is_lh: bool,
        is_eagle: bool,
        is_range_row: bool,
    ) -> tuple[str, Optional[str]]:
        """Resolve per-field compute_status for the current scope.

        Returns (status, blocker_id_or_None). Status values: passthrough,
        input_required, computed_when_inputs_present, blocked, refused, spec_only.
        """
        field_id = field.get("field_id", "")
        category = field.get("category", "")
        method_ref = field.get("method_id_ref")

        if is_eagle:
            return ("blocked", "not_in_workbook")
        if is_lh:
            return ("blocked", "aaj_error_cascade")
        if is_range_row:
            return ("refused", "range_row_unratified")
        if method_ref == "warranty_at_sale":
            return ("refused", "warranty_rate_unratified")
        if scope_decision == "spec_only":
            if category in {"key", "input"}:
                return ("input_required", "master_no_pricing")
            if category in {"computed", "input_estimated"}:
                return ("blocked", "master_no_pricing")
            return ("spec_only", "master_no_pricing")
        if scope_decision == "compute_ready_with_caveat" and is_pf and method_ref == "indirect_community":
            return ("computed_with_caveat", "pf_indirects_negative_sign")
        if scope_decision in {"compute_ready", "compute_ready_with_caveat"}:
            if category in {"key", "input"}:
                return ("passthrough", None)
            return ("computed_when_inputs_present", None)
        if scope_decision == "blocked":
            return ("blocked", "see_scope_decision")
        return (field.get("compute_status", "spec_only"), None)


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


def register_bcp_dev_workflow_tools(registry, context: BcpDevContext | None = None):
    """Register all BCP Dev v0.2 MVP tools on a ToolRegistry. Returns the registry."""
    ctx = context or BcpDevContext()
    registry.register(QueryBcpDevProcessTool(context=ctx))
    registry.register(ExplainAllocationLogicTool(context=ctx))
    registry.register(ValidateCrosswalkReadinessTool(context=ctx))
    registry.register(CheckAllocationReadinessTool(context=ctx))
    registry.register(DetectAccountingEventsTool(context=ctx))
    registry.register(GeneratePerLotOutputSpecTool(context=ctx))
    return registry


BCP_DEV_WORKFLOW_TOOLS = (
    QueryBcpDevProcessTool,
    ExplainAllocationLogicTool,
    ValidateCrosswalkReadinessTool,
    CheckAllocationReadinessTool,
    DetectAccountingEventsTool,
    GeneratePerLotOutputSpecTool,
)


__all__ = [
    "QueryBcpDevProcessTool",
    "ExplainAllocationLogicTool",
    "ValidateCrosswalkReadinessTool",
    "CheckAllocationReadinessTool",
    "DetectAccountingEventsTool",
    "GeneratePerLotOutputSpecTool",
    "BCP_DEV_WORKFLOW_TOOLS",
    "register_bcp_dev_workflow_tools",
]
