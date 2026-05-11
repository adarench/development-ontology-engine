"""Tiny .env loader. Uses python-dotenv if available; otherwise parses inline.

Loads the project-root .env (alongside this repo's top-level files) into
os.environ. Existing env vars are NOT overwritten.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT  = Path(__file__).resolve().parent.parent
DEFAULT_ENV = REPO_ROOT / ".env"


def load_env(path: Path | str | None = None) -> bool:
    """Load environment variables from a .env file. Returns True if loaded."""
    p = Path(path) if path is not None else DEFAULT_ENV
    if not p.exists():
        return False

    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=p, override=False)
        return True
    except ImportError:
        pass

    # Fallback parser: KEY=VALUE per line, optional surrounding quotes, # comments.
    for raw in p.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        os.environ.setdefault(key, val)
    return True
