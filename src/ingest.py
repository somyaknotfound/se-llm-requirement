"""Corpus acquisition, cleaning and chunking.

    python -m src.ingest fetch      # network -> corpus/raw/ + MANIFEST.csv
    python -m src.ingest process    # corpus/raw/ -> corpus/processed/*.txt
    python -m src.ingest chunk      # corpus/processed/ -> corpus/chunks.jsonl
    python -m src.ingest all

The fetch step is scripted rather than manual so that provenance is a computed
fact: every row of MANIFEST.csv carries the sha256 of the bytes that were actually
parsed, so a marker can re-download the sources and prove the corpus was not
curated after the fact to make the requirements look well-grounded.

Section identity is preserved end to end. eCFR XML exposes real section numbers on
DIV8/@N; FHIR HTML carries them as numeric prefixes on heading tags. Both become
the `S...` component of a chunk_id like `D06#S1311.115#c02`, which is what every
downstream traceability claim resolves against.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import requests
import tiktoken
from bs4 import BeautifulSoup

from . import ensure_dir, load_pipeline, resolve

USER_AGENT = (
    "se-llm-requirements/1.0 (academic software-engineering coursework; "
    "corpus acquisition for requirements-engineering study)"
)

# --- Corpus definition ----------------------------------------------------
# Six documents, deliberately split between interoperability standards (what the
# artifact looks like) and binding regulation (what the system must guarantee).
# The regulatory half is what gives the e-Rx functionality its NFR density; a
# corpus of FHIR pages alone would under-generate security and audit requirements.
SOURCES: list[dict[str, Any]] = [
    {
        "doc_id": "D01",
        "title": "HL7 FHIR R4 — MedicationRequest Resource",
        "source_url": "https://hl7.org/fhir/R4/medicationrequest.html",
        "publisher": "Health Level Seven International",
        "year": 2019,
        "license": "CC0-1.0",
        "doc_type": "interoperability_standard",
        "parser": "fhir_html",
    },
    {
        "doc_id": "D02",
        "title": "HL7 FHIR R4 — AllergyIntolerance Resource",
        "source_url": "https://hl7.org/fhir/R4/allergyintolerance.html",
        "publisher": "Health Level Seven International",
        "year": 2019,
        "license": "CC0-1.0",
        "doc_type": "interoperability_standard",
        "parser": "fhir_html",
    },
    {
        "doc_id": "D03",
        "title": "HL7 FHIR R4 — Security and Privacy Module",
        "source_url": "https://hl7.org/fhir/R4/security.html",
        "publisher": "Health Level Seven International",
        "year": 2019,
        "license": "CC0-1.0",
        "doc_type": "interoperability_standard",
        "parser": "fhir_html",
    },
    {
        "doc_id": "D04",
        "title": "HIPAA Security Rule — 45 CFR Part 164 Subpart C (Security Standards)",
        "source_url": (
            "https://www.ecfr.gov/api/versioner/v1/full/2025-01-01/"
            "title-45.xml?part=164&subpart=C"
        ),
        "publisher": "U.S. Office of the Federal Register (eCFR)",
        "year": 2025,
        "license": "US-Gov-Public-Domain",
        "doc_type": "regulation",
        "parser": "ecfr_xml",
    },
    {
        "doc_id": "D05",
        "title": "ONC Health IT Certification Criteria — 45 CFR 170.315",
        "source_url": (
            "https://www.ecfr.gov/api/versioner/v1/full/2025-01-01/"
            "title-45.xml?part=170&section=170.315"
        ),
        "publisher": "U.S. Office of the Federal Register (eCFR)",
        "year": 2025,
        "license": "US-Gov-Public-Domain",
        "doc_type": "regulation",
        "parser": "ecfr_xml",
    },
    {
        "doc_id": "D06",
        "title": (
            "DEA Electronic Prescriptions for Controlled Substances — "
            "21 CFR Part 1311"
        ),
        "source_url": "https://www.ecfr.gov/api/versioner/v1/full/2025-01-01/title-21.xml?part=1311",
        "publisher": "U.S. Office of the Federal Register (eCFR)",
        "year": 2025,
        "license": "US-Gov-Public-Domain",
        "doc_type": "regulation",
        "parser": "ecfr_xml",
    },
]

MANIFEST_COLUMNS = [
    "doc_id",
    "title",
    "source_url",
    "publisher",
    "year",
    "license",
    "doc_type",
    "pages",
    "sha256",
    "retrieved_on",
    # Additive columns — not required by the spec, but the report's corpus table
    # needs size and structure figures and recomputing them by hand is error-prone.
    "bytes",
    "n_sections",
    "n_chunks",
]

SECTION_MARKER = "### "

# Absolute floor, independent of chunking.min_chunk_tokens: a window this small
# carries no retrievable meaning regardless of where it came from.
HARD_MIN_TOKENS = 20

_ENCODER = None


def _count_tokens(text: str) -> int:
    global _ENCODER
    if _ENCODER is None:
        _ENCODER = tiktoken.get_encoding(load_pipeline()["chunking"]["tokenizer"])
    return len(_ENCODER.encode(text))


def _ext_for(parser: str) -> str:
    return {"fhir_html": "html", "ecfr_xml": "xml", "pdf": "pdf"}[parser]


# --- fetch ----------------------------------------------------------------


def fetch() -> None:
    cfg = load_pipeline()
    raw_dir = ensure_dir(resolve(cfg["paths"]["corpus_raw"]))
    manifest_path = resolve(cfg["paths"]["manifest"])
    today = date.today().isoformat()

    rows = []
    for src in SOURCES:
        dest = raw_dir / f"{src['doc_id']}.{_ext_for(src['parser'])}"
        print(f"[fetch] {src['doc_id']} <- {src['source_url']}")
        resp = requests.get(
            src["source_url"], headers={"User-Agent": USER_AGENT}, timeout=120
        )
        resp.raise_for_status()
        dest.write_bytes(resp.content)

        sha = hashlib.sha256(resp.content).hexdigest()
        pages = ""
        if src["parser"] == "pdf":
            from pypdf import PdfReader

            pages = len(PdfReader(str(dest)).pages)

        rows.append(
            {
                "doc_id": src["doc_id"],
                "title": src["title"],
                "source_url": src["source_url"],
                "publisher": src["publisher"],
                "year": src["year"],
                "license": src["license"],
                "doc_type": src["doc_type"],
                "pages": pages,
                "sha256": sha,
                "retrieved_on": today,
                "bytes": len(resp.content),
                "n_sections": "",
                "n_chunks": "",
            }
        )
        print(f"         -> {dest.name}  {len(resp.content):,} bytes  sha256={sha[:16]}...")

    _write_manifest(manifest_path, rows)
    print(f"\n[fetch] {len(rows)} documents -> {manifest_path}")


def _write_manifest(path: Path, rows: list[dict[str, Any]]) -> None:
    import pandas as pd

    ensure_dir(path.parent)
    pd.DataFrame(rows, columns=MANIFEST_COLUMNS).to_csv(path, index=False, encoding="utf-8")


def _read_manifest(path: Path) -> list[dict[str, Any]]:
    import pandas as pd

    return pd.read_csv(path, dtype=str).fillna("").to_dict("records")


# --- process --------------------------------------------------------------


def _clean(text: str) -> str:
    text = text.replace(" ", " ").replace("‑", "-")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _parse_fhir_html(raw: bytes) -> list[tuple[str, str, str]]:
    """-> [(section_id, heading, body)] from an HL7 FHIR R4 specification page.

    Content lives in div#tabs; everything outside it is site chrome. FHIR numbers
    its headings ('11.1.3 Resource Content'), so the numeric prefix is a stable
    section id that a reader can find in the published page.
    """
    soup = BeautifulSoup(raw, "lxml")
    # div#segment-content is the superset container. On resource pages (e.g.
    # MedicationRequest) div#tabs holds only the element tables and contains no
    # headings at all, so selecting it first collapses the whole page into one
    # section — silently, since the text still looks fine.
    root = soup.select_one("div#segment-content") or soup.select_one("div#tabs") or soup
    for junk in root.select(
        "script, style, nav, footer, #segment-breadcrumb, #segment-footer, "
        "#segment-navbar, #segment-header, .nav, .navbar"
    ):
        junk.decompose()

    sections: list[tuple[str, str, str]] = []
    current_id, current_head, buf = "0", "Preamble", []

    for el in root.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "th", "pre"]):
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        if el.name in ("h1", "h2", "h3", "h4"):
            if buf:
                sections.append((current_id, current_head, _clean("\n".join(buf))))
                buf = []
            m = re.match(r"^((?:\d+\.)*\d+)\s+(.*)$", text)
            if m:
                current_id, current_head = m.group(1), m.group(2)
            else:
                current_id, current_head = _slug_id(text), text
        else:
            buf.append(text)

    if buf:
        sections.append((current_id, current_head, _clean("\n".join(buf))))
    return [s for s in sections if s[2]]


def _parse_ecfr_xml(raw: bytes) -> list[tuple[str, str, str]]:
    """-> [(section_id, heading, body)] from eCFR versioner XML.

    DIV8 is one CFR section and carries the citation number on @N, which is the
    identifier a regulator, an auditor and the report all use. Preserving it means
    a generated requirement can cite '45 CFR 164.312' and be checked mechanically.
    """
    soup = BeautifulSoup(raw, "xml")
    sections: list[tuple[str, str, str]] = []

    for div in soup.find_all("DIV8"):
        sec_id = (div.get("N") or "").strip()
        head_el = div.find("HEAD")
        heading = head_el.get_text(" ", strip=True) if head_el else sec_id
        parts = [
            p.get_text(" ", strip=True)
            for p in div.find_all(["P", "FP"])
            if p.get_text(strip=True)
        ]
        if not (sec_id and parts):
            continue
        sections.extend(
            _split_by_designator(
                sec_id, heading, parts, load_pipeline()["chunking"]["target_tokens"]
            )
        )

    return sections


def _split_by_designator(
    sec_id: str, heading: str, paragraphs: list[str], target_tokens: int
) -> list[tuple[str, str, str]]:
    """Subdivide a CFR section on its top-level (a)/(b)/(c) paragraph designators.

    Without this, 45 CFR 170.315 — which is a single DIV8 carrying every ONC
    certification criterion — yields one undifferentiated section, and a citation
    to it says only 'somewhere in the certification criteria'. Splitting on the
    designator makes the far more useful '170.315(b)' addressable, which is the
    granularity at which e-prescribing and audit-log criteria are actually cited.

    Splitting naively in the other direction is just as harmful: most CFR sections
    are two sentences, and one chunk per designator turns them into 40-token
    fragments that retrieve badly and carry no context. So sections under the
    target size are left whole, and adjacent designator groups are merged back up
    toward the target — the id then names the span it actually covers, e.g.
    '1311.115(a)-(b)'.
    """
    total = _count_tokens("\n".join(paragraphs))
    if total <= target_tokens:
        return [(sec_id, heading, _clean("\n".join(paragraphs)))]

    groups: list[tuple[str | None, list[str]]] = []
    current: tuple[str | None, list[str]] | None = None
    expected: str | None = None

    for para in paragraphs:
        # CFR nests (a)(1)(i)(A). Only the outermost single-letter level is a
        # section subdivision; matching [a-z]{1,2} also swallows roman numerals
        # like (ii), which are sub-paragraphs and produce nonsense citations such
        # as '170.315(ii)-(ii)'. Requiring the letter to be the next one in
        # sequence keeps '(i)' as a genuine ninth designator when it follows (h)
        # and rejects it as roman-one everywhere else.
        m = re.match(r"^\(([a-z])\)\s", para)
        desig = m.group(1) if m else None
        starts_group = desig is not None and (expected is None or desig == expected)

        if starts_group:
            if current:
                groups.append(current)
            current = (desig, [para])
            expected = chr(ord(desig) + 1)
        elif current:
            current[1].append(para)
        else:
            current = (None, [para])

    if current:
        groups.append(current)

    merged: list[tuple[list[str], list[str]]] = []
    for desig, paras in groups:
        tokens = _count_tokens("\n".join(paras))
        if merged and _count_tokens("\n".join(merged[-1][1])) + tokens <= target_tokens:
            merged[-1][0].append(desig or "")
            merged[-1][1].extend(paras)
        else:
            merged.append(([desig or ""], list(paras)))

    out: list[tuple[str, str, str]] = []
    for desigs, paras in merged:
        body = _clean("\n".join(paras))
        if not body:
            continue
        labels = [d for d in desigs if d]
        if not labels:
            sub_id, sub_head = sec_id, heading
        elif len(labels) == 1:
            sub_id = f"{sec_id}({labels[0]})"
            sub_head = f"{heading} - ({labels[0]})"
        else:
            sub_id = f"{sec_id}({labels[0]})-({labels[-1]})"
            sub_head = f"{heading} - ({labels[0]})-({labels[-1]})"
        # Carry the parent heading so a retrieved chunk still identifies its
        # section; the designator alone is meaningless out of context.
        out.append((sub_id, sub_head, body))

    return out or [(sec_id, heading, _clean("\n".join(paragraphs)))]


def _parse_pdf(raw_path: Path) -> list[tuple[str, str, str]]:
    """-> [(section_id, heading, body)] from a PDF, one entry per page.

    PDFs carry no reliable structural markup, so pages are the only honest section
    unit. Page-number-only lines and repeated headers are stripped as noise.
    """
    from pypdf import PdfReader

    sections = []
    for i, page in enumerate(PdfReader(str(raw_path)).pages, start=1):
        text = page.extract_text() or ""
        lines = [
            ln
            for ln in text.splitlines()
            if ln.strip() and not re.fullmatch(r"\s*(page\s*)?\d+\s*", ln, re.I)
        ]
        body = _clean("\n".join(lines))
        if body:
            sections.append((f"p{i}", f"Page {i}", body))
    return sections


def _slug_id(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")[:40] or "sec"


def process() -> None:
    cfg = load_pipeline()
    raw_dir = resolve(cfg["paths"]["corpus_raw"])
    out_dir = ensure_dir(resolve(cfg["paths"]["corpus_processed"]))
    manifest_path = resolve(cfg["paths"]["manifest"])
    manifest = {r["doc_id"]: r for r in _read_manifest(manifest_path)}

    for src in SOURCES:
        doc_id = src["doc_id"]
        raw_path = raw_dir / f"{doc_id}.{_ext_for(src['parser'])}"
        if not raw_path.exists():
            raise FileNotFoundError(f"{raw_path} missing — run `python -m src.ingest fetch` first")

        raw = raw_path.read_bytes()
        # Integrity gate: the processed text must derive from the exact bytes the
        # manifest attests to, or every traceability claim downstream is unfounded.
        actual = hashlib.sha256(raw).hexdigest()
        recorded = manifest.get(doc_id, {}).get("sha256", "")
        if recorded and actual != recorded:
            raise ValueError(
                f"{doc_id}: sha256 mismatch vs MANIFEST.csv "
                f"(recorded {recorded[:16]}..., actual {actual[:16]}...). "
                "Re-run fetch, or the corpus has drifted from its provenance record."
            )

        if src["parser"] == "fhir_html":
            sections = _parse_fhir_html(raw)
        elif src["parser"] == "ecfr_xml":
            sections = _parse_ecfr_xml(raw)
        else:
            sections = _parse_pdf(raw_path)

        lines = [f"# {doc_id} | {src['title']}", ""]
        for sec_id, heading, body in sections:
            lines.append(f"{SECTION_MARKER}{sec_id} | {heading}")
            lines.append(body)
            lines.append("")

        (out_dir / f"{doc_id}.txt").write_text("\n".join(lines), encoding="utf-8")
        manifest.setdefault(doc_id, {})["n_sections"] = str(len(sections))
        print(f"[process] {doc_id}: {len(sections):>3} sections -> {doc_id}.txt")

    _write_manifest(manifest_path, list(manifest.values()))


# --- chunk ----------------------------------------------------------------


def _read_processed(path: Path) -> list[tuple[str, str, str]]:
    sections = []
    sec_id = heading = None
    buf: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(SECTION_MARKER):
            if sec_id is not None:
                sections.append((sec_id, heading, "\n".join(buf).strip()))
            payload = line[len(SECTION_MARKER) :]
            sec_id, _, heading = payload.partition(" | ")
            buf = []
        elif sec_id is not None:
            buf.append(line)
    if sec_id is not None:
        sections.append((sec_id, heading, "\n".join(buf).strip()))
    return [s for s in sections if s[2]]


def _windows(tokens: list[int], size: int, overlap: int) -> Iterable[list[int]]:
    if len(tokens) <= size:
        yield tokens
        return
    step = max(1, size - overlap)
    for start in range(0, len(tokens), step):
        window = tokens[start : start + size]
        if not window:
            break
        yield window
        if start + size >= len(tokens):
            break


def chunk() -> None:
    cfg = load_pipeline()
    ck = cfg["chunking"]
    enc = tiktoken.get_encoding(ck["tokenizer"])
    proc_dir = resolve(cfg["paths"]["corpus_processed"])
    out_path = resolve(cfg["paths"]["chunks"])
    manifest_path = resolve(cfg["paths"]["manifest"])
    manifest = {r["doc_id"]: r for r in _read_manifest(manifest_path)}

    records: list[dict[str, Any]] = []
    per_doc: dict[str, int] = {}

    for src in SOURCES:
        doc_id = src["doc_id"]
        path = proc_dir / f"{doc_id}.txt"
        if not path.exists():
            raise FileNotFoundError(f"{path} missing — run `python -m src.ingest process` first")

        n = 0
        for sec_id, heading, body in _read_processed(path):
            tokens = enc.encode(body)
            windows = list(_windows(tokens, ck["target_tokens"], ck["overlap_tokens"]))
            for i, win in enumerate(windows, start=1):
                # Drop undersized fragments only when the section produced several
                # windows — a short section is real content (many CFR sections are
                # two sentences), whereas a short tail window is a split artifact.
                # Below the hard floor nothing is worth indexing either way: those
                # are stray headings and cross-reference stubs.
                if len(win) < HARD_MIN_TOKENS:
                    continue
                if len(win) < ck["min_chunk_tokens"] and len(windows) > 1:
                    continue
                n += 1
                records.append(
                    {
                        "chunk_id": f"{doc_id}#S{sec_id}#c{n:02d}",
                        "doc_id": doc_id,
                        "section": sec_id,
                        "heading": heading,
                        "text": enc.decode(win),
                        "token_count": len(win),
                    }
                )
        per_doc[doc_id] = n
        print(f"[chunk] {doc_id}: {n:>4} chunks")

    ensure_dir(out_path.parent)
    with out_path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    for doc_id, n in per_doc.items():
        manifest.setdefault(doc_id, {})["n_chunks"] = str(n)
    _write_manifest(manifest_path, list(manifest.values()))

    total_tokens = sum(r["token_count"] for r in records)
    print(
        f"\n[chunk] {len(records)} chunks, {total_tokens:,} tokens "
        f"(mean {total_tokens // max(1, len(records))}) -> {out_path}"
    )
    _verify_roundtrip(records)


def _verify_roundtrip(records: list[dict[str, Any]]) -> None:
    """chunk_id must be unique and must parse back to its three components.

    Traceability is the backbone of this project; a duplicated or malformed
    chunk_id would silently corrupt every citation the model produces.
    """
    ids = [r["chunk_id"] for r in records]
    dupes = {i for i in ids if ids.count(i) > 1} if len(set(ids)) != len(ids) else set()
    if dupes:
        raise ValueError(f"duplicate chunk_ids: {sorted(dupes)[:5]}")

    for rec in records:
        m = re.fullmatch(r"(D\d{2})#S(.+)#c(\d+)", rec["chunk_id"])
        if not m or m.group(1) != rec["doc_id"] or m.group(2) != rec["section"]:
            raise ValueError(f"chunk_id does not round-trip: {rec['chunk_id']}")

    print(f"[verify] {len(ids)} chunk_ids unique and round-tripping OK")


def load_chunks() -> list[dict[str, Any]]:
    """Shared loader used by index.py and the validation layer."""
    path = resolve(load_pipeline()["paths"]["chunks"])
    if not path.exists():
        raise FileNotFoundError(f"{path} missing — run `python -m src.ingest all` first")
    with path.open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description="Corpus ingestion")
    ap.add_argument("stage", choices=["fetch", "process", "chunk", "all"])
    args = ap.parse_args()

    if args.stage in ("fetch", "all"):
        fetch()
    if args.stage in ("process", "all"):
        process()
    if args.stage in ("chunk", "all"):
        chunk()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
