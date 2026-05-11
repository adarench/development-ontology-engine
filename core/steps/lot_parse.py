from __future__ import annotations

import re

import pandas as pd

from core.steps.base import DeterministicToolStep


def _is_real(v) -> bool:
    """True if `v` is a real present value (not None, not NaN, not empty/blank).

    Needed because bool(numpy.nan) is True. Plain `if v:` will admit NaN as
    truthy, producing keys like 'FALLBACK_nan_nan' for fully-unparseable rows.
    """
    if v is None:
        return False
    try:
        if pd.isna(v):
            return False
    except (TypeError, ValueError):
        pass
    if isinstance(v, str):
        return bool(v.strip())
    return bool(v)

DEFAULT_STAGE_ALIASES: dict[str, str] = {
    "dug": "Dug", "excavation": "Dug", "excavate": "Dug",
    "footing": "Footings", "footings": "Footings",
    "wall": "Walls", "walls": "Walls", "foundation": "Walls",
    "backfill": "Backfill",
    "spec": "Spec",
    "rough": "Rough", "rough in": "Rough", "rough-in": "Rough",
    "framing": "Rough",
    "finish": "Finish", "walk": "Finish", "walkthrough": "Finish",
    "walk-through": "Finish", "walk stage": "Finish",
    "complete": "Complete", "completed": "Complete",
    "c_of_o": "Complete", "c of o": "Complete", "cofo": "Complete",
    "co": "Complete", "close": "Complete", "closed": "Complete",
    "sold": "Sold",
}


class LotParseStep(DeterministicToolStep):
    """Parses ClickUp task names into structured lot records and assigns lot keys.

    Input:  raw DataFrame from ClickUpConnector (must have "name" column)
    Output: DataFrame with added columns:
            project_code, lot_number, stage_raw, stage_canonical, lot_label, lot_key

    Task name convention: "<project_code> <lot_number> <stage>"
    e.g. "H 12 Footings" → project_code="H", lot_number="12", stage_canonical="Footings"

    Args:
        stage_aliases: maps lowercased free-text → canonical stage name
    """

    def __init__(self, stage_aliases: dict[str, str] | None = None):
        self.stage_aliases = stage_aliases if stage_aliases is not None else DEFAULT_STAGE_ALIASES
        self._warnings: list[str] = []

    @property
    def warnings(self) -> list[str]:
        return list(self._warnings)

    def run(self, data: pd.DataFrame) -> pd.DataFrame:
        self._warnings.clear()
        df = data.copy()

        parsed = df["name"].apply(self._parse_name)
        df["project_code"]    = [p for p, _, _, _ in parsed]
        df["lot_number"]      = [n for _, n, _, _ in parsed]
        df["stage_raw"]       = [r for _, _, r, _ in parsed]
        df["stage_canonical"] = [c for _, _, _, c in parsed]
        df["lot_label"] = df.apply(
            lambda r: f"{r['project_code']} {r['lot_number']}".strip()
            if _is_real(r["project_code"]) and _is_real(r["lot_number"]) else None,
            axis=1,
        )
        df = self._assign_lot_keys(df)
        return df.reset_index(drop=True)

    def _parse_name(self, name) -> tuple[str | None, str | None, str | None, str | None]:
        if not isinstance(name, str) or not name.strip():
            return None, None, None, None
        tokens = re.split(r"\s+", name.strip())
        digit_idx = [i for i, t in enumerate(tokens) if t.isdigit()]
        if not digit_idx:
            self._warnings.append(f"no numeric token: {name!r}")
            return None, None, None, None
        last = digit_idx[-1]
        project_code = " ".join(tokens[:last]).strip() or None
        lot_number   = tokens[last]
        stage_raw    = " ".join(tokens[last + 1:]).strip() or None
        stage_canon  = self.stage_aliases.get(stage_raw.lower()) if stage_raw else None
        if stage_raw and not stage_canon:
            self._warnings.append(f"unknown stage {stage_raw!r} in {name!r}")
        return project_code, lot_number, stage_raw, stage_canon

    def _assign_lot_keys(self, df: pd.DataFrame) -> pd.DataFrame:
        pid_col = "top_level_parent_id"
        df = df.copy()
        has_pid = (
            df[pid_col].notna() & (df[pid_col].str.len() > 0)
            if pid_col in df.columns
            else pd.Series(False, index=df.index)
        )

        # Build (project_code, lot_number) → canonical parent_id from rows that have one.
        label_to_pid: dict[tuple, str] = {}
        for (pc, ln), sub in df[has_pid].groupby(
            ["project_code", "lot_number"], dropna=True
        ):
            modes = sub[pid_col].mode()
            if len(modes):
                label_to_pid[(pc, ln)] = modes.iat[0]

        def key_for(row):
            if has_pid.loc[row.name]:
                return row[pid_col]
            pc, ln = row["project_code"], row["lot_number"]
            # NaN-safe: bool(numpy.nan) is True, which would wrongly enter the
            # FALLBACK branch and produce 'FALLBACK_nan_nan' for fully
            # unparseable rows on pandas >= 2.x. Use pd.notna() to detect real
            # values regardless of None / NaN representation.
            if _is_real(pc) and _is_real(ln):
                return label_to_pid.get(
                    (pc, ln), f"FALLBACK_{pc}_{ln}".replace(" ", "_")
                )
            return f"ROW_{row.name}"

        df["lot_key"] = df.apply(key_for, axis=1)
        return df
