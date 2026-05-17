"""Compatibility shim. Canonical home is core.steps.transform.chunk_generation.

Will be removed in Phase 0 milestone P0.6 after all callers migrate.
"""
from core.steps.transform.chunk_generation import Chunk, ChunkGenerationStep, chunk_generation

__all__ = ["Chunk", "ChunkGenerationStep", "chunk_generation"]
