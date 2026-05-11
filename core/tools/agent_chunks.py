from __future__ import annotations

import json
from pathlib import Path

from core.connectors.base import Connector
from core.steps.chunk_generation import ChunkGenerationStep, Chunk
from core.tools.base import Tool


class AgentChunksTool(Tool):
    """Generates indexed RAG chunks from an operating state and writes them to disk.

    Input:  operating state dict (from OperatingStateTool.run() parsed back to dict,
            or passed directly as data=dict)
    Output: index JSON string (side effect: chunk .md files written to output_dir)

    Args:
        connector:    FileConnector pointing at operating_state_*.json (optional)
        output_dir:   directory to write chunk files (default: output/agent_chunks/)
        state_version: schema_version string embedded in each chunk
    """

    output_format = "json"
    name = "agent_chunks"
    description = (
        "Generates source-backed RAG chunks from the operating state and returns the "
        "chunk index. Each chunk has frontmatter (chunk_id, confidence, caveats) and "
        "a plain-English body. Guardrail chunks are always included."
    )

    def __init__(
        self,
        connector: Connector | None = None,
        output_dir: str | Path | None = None,
        state_version: str = "operating_state_v1",
    ):
        super().__init__(connector)
        self.output_dir   = Path(output_dir) if output_dir else Path("output/agent_chunks")
        self._chunk_step  = ChunkGenerationStep(state_version=state_version)

    def run(self, data=None, **kwargs) -> str:
        if data is None:
            raw = self.connector.fetch()
            state = raw if isinstance(raw, dict) else json.loads(str(raw))
        elif isinstance(data, str):
            state = json.loads(data)
        else:
            state = data

        chunks = self._chunk_step.run(state)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._write_chunks(chunks)
        index = self._build_index(chunks)
        return json.dumps(index, indent=2)

    def _write_chunks(self, chunks: list[Chunk]) -> None:
        for chunk in chunks:
            frontmatter = "\n".join([
                "---",
                f"chunk_id: {chunk.chunk_id}",
                f"chunk_type: {chunk.chunk_type}",
                f"title: {chunk.title}",
                f"project: {chunk.project}",
                f"state_version: {chunk.state_version}",
                f"confidence: {chunk.confidence}",
                f"last_generated: {chunk.last_generated}",
                f"allowed_uses: [{', '.join(chunk.allowed_uses)}]",
                f"caveats: [{', '.join(chunk.caveats)}]",
                "---",
            ])
            content = f"{frontmatter}\n\n# {chunk.title}\n\n{chunk.body}\n"
            (self.output_dir / f"{chunk.chunk_id}.md").write_text(content)

    def _build_index(self, chunks: list[Chunk]) -> dict:
        return {
            "chunk_count": len(chunks),
            "chunks": [
                {
                    "chunk_id":   c.chunk_id,
                    "chunk_type": c.chunk_type,
                    "title":      c.title,
                    "project":    c.project,
                    "confidence": c.confidence,
                    "file":       f"{c.chunk_id}.md",
                }
                for c in chunks
            ],
        }
