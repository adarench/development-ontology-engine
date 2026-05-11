"""Content-addressed embedding cache.

Key: sha256(model_id + "::" + text)[:32]. On-disk parquet at
output/embeddings_cache.parquet. Idempotent — same input -> same vector.
Cache hits skip the embedding call entirely, which is the primary mechanism
that makes eval runs offline-deterministic.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def cache_key(model_id: str, text: str) -> str:
    return hashlib.sha256(f"{model_id}::{text}".encode("utf-8")).hexdigest()[:32]


class EmbeddingCache:
    """Append-only on-disk cache. Pandas-backed parquet.

    Columns: key (str), model_id (str), dim (int), vector (object, list[float]).
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self._mem: Dict[str, List[float]] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self.path.exists():
            return
        import pandas as pd

        df = pd.read_parquet(self.path)
        for _, row in df.iterrows():
            self._mem[row["key"]] = list(row["vector"])

    def get(self, model_id: str, text: str) -> Optional[List[float]]:
        self._ensure_loaded()
        return self._mem.get(cache_key(model_id, text))

    def get_many(self, model_id: str, texts: List[str]) -> List[Optional[List[float]]]:
        self._ensure_loaded()
        return [self._mem.get(cache_key(model_id, t)) for t in texts]

    def put_many(self, model_id: str, items: List[Tuple[str, List[float]]]) -> None:
        """items = [(text, vector), ...]"""
        self._ensure_loaded()
        for text, vector in items:
            self._mem[cache_key(model_id, text)] = vector

    def flush(self) -> None:
        if not self._mem:
            return
        import pandas as pd

        rows = []
        for key, vector in self._mem.items():
            rows.append({"key": key, "dim": len(vector), "vector": vector})
        df = pd.DataFrame(rows)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(self.path, index=False)

    def __len__(self) -> int:
        self._ensure_loaded()
        return len(self._mem)
