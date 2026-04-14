"""
build_lot_state.py — State Engine v1

Computes LotState records by joining lot lifecycle dates with 2025Status cost
data and applying the deterministic state waterfall.

Pipeline:
    1. Load Lot Data (lifecycle dates)
    2. Load 2025Status (costs, vert_sold, collateral bucket)
    3. Join on Project + Phase + Lot
    4. Clean dates (filter 1899 sentinel, parse to datetime)
    5. Build identity fields
    6. Compute lot_state via waterfall
    7. Compute lot_type, lot_state_group, collateral_bucket
    8. Compute cost_to_date (sum of 4 components)
    9. Compute days_in_state, days_since_purchase, pct_complete
    10. Compute advance_rate, capital_exposure
    11. Write CSV + Parquet output

Run:
    python pipelines/build_lot_state.py
"""

from datetime import datetime
from typing import Optional, Tuple

import pandas as pd

import config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_money(value) -> float:
    """Parse a money value from the 2025Status CSV.

    Source values look like '"  47,037.08 "', '$226,478', '$0', '  -   '.
    Returns 0.0 for null, dash, or unparseable values.
    """
    if pd.isna(value):
        return 0.0
    s = str(value).strip()
    if s in ("", "-", "—"):
        return 0.0
    # Strip currency, commas, parens, whitespace
    s = s.replace("$", "").replace(",", "").replace("(", "-").replace(")", "").strip()
    if s == "" or s == "-":
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def clean_date(series: pd.Series) -> pd.Series:
    """Parse a date column and replace 1899 sentinel with NaT."""
    parsed = pd.to_datetime(series, errors="coerce")
    sentinel = pd.Timestamp(config.SENTINEL_DATE)
    return parsed.where(parsed != sentinel)


def strip_str(value) -> str:
    """Strip whitespace from a string-like value, handling NaN."""
    if pd.isna(value):
        return ""
    return str(value).strip()


# ---------------------------------------------------------------------------
# Step 1+2: Load source files
# ---------------------------------------------------------------------------

def load_lot_data() -> pd.DataFrame:
    """Load Lot Data CSV — one row per lot with all lifecycle dates."""
    df = pd.read_csv(config.LOT_DATA_FILE, dtype=str)

    # Strip whitespace from key string fields used for joining
    for col in ["Project", "Phase", "LotNo."]:
        df[col] = df[col].map(strip_str)

    # Parse + clean all date columns, then rename to ontology field names
    for source_col, target_col in config.LOT_DATA_DATE_COLUMNS.items():
        df[target_col] = clean_date(df[source_col])

    return df


def load_status_2025() -> Tuple[pd.DataFrame, pd.Timestamp]:
    """Load 2025Status CSV — costs, status, collateral bucket per lot.

    Returns (df, as_of_date).
    """
    # Extract as_of_date from row 1 before reading the table.
    raw = pd.read_csv(config.STATUS_2025_FILE, header=None, nrows=1, dtype=str)
    as_of_str = raw.iloc[0, 1]
    as_of_date = pd.to_datetime(as_of_str)

    # Read the actual data, header on row 3 (skip 2 header rows)
    df = pd.read_csv(
        config.STATUS_2025_FILE,
        skiprows=config.STATUS_2025_HEADER_ROW,
        dtype=str,
    )

    # Filter to the 16 main columns — beyond column 16 is a pivot table sidebar
    main_columns = [
        "Project", "Phase", "Lot", "Product Type", "Lot Count", "Status",
        "Status Date", "Vert Sold", "Collateral Bucket",
        "Permits and Fees", "Direct Construction - Lot", "Direct Construction",
        "Vertical Costs", "Shared Cost Alloc.", "Lot Cost", "HorzCustomer",
    ]
    df = df[[c for c in main_columns if c in df.columns]].copy()

    # Drop empty rows (the sidebar rows leave many blank lines in the main table area)
    df = df.dropna(subset=["Project", "Phase", "Lot"], how="any")

    # Strip whitespace from join keys
    for col in ["Project", "Phase", "Lot"]:
        df[col] = df[col].map(strip_str)

    # Parse cost components
    for col in config.COST_TO_DATE_COMPONENTS:
        df[col] = df[col].map(parse_money)

    return df, as_of_date


# ---------------------------------------------------------------------------
# Step 3: Join lot data with status
# ---------------------------------------------------------------------------

def join_sources(lots: pd.DataFrame, status: pd.DataFrame) -> pd.DataFrame:
    """Join lot lifecycle data with status/cost data on Project + Phase + Lot.

    Both source files contain a small number of duplicate (Project, Phase, Lot)
    entries — typically aggregate/commercial rows with Lot = "0". We dedupe on
    the join key (keeping the first occurrence) to prevent fan-out during merge.
    """
    lots_dupes = lots.duplicated(subset=["Project", "Phase", "LotNo."]).sum()
    status_dupes = status.duplicated(subset=["Project", "Phase", "Lot"]).sum()
    if lots_dupes:
        print(f"  WARN: dropping {lots_dupes} duplicate keys in Lot Data")
        lots = lots.drop_duplicates(subset=["Project", "Phase", "LotNo."], keep="first")
    if status_dupes:
        print(f"  WARN: dropping {status_dupes} duplicate keys in 2025Status")
        status = status.drop_duplicates(subset=["Project", "Phase", "Lot"], keep="first")

    merged = lots.merge(
        status,
        left_on=["Project", "Phase", "LotNo."],
        right_on=["Project", "Phase", "Lot"],
        how="left",
        suffixes=("", "_status"),
    )
    unmatched = merged["Lot"].isna().sum()
    if unmatched:
        print(f"  WARN: {unmatched} lots in Lot Data have no matching row in 2025Status")
    return merged


# ---------------------------------------------------------------------------
# Step 4-7: Derived state fields
# ---------------------------------------------------------------------------

def compute_lot_state(row, as_of_date: pd.Timestamp) -> str:
    """Apply the deterministic waterfall — first date that has actually occurred wins.

    CRITICAL: source Lot Data contains future projected dates (e.g., a planned
    VertStart in 2027). Only consider dates that are <= as_of_date — these
    represent events that have actually happened. Future dates are forecasts,
    not real lifecycle events.
    """
    for date_field, state in config.LOT_STATE_WATERFALL:
        date_val = row.get(date_field)
        if pd.notna(date_val) and date_val <= as_of_date:
            return state
    return config.DEFAULT_LOT_STATE


def compute_lot_type(row) -> Optional[str]:
    """SPEC vs PRESOLD inference. MODEL is not derivable from data.

    Only meaningful for vertical-or-later states.
    """
    state = row["lot_state"]
    if state in ("PROSPECT", "LAND_OWNED", "HORIZONTAL_IN_PROGRESS",
                 "FINISHED_LOT"):
        return None
    vert_sold = strip_str(row.get("Vert Sold"))
    if vert_sold.lower() == "yes":
        return "PRESOLD"
    return "SPEC"


# ---------------------------------------------------------------------------
# Step 8-10: Cost, timing, capital
# ---------------------------------------------------------------------------

def compute_cost_to_date(row) -> float:
    """Sum the 4 cost components from 2025Status."""
    return sum(row.get(c, 0.0) or 0.0 for c in config.COST_TO_DATE_COMPONENTS)


def compute_days_in_state(row, as_of_date: pd.Timestamp):
    """Days since the date that triggered the current lot_state."""
    state = row["lot_state"]
    if state == "PROSPECT":
        return None
    triggering_field = config.LOT_STATE_TO_TRIGGERING_DATE.get(state)
    if not triggering_field:
        return None
    triggering_date = row.get(triggering_field)
    if pd.isna(triggering_date):
        return None
    return (as_of_date - triggering_date).days


def compute_days_since_purchase(row, as_of_date: pd.Timestamp):
    """Days since the lot was first purchased (horizontal preferred, vertical fallback)."""
    purchase = row.get("horiz_purchase_date")
    if pd.isna(purchase):
        purchase = row.get("vert_purchase_date")
    if pd.isna(purchase):
        return None
    return (as_of_date - purchase).days


def compute_capital_exposure(row):
    """Capital at risk = cost_to_date for non-CLOSED lots; null for CLOSED."""
    if row["lot_state"] == "CLOSED":
        return None
    return row["cost_to_date"]


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def build_lot_state() -> pd.DataFrame:
    print("[1/4] Loading sources...")
    lots = load_lot_data()
    status, as_of_date = load_status_2025()
    print(f"  - Lot Data:    {len(lots)} rows")
    print(f"  - 2025Status:  {len(status)} rows")
    print(f"  - As of date:  {as_of_date.date()}")

    print("[2/4] Joining sources on Project + Phase + Lot...")
    df = join_sources(lots, status)

    print("[3/4] Computing derived fields...")

    # Identity fields
    df["project_name"] = df["Project"]
    df["phase_name"] = df["Phase"]
    df["lot_number"] = df["LotNo."]
    df["canonical_lot_id"] = (
        df["project_name"] + "::" + df["phase_name"] + "::" + df["lot_number"]
    )
    df["project_id"] = df["project_name"]
    df["phase_id"] = df["project_name"] + "::" + df["phase_name"]

    # Customer / buyer
    df["customer_name"] = df["HorzCustomer"].map(strip_str).replace("", None)
    df["buyer_id"] = None  # Not in source data

    # State waterfall — only consider dates that have actually occurred
    df["lot_state"] = df.apply(lambda r: compute_lot_state(r, as_of_date), axis=1)
    df["lot_state_group"] = df["lot_state"].map(config.LOT_STATE_TO_GROUP)
    df["collateral_bucket"] = df["lot_state"].map(config.LOT_STATE_TO_COLLATERAL_BUCKET)
    df["lot_type"] = df.apply(compute_lot_type, axis=1)

    # Cost
    df["cost_to_date"] = df.apply(compute_cost_to_date, axis=1)
    df["remaining_cost"] = None  # No per-lot source in v1

    # Timing
    df["days_in_state"] = df.apply(lambda r: compute_days_in_state(r, as_of_date), axis=1)
    df["days_since_purchase"] = df.apply(
        lambda r: compute_days_since_purchase(r, as_of_date), axis=1
    )
    df["pct_complete"] = df["lot_state"].map(config.LOT_STATE_TO_PCT_COMPLETE)

    # Capital
    df["advance_rate"] = df["collateral_bucket"].map(config.ADVANCE_RATES)
    df["capital_exposure"] = df.apply(compute_capital_exposure, axis=1)

    # Metadata
    df["as_of_date"] = as_of_date.date()
    df["source_systems"] = "lot_data,status_2025"
    df["last_computed_at"] = datetime.now().isoformat(timespec="seconds")

    print("[4/4] Writing output...")
    output = df[config.LOT_STATE_OUTPUT_COLUMNS].copy()

    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output.to_csv(config.LOT_STATE_CSV, index=False)
    output.to_parquet(config.LOT_STATE_PARQUET, index=False)
    print(f"  - {config.LOT_STATE_CSV.relative_to(config.REPO_ROOT)}  ({len(output)} rows)")
    print(f"  - {config.LOT_STATE_PARQUET.relative_to(config.REPO_ROOT)}")

    # Quick summary
    print("\nLot state distribution:")
    for state, count in output["lot_state"].value_counts().items():
        print(f"  {state:25s} {count:>6d}")

    return output


if __name__ == "__main__":
    build_lot_state()
