from __future__ import annotations

import pandas as pd

from core.engine.registry import step
from core.steps.base import DeterministicToolStep

OUTPUT_COLS = [
    "project_code", "lot_number", "stage", "completion_pct",
    "status", "phase_id_estimated",
]

DEFAULT_PROJECT_TO_ENTITY: dict[str, str] = {
    "LE":    "Anderson Geneva LLC",
    "H":     "Flagborough LLC",
    "H MF":  "Flagborough LLC",
    "H A14": "Flagborough LLC",
    "H A13": "Flagborough LLC",
    "AS":    "Arrowhead Springs Development LLC",
}


class OperatingViewStep(DeterministicToolStep):
    """Joins lot state, project state, and GL financials into a flat operating view.

    Input:  dict with keys:
              "lot_state"     — DataFrame from PhaseClusterStep (has phase_id)
              "project_state" — DataFrame from ProjectStateStep
              "gl_normalized" — DataFrame from GLNormalizeStep (optional)
    Output: 6-column operating view DataFrame

    Args:
        project_to_entity: maps project_code → GL entity name for cost join
    """

    def __init__(self, project_to_entity: dict[str, str] | None = None):
        self.project_to_entity = (
            project_to_entity if project_to_entity is not None else DEFAULT_PROJECT_TO_ENTITY
        )

    def run(self, data: dict) -> pd.DataFrame:
        lots    = data["lot_state"].copy()
        project = data["project_state"]
        gl      = data.get("gl_normalized")

        if "phase_id" not in lots.columns and "phase_id_estimated" not in lots.columns:
            raise ValueError(
                "OperatingViewStep: lot_state must have 'phase_id' or "
                "'phase_id_estimated' — run PhaseClusterStep first"
            )
        phase_col = "phase_id" if "phase_id" in lots.columns else "phase_id_estimated"

        lots = lots.merge(project, on="project_code", how="left", suffixes=("", "_project"))

        if gl is not None:
            proj_only = gl[gl["entity_role"] == "project"]
            cost_total = (
                proj_only.groupby("entity")["amount"]
                .apply(lambda s: s.abs().sum())
                .to_dict()
            )
            lots["gl_entity"]           = lots["project_code"].map(self.project_to_entity)
            lots["project_total_cost"]  = lots["gl_entity"].map(cost_total).fillna(0.0)
        else:
            lots["gl_entity"]          = None
            lots["project_total_cost"] = 0.0

        out = pd.DataFrame({
            "project_code":       lots["project_code"],
            "lot_number":         lots["lot_number"],
            "stage":              lots["current_stage"],
            "completion_pct":     lots["completion_pct"],
            "status":             lots["status"],
            "phase_id_estimated": lots[phase_col],
        })[OUTPUT_COLS].sort_values(
            ["project_code", "phase_id_estimated", "lot_number"],
            na_position="last",
        ).reset_index(drop=True)

        return out


@step(
    name="operating_view",
    inputs={"lot_state": pd.DataFrame, "project_state": pd.DataFrame, "gl_normalized": pd.DataFrame},
    outputs={"operating_view": pd.DataFrame},
    effects=(),
    description="Join lot state, project state, and (optional) GL into a flat 6-column operating view.",
)
def operating_view(
    lot_state: pd.DataFrame,
    project_state: pd.DataFrame,
    gl_normalized: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    return {
        "operating_view": OperatingViewStep().run({
            "lot_state": lot_state,
            "project_state": project_state,
            "gl_normalized": gl_normalized,
        })
    }
