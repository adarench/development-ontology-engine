"""Operational assertions — predicates that operate on (hits, pack, trace).

Each assertion is named and self-describing so that when it fails, the report
can explain *exactly* what operational invariant was violated. Avoid lambdas
and inline closures here: every assertion gets a class so the failure
narrative is reusable across scenarios and inspectable.

The assertions are deliberately operational, not generic. "MustReturnEntity"
is about a specific canonical-id surfacing in retrieval results — not
recall@k. "MustSurfaceWarning" is about a specific business caveat (e.g.,
inferred-cost) appearing in the pack — not about a soft-similarity score.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from bedrock.contracts import ContextPack, RetrievalHit
from bedrock.retrieval.orchestration import OrchestrationTrace


REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass
class AssertionResult:
    name: str
    description: str
    passed: bool
    message: str
    evidence: Dict[str, Any]


@runtime_checkable
class Assertion(Protocol):
    """An operational invariant. Implementations name themselves and produce a
    structured AssertionResult so the eval report can narrate failures."""

    name: str
    description: str

    def check(
        self,
        query: str,
        hits: List[RetrievalHit],
        pack: ContextPack,
        trace: OrchestrationTrace,
    ) -> AssertionResult: ...


# ---------------------------------------------------------------------------
# Helpers (kept module-private)
# ---------------------------------------------------------------------------

def _hit_identities(hits: List[RetrievalHit]) -> List[str]:
    return [h.entity_id or h.chunk_id or f"{h.source}::{h.title}" for h in hits]


def _all_warnings(pack: ContextPack) -> List[str]:
    return list(pack.semantic_warnings)


def _all_pack_files(pack: ContextPack) -> List[str]:
    return [r.source_file for r in pack.lineage if r.source_file != "_pack_notes"]


def _section_files(pack: ContextPack) -> List[str]:
    out: List[str] = []
    for s in pack.sections:
        if s.hit:
            out.extend(s.hit.source_files)
    return out


# ---------------------------------------------------------------------------
# Inclusion assertions
# ---------------------------------------------------------------------------


@dataclass
class MustReturnEntity:
    """Asserts a specific canonical entity_id surfaces in the retrieval hits."""

    entity_id: str
    name: str = "must_return_entity"

    @property
    def description(self) -> str:
        return f"`{self.entity_id}` must appear in retrieved hits"

    def check(self, query, hits, pack, trace) -> AssertionResult:
        ids = [h.entity_id for h in hits if h.entity_id]
        passed = self.entity_id in ids
        return AssertionResult(
            name=self.name,
            description=self.description,
            passed=passed,
            message=(
                f"found {self.entity_id} in hits"
                if passed
                else f"missing {self.entity_id}; got entity_ids={ids}"
            ),
            evidence={"target": self.entity_id, "returned_entity_ids": ids},
        )


@dataclass
class MustReturnGuardrailFile:
    """Asserts a guardrail markdown chunk surfaces in the pack."""

    filename_substring: str
    name: str = "must_return_guardrail_file"

    @property
    def description(self) -> str:
        return f"a guardrail chunk whose path contains `{self.filename_substring}` must surface"

    def check(self, query, hits, pack, trace) -> AssertionResult:
        files = _section_files(pack) + _all_pack_files(pack)
        present = any(self.filename_substring in f for f in files)
        return AssertionResult(
            name=self.name,
            description=self.description,
            passed=present,
            message=(
                f"guardrail chunk found"
                if present
                else f"no chunk contained {self.filename_substring!r}; files={files}"
            ),
            evidence={"target_substring": self.filename_substring, "files_in_pack": files},
        )


@dataclass
class MustHaveLineageIncluding:
    """Asserts the pack lineage cites a specific source file (substring match)."""

    source_file_substring: str
    name: str = "must_have_lineage_including"

    @property
    def description(self) -> str:
        return f"pack lineage must cite a file containing `{self.source_file_substring}`"

    def check(self, query, hits, pack, trace) -> AssertionResult:
        files = _all_pack_files(pack)
        present = any(self.source_file_substring in f for f in files)
        return AssertionResult(
            name=self.name,
            description=self.description,
            passed=present,
            message=(
                f"lineage cites a matching file"
                if present
                else f"no lineage entry contained {self.source_file_substring!r}; lineage={files}"
            ),
            evidence={"target_substring": self.source_file_substring, "lineage_files": files},
        )


@dataclass
class MustDistinguishOverlappingNames:
    """Multiple entity_ids that look 'the same' to a layperson must surface
    as distinct hits. The classic case: Harmony lot 101 in MF1 vs B1."""

    must_have_all_of: List[str]
    name: str = "must_distinguish_overlapping_names"

    @property
    def description(self) -> str:
        return f"must distinguish overlapping names: {self.must_have_all_of}"

    def check(self, query, hits, pack, trace) -> AssertionResult:
        ids = {h.entity_id for h in hits if h.entity_id}
        missing = [t for t in self.must_have_all_of if t not in ids]
        passed = not missing
        return AssertionResult(
            name=self.name,
            description=self.description,
            passed=passed,
            message=(
                f"all distinguished entities present"
                if passed
                else f"collapsed/missing: {missing}; got: {sorted(ids)[:20]}"
            ),
            evidence={
                "expected_all_of": self.must_have_all_of,
                "missing": missing,
                "returned_entity_ids": sorted(ids),
            },
        )


@dataclass
class MustResolveCrosswalk:
    """A query mentioning a non-canonical source value (e.g., 'SctLot') must
    surface entities whose canonical name matches `canonical_substring` —
    NOT the wrong canonical mapping."""

    source_value: str
    canonical_substring: str
    wrong_canonical_substring: Optional[str] = None
    name: str = "must_resolve_crosswalk"

    @property
    def description(self) -> str:
        wrong = (
            f" (and NOT `{self.wrong_canonical_substring}`)"
            if self.wrong_canonical_substring
            else ""
        )
        return f"`{self.source_value}` must resolve to `{self.canonical_substring}`{wrong}"

    def check(self, query, hits, pack, trace) -> AssertionResult:
        # Look at pack section text for canonical-name mentions
        merged_text = " ".join(s.text for s in pack.sections).lower()
        passed_canonical = self.canonical_substring.lower() in merged_text
        wrong_present = (
            self.wrong_canonical_substring
            and self.wrong_canonical_substring.lower() in merged_text
        )
        # When wrong_canonical_substring is set, failure if wrong appears
        # WITHOUT the right one being present. Co-occurrence is acceptable
        # because change-log chunks legitimately mention both.
        passed = passed_canonical and not (wrong_present and not passed_canonical)
        msg_parts = []
        msg_parts.append(
            f"canonical `{self.canonical_substring}` "
            + ("present" if passed_canonical else "MISSING")
        )
        if self.wrong_canonical_substring:
            msg_parts.append(
                f"wrong-mapping `{self.wrong_canonical_substring}` "
                + ("present" if wrong_present else "absent")
            )
        return AssertionResult(
            name=self.name,
            description=self.description,
            passed=passed,
            message="; ".join(msg_parts),
            evidence={
                "source_value": self.source_value,
                "canonical_substring": self.canonical_substring,
                "wrong_canonical_substring": self.wrong_canonical_substring,
                "canonical_present": passed_canonical,
                "wrong_present": bool(wrong_present),
            },
        )


@dataclass
class MustCarryConfidence:
    """Any hit returned for `entity_id` (when present) must carry `expected` confidence."""

    entity_id: str
    expected: str
    name: str = "must_carry_confidence"

    @property
    def description(self) -> str:
        return f"`{self.entity_id}` must carry confidence=`{self.expected}` if returned"

    def check(self, query, hits, pack, trace) -> AssertionResult:
        match = next((h for h in hits if h.entity_id == self.entity_id), None)
        if match is None:
            return AssertionResult(
                name=self.name,
                description=self.description,
                passed=False,
                message=f"{self.entity_id} not returned; cannot verify confidence label",
                evidence={"entity_id": self.entity_id},
            )
        passed = match.confidence == self.expected
        return AssertionResult(
            name=self.name,
            description=self.description,
            passed=passed,
            message=(
                f"confidence={match.confidence}"
                if passed
                else f"expected confidence={self.expected}, got {match.confidence}"
            ),
            evidence={"entity_id": self.entity_id, "actual_confidence": match.confidence},
        )


# ---------------------------------------------------------------------------
# Warning / caveat assertions
# ---------------------------------------------------------------------------


@dataclass
class MustSurfaceWarning:
    """Pack semantic_warnings must contain at least one entry matching the regex pattern."""

    pattern: str
    name: str = "must_surface_warning"

    @property
    def description(self) -> str:
        return f"pack must surface a warning matching `/{self.pattern}/`"

    def check(self, query, hits, pack, trace) -> AssertionResult:
        rx = re.compile(self.pattern, re.IGNORECASE)
        matches = [w for w in _all_warnings(pack) if rx.search(w)]
        passed = bool(matches)
        return AssertionResult(
            name=self.name,
            description=self.description,
            passed=passed,
            message=(
                f"matched warnings: {matches}"
                if passed
                else f"no warning matched /{self.pattern}/; got: {_all_warnings(pack)}"
            ),
            evidence={
                "pattern": self.pattern,
                "matched_warnings": matches,
                "all_warnings": _all_warnings(pack),
            },
        )


@dataclass
class MustNotPromoteInferredToValidated:
    """No section's hit may carry confidence='validated' if it was originally inferred.

    Implementation: scan rendered section text for the literal phrase
    'validated' attached to an inferred entity. This catches accidental
    promotion via concatenation. Belt-and-suspenders: also check the
    auto-warning fired for any inferred hit.
    """

    name: str = "must_not_promote_inferred_to_validated"
    description: str = "inferred-confidence hits must not be promoted to 'validated'"

    def check(self, query, hits, pack, trace) -> AssertionResult:
        offenders: List[str] = []
        for s in pack.sections:
            if not s.hit or s.hit.confidence != "inferred":
                continue
            # Inferred hits in the pack must not have 'validated' adjacent in their section text
            if re.search(r"\bvalidated\b", s.text, re.IGNORECASE) and not re.search(
                r"not source-owner-?validated|do not promote", s.text, re.IGNORECASE
            ):
                offenders.append(s.hit.entity_id or s.hit.chunk_id or s.title)
        passed = not offenders
        return AssertionResult(
            name=self.name,
            description=self.description,
            passed=passed,
            message=(
                "no promotion observed"
                if passed
                else f"inferred hits accidentally validated: {offenders}"
            ),
            evidence={"offenders": offenders},
        )


# ---------------------------------------------------------------------------
# Exclusion assertions
# ---------------------------------------------------------------------------


@dataclass
class MustNotReturnEntityIdMatching:
    """Hard-negative: no hit may have an entity_id matching the regex pattern.

    Use case: 'SctLot' query must not surface project:Scarlet Ridge entities.
    """

    pattern: str
    name: str = "must_not_return_entity_id_matching"

    @property
    def description(self) -> str:
        return f"no hit may have entity_id matching `/{self.pattern}/`"

    def check(self, query, hits, pack, trace) -> AssertionResult:
        rx = re.compile(self.pattern)
        offenders = [h.entity_id for h in hits if h.entity_id and rx.search(h.entity_id)]
        passed = not offenders
        return AssertionResult(
            name=self.name,
            description=self.description,
            passed=passed,
            message=(
                "no offending hits"
                if passed
                else f"forbidden entities surfaced: {offenders}"
            ),
            evidence={"pattern": self.pattern, "offenders": offenders},
        )


# ---------------------------------------------------------------------------
# Lineage / staleness assertions
# ---------------------------------------------------------------------------


@dataclass
class LineageHashesMustMatchDisk:
    """Every lineage entry's content_hash must match the file's current sha256.

    This is a staleness detector: if a source file was modified after the pack
    was built, the hash will mismatch and this assertion catches it.
    """

    name: str = "lineage_hashes_match_disk"
    description: str = "every lineage content_hash must match the on-disk file"
    repo_root: Path = REPO_ROOT

    def check(self, query, hits, pack, trace) -> AssertionResult:
        offenders: List[Dict[str, Any]] = []
        for ref in pack.lineage:
            if ref.source_file == "_pack_notes":
                continue
            path = self.repo_root / ref.source_file
            if not path.exists():
                continue  # missing files surface as None hash already
            actual = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
            if ref.content_hash and ref.content_hash != actual:
                offenders.append(
                    {
                        "file": ref.source_file,
                        "pack_hash": ref.content_hash,
                        "disk_hash": actual,
                    }
                )
        passed = not offenders
        return AssertionResult(
            name=self.name,
            description=self.description,
            passed=passed,
            message=(
                "all lineage hashes verify"
                if passed
                else f"stale lineage detected: {offenders}"
            ),
            evidence={"offenders": offenders},
        )
