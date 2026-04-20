"""
build_phase_state.py — State Engine v1

Computes PhaseState records by aggregating LotState (for actuals + composition)
and joining expected cost data from allocation sheets (LH + PF) with a
Collateral Report fallback for other phases.

Pipeline:
    1. Load LotState output
    2. Aggregate composition + actuals + timing per phase
    3. Compute phase_state and phase_majority_state
    4. Parse allocation sheets (LH + PF) → expected costs (FULL fidelity)
    5. Parse Collateral Report → expected costs (PARTIAL fidelity, fallback)
    6. Compute variance
    7. Write CSV + Parquet output

Run:
    python pipelines/build_phase_state.py
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

import config


# ---------------------------------------------------------------------------
# Money parser (same as build_lot_state, duplicated for module independence)
# ---------------------------------------------------------------------------

def parse_money(value) -> float:
    """Parse a money value from raw CSV: handles $, commas, parens, dashes."""
    if pd.isna(value):
        return 0.0
    s = str(value).strip()
    if s in ("", "-", "—"):
        return 0.0
    s = s.replace("$", "").replace(",", "").replace("(", "-").replace(")", "").strip()
    if s == "" or s == "-":
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def strip_str(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


# ---------------------------------------------------------------------------
# Step 1: Load LotState
# ---------------------------------------------------------------------------

def load_lot_state() -> Tuple[pd.DataFrame, pd.Timestamp]:
    df = pd.read_csv(config.LOT_STATE_CSV, parse_dates=["as_of_date"])
    as_of_date = df["as_of_date"].iloc[0]
    return df, pd.Timestamp(as_of_date)


# ---------------------------------------------------------------------------
# Step 2-3: Phase aggregation
# ---------------------------------------------------------------------------

def compute_phase_state(lot_states: List[str]) -> str:
    """Waterfall: most-advanced lot defines phase status."""
    states = set(lot_states)
    if states == {"CLOSED"}:
        return "CLOSED_OUT"
    if states & {"SOLD_NOT_CLOSED", "CLOSED"}:
        return "SELLING"
    if states & config.VERTICAL_LOT_STATES:
        return "VERTICAL_ACTIVE"
    if states & config.HORIZONTAL_LOT_STATES:
        return "HORIZONTAL_ACTIVE"
    if "LAND_OWNED" in states:
        return "LAND_ACQUIRED"
    return "PLANNED"


def compute_phase_majority_state(lot_state_groups: List[str]) -> str:
    """Plurality lot_state_group; ties broken by most advanced group."""
    counts = pd.Series(lot_state_groups).value_counts()
    max_count = counts.max()
    tied = [g for g in counts.index if counts[g] == max_count]
    # Tie-break: pick most advanced
    for group in reversed(config.LOT_STATE_GROUP_ORDER):
        if group in tied:
            return group
    return tied[0]


def aggregate_phase(group: pd.DataFrame) -> pd.Series:
    """Aggregate LotState rows into a single PhaseState row."""
    lot_states = group["lot_state"].tolist()
    state_groups = group["lot_state_group"].tolist()

    # Composition
    lot_count_total = len(group)
    lot_count_by_state = group["lot_state"].value_counts().to_dict()
    # lot_type may have NaN — treat as "null" key for the map
    lot_type_series = group["lot_type"].fillna("null")
    lot_count_by_type = lot_type_series.value_counts().to_dict()
    product_mix_pct = {k: round(v / lot_count_total, 4) for k, v in lot_count_by_type.items()}

    # Actuals
    actual_cost_total = group["cost_to_date"].sum()
    actual_cost_per_lot = actual_cost_total / lot_count_total if lot_count_total else 0.0

    # Phase lifecycle
    phase_state = compute_phase_state(lot_states)
    majority_group = compute_phase_majority_state(state_groups)
    leading_group = config.PHASE_STATE_TO_GROUP[phase_state]
    is_transitioning = leading_group != majority_group

    # Timing
    active_mask = ~group["lot_state"].isin(["PROSPECT", "CLOSED"])
    active = group[active_mask]
    avg_days_in_state = active["days_in_state"].mean() if len(active) else None
    avg_days_since_purchase = group["days_since_purchase"].dropna().mean()
    if pd.isna(avg_days_since_purchase):
        avg_days_since_purchase = None

    # Phase start = earliest horizontal date across lots
    horiz_dates = pd.concat([
        pd.to_datetime(group["horiz_purchase_date"], errors="coerce"),
        pd.to_datetime(group["horiz_start_date"], errors="coerce"),
    ])
    horiz_dates = horiz_dates.dropna()
    phase_start_date = horiz_dates.min() if len(horiz_dates) else None

    return pd.Series({
        "lot_count_total": lot_count_total,
        "lot_count_by_state": json.dumps(lot_count_by_state),
        "lot_count_by_type": json.dumps(lot_count_by_type),
        "product_mix_pct": json.dumps(product_mix_pct),
        "actual_cost_total": actual_cost_total,
        "actual_cost_per_lot": actual_cost_per_lot,
        "phase_state": phase_state,
        "phase_majority_state": majority_group,
        "is_transitioning": is_transitioning,
        "avg_days_in_state": avg_days_in_state,
        "avg_days_since_purchase": avg_days_since_purchase,
        "phase_start_date": phase_start_date,
    })


def build_phase_aggregates(lot_state: pd.DataFrame) -> pd.DataFrame:
    """Group LotState by phase and aggregate."""
    grouped = lot_state.groupby(
        ["project_name", "phase_name", "phase_id"], as_index=False
    ).apply(aggregate_phase, include_groups=False)
    # In some pandas versions include_groups isn't supported — handle both
    if "project_name" not in grouped.columns:
        grouped = grouped.reset_index()
    return grouped


# ---------------------------------------------------------------------------
# Step 4: Allocation sheet parsing (per-phase expected costs)
# ---------------------------------------------------------------------------

def parse_allocation_sheet(file_path, project_name: Optional[str] = None) -> pd.DataFrame:
    """Parse a semi-structured allocation CSV into per-phase expected cost rows.

    The source files have multiple sections with identical column layouts:
      - "Summary per lot" — values are PER LOT (what we want)
      - "Budgeting" — different schema, line-item budgets
      - "Allocation" — same column layout as Summary but values are TOTALS
        (already multiplied by lot count)

    We only want the first section. We scan for the first row that contains
    a "Budgeting" or "Allocation" section header and stop parsing there.

    Cost columns are stored as negatives (deductions from sales). We take
    abs() to get positive expected cost values.
    """
    raw = pd.read_csv(file_path, header=None, dtype=str)

    # Find the row index of the first "Budgeting" or "Allocation" section header.
    # These appear as a label in one of the early columns.
    stop_at = len(raw)
    for idx, row in raw.iterrows():
        # Check the first 5 columns for the section header label
        for col_idx in range(5):
            cell = strip_str(row.get(col_idx))
            if cell in ("Budgeting", "Allocation"):
                stop_at = idx
                break
        if stop_at != len(raw):
            break

    rows = []
    for idx, row in raw.iloc[:stop_at].iterrows():
        phase_raw = strip_str(row.get(config.ALLOCATION_PHASE_COL))
        lot_count_raw = strip_str(row.get(config.ALLOCATION_LOTCOUNT_COL))
        if not phase_raw or not lot_count_raw:
            continue
        # Normalize phase name through the same hook used by LotState so
        # that allocation joins use canonical identifiers.
        phase = config.normalize_phase(project_name, phase_raw)
        try:
            lot_count = int(float(lot_count_raw))
        except ValueError:
            continue
        if lot_count <= 0:
            continue

        land_per_lot = abs(parse_money(row.get(config.ALLOCATION_LAND_COST_COL)))
        direct_per_lot = abs(parse_money(row.get(config.ALLOCATION_DIRECT_DEV_COL)))
        water_per_lot = abs(parse_money(row.get(config.ALLOCATION_WATER_COST_COL)))
        indirect_per_lot = abs(parse_money(row.get(config.ALLOCATION_INDIRECTS_COL)))
        total_per_lot = abs(parse_money(row.get(config.ALLOCATION_TOTAL_COST_COL)))

        # Some allocation sheets omit total; reconstruct total from components.
        if total_per_lot == 0:
            total_per_lot = land_per_lot + direct_per_lot + water_per_lot + indirect_per_lot

        rows.append({
            "phase": phase,
            "prod_type": strip_str(row.get(config.ALLOCATION_PRODTYPE_COL)),
            "lot_count": lot_count,
            "land_per_lot": land_per_lot,
            "direct_per_lot": direct_per_lot,
            "water_per_lot": water_per_lot,
            "indirect_per_lot": indirect_per_lot,
            "total_per_lot": total_per_lot,
        })

    return pd.DataFrame(rows)


def build_allocation_expected() -> pd.DataFrame:
    """Build a phase-level expected cost dataframe from all allocation sheets.

    Each row in the parsed allocation sheet represents one (phase, prod_type,
    price_tier) bucket with its own lot_count. We compute row-level totals
    (per_lot * lot_count) up front, then sum at the phase level.
    """
    frames = []
    for file_path, (project_name, source_label) in config.ALLOCATION_SOURCES.items():
        df = parse_allocation_sheet(file_path, project_name=project_name)
        if df.empty:
            continue
        df["project_name"] = project_name
        df["expected_cost_source"] = source_label

        # Precompute row-level totals (per-lot cost × lot count)
        df["row_direct_total"] = df["direct_per_lot"] * df["lot_count"]
        df["row_indirect_total"] = df["indirect_per_lot"] * df["lot_count"]
        df["row_grand_total"] = df["total_per_lot"] * df["lot_count"]

        agg = df.groupby(["project_name", "phase", "expected_cost_source"], as_index=False).agg(
            expected_lot_count=("lot_count", "sum"),
            expected_direct_cost_total=("row_direct_total", "sum"),
            expected_indirect_cost_total=("row_indirect_total", "sum"),
            expected_total_cost=("row_grand_total", "sum"),
        )
        frames.append(agg)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Step 5: Collateral Report fallback (Total Dev Cost only)
# ---------------------------------------------------------------------------

def parse_collateral_report() -> pd.DataFrame:
    """Parse Collateral Report → per-phase expected costs (fallback source).

    Provides only `expected_total_cost` (no direct/indirect split).
    Project names are in CAPS in this file; phase has trailing whitespace.
    """
    df = pd.read_csv(
        config.COLLATERAL_REPORT_FILE,
        header=config.COLLATERAL_REPORT_HEADER_ROW,
        dtype=str,
    )
    # Strip whitespace from all column names — source has leading/trailing spaces
    df.columns = [c.strip() for c in df.columns]
    df = df.dropna(subset=["Project", "Phase"])

    # Normalize: project to title case; phase through normalize_phase so
    # any override applies symmetrically with LotState.
    df["project_name"] = df["Project"].str.strip().str.title()
    df["phase_name"] = df.apply(
        lambda r: config.normalize_phase(
            str(r["Project"]).strip().title() if pd.notna(r["Project"]) else "",
            r["Phase"],
        ),
        axis=1,
    )

    df["expected_total_cost"] = df["Total Dev Cost (Spent + Remaining)"].map(parse_money)
    df["expected_cost_source"] = "Collateral Report Dec 2025"

    return df[["project_name", "phase_name", "expected_total_cost", "expected_cost_source"]]


# ---------------------------------------------------------------------------
# Step 6: Attach expected costs to phase aggregates
# ---------------------------------------------------------------------------

def attach_expected_costs(
    phases: pd.DataFrame,
    allocation_expected: pd.DataFrame,
    collateral_expected: pd.DataFrame,
) -> pd.DataFrame:
    """Attach expected cost fields. Allocation sheets take priority; Collateral
    Report is the fallback for phases without allocation data."""

    # Initialize expected fields as null
    phases = phases.copy()
    phases["expected_direct_cost_total"] = None
    phases["expected_indirect_cost_total"] = None
    phases["expected_total_cost"] = None
    phases["expected_cost_source"] = None
    phases["cost_data_completeness"] = None
    # expected_lot_count records the denominator reported by the source,
    # used to decide FULL vs PARTIAL in expected_cost_status.
    phases["expected_lot_count"] = None

    # Priority 1: allocation sheets (FULL fidelity)
    # Only use the allocation sheet match if it produced a non-zero total cost.
    # The LH allocation sheet has direct costs but missing indirect/total
    # columns — those phases fall through to the Collateral Report fallback.
    if not allocation_expected.empty:
        for _, alloc in allocation_expected.iterrows():
            if alloc["expected_total_cost"] <= 0:
                continue
            mask = (
                (phases["project_name"] == alloc["project_name"])
                & (phases["phase_name"] == alloc["phase"])
            )
            if mask.any():
                phases.loc[mask, "expected_direct_cost_total"] = alloc["expected_direct_cost_total"]
                phases.loc[mask, "expected_indirect_cost_total"] = alloc["expected_indirect_cost_total"]
                phases.loc[mask, "expected_total_cost"] = alloc["expected_total_cost"]
                phases.loc[mask, "expected_cost_source"] = alloc["expected_cost_source"]
                phases.loc[mask, "cost_data_completeness"] = "FULL"
                phases.loc[mask, "expected_lot_count"] = alloc["expected_lot_count"]

    # Priority 2: Collateral Report fallback (PARTIAL — total only)
    for _, cr in collateral_expected.iterrows():
        mask = (
            (phases["project_name"] == cr["project_name"])
            & (phases["phase_name"] == cr["phase_name"])
            & (phases["expected_total_cost"].isna())  # only fill where allocation was missing
        )
        if mask.any() and cr["expected_total_cost"] > 0:
            phases.loc[mask, "expected_total_cost"] = cr["expected_total_cost"]
            phases.loc[mask, "expected_cost_source"] = cr["expected_cost_source"]
            phases.loc[mask, "cost_data_completeness"] = "PARTIAL"

    # Diagnostics — surface phase-alignment issues in both directions.
    lot_state_keys = set(zip(phases["project_name"], phases["phase_name"]))
    alloc_keys = set()
    if not allocation_expected.empty:
        alloc_keys = set(zip(allocation_expected["project_name"],
                              allocation_expected["phase"]))
    cr_keys = set()
    if not collateral_expected.empty:
        cr_nonzero = collateral_expected[collateral_expected["expected_total_cost"] > 0]
        cr_keys = set(zip(cr_nonzero["project_name"], cr_nonzero["phase_name"]))

    unmapped_alloc = sorted(alloc_keys - lot_state_keys)
    unmapped_cr = sorted(cr_keys - lot_state_keys)
    unmatched_phases = sorted(
        k for k in lot_state_keys - alloc_keys - cr_keys
    )
    if unmapped_alloc:
        print(f"  DIAG: allocation phases with no LotState match ({len(unmapped_alloc)}):")
        for p, ph in unmapped_alloc:
            print(f"    - {p}::{ph}")
    if unmapped_cr:
        print(f"  DIAG: Collateral-Report phases (nonzero) with no LotState match ({len(unmapped_cr)}):")
        for p, ph in unmapped_cr:
            print(f"    - {p}::{ph}")
    print(f"  DIAG: LotState phases with no expected-cost source: {len(unmatched_phases)} / {len(lot_state_keys)}")

    # Compute per-lot averages
    phases["expected_direct_cost_per_lot"] = phases.apply(
        lambda r: r["expected_direct_cost_total"] / r["lot_count_total"]
        if pd.notna(r["expected_direct_cost_total"]) else None,
        axis=1,
    )
    phases["expected_indirect_cost_per_lot"] = phases.apply(
        lambda r: r["expected_indirect_cost_total"] / r["lot_count_total"]
        if pd.notna(r["expected_indirect_cost_total"]) else None,
        axis=1,
    )
    phases["expected_total_cost_per_lot"] = phases.apply(
        lambda r: r["expected_total_cost"] / r["lot_count_total"]
        if pd.notna(r["expected_total_cost"]) else None,
        axis=1,
    )

    return phases


# ---------------------------------------------------------------------------
# Step 7: Variance
# ---------------------------------------------------------------------------

def compute_variance(phases: pd.DataFrame) -> pd.DataFrame:
    """Compute variance fields where expected costs are available."""
    phases = phases.copy()

    def variance_total(r):
        if pd.isna(r["expected_total_cost"]):
            return None
        return r["actual_cost_total"] - r["expected_total_cost"]

    def variance_per_lot(r):
        if pd.isna(r["expected_total_cost_per_lot"]):
            return None
        return r["actual_cost_per_lot"] - r["expected_total_cost_per_lot"]

    def variance_pct(r):
        if pd.isna(r["expected_total_cost"]) or r["expected_total_cost"] == 0:
            return None
        return (r["actual_cost_total"] - r["expected_total_cost"]) / r["expected_total_cost"]

    phases["variance_total"] = phases.apply(variance_total, axis=1)
    phases["variance_per_lot"] = phases.apply(variance_per_lot, axis=1)
    phases["variance_pct"] = phases.apply(variance_pct, axis=1)

    # Variance is only meaningful when both expected and actual costs exist
    # and represent comparable horizontal cost categories.
    phases["variance_meaningful"] = (
        phases["actual_cost_total"].fillna(0).gt(0)
        & phases["expected_total_cost"].notna()
    )
    not_meaningful = ~phases["variance_meaningful"]
    phases.loc[not_meaningful, "variance_total"] = None
    phases.loc[not_meaningful, "variance_per_lot"] = None
    phases.loc[not_meaningful, "variance_pct"] = None

    # Lightweight sanity check — flag large mismatches for debugging only.
    for _, r in phases.iterrows():
        if not r["variance_meaningful"]:
            continue
        expected = r["expected_total_cost"]
        actual = r["actual_cost_total"]
        if expected and expected > 0 and actual > expected * 3:
            print(f"  WARNING: Large variance detected for phase {r['phase_id']} "
                  f"(actual=${actual:,.0f}, expected=${expected:,.0f})")

    # Direct/indirect actuals — not available at lot level in v1
    phases["actual_direct_cost_total"] = None
    phases["actual_indirect_cost_total"] = None

    # expected_cost_status — confidence bucket used to gate product queries.
    #   FULL    = allocation-sheet source AND denominator matches lot_count_total
    #   PARTIAL = any other nonzero expected (e.g., Collateral Report fallback)
    #             or denominator mismatch
    #   NONE    = no expected cost available
    def _cost_status(r):
        if pd.isna(r["expected_total_cost"]):
            return "NONE"
        source = r.get("expected_cost_source") or ""
        denom_ok = (
            pd.notna(r.get("expected_lot_count"))
            and int(r["expected_lot_count"]) == int(r["lot_count_total"])
        )
        if str(source).startswith("Allocation Sheet") and denom_ok:
            return "FULL"
        return "PARTIAL"

    phases["expected_cost_status"] = phases.apply(_cost_status, axis=1)
    phases["is_queryable"] = (
        (phases["expected_cost_status"] == "FULL")
        & (phases["variance_meaningful"] == True)  # noqa: E712
    )

    return phases


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def build_phase_state() -> pd.DataFrame:
    print("[1/5] Loading LotState...")
    lot_state, as_of_date = load_lot_state()
    print(f"  - {len(lot_state)} lot rows")
    print(f"  - As of: {as_of_date.date()}")

    print("[2/5] Aggregating phases from LotState...")
    phases = build_phase_aggregates(lot_state)
    print(f"  - {len(phases)} unique phases")

    print("[3/5] Parsing allocation sheets (LH + PF)...")
    allocation_expected = build_allocation_expected()
    print(f"  - {len(allocation_expected)} phases with allocation sheet data")

    print("[4/5] Parsing Collateral Report (fallback)...")
    collateral_expected = parse_collateral_report()
    print(f"  - {len(collateral_expected)} phases with Collateral Report data")

    print("[5/5] Attaching expected costs and computing variance...")
    phases = attach_expected_costs(phases, allocation_expected, collateral_expected)
    phases = compute_variance(phases)

    # Identity + metadata
    phases["canonical_phase_id"] = phases["phase_id"]
    phases["expected_duration_days"] = None  # No structured source
    phases["as_of_date"] = as_of_date.date()
    phases["last_computed_at"] = datetime.now().isoformat(timespec="seconds")

    output = phases[config.PHASE_STATE_OUTPUT_COLUMNS].copy()

    print("\nWriting output...")
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output.to_csv(config.PHASE_STATE_CSV, index=False)
    output.to_parquet(config.PHASE_STATE_PARQUET, index=False)
    print(f"  - {config.PHASE_STATE_CSV.relative_to(config.REPO_ROOT)}  ({len(output)} rows)")
    print(f"  - {config.PHASE_STATE_PARQUET.relative_to(config.REPO_ROOT)}")

    # Summary
    print("\nPhase state distribution:")
    for state, count in output["phase_state"].value_counts().items():
        print(f"  {state:20s} {count:>4d}")

    print("\nCost data completeness:")
    print(output["cost_data_completeness"].fillna("NONE").value_counts().to_string())

    phases_with_variance = output["variance_total"].notna().sum()
    print(f"\nPhases with computable variance: {phases_with_variance}/{len(output)}")

    # ----- Query-ready dataset (FULL + variance_meaningful only) -----
    query_columns = [
        "project_name",
        "phase_name",
        "lot_count_total",
        "expected_total_cost_per_lot",
        "actual_cost_per_lot",
        "variance_per_lot",
        "variance_pct",
        "product_mix_pct",
        "phase_state",
        "phase_majority_state",
    ]
    query_df = output[
        (output["expected_cost_status"] == "FULL")
        & (output["variance_meaningful"] == True)  # noqa: E712
    ][query_columns].copy()
    query_df = query_df.sort_values(by="variance_per_lot", ascending=False)

    query_df.to_csv(config.PHASE_COST_QUERY_CSV, index=False)
    query_df.to_parquet(config.PHASE_COST_QUERY_PARQUET, index=False)
    print(f"  - {config.PHASE_COST_QUERY_CSV.relative_to(config.REPO_ROOT)}  ({len(query_df)} rows)")
    print(f"  - {config.PHASE_COST_QUERY_PARQUET.relative_to(config.REPO_ROOT)}")

    # ----- Summary bucket counts -----
    status_counts = output["expected_cost_status"].value_counts()
    print("\n" + "=" * 40)
    print(f"TOTAL PHASES: {len(output)}")
    print(f"FULL:    {int(status_counts.get('FULL', 0))}")
    print(f"PARTIAL: {int(status_counts.get('PARTIAL', 0))}")
    print(f"NONE:    {int(status_counts.get('NONE', 0))}")
    print()
    print(f"QUERYABLE PHASES: {int(output['is_queryable'].sum())}")
    print("=" * 40)

    return output


if __name__ == "__main__":
    build_phase_state()
