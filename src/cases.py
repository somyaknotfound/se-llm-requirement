"""Case-study definitions.

Each case under `cases/<id>/` is one healthcare functionality the system is run and
evaluated on:

    case.yaml   functionality, knowledge-source allowlist, retrieval facets,
                stakeholder personas (with hidden fact sheets), input documents,
                project context for SDLC selection
    gold.yaml   the reviewed gold standard: requirements, seeded ambiguities and
                conflicts, seeded prompt injections, applicable controls, and the
                expert SDLC decision
    documents/  the unstructured inputs (meeting notes, emails, policies, legacy
                interface specs, incident reports)

Case materials are synthetic. The gold standard only counts once the author has
reviewed it (`reviewed_by`), and the fields that need human judgement are never
filled by code.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from . import ensure_dir, load_pipeline, resolve

CASES_DIR = resolve("cases")


def case_ids() -> list[str]:
    return sorted(p.parent.name for p in CASES_DIR.glob("*/case.yaml"))


@lru_cache(maxsize=None)
def load_case(case_id: str) -> dict[str, Any]:
    path = CASES_DIR / case_id / "case.yaml"
    if not path.exists():
        raise FileNotFoundError(f"unknown case {case_id!r}; available: {case_ids()}")
    case = yaml.safe_load(path.read_text(encoding="utf-8"))
    case["id"] = case_id
    for doc in case.get("documents", []):
        doc_path = CASES_DIR / case_id / doc["path"]
        doc["text"] = doc_path.read_text(encoding="utf-8")
    return case


def load_gold(case_id: str) -> dict[str, Any]:
    path = CASES_DIR / case_id / "gold.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def case_out_dir(case_id: str) -> Path:
    return ensure_dir(resolve(load_pipeline()["paths"]["outputs"]) / "cases" / case_id)


def target_for(case_id: str | None) -> dict[str, Any]:
    """The functionality under analysis: the pipeline default, or a case's own."""
    if not case_id:
        return load_pipeline()["target"]
    fn = load_case(case_id)["functionality"]
    return {"id": case_id, "name": fn["name"], "description": fn["description"],
            "keywords": fn.get("keywords", [])}
