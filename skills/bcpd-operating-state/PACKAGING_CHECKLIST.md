# Packaging Checklist — BCPD Operating State Skill

_Step-by-step from "skeleton on disk" to "shippable Skill archive". Run
top-to-bottom; do not skip steps._

---

## Pre-flight

- [ ] Confirm working tree is clean: `git status --short` is empty.
- [ ] Confirm on `main`: `git rev-parse --abbrev-ref HEAD` returns `main`.
- [ ] Pull latest: `git pull --ff-only`.
- [ ] Confirm v2.1 state files exist (per `state/README.md`):
  - `output/operating_state_v2_1_bcpd.json`
  - `output/agent_chunks_v2_bcpd/` (46 chunks)
  - `output/agent_context_v2_1_bcpd.md`
  - `output/state_quality_report_v2_1_bcpd.md`
  - `data/reports/v2_0_to_v2_1_change_log.md`
  - `data/reports/coverage_improvement_opportunities.md`
  - `output/bcpd_data_gap_audit_for_streamline_session.md`

## 1. Run the full regression bar

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/
```

- [ ] Expect: **424 passed**.
- [ ] If any test fails: STOP. Do not package.

## 2. Regenerate runtime demos and verify no drift

```bash
python3 -m bedrock.workflows.cli all
git diff --exit-code output/runtime_demo/
```

- [ ] Expect: 6 demo files re-written, diff is empty.
- [ ] If diff is non-empty: a tool output changed. Either regenerate +
      commit (if intentional) or fix (if regression). Do not package
      until diff is empty.

## 3. Confirm guardrails by manual smoke

Spot-check each capability with one or two prompts. (Tool inputs match
`prompts/sample_questions.md`.) For each, confirm:

- [ ] **Generate Project Brief — Parkway Fields** mentions AultF /
      B-suffix / B1 / $4.0M / inferred.
- [ ] **Review Margin Report Readiness — bcpd** says "missing cost is
      unknown, not $0".
- [ ] **Find False Precision Risks — bcpd** lists $45,752,047 range/shell
      "not safe at lot grain".
- [ ] **Summarize Change Impact** lists all four dollar magnitudes
      ($4.0M / $6.75M / $6.55M / $45.75M) AND a "What did NOT change"
      section noting org-wide v2 is not available.
- [ ] **Prepare Finance / Land Review** has `## Finance`, `## Land`, and
      `## Ops` sections plus a `Decisions needed` section.
- [ ] **Draft Owner Update** explicitly says "org-wide v2 is NOT ready"
      AND lists BCPD / BCPBL / ASD / BCPI as in-scope entities AND lists
      Hillcrest / Flagship as out-of-scope.

## 4. Confirm the eight boundary refusals

Issue each of the 8 boundary questions from `prompts/sample_questions.md`.
Verify each is refused using the corresponding template in
`prompts/refusal_patterns.md`.

- [ ] Org-wide rollup → refused.
- [ ] "Allocate range rows anyway" → refused.
- [ ] "Treat missing as zero" → refused.
- [ ] "Ignore the inferred caveat" → refused.
- [ ] "Is the per-lot decoder validated?" → answered honestly **NO**.
- [ ] "Refresh from QuickBooks" → refused.
- [ ] "Combine HarmCo X-X with Harmony residential" → refused.
- [ ] "Roll SctLot into Scarlet Ridge" → refused.

## 5. Bundle the state into the Skill archive

For each bundled file in `state/README.md`'s "What the Skill reads" table,
copy or reference it inside the Skill archive at the expected path. The
exact path layout depends on the Skill platform — `state/README.md` gives
the canonical list.

- [ ] `output/operating_state_v2_1_bcpd.json` copied.
- [ ] `output/agent_chunks_v2_bcpd/` copied (full directory, 46 chunks).
- [ ] `output/agent_context_v2_1_bcpd.md` copied.
- [ ] `output/state_quality_report_v2_1_bcpd.md` copied.
- [ ] `data/reports/v2_0_to_v2_1_change_log.md` copied.
- [ ] `data/reports/coverage_improvement_opportunities.md` copied.
- [ ] `output/bcpd_data_gap_audit_for_streamline_session.md` copied.

## 6. Verify bundle hygiene

- [ ] Bundle size is ~5 MB (±1 MB). Sanity-check: `du -sh <bundle-dir>`.
- [ ] **No raw source CSVs** in the bundle:
      `find <bundle-dir> -name "*.csv" -path "*Collateral*"` → empty.
      `find <bundle-dir> -name "*.csv" -path "*LH Allocation*"` → empty.
- [ ] **No parquet files** in the bundle: `find <bundle-dir> -name "*.parquet"` → empty.
- [ ] **No scratch / dev artifacts**: `find <bundle-dir> -path "*scratch*"` → empty.
- [ ] **No staged tables**: `find <bundle-dir> -path "*data/staged*"` → empty.
- [ ] **No `.env` / `.key` / `.pem` files** in the bundle: `find <bundle-dir> \( -name ".env*" -o -name "*.key" -o -name "*.pem" \)` → empty.
- [ ] **No `__pycache__`** in the bundle: `find <bundle-dir> -name "__pycache__"` → empty.

## 7. Record v2.1 state sha256 manifest

```bash
( cd <bundle-dir> && find . -type f -name "*.json" -o -name "*.md" | sort | xargs sha256sum ) > <bundle-dir>/state/MANIFEST.sha256
```

- [ ] `MANIFEST.sha256` written.
- [ ] The line for `operating_state_v2_1_bcpd.json` matches the repo's
      current sha256 (verify with `sha256sum output/operating_state_v2_1_bcpd.json`).
- [ ] No mismatches.

## 8. Verify no protected file changed during bundling

```bash
git diff HEAD -- \
  output/operating_state_v2_1_bcpd.json \
  output/agent_context_v2_1_bcpd.md \
  output/state_quality_report_v2_1_bcpd.md \
  data/reports/v2_0_to_v2_1_change_log.md \
  data/reports/coverage_improvement_opportunities.md \
  data/reports/crosswalk_quality_audit_v1.md \
  data/reports/vf_lot_code_decoder_v1_report.md
```

- [ ] Expect: empty output.
- [ ] If any file shows a diff: STOP. The bundling step accidentally
      mutated source state.

## 9. Optional: produce the archive

The exact archive format depends on the Skill platform. As a placeholder:

```bash
# Example tarball — replace with the Skill platform's actual archive command.
tar -czf bcpd-operating-state-v2.1.tar.gz -C skills bcpd-operating-state/
```

- [ ] Archive created at the expected path.
- [ ] Archive size sanity-checked (~5–6 MB compressed).

## 10. Final manual sanity

- [ ] `SKILL.md` version field correctly reads "BCPD v2.1".
- [ ] `README.md` cross-references point to actual repo paths.
- [ ] `prompts/system_prompt.md` lists all eight guardrails.
- [ ] `prompts/refusal_patterns.md` covers all six refusal cases.
- [ ] `prompts/sample_questions.md` covers all six capabilities + all
      eight boundary cases.

## 11. Ship

- [ ] Tag the repo commit the bundle was built from:
      `git tag bcpd-operating-state-v2.1 -m "Skill bundle: BCPD Operating State v2.1"`.
- [ ] Push the tag: `git push --tags`.
- [ ] Upload the archive to the Skill distribution platform (per their
      docs — out of scope for this checklist).

## Rollback plan

If the Skill needs to be rolled back after ship:

1. Remove the Skill version from the distribution platform.
2. Re-publish the previous Skill version (if any).
3. File an issue against the runtime PR that introduced the regression.

The repo's `main` branch is unaffected by Skill ship/rollback — the
runtime continues to serve via CLI for any local user while the Skill is
out of service.
