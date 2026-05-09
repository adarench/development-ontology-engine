"""HashingEmbeddingProvider — deterministic, install-free fallback.

Maps text -> fixed-dim vector via hashed token bucketing (similar to scikit-learn's
HashingVectorizer projected to L2-normalized form). This is NOT a semantic
embedding — it captures lexical overlap, not paraphrase equivalence. Its
purpose is to let the retrieval pipeline mechanics (filters, score components,
trace assembly, lineage preservation) be tested end-to-end without depending
on Voyage/sentence-transformers.

When Voyage or sentence-transformers is available, prefer those for actual
semantic retrieval. The pipeline contract (EmbeddingProvider Protocol) is the
same; only the model_id differs.
"""

from __future__ import annotations

import hashlib
import re
from typing import List


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
_STOPWORDS = frozenset(
    {
        "the", "a", "an", "and", "or", "but", "of", "in", "on", "at", "to",
        "for", "with", "from", "by", "is", "are", "was", "were", "be", "been",
        "being", "this", "that", "these", "those", "it", "its", "as",
    }
)


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "") if t.lower() not in _STOPWORDS]


def _hash_to_bucket(token: str, dim: int) -> int:
    h = hashlib.sha256(token.encode("utf-8")).digest()
    # 8 bytes is plenty of entropy for any reasonable dim
    return int.from_bytes(h[:8], "big") % dim


def _hash_to_sign(token: str) -> int:
    h = hashlib.sha256(("sign:" + token).encode("utf-8")).digest()
    return 1 if (h[0] & 1) else -1


class HashingEmbeddingProvider:
    """Deterministic token-hash projection. dim controlled at construction."""

    model_id: str = "hashing-v1"

    def __init__(self, dim: int = 256) -> None:
        if dim < 16:
            raise ValueError("HashingEmbeddingProvider dim must be >= 16")
        self.dim = dim
        self.model_id = f"hashing-v1-d{dim}"

    def embed(self, texts: List[str]) -> List[List[float]]:
        out: List[List[float]] = []
        for t in texts:
            v = [0.0] * self.dim
            tokens = _tokenize(t)
            if not tokens:
                out.append(v)
                continue
            for tok in tokens:
                bucket = _hash_to_bucket(tok, self.dim)
                v[bucket] += float(_hash_to_sign(tok))
            # L2 normalize
            norm = sum(x * x for x in v) ** 0.5
            if norm > 0:
                v = [x / norm for x in v]
            out.append(v)
        return out
