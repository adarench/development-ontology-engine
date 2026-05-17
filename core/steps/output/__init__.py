"""Output steps — human-facing artifacts (HTML reports, dashboards, etc.).

Renderers convert data into formatted strings for human consumption. They are
distinct from `tools/` (LLM-facing). Each renderer is also exposed as an
@step-decorated wrapper so it can participate in graphs.
"""

from core.steps.output.base import Renderer
from core.steps.output.dashboard import DashboardRenderer, render_dashboard

__all__ = ["Renderer", "DashboardRenderer", "render_dashboard"]
