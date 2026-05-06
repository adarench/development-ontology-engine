from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from core.connectors.base import Connector
from core.steps.gl_clean import GLCleanStep
from core.steps.gl_normalize import GLNormalizeStep
from core.steps.lot_parse import LotParseStep
from core.steps.lot_state import LotStateStep
from core.steps.project_state import ProjectStateStep
from core.steps.phase_cluster import PhaseClusterStep
from core.steps.phase_state import PhaseStateStep
from core.steps.operating_view import OperatingViewStep, DEFAULT_PROJECT_TO_ENTITY
from core.tools.base import Tool


class OperatingStateTool(Tool):
    """Full v1 pipeline: ClickUp + GL → agent-ready operating state JSON.

    Orchestrates:
      ClickUp: LotParseStep → LotStateStep → ProjectStateStep → PhaseClusterStep
               → PhaseStateStep → OperatingViewStep
      GL (optional): GLCleanStep → GLNormalizeStep
      Packages everything into a nested JSON string.

    Args:
        connector:          ClickUpConnector (or FileConnector for mocks)
        gl_connector:       QuickBooksConnector / FileConnector for GL (optional)
        gap_threshold:      phase clustering gap threshold (default 10)
        project_to_entity:  maps project_code → GL entity for cost join
        entity_map:         GL entity → (role, project_id)
    """

    output_format = "json"
    name = "operating_state"
    description = (
        "Builds the full operating state from ClickUp task data and optional GL financials. "
        "Returns a JSON object with per-project lot counts, stage distributions, phase "
        "estimates, and financial coverage. Phase IDs are probabilistic (heuristic clustering)."
    )

    def __init__(
        self,
        connector: Connector | None = None,
        gl_connector: Connector | None = None,
        gap_threshold: int = 10,
        project_to_entity: dict | None = None,
        entity_map: dict | None = None,
    ):
        super().__init__(connector)
        self.gl_connector    = gl_connector
        self._lot_parse      = LotParseStep()
        self._lot_state      = LotStateStep()
        self._project_state  = ProjectStateStep()
        self._phase_cluster  = PhaseClusterStep(gap_threshold=gap_threshold)
        self._phase_state    = PhaseStateStep()
        self._op_view        = OperatingViewStep(project_to_entity=project_to_entity)
        self._gl_clean       = GLCleanStep()
        self._gl_normalize   = GLNormalizeStep(entity_map=entity_map)
        self._project_to_entity = project_to_entity or DEFAULT_PROJECT_TO_ENTITY

    def run(self, data: pd.DataFrame | None = None, **kwargs) -> str:
        self._reset_provenance()
        raw_clickup = data if data is not None else self.connector.fetch()

        self._track(self._lot_parse)
        parsed        = self._lot_parse.run(raw_clickup)
        self._track(self._lot_state)
        lot_state     = self._lot_state.run(parsed)
        self._track(self._project_state)
        project_state = self._project_state.run(lot_state)
        self._track(self._phase_cluster)          # probabilistic
        with_phase    = self._phase_cluster.run(lot_state)
        self._track(self._phase_state)
        phase_state   = self._phase_state.run(with_phase)

        gl_norm = None
        if self.gl_connector is not None:
            self._track(self._gl_clean)
            raw_gl   = self.gl_connector.fetch()
            clean_gl = self._gl_clean.run(raw_gl)
            self._track(self._gl_normalize)
            gl_norm  = self._gl_normalize.run(clean_gl)

        state = self._build_state(with_phase, phase_state, project_state, gl_norm)
        return json.dumps(state, indent=2, default=str)

    def _build_state(
        self,
        lots: pd.DataFrame,
        phases: pd.DataFrame,
        projects: pd.DataFrame,
        gl_norm: pd.DataFrame | None,
    ) -> dict:
        cost_map: dict[str, float] = {}
        if gl_norm is not None:
            proj_only = gl_norm[gl_norm["entity_role"] == "project"]
            cost_map = (
                proj_only.groupby("entity")["amount"]
                .apply(lambda s: s.abs().sum())
                .to_dict()
            )

        project_blocks = []
        for _, proj_row in projects.iterrows():
            code      = proj_row["project_code"]
            gl_entity = self._project_to_entity.get(code)
            cost      = float(cost_map.get(gl_entity, 0.0)) if gl_entity else 0.0

            if gl_entity and cost > 0:
                fin_conf = "high"
                fin_note = f"GL entity '{gl_entity}' matched."
            elif gl_entity:
                fin_conf = "low"
                fin_note = f"GL entity '{gl_entity}' mapped but no Activity rows found."
            else:
                fin_conf = "low"
                fin_note = "No GL entity mapping for this project_code."

            phase_blocks = []
            proj_phases = phases[phases["project_code"] == code]
            for _, ph in proj_phases.iterrows():
                pid = ph["phase_id"]
                phase_lots = lots[
                    (lots["project_code"] == code) & (lots["phase_id"] == pid)
                ]
                lot_blocks = [
                    {
                        "lot_number":     str(lot["lot_number"]) if pd.notna(lot["lot_number"]) else None,
                        "stage":          lot["current_stage"] if pd.notna(lot["current_stage"]) else None,
                        "completion_pct": float(lot["completion_pct"]) if pd.notna(lot["completion_pct"]) else 0.0,
                        "status":         lot["status"],
                    }
                    for _, lot in phase_lots.iterrows()
                ]
                phase_blocks.append({
                    "phase_id_estimated": pid,
                    "lots_in_phase":      int(ph["lots_in_phase"]),
                    "dominant_stage":     ph["dominant_stage"] if pd.notna(ph["dominant_stage"]) else None,
                    "avg_completion_pct": float(ph["avg_completion_pct"]),
                    "lots":               lot_blocks,
                })

            project_blocks.append({
                "project_code":       code,
                "lots_total":         int(proj_row["total_lots"]),
                "avg_completion_pct": float(proj_row["avg_completion_pct"]),
                "stage_distribution": proj_row["stage_distribution"],
                "financials": {
                    "gl_entity":            gl_entity,
                    "project_total_cost":   round(cost, 2),
                    "financial_confidence": fin_conf,
                    "financial_notes":      fin_note,
                },
                "phases": phase_blocks,
            })

        quality = {
            "lots_total":      int(len(lots)),
            "projects_total":  int(len(projects)),
            "phases_estimated": int(len(phases)),
        }

        state: dict = {
            "schema_version": "operating_state_v1",
            "generated_at":   datetime.now(timezone.utc).isoformat(),
            "data_quality":   quality,
            "projects":       project_blocks,
        }
        prov = self._provenance_dict()
        if prov is not None:
            state["provenance"] = prov
        return state
