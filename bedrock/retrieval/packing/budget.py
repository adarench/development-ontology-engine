"""Token counting for the packer.

Prefers tiktoken (cl100k_base) when available; falls back to a deliberately
conservative len(text)/4 + small overhead. Both are deterministic and free
of LLM dependencies — token counting must NEVER call out to a model.

The fallback heuristic is intentionally tuned to over-estimate slightly so
the budget gate trips earlier rather than later when packing without tiktoken.
"""

from __future__ import annotations

from typing import Optional


_FALLBACK_CHARS_PER_TOKEN = 3.5  # conservative; English ~4, structured ~3
_FALLBACK_CONST_OVERHEAD = 4    # accounts for newlines + punctuation framing


_tiktoken_encoder = None
_tried_tiktoken = False


def _try_tiktoken_encoder():
    global _tiktoken_encoder, _tried_tiktoken
    if _tried_tiktoken:
        return _tiktoken_encoder
    _tried_tiktoken = True
    try:
        import tiktoken  # type: ignore

        _tiktoken_encoder = tiktoken.get_encoding("cl100k_base")
    except Exception:
        _tiktoken_encoder = None
    return _tiktoken_encoder


def count_tokens(text: str, encoder_name: str = "cl100k_base") -> int:
    """Count tokens in `text`. Deterministic; no network, no LLM."""
    if not text:
        return 0
    enc = _try_tiktoken_encoder()
    if enc is not None and encoder_name == "cl100k_base":
        try:
            return len(enc.encode(text, disallowed_special=()))
        except Exception:
            pass
    return _fallback_count(text)


def _fallback_count(text: str) -> int:
    return int(len(text) / _FALLBACK_CHARS_PER_TOKEN) + _FALLBACK_CONST_OVERHEAD


def using_tiktoken() -> bool:
    return _try_tiktoken_encoder() is not None
