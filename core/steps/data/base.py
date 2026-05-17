from __future__ import annotations
from typing import Any


class Connector:
    """Fetches raw data from a source and returns it as a Python object.

    Connectors own schema validation, column normalization, and any
    source-specific dedup or format quirks. They do not apply business logic.
    """

    def fetch(self, **kwargs) -> Any:
        raise NotImplementedError

    def validate(self) -> bool:
        """Return True if the source is accessible and structurally valid."""
        raise NotImplementedError
