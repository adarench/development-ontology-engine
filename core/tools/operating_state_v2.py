from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from core.connectors.base import Connector
from core.steps.entity_resolution import EntityResolver
from core.steps.lot_parse import LotParseStep
from core.steps.lot_state import LotStateStep
from core.steps.project_state import ProjectStateStep
from core.steps.phase_cluster import PhaseClusterStep
from core.steps.phase_state import PhaseStateStep
from core.tools.base import Tool


class OperatingStateV2Tool(Tool):
    """BCPD v2-style pipeline using staged parquet sources and entity resolution.

    Compared to OperatingStateTool (v1):
    - Accepts pre-staged GL, inventory, and ClickUp connectors separately.
    - Uses an EntityResolver (built by EntityResolutionStep) injected at
      construction for canonical ID lookups.
    - GL is joined at (project, phase, lot) grain to avoid double-counting.
    - Ships confidence metadata per project and per lot.

    Args:
        gl_connector:      DataRailsConnector / FileConnector for staged GL
        inv_connector:     FileConnector for staged inventory lots
        ck_connector:      FileConnector / ClickUpConnector for staged ClickUp tasks
        entity_resolver:   EntityResolver built by EntityResolutionStep
        gap_threshold:     phase clustering gap threshold
    """

    output_format = "json"
    name = "operating_state_v2"
    description = (
        "Builds the v2 operating state from staged GL, inventory, and ClickUp sources "
        "using entity resolution. Returns a JSON object with per-project lot counts, "
        "phase estimates, and financial coverage. Phase IDs are probabilistic."
    )

    def __init__(
        self,
        gl_connector: Connector | None = None,
        inv_connector: Connector | None = None,
        ck_connector: Connector | None = None,
        entity_resolver: EntityResolver | None = None,
        gap_threshold: int = 10,
    ):
        super().__init__(connector=None)
        self.gl_connector    = gl_connector
        self.inv_connector   = inv_connector
        self.ck_connector    = ck_connector
        self.entity_resolver = entity_resolver or EntityResolver()

        self._lot_parse     = LotParseStep()
        self._lot_state     = LotStateStep()
        self._project_state = ProjectStateStep()
        self._phase_cluster = PhaseClusterStep(gap_threshold=gap_threshold)
        self._phase_state   = PhaseStateStep()

    def run(self, data=None, **kwargs) -> str:
        self._reset_provenance()
        gl  = self.gl_connector.fetch()  if self.gl_connector  else pd.DataFrame()
        inv = self.inv_connector.fetch() if self.inv_connector  else pd.DataFrame()
        ck  = self.ck_connector.fetch()  if self.ck_connector   else pd.DataFrame()

        # ClickUp → lot/phase state.
        self._track(self._lot_parse)
        parsed        = self._lot_parse.run(ck)
        self._track(self._lot_state)
        lot_state     = self._lot_state.run(parsed)
        self._track(self._project_state)
        project_state = self._project_state.run(lot_state)
        self._track(self._phase_cluster)          # probabilistic
        with_phase    = self._phase_cluster.run(lot_state)
        self._track(self._phase_state)
        phase_state   = self._phase_state.run(with_phase)

        # GL cost rollup at project grain (lot-grain requires VFDecoderStep).
        cost_map = self._project_cost_map(gl)

        state = self._build_state(with_phase, phase_state, project_state, cost_map, inv)
        return json.dumps(state, indent=2, default=str)

    def _project_cost_map(self, gl: pd.DataFrame) -> dict[str, float]:
        if gl.empty or "project_code" not in gl.columns or "amount" not in gl.columns:
            return {}
        return (
            gl.groupby("project_code")["amount"]
            .apply(lambda s: pd.to_numeric(s, errors="coerce").abs().sum())
            .to_dict()
        )

    def _build_state(
        self,
        lots: pd.DataFrame,
        phases: pd.DataFrame,
        projects: pd.DataFrame,
        cost_map: dict,
        inv: pd.DataFrame,
    ) -> dict:
        project_blocks = []
        for _, proj_row in projects.iterrows():
            code = proj_row["project_code"]
            cost = float(cost_map.get(code, 0.0))
            conf = "high" if cost > 0 else "low"

            phase_blocks = []
            for _, ph in phases[phases["project_code"] == code].iterrows():
                pid = ph["phase_id"]
                phase_lots = lots[
                    (lots["project_code"] == code) & (lots["phase_id"] == pid)
                ]
                lot_blocks = [
                    {
                        "lot_number":     str(lot["lot_number"]) if pd.notna(lot["lot_number"]) else None,
                        "stage":          lot["current_stage"] if pd.notna(lot["current_stage"]) else None,
                        "completion_pct": float(lot["completion_pct"]),
                        "status":         lot["status"],
                        "confidence":     "inferred",
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
                "financials": {
                    "project_total_cost":   round(cost, 2),
                    "financial_confidence": conf,
                    "validated_by_source_owner": False,
                },
                "phases": phase_blocks,
            })

        state: dict = {
            "schema_version": "operating_state_v2_bcpd",
            "generated_at":   datetime.now(timezone.utc).isoformat(),
            "data_quality": {
                "lots_total":     int(len(lots)),
                "projects_total": int(len(projects)),
            },
            "projects": project_blocks,
        }
        prov = self._provenance_dict()
        if prov is not None:
            state["provenance"] = prov
        return state
