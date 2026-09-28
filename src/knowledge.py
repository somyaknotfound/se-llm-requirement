"""The authorised, version-controlled knowledge base (brief point 5).

    corpus/MANIFEST.csv     source documents with jurisdiction, authority, effective
                            date, version, applicability and SHA-256
    config/controls.yaml    compliance and security controls, each tied to a corpus section
    config/sdlc.yaml        SDLC decision factors, rules, profiles and workflow templates
    config/stakeholders.yaml  role-specific interview templates and approval authority

`fingerprint()` is what every run records, so a result can always be traced to the
exact knowledge it was produced from.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import Any

import yaml

from . import load_pipeline, resolve


@lru_cache(maxsize=1)
def _controls_file() -> dict[str, Any]:
    return yaml.safe_load((resolve("config") / "controls.yaml").read_text(encoding="utf-8"))


def load_controls() -> list[dict[str, Any]]:
    return _controls_file()["controls"]


def controls_by_id() -> dict[str, dict[str, Any]]:
    return {c["id"]: c for c in load_controls()}


def applicable_controls(case: dict[str, Any]) -> list[dict[str, Any]]:
    """Controls that apply to a case and come from one of its authorised sources."""
    sources = set(case.get("knowledge_sources", []))
    return [c for c in load_controls() if case["id"] in c.get("applies_to", []) and c["doc"] in sources]


@lru_cache(maxsize=1)
def load_stakeholder_templates() -> dict[str, Any]:
    return yaml.safe_load((resolve("config") / "stakeholders.yaml").read_text(encoding="utf-8"))


def _sha(path) -> str:
    return hashlib.sha256(resolve(path).read_bytes()).hexdigest()[:16]


def fingerprint() -> dict[str, Any]:
    from .sdlc_engine import load_sdlc

    cfg = load_pipeline()
    return {
        "kb_version": cfg.get("kb_version"),
        "controls_version": _controls_file().get("kb_version"),
        "sdlc_version": load_sdlc().get("version"),
        "manifest_sha": _sha(cfg["paths"]["manifest"]),
        "chunks_sha": _sha(cfg["paths"]["chunks"]),
        "controls_sha": _sha("config/controls.yaml"),
        "sdlc_sha": _sha("config/sdlc.yaml"),
        "stakeholders_sha": _sha("config/stakeholders.yaml"),
        "pipeline_sha": _sha("config/pipeline.yaml"),
        "models_sha": _sha("config/models.yaml"),
    }
