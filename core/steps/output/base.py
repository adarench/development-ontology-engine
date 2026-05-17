from __future__ import annotations

import json
from abc import ABC, abstractmethod

from core.connectors.base import Connector


class Renderer(ABC):
    """Base class for human-facing output (HTML, PDF, terminal, etc.).

    Renderers are NOT for LLM consumption — use Tool subclasses for that.
    A Renderer takes data (dict, DataFrame, operating state JSON) and returns
    a formatted string meant to be viewed by a person.

    output_format signals the format: "html", "markdown", "text", etc.
    """

    output_format: str = "html"

    def __init__(self, connector: Connector | None = None):
        self.connector = connector

    @abstractmethod
    def render(self, data=None, **kwargs) -> str:
        """Render data to a human-readable string.

        Args:
            data: operating state dict, JSON string, or None (loads from connector)
        Returns:
            Formatted string in output_format
        """

    def _load(self, data) -> dict:
        if data is None:
            if self.connector is None:
                return {}
            raw = self.connector.fetch()
            return raw if isinstance(raw, dict) else {}
        if isinstance(data, str):
            return json.loads(data)
        return data
