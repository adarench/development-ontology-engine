"""
Configuration constants for the State Engine v1 pipeline.

All file paths, column mappings, sentinel values, and lookup dictionaries live here.
The pipeline scripts import from this module — no magic strings in the pipeline code.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent

# Source CSV files (kept under their original Excel-export names)
LOT_DATA_FILE = REPO_ROOT / "Collateral Dec2025 01 Claude.xlsx - Lot Data.csv"
STATUS_2025_FILE = REPO_ROOT / "Collateral Dec2025 01 Claude.xlsx - 2025Status.csv"
COLLATERAL_REPORT_FILE = REPO_ROOT / "Collateral Dec2025 01 Claude.xlsx - Collateral Report.csv"
ALLOCATION_LH_FILE = REPO_ROOT / "LH Allocation 2025.10.xlsx - LH.csv"
ALLOCATION_PF_FILE = REPO_ROOT / "Parkway Allocation 2025.10.xlsx - PF.csv"

# Output paths
OUTPUT_DIR = REPO_ROOT / "output"
LOT_STATE_CSV = OUTPUT_DIR / "lot_state.csv"
LOT_STATE_PARQUET = OUTPUT_DIR / "lot_state.parquet"
PHASE_STATE_CSV = OUTPUT_DIR / "phase_state.csv"
PHASE_STATE_PARQUET = OUTPUT_DIR / "phase_state.parquet"
PHASE_COST_QUERY_CSV = OUTPUT_DIR / "phase_cost_query.csv"
PHASE_COST_QUERY_PARQUET = OUTPUT_DIR / "phase_cost_query.parquet"

# ---------------------------------------------------------------------------
# Ingestion rules
# ---------------------------------------------------------------------------

# Excel epoch sentinel — appears in source data as a null placeholder
SENTINEL_DATE = "1899-12-30"

# Header row index (0-indexed) in 2025Status — first 2 rows are metadata
STATUS_2025_HEADER_ROW = 2

# Header row index in Collateral Report
COLLATERAL_REPORT_HEADER_ROW = 8

# ---------------------------------------------------------------------------
# Column rename map: Lot Data CSV → ontology field names
# ---------------------------------------------------------------------------

LOT_DATA_DATE_COLUMNS = {
    "HorzPurchase": "horiz_purchase_date",
    "HorzMDA": "horiz_mda_date",
    "HorzPrelimPlat": "horiz_prelim_plat_date",
    "HorzFinalPlat": "horiz_final_plat_date",
    "HorzStart": "horiz_start_date",
    "HorzEnd": "horiz_end_date",
    "HorzFinInv": "horiz_fin_inv_date",
    "HorzRecord": "horiz_record_date",
    "HorzWEnter": "horiz_w_enter_date",
    "HorzWExit": "horiz_w_exit_date",
    "HorzContract": "horiz_contract_date",
    "HorzSale": "horiz_sale_date",
    "VertPurchase": "vert_purchase_date",
    "VertStart": "vert_start_date",
    "VertCO": "vert_co_date",
    "VertSale": "vert_sale_date",
    "VertClose": "vert_close_date",
}

# All date column names after rename — for bulk operations
ALL_DATE_COLUMNS = list(LOT_DATA_DATE_COLUMNS.values())

# ---------------------------------------------------------------------------
# 2025Status cost columns — these are summed to produce cost_to_date
# ---------------------------------------------------------------------------

# cost_to_date is intentionally restricted to horizontal (land development) costs only.
# This aligns with expected costs from allocation sheets.
# "Direct Construction" is excluded because it mixes vertical + horizontal spend.
# "Vertical Costs" and "Lot Cost" are excluded for the same reason (and to avoid
# double-counting with "Direct Construction - Lot").
COST_TO_DATE_COMPONENTS = [
    "Permits and Fees",
    "Direct Construction - Lot",
    "Shared Cost Alloc.",
]

# ---------------------------------------------------------------------------
# Lot state waterfall — ordered list of (date_field, state) pairs.
# Evaluated top-down; first non-null date determines the state.
# ---------------------------------------------------------------------------

LOT_STATE_WATERFALL = [
    ("vert_close_date", "CLOSED"),
    ("vert_sale_date", "SOLD_NOT_CLOSED"),
    ("vert_co_date", "VERTICAL_COMPLETE"),
    ("vert_start_date", "VERTICAL_IN_PROGRESS"),
    ("vert_purchase_date", "VERTICAL_PURCHASED"),
    ("horiz_record_date", "FINISHED_LOT"),
    ("horiz_start_date", "HORIZONTAL_IN_PROGRESS"),
    ("horiz_purchase_date", "LAND_OWNED"),
]
DEFAULT_LOT_STATE = "PROSPECT"

# Reverse lookup: lot_state → the date field that triggered it.
# Used to compute days_in_state.
LOT_STATE_TO_TRIGGERING_DATE = {state: date_field for date_field, state in LOT_STATE_WATERFALL}

# ---------------------------------------------------------------------------
# Lot state group mapping
# ---------------------------------------------------------------------------

LOT_STATE_TO_GROUP = {
    "PROSPECT": "PRE_DEVELOPMENT",
    "LAND_OWNED": "PRE_DEVELOPMENT",
    "HORIZONTAL_IN_PROGRESS": "HORIZONTAL",
    "FINISHED_LOT": "HORIZONTAL",
    "VERTICAL_PURCHASED": "VERTICAL",
    "VERTICAL_IN_PROGRESS": "VERTICAL",
    "VERTICAL_COMPLETE": "VERTICAL",
    "SOLD_NOT_CLOSED": "DISPOSITION",
    "CLOSED": "DISPOSITION",
}

# Group ordering (least → most advanced) for tie-breaking in phase_majority_state
LOT_STATE_GROUP_ORDER = ["PRE_DEVELOPMENT", "HORIZONTAL", "VERTICAL", "DISPOSITION"]

# ---------------------------------------------------------------------------
# Collateral bucket mapping
# ---------------------------------------------------------------------------

LOT_STATE_TO_COLLATERAL_BUCKET = {
    "PROSPECT": "Raw Land",
    "LAND_OWNED": "Raw Land",
    "HORIZONTAL_IN_PROGRESS": "Land Under Development",
    "FINISHED_LOT": "Finished Lots",
    "VERTICAL_PURCHASED": "Finished Lots",
    "VERTICAL_IN_PROGRESS": "Vertical WIP",
    "VERTICAL_COMPLETE": "Completed Inventory",
    "SOLD_NOT_CLOSED": "Sold Inventory",
    "CLOSED": "N/A",
}

# Lender advance rates per collateral bucket (from Collateral Report header).
# Models bucket carries 0.75 but we don't derive that from lot_state alone in v1.
ADVANCE_RATES = {
    "Raw Land": 0.50,
    "Land Under Development": 0.55,
    "Finished Lots": 0.60,
    "Vertical WIP": 0.70,
    "Completed Inventory": 0.80,
    "Sold Inventory": 0.90,
    "N/A": None,
}

# ---------------------------------------------------------------------------
# State-based pct_complete (v1 approximation — no per-lot expected total)
# ---------------------------------------------------------------------------

LOT_STATE_TO_PCT_COMPLETE = {
    "PROSPECT": None,
    "LAND_OWNED": 0.05,
    "HORIZONTAL_IN_PROGRESS": 0.15,
    "FINISHED_LOT": 0.30,
    "VERTICAL_PURCHASED": 0.35,
    "VERTICAL_IN_PROGRESS": 0.55,
    "VERTICAL_COMPLETE": 0.85,
    "SOLD_NOT_CLOSED": 0.95,
    "CLOSED": None,
}

# ---------------------------------------------------------------------------
# Phase state waterfall (used in build_phase_state.py)
# ---------------------------------------------------------------------------

VERTICAL_LOT_STATES = {"VERTICAL_PURCHASED", "VERTICAL_IN_PROGRESS", "VERTICAL_COMPLETE"}
HORIZONTAL_LOT_STATES = {"HORIZONTAL_IN_PROGRESS", "FINISHED_LOT"}
DISPOSITION_LOT_STATES = {"SOLD_NOT_CLOSED", "CLOSED"}

# Map phase_state → its corresponding lot_state_group (for is_transitioning derivation)
PHASE_STATE_TO_GROUP = {
    "CLOSED_OUT": "DISPOSITION",
    "SELLING": "DISPOSITION",
    "VERTICAL_ACTIVE": "VERTICAL",
    "HORIZONTAL_ACTIVE": "HORIZONTAL",
    "LAND_ACQUIRED": "PRE_DEVELOPMENT",
    "PLANNED": "PRE_DEVELOPMENT",
}

# ---------------------------------------------------------------------------
# Allocation sheet column positions (0-indexed)
# These are semi-structured Excel exports — column positions are stable
# across the LH and PF files but row positions of section headers vary.
# ---------------------------------------------------------------------------

ALLOCATION_PHASE_COL = 5
ALLOCATION_PRODTYPE_COL = 6
ALLOCATION_LOTCOUNT_COL = 7
ALLOCATION_SALES_COL = 12
ALLOCATION_LAND_COST_COL = 13
ALLOCATION_DIRECT_DEV_COL = 14
ALLOCATION_WATER_COST_COL = 15
ALLOCATION_INDIRECTS_COL = 16
ALLOCATION_TOTAL_COST_COL = 17

# Map allocation source files to their (project_name, source_label) for tagging
ALLOCATION_SOURCES = {
    str(ALLOCATION_LH_FILE): ("Lomond Heights", "Allocation Sheet LH 2025.10"),
    str(ALLOCATION_PF_FILE): ("Parkway Fields", "Allocation Sheet PF 2025.10"),
}

# ---------------------------------------------------------------------------
# Phase-name normalization
# ---------------------------------------------------------------------------
# PHASE_NAME_OVERRIDES handles the rare case where a source file labels a
# phase differently from Lot Data. Key = (project_name, raw_phase_name)
# exactly as it appears in the source; value = the canonical phase_name used
# in Lot Data. Kept small and explicit — no fuzzy matching.
#
# Current evidence: all 22 non-zero Collateral Report phases and all 17
# allocation-sheet phases already match Lot Data after whitespace
# normalization. This dict is an intentionally empty hook for future renames.
PHASE_NAME_OVERRIDES: dict = {
    # ("Example Project", "Phase 2C"): "2C",
}


def normalize_phase(project_name, raw_phase_name) -> str:
    """Return a canonical phase_name for any (project, phase) input.

    Deterministic rules (applied in order):
      1. Coerce to string, strip leading/trailing whitespace.
      2. Collapse any internal runs of whitespace to a single space.
      3. Apply PHASE_NAME_OVERRIDES for the (project, raw) pair.

    Callers build canonical_phase_id as f"{project_name}::{normalized_phase}".
    """
    if raw_phase_name is None:
        return ""
    s = str(raw_phase_name).strip()
    if not s:
        return ""
    s = " ".join(s.split())
    proj = str(project_name).strip() if project_name is not None else ""
    return PHASE_NAME_OVERRIDES.get((proj, s), s)

# ---------------------------------------------------------------------------
# Output column ordering (matches ontology field order)
# ---------------------------------------------------------------------------

LOT_STATE_OUTPUT_COLUMNS = [
    # Identity
    "canonical_lot_id",
    "project_name",
    "phase_name",
    "lot_number",
    # Relationships
    "project_id",
    "phase_id",
    "customer_name",
    "buyer_id",
    # Horizontal lifecycle dates
    "horiz_purchase_date",
    "horiz_mda_date",
    "horiz_prelim_plat_date",
    "horiz_final_plat_date",
    "horiz_start_date",
    "horiz_end_date",
    "horiz_fin_inv_date",
    "horiz_record_date",
    "horiz_w_enter_date",
    "horiz_w_exit_date",
    "horiz_contract_date",
    "horiz_sale_date",
    # Vertical lifecycle dates
    "vert_purchase_date",
    "vert_start_date",
    "vert_co_date",
    "vert_sale_date",
    "vert_close_date",
    # Derived state
    "lot_state",
    "lot_type",
    "lot_state_group",
    "collateral_bucket",
    # Timing
    "days_in_state",
    "days_since_purchase",
    "pct_complete",
    # Financials
    "cost_to_date",
    "remaining_cost",
    # Capital
    "advance_rate",
    "capital_exposure",
    # Metadata
    "as_of_date",
    "source_systems",
    "last_computed_at",
]

PHASE_STATE_OUTPUT_COLUMNS = [
    # Identity
    "canonical_phase_id",
    "project_name",
    "phase_name",
    # Composition
    "lot_count_total",
    "lot_count_by_state",
    "lot_count_by_type",
    "product_mix_pct",
    # Expected / budget
    "expected_direct_cost_total",
    "expected_indirect_cost_total",
    "expected_total_cost",
    "expected_direct_cost_per_lot",
    "expected_indirect_cost_per_lot",
    "expected_total_cost_per_lot",
    "expected_cost_source",
    # Actuals
    "actual_cost_total",
    "actual_cost_per_lot",
    "actual_direct_cost_total",
    "actual_indirect_cost_total",
    "cost_data_completeness",
    # Variance
    "variance_total",
    "variance_per_lot",
    "variance_pct",
    "variance_meaningful",
    "expected_cost_status",
    "is_queryable",
    # Phase lifecycle
    "phase_state",
    "phase_majority_state",
    "is_transitioning",
    # Timing
    "avg_days_in_state",
    "avg_days_since_purchase",
    "expected_duration_days",
    "phase_start_date",
    # Metadata
    "as_of_date",
    "last_computed_at",
]
