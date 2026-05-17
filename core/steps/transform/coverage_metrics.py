from __future__ import annotations

import pandas as pd

from core.engine.registry import step
from core.steps.base import DeterministicToolStep


class CoverageMetricsStep(DeterministicToolStep):
    """Measures GL ↔ inventory ↔ ClickUp join coverage at lot grain.

    Input:  dict with keys:
              "inventory"  — DataFrame with (project_code/subdiv, lot_number/lot_num)
              "gl"         — DataFrame with (project_code, lot)
              "clickup"    — DataFrame with (subdivision, lot_num)  [optional]
    Output: dict of coverage metrics:
              inventory_lots, gl_lot_pairs, clickup_lot_pairs,
              gl_coverage_pct, clickup_coverage_pct, full_triangle_pct,
              per_project (list of dicts)
    """

    def run(self, data: dict) -> dict:
        inv = data.get("inventory", pd.DataFrame())
        gl  = data.get("gl", pd.DataFrame())
        ck  = data.get("clickup", pd.DataFrame())

        inv_pairs = self._inv_pairs(inv)
        gl_pairs  = self._gl_pairs(gl)
        ck_pairs  = self._ck_pairs(ck)

        n_inv = len(inv_pairs)
        n_gl  = len(gl_pairs & inv_pairs)
        n_ck  = len(ck_pairs & inv_pairs)
        n_tri = len(gl_pairs & ck_pairs & inv_pairs)

        pct = lambda a, b: round(100.0 * a / b, 1) if b else 0.0

        projects = sorted({p for p, _ in inv_pairs})
        per_project = []
        for proj in projects:
            i_lots = {l for p, l in inv_pairs if p == proj}
            g_lots = {l for p, l in gl_pairs if p == proj}
            c_lots = {l for p, l in ck_pairs if p == proj}
            n = len(i_lots)
            per_project.append({
                "project_code":        proj,
                "inventory_lots":      n,
                "gl_matched":          len(g_lots & i_lots),
                "clickup_matched":     len(c_lots & i_lots),
                "full_triangle":       len(g_lots & c_lots & i_lots),
                "gl_coverage_pct":     pct(len(g_lots & i_lots), n),
                "clickup_coverage_pct": pct(len(c_lots & i_lots), n),
            })

        return {
            "inventory_lots":       n_inv,
            "gl_lot_pairs":         len(gl_pairs),
            "clickup_lot_pairs":    len(ck_pairs),
            "gl_coverage_pct":      pct(n_gl, n_inv),
            "clickup_coverage_pct": pct(n_ck, n_inv),
            "full_triangle_pct":    pct(n_tri, n_inv),
            "per_project":          per_project,
        }

    def _norm_lot(self, s) -> str:
        if s is None or (isinstance(s, float) and pd.isna(s)):
            return ""
        s = str(s).strip().lstrip("0") or "0"
        if s.endswith(".0"):
            s = s[:-2]
        return s

    def _inv_pairs(self, df: pd.DataFrame) -> set[tuple[str, str]]:
        if df.empty:
            return set()
        proj_col = "project_code" if "project_code" in df.columns else "subdiv"
        lot_col  = "lot_number"   if "lot_number"   in df.columns else "lot_num"
        if proj_col not in df.columns or lot_col not in df.columns:
            return set()
        return {
            (str(r[proj_col]).strip(), self._norm_lot(r[lot_col]))
            for _, r in df.iterrows()
            if pd.notna(r[proj_col]) and pd.notna(r[lot_col])
        }

    def _gl_pairs(self, df: pd.DataFrame) -> set[tuple[str, str]]:
        if df.empty:
            return set()
        if "project_code" not in df.columns or "lot" not in df.columns:
            return set()
        return {
            (str(r["project_code"]).strip(), self._norm_lot(r["lot"]))
            for _, r in df.iterrows()
            if pd.notna(r["project_code"]) and pd.notna(r["lot"])
        }

    def _ck_pairs(self, df: pd.DataFrame) -> set[tuple[str, str]]:
        if df.empty:
            return set()
        proj_col = "subdivision" if "subdivision" in df.columns else "project_code"
        lot_col  = "lot_num" if "lot_num" in df.columns else "lot_number"
        if proj_col not in df.columns or lot_col not in df.columns:
            return set()
        return {
            (str(r[proj_col]).strip(), self._norm_lot(r[lot_col]))
            for _, r in df.iterrows()
            if pd.notna(r[proj_col]) and pd.notna(r[lot_col])
        }


@step(
    name="coverage_metrics",
    inputs={"inventory": pd.DataFrame, "gl": pd.DataFrame, "clickup": pd.DataFrame},
    outputs={"metrics": dict},
    effects=(),
    description="Measure GL ↔ inventory ↔ ClickUp join coverage at lot grain.",
)
def coverage_metrics(
    inventory: pd.DataFrame,
    gl: pd.DataFrame,
    clickup: pd.DataFrame | None = None,
) -> dict[str, dict]:
    return {
        "metrics": CoverageMetricsStep().run({
            "inventory": inventory,
            "gl": gl,
            "clickup": clickup if clickup is not None else pd.DataFrame(),
        })
    }
