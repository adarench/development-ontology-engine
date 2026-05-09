"""Local embedding provider — sentence-transformers all-MiniLM-L6-v2 (dim=384).

Used for offline development and as the deterministic fallback. Never the
production target; Voyage is the planned default per the architecture plan.
"""

from __future__ import annotations

from typing import List, Optional


class LocalEmbeddingProvider:
    """sentence-transformers wrapper. Lazy import so it isn't a hard dep."""

    model_id: str = "sentence-transformers/all-MiniLM-L6-v2"
    dim: int = 384

    def __init__(self, model_id: Optional[str] = None) -> None:
        if model_id:
            self.model_id = model_id
        self._model = None  # populated on first embed() call

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as e:
            raise ImportError(
                "Local embedding provider requires sentence-transformers. "
                "Install via `pip install sentence-transformers` or use VoyageEmbeddingProvider."
            ) from e
        self._model = SentenceTransformer(self.model_id)
        # Update dim from the actual model in case a non-default model was supplied.
        try:
            self.dim = int(self._model.get_sentence_embedding_dimension())
        except Exception:
            pass

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        self._ensure_model()
        assert self._model is not None
        vectors = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [list(map(float, v)) for v in vectors]
