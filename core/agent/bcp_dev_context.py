"""BcpDevContext — loader, integrity validator, and helper layer for v0.2.

Loads the 11 versioned JSON state files (6 process rules + 5 BCP Dev state)
that drive the v0.2 allocation/accounting tool family, exposes them as
immutable indexed structures, and validates cross-file integrity.

This module is the foundation for PR 2+ tools. It does not call out to
ClickUp / QBD / DataRails; v0.2 is file-based.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Optional


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class BcpDevContextError(Exception):
    """Base class for BcpDevContext errors."""


class BcpDevContextIntegrityError(BcpDevContextError):
    """Raised when validate_integrity() finds one or more issues."""

    def __init__(self, issues: list[str]):
        self.issues = list(issues)
        msg = "Integrity validation failed with {} issue(s):\n  - {}".format(
            len(self.issues), "\n  - ".join(self.issues)
        )
        super().__init__(msg)


class BcpDevContextFileMissing(BcpDevContextError):
    """Raised when a required v0.2 state file is not present on disk."""

    def __init__(self, file_path: Path, expected_consumers: Optional[list[str]] = None):
        self.file_path = Path(file_path)
        self.expected_consumers = list(expected_consumers or [])
        suffix = (
            f" (expected consumers: {', '.join(self.expected_consumers)})"
            if self.expected_consumers
            else ""
        )
        super().__init__(f"Required state file is missing: {self.file_path}{suffix}")


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolveResult:
    """Outcome of resolve_canonical(). canonical_value=None means
    explicitly unmapped — never a guess."""

    canonical_value: Optional[str]
    confidence: str
    validation_status: str
    evidence: str
    notes: str
    canonical_type: Optional[str] = None
    source_system: Optional[str] = None
    source_value: Optional[str] = None
    found: bool = False


@dataclass(frozen=True)
class FreshnessWarning:
    file_id: str
    path: str
    freshness_caveat: str
    last_modified: Optional[str]
    message: str


@dataclass(frozen=True)
class MdaDayResult:
    status: str  # 'pass' | 'partial' | 'fail' | 'unknown'
    counts: Mapping[str, Optional[int]]
    note: str = ""


@dataclass(frozen=True)
class ComputeStatusResult:
    decision: str  # 'compute_ready' | 'compute_ready_with_caveat' | 'blocked' | 'spec_only'
    community: str
    phase: Optional[str]
    reason: Optional[str]
    blockers: tuple[str, ...] = ()
    caveats: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


REQUIRED_PROCESS_RULES_FILES: Mapping[str, str] = MappingProxyType({
    "status_taxonomy": "state/process_rules/status_taxonomy_v1.json",
    "event_map": "state/process_rules/clickup_gl_event_map_v1.json",
    "account_prefix_matrix": "state/process_rules/account_prefix_matrix_v1.json",
    "allocation_methods": "state/process_rules/allocation_methods_v1.json",
    "monthly_review_checks": "state/process_rules/monthly_review_checks_v1.json",
    "exception_rules": "state/process_rules/exception_rules_v1.json",
})

REQUIRED_BCP_DEV_FILES: Mapping[str, str] = MappingProxyType({
    "allocation_workbook_schema": "state/bcp_dev/allocation_workbook_schema_v1.json",
    "allocation_input_requirements": "state/bcp_dev/allocation_input_requirements_v1.json",
    "per_lot_output_schema": "state/bcp_dev/per_lot_output_schema_v1.json",
    "source_crosswalks": "state/bcp_dev/source_crosswalks_v1.json",
    "source_file_manifest": "state/bcp_dev/source_file_manifest_v1.json",
})

TRIGGER_EVENT_META_WHITELIST: frozenset[str] = frozenset({
    "lot_sale",
    "ongoing",
    "pre_con_or_letter_received",
    "n/a",
})

TRIGGER_EVENT_META_RESOLUTION: Mapping[str, tuple[str, ...]] = MappingProxyType({
    "lot_sale": ("lot_sale_sih", "lot_sale_3rdy"),
    "ongoing": (),
    "pre_con_or_letter_received": (),
    "n/a": (),
})

ACCOUNT_SENTINEL_WHITELIST: frozenset[str] = frozenset({
    "cash_or_emd_release",
    "intercompany_revenue_or_transfer_clearing",
    "land_sale_revenue",
    "cash",
    "intercompany_clearing",
})

METHOD_ID_REF_WHITELIST: frozenset[str] = frozenset({
    "multiple",
    "computed_downstream",
    "none",
    "manual_input",
})

UNRES_PATTERN = re.compile(r"^UNRES-\d{2}$")

OUT_OF_SCOPE_DEVCOS: frozenset[str] = frozenset()
OUT_OF_SCOPE_COMMUNITIES: frozenset[str] = frozenset({"Hillcrest", "Flagship Belmont"})

PF_REMAINING_COMPUTE_READY: frozenset[str] = frozenset({"D2", "E1"})
PF_REMAINING_COMPUTE_READY_WITH_CAVEAT: frozenset[str] = frozenset({
    "E2", "F", "G1 SFR", "G1 Comm", "G2", "H",
})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _freeze(value: Any) -> Any:
    """Recursively wrap dicts in MappingProxyType and convert lists to tuples."""
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


def _detect_repo_root(start: Path | None = None) -> Path:
    here = Path(start or __file__).resolve()
    for parent in [here] + list(here.parents):
        if (parent / "state" / "process_rules").is_dir() and (parent / "core").is_dir():
            return parent
    raise RuntimeError(
        f"Could not detect repo root from {here} — no ancestor has state/process_rules and core/."
    )


# ---------------------------------------------------------------------------
# BcpDevContext
# ---------------------------------------------------------------------------


class BcpDevContext:
    """Lazy loader + integrity validator for the v0.2 state substrate.

    Loaders return immutable, indexed views (dicts wrapped in MappingProxyType,
    lists converted to tuples). Helper methods (resolve_canonical, mda_day_check,
    compute_status_for) provide downstream tools with deterministic answers
    grounded in those files.
    """

    def __init__(
        self,
        repo_root: Path | None = None,
        manifest_overrides: dict | None = None,
    ) -> None:
        self._repo_root = Path(repo_root) if repo_root else _detect_repo_root()
        self._manifest_overrides = MappingProxyType(dict(manifest_overrides or {}))
        self._raw: dict[str, Mapping[str, Any]] = {}

    # ------------------------------------------------------------------
    # Properties / paths
    # ------------------------------------------------------------------

    @property
    def repo_root(self) -> Path:
        return self._repo_root

    def _resolve_path(self, key: str, default_rel: str) -> Path:
        override = self._manifest_overrides.get(key) if self._manifest_overrides else None
        if override:
            return Path(override)
        return self._repo_root / default_rel

    def _load_json(
        self,
        key: str,
        default_rel: str,
        consumers: list[str] | None = None,
    ) -> Mapping[str, Any]:
        if key in self._raw:
            return self._raw[key]
        path = self._resolve_path(key, default_rel)
        if not path.exists():
            raise BcpDevContextFileMissing(path, expected_consumers=consumers)
        with open(path, "r") as f:
            data = json.load(f)
        frozen = _freeze(data)
        self._raw[key] = frozen
        return frozen

    # ------------------------------------------------------------------
    # Process rules loaders
    # ------------------------------------------------------------------

    def status_taxonomy(self) -> Mapping[str, Any]:
        return self._load_json(
            "status_taxonomy", REQUIRED_PROCESS_RULES_FILES["status_taxonomy"]
        )

    def event_map(self) -> Mapping[str, Any]:
        return self._load_json(
            "event_map", REQUIRED_PROCESS_RULES_FILES["event_map"]
        )

    def account_prefix_matrix(self) -> Mapping[str, Any]:
        return self._load_json(
            "account_prefix_matrix", REQUIRED_PROCESS_RULES_FILES["account_prefix_matrix"]
        )

    def allocation_methods(self) -> Mapping[str, Any]:
        return self._load_json(
            "allocation_methods", REQUIRED_PROCESS_RULES_FILES["allocation_methods"]
        )

    def monthly_review_checks(self) -> Mapping[str, Any]:
        return self._load_json(
            "monthly_review_checks", REQUIRED_PROCESS_RULES_FILES["monthly_review_checks"]
        )

    def exception_rules(self) -> Mapping[str, Any]:
        return self._load_json(
            "exception_rules", REQUIRED_PROCESS_RULES_FILES["exception_rules"]
        )

    # ------------------------------------------------------------------
    # BCP Dev state loaders
    # ------------------------------------------------------------------

    def allocation_workbook_schema(self) -> Mapping[str, Any]:
        return self._load_json(
            "allocation_workbook_schema",
            REQUIRED_BCP_DEV_FILES["allocation_workbook_schema"],
        )

    def allocation_input_requirements(self) -> Mapping[str, Any]:
        return self._load_json(
            "allocation_input_requirements",
            REQUIRED_BCP_DEV_FILES["allocation_input_requirements"],
        )

    def per_lot_output_schema(self) -> Mapping[str, Any]:
        return self._load_json(
            "per_lot_output_schema",
            REQUIRED_BCP_DEV_FILES["per_lot_output_schema"],
        )

    def source_crosswalks(self) -> Mapping[str, Any]:
        return self._load_json(
            "source_crosswalks",
            REQUIRED_BCP_DEV_FILES["source_crosswalks"],
        )

    def source_file_manifest(self) -> Mapping[str, Any]:
        return self._load_json(
            "source_file_manifest",
            REQUIRED_BCP_DEV_FILES["source_file_manifest"],
        )

    def aliases(self) -> Mapping[str, Any]:
        path = self._repo_root / "state" / "aliases.json"
        if not path.exists():
            return MappingProxyType({})
        with open(path, "r") as f:
            return _freeze(json.load(f))

    def load_all(self) -> None:
        """Force-load every required file. Tests use this to surface missing files
        early; tools normally rely on lazy loading."""
        for key, rel in REQUIRED_PROCESS_RULES_FILES.items():
            self._load_json(key, rel)
        for key, rel in REQUIRED_BCP_DEV_FILES.items():
            self._load_json(key, rel)

    # ------------------------------------------------------------------
    # Integrity validation
    # ------------------------------------------------------------------

    def validate_integrity(self) -> None:
        """Run all cross-file checks. Raises BcpDevContextIntegrityError if any fail."""
        issues: list[str] = []
        self.load_all()

        event_ids = {e["event_id"] for e in self.event_map()["events"]}
        method_ids = {m["method_id"] for m in self.allocation_methods()["methods"]}
        status_codes = {s["status_code"] for s in self.status_taxonomy()["statuses"]}
        chart_codes = {a["code"] for a in self.account_prefix_matrix()["posting_accounts"]} | {
            a["code"] for a in self.account_prefix_matrix()["alloc_accounts"]
        }

        # Check 1: allocation_methods.trigger_event resolves to event_id or whitelist
        for method in self.allocation_methods()["methods"]:
            trigger = method.get("trigger_event")
            if trigger is None:
                continue
            if trigger in event_ids:
                continue
            if trigger in TRIGGER_EVENT_META_WHITELIST:
                continue
            issues.append(
                f"allocation_methods[{method.get('method_id')}].trigger_event "
                f"= {trigger!r} does not resolve to an event_id or meta-event whitelist."
            )

        # Check 2: event_map.gl_entries scalar debit/credit_account resolve
        for event in self.event_map()["events"]:
            for entry in event.get("gl_entries", ()):
                for field_name in ("debit_account", "credit_account"):
                    value = entry.get(field_name)
                    if value is None:
                        continue
                    if value in chart_codes:
                        continue
                    if value in ACCOUNT_SENTINEL_WHITELIST:
                        continue
                    issues.append(
                        f"event_map[{event.get('event_id')}].{entry.get('entry_id')}.{field_name} "
                        f"= {value!r} does not resolve to chart code or sentinel whitelist."
                    )

        # Check 3: event_map.trigger.status_change_to resolves to status_taxonomy
        for event in self.event_map()["events"]:
            trig = event.get("trigger") or {}
            target = trig.get("status_change_to")
            if target is None:
                continue
            if target == "any":
                # status_change_from='any' shape (cancellation) — skip target check
                continue
            if target in status_codes:
                continue
            issues.append(
                f"event_map[{event.get('event_id')}].trigger.status_change_to "
                f"= {target!r} is not present in status_taxonomy."
            )

        # Check 4: status_taxonomy.event_trigger_id resolves to event_map
        for status in self.status_taxonomy()["statuses"]:
            etid = status.get("event_trigger_id")
            if etid is None:
                continue
            if etid in event_ids:
                continue
            issues.append(
                f"status_taxonomy[{status.get('status_code')}].event_trigger_id "
                f"= {etid!r} is not present in event_map."
            )

        # Check 5: per_lot_output_schema.fields[*].method_id_ref resolves
        for field_def in self.per_lot_output_schema()["fields"]:
            mref = field_def.get("method_id_ref")
            if mref is None:
                continue
            if mref in method_ids:
                continue
            if mref in METHOD_ID_REF_WHITELIST:
                continue
            issues.append(
                f"per_lot_output_schema.fields[{field_def.get('field_id')}].method_id_ref "
                f"= {mref!r} does not resolve to a method_id or whitelist."
            )

        # Check 6: UNRES-* id pattern
        for entry in self.source_crosswalks().get("unresolved_mappings", ()):
            uid = entry.get("id")
            if not isinstance(uid, str) or not UNRES_PATTERN.match(uid):
                issues.append(
                    f"source_crosswalks.unresolved_mappings entry id = {uid!r} "
                    f"does not match pattern UNRES-\\d{{2}}."
                )

        if issues:
            raise BcpDevContextIntegrityError(issues)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def resolve_canonical(
        self,
        source_system: str,
        source_value: str,
        canonical_type: str,
    ) -> ResolveResult:
        """Look up a source-system value in source_crosswalks_v1.json.

        Returns a frozen ResolveResult. canonical_value=None means the row
        exists but is explicitly unmapped (held for source-owner review); a
        ResolveResult with found=False means no row exists at all. Either way,
        confidence='inferred-unknown' and tools must not guess a mapping.
        """
        for table in self.source_crosswalks().get("tables", ()):
            for row in table.get("rows", ()):
                if (
                    str(row.get("source_system", "")).lower() == source_system.lower()
                    and str(row.get("source_value", "")) == source_value
                    and str(row.get("canonical_type", "")) == canonical_type
                ):
                    return ResolveResult(
                        canonical_value=row.get("canonical_value"),
                        confidence=str(row.get("confidence", "inferred-unknown")),
                        validation_status=str(row.get("validation_status", "unvalidated")),
                        evidence=str(row.get("evidence", "")),
                        notes=str(row.get("notes", "")),
                        canonical_type=canonical_type,
                        source_system=source_system,
                        source_value=source_value,
                        found=True,
                    )
        return ResolveResult(
            canonical_value=None,
            confidence="inferred-unknown",
            validation_status="unvalidated",
            evidence="",
            notes="No matching crosswalk row.",
            canonical_type=canonical_type,
            source_system=source_system,
            source_value=source_value,
            found=False,
        )

    def check_source_freshness(
        self,
        file_id: str | None = None,
        tool_name: str | None = None,
    ) -> list[FreshnessWarning]:
        """Return freshness warnings for files declared in source_file_manifest_v1.

        Files marked 'current' are skipped. file_id and tool_name filter the
        manifest scan. PR 1 returns the declared caveat verbatim; PR 3+ may
        layer last_modified-vs-threshold logic on top.
        """
        warnings: list[FreshnessWarning] = []
        for entry in self.source_file_manifest().get("files", ()):
            if file_id is not None and entry.get("file_id") != file_id:
                continue
            if tool_name is not None:
                consumers = entry.get("used_by_tools", ()) or ()
                if tool_name not in consumers:
                    continue
            caveat = str(entry.get("freshness_caveat", ""))
            if caveat == "current":
                continue
            warnings.append(
                FreshnessWarning(
                    file_id=str(entry.get("file_id", "")),
                    path=str(entry.get("path", "")),
                    freshness_caveat=caveat,
                    last_modified=entry.get("last_modified"),
                    message=f"{entry.get('file_id')}: {caveat}",
                )
            )
        return warnings

    def mda_day_check(self, community: str, phase: str) -> MdaDayResult:
        """Three-way lot-count tie check (skeleton for PR 1).

        Reads count overrides from manifest_overrides['mda_counts'] keyed as
        {community: {phase: {'clickup': n, 'mda': n, 'workbook': n}}}. Returns
        'partial' (not 'fail') when only two of three counts are available and
        the two agree, per exception_rules.mda_day_partial_tie_handling. Full
        data-source integration lands in PR 3.
        """
        counts_overrides = self._manifest_overrides.get("mda_counts") or {}
        scoped = (counts_overrides.get(community) or {}).get(phase) or {}
        clickup = scoped.get("clickup")
        mda = scoped.get("mda")
        workbook = scoped.get("workbook")
        counts = MappingProxyType({"clickup": clickup, "mda": mda, "workbook": workbook})

        present = [v for v in (clickup, mda, workbook) if v is not None]

        if not present:
            return MdaDayResult(
                status="unknown",
                counts=counts,
                note="No lot counts available; check cannot run yet.",
            )

        if len(present) == 3:
            if clickup == mda == workbook:
                return MdaDayResult(status="pass", counts=counts, note="All three counts agree.")
            return MdaDayResult(
                status="fail",
                counts=counts,
                note="All three counts present but they do not agree.",
            )

        if len(present) == 2:
            if len(set(present)) == 1:
                return MdaDayResult(
                    status="partial",
                    counts=counts,
                    note="Two of three counts available and they agree; the third is missing.",
                )
            return MdaDayResult(
                status="fail",
                counts=counts,
                note="Two counts available and they disagree.",
            )

        return MdaDayResult(
            status="partial",
            counts=counts,
            note="Only one count available; cannot tie-out.",
        )

    def compute_status_for(
        self, community: str, phase: str | None = None
    ) -> ComputeStatusResult:
        """Decision tree from implementation plan §4.

        Returns 'blocked', 'compute_ready', 'compute_ready_with_caveat', or
        'spec_only' for the (community, phase) pair, with reasons and blockers.
        """
        if community in OUT_OF_SCOPE_COMMUNITIES:
            return ComputeStatusResult(
                decision="blocked",
                community=community,
                phase=phase,
                reason="out_of_scope",
                blockers=(f"{community} is out of v0.2 scope (PROJECT_STATE org-wide rule).",),
            )

        if community == "Lomond Heights":
            return ComputeStatusResult(
                decision="blocked",
                community=community,
                phase=phase,
                reason="aaj_error_cascade",
                blockers=(
                    "AAJ Capitalized Interest #ERROR! cascades through LH Indirects.",
                ),
            )

        if community == "Eagle Vista":
            return ComputeStatusResult(
                decision="blocked",
                community=community,
                phase=phase,
                reason="not_in_workbook",
                blockers=(
                    "Eagle Vista is not present in the master Allocation Engine.",
                ),
            )

        if phase is not None and self._is_range_row_phase(phase):
            return ComputeStatusResult(
                decision="blocked",
                community=community,
                phase=phase,
                reason="range_row_unratified",
                blockers=(
                    "Range-row allocation method is unratified — refused per "
                    "allocation_methods_v1.range_row_unratified.refusal_reason.",
                ),
            )

        if community == "Parkway Fields" and phase is not None:
            key = phase.strip()
            if key in PF_REMAINING_COMPUTE_READY:
                return ComputeStatusResult(
                    decision="compute_ready",
                    community=community,
                    phase=phase,
                    reason=None,
                )
            if key in PF_REMAINING_COMPUTE_READY_WITH_CAVEAT:
                return ComputeStatusResult(
                    decision="compute_ready_with_caveat",
                    community=community,
                    phase=phase,
                    reason="estimated_direct_base_or_indirects_sign",
                    caveats=(
                        "PF Indirects pool is negative ($-1.25M) — workbook treats as credit.",
                        "Estimated Direct Base ($60K/lot SFR; $300K commercial) used where LandDev budget is absent.",
                    ),
                )

        return ComputeStatusResult(
            decision="spec_only",
            community=community,
            phase=phase,
            reason="master_no_pricing",
            blockers=(
                "Master Allocation Workbook v3 has no pricing populated; "
                "Sales Basis % = 0% for every phase.",
            ),
        )

    @staticmethod
    def _is_range_row_phase(phase: str) -> bool:
        """Recognise range-row phase identifiers such as 'AS 1-3', 'AS 4-6'."""
        return bool(re.match(r"^[A-Za-z]+\s?\d+\s?-\s?\d+$", phase.strip()))


__all__ = [
    "BcpDevContext",
    "BcpDevContextError",
    "BcpDevContextIntegrityError",
    "BcpDevContextFileMissing",
    "ResolveResult",
    "FreshnessWarning",
    "MdaDayResult",
    "ComputeStatusResult",
    "REQUIRED_PROCESS_RULES_FILES",
    "REQUIRED_BCP_DEV_FILES",
    "TRIGGER_EVENT_META_WHITELIST",
    "TRIGGER_EVENT_META_RESOLUTION",
    "ACCOUNT_SENTINEL_WHITELIST",
    "METHOD_ID_REF_WHITELIST",
    "PF_REMAINING_COMPUTE_READY",
    "PF_REMAINING_COMPUTE_READY_WITH_CAVEAT",
    "OUT_OF_SCOPE_COMMUNITIES",
]
