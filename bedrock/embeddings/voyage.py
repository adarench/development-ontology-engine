"""Voyage AI embedding provider — voyage-3 (dim=1024).

Gated on VOYAGE_API_KEY (read from environment or .env). Per the architecture
plan, this is the planned production default. Phase 2 ships it but does not
require it; correctness work uses LocalEmbeddingProvider by default.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional


class VoyageEmbeddingProvider:
    """Thin wrapper around voyageai.Client."""

    model_id: str = "voyage-3"
    dim: int = 1024

    def __init__(self, model_id: Optional[str] = None, api_key: Optional[str] = None) -> None:
        if model_id:
            self.model_id = model_id
        self._api_key = api_key or _read_voyage_api_key()
        if not self._api_key:
            raise RuntimeError(
                "VOYAGE_API_KEY not set. Add it to .env or export it; "
                "or use LocalEmbeddingProvider for offline dev."
            )
        self._client = None

    def _ensure_client(self) -> None:
        if self._client is not None:
            return
        try:
            import voyageai  # type: ignore
        except ImportError as e:
            raise ImportError(
                "Voyage embedding provider requires voyageai. "
                "Install via `pip install voyageai`."
            ) from e
        self._client = voyageai.Client(api_key=self._api_key)

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        self._ensure_client()
        assert self._client is not None
        result = self._client.embed(texts, model=self.model_id, input_type="document")
        return [list(map(float, v)) for v in result.embeddings]


def _read_voyage_api_key() -> Optional[str]:
    if os.environ.get("VOYAGE_API_KEY"):
        return os.environ["VOYAGE_API_KEY"]
    # Mirrors the .env-loading pattern from financials/qa/llm_eval/claude_client.py
    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"):
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if line.startswith("VOYAGE_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None
