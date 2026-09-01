"""Shared paths and config loading for the SE LLM-RE pipeline."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resolve(rel: str | Path) -> Path:
    """Resolve a config-declared relative path against the project root."""
    p = Path(rel)
    return p if p.is_absolute() else PROJECT_ROOT / p


@lru_cache(maxsize=None)
def _load_yaml(name: str) -> dict[str, Any]:
    path = PROJECT_ROOT / "config" / name
    if not path.exists():
        raise FileNotFoundError(f"missing config file: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_pipeline() -> dict[str, Any]:
    return _load_yaml("pipeline.yaml")


def load_models() -> dict[str, Any]:
    cfg = _load_yaml("models.yaml")
    # .env / environment wins over the checked-in default so the daemon can be
    # relocated without editing a file that is part of the reproducibility record.
    host = os.environ.get("OLLAMA_HOST")
    if host:
        cfg = {**cfg, "host": host}
    return cfg


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
