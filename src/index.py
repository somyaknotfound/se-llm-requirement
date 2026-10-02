"""FAISS index over the corpus chunks.

    python -m src.index build
    python -m src.index sanity                 # 3 canned queries, manual inspection
    python -m src.index query "audit trail for controlled substances" -k 8

Embeddings are L2-normalised and the index is inner-product, which makes the
reported score a cosine similarity in [-1, 1] rather than an unbounded distance.
The ranking is identical to the flat-L2 index the build spec allows — normalising
makes L2 a monotone function of cosine — but an interpretable score matters here,
because retrieval quality has to be argued in the report rather than assumed.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from . import ensure_dir, load_pipeline, resolve
from .ingest import load_chunks

_MODEL_CACHE: dict[str, Any] = {}


def _embedder(model_name: str):
    """Load the sentence-transformer once per process — it is ~90 MB on disk."""
    if model_name not in _MODEL_CACHE:
        from sentence_transformers import SentenceTransformer

        # CPU on purpose: GPU kernels give slightly different floats than CPU ones, which
        # can reorder near-tied retrieval hits between machines, and on a T4 the CUDA
        # context would take VRAM that Ollama needs to keep both models fully resident.
        _MODEL_CACHE[model_name] = SentenceTransformer(model_name, device="cpu")
    return _MODEL_CACHE[model_name]


def build_query() -> str:
    """The retrieval query for the target functionality.

    The plain feature description under-retrieves badly: source documents speak in
    regulatory and interoperability vocabulary ('CSOS digital certificate',
    'AllergyIntolerance'), not feature vocabulary ('prescription screen'). The
    keyword expansion in pipeline.yaml is what bridges that gap, and it is config
    rather than code so the report can state exactly what was searched for.
    """
    target = load_pipeline()["target"]
    keywords = " ".join(target.get("keywords", []))
    return f"{target['name']}. {target['description'].strip()} {keywords}"


@dataclass
class Hit:
    chunk_id: str
    doc_id: str
    section: str
    heading: str
    text: str
    token_count: int
    score: float
    rank: int
    facet: str = "single"


class Retriever:
    def __init__(self, index, chunks: list[dict[str, Any]], model_name: str) -> None:
        self._index = index
        self._chunks = chunks
        self._model_name = model_name
        self._by_id = {c["chunk_id"]: c for c in chunks}

    def search(self, query: str, k: int, allowed_docs: set[str] | None = None) -> list[Hit]:
        """Top-k chunks for a query, optionally restricted to an allowlist of documents.

        The allowlist is how an agent is limited to authorised sources: a chunk from
        a document outside it is never returned, so it can never be shown or cited.
        At 148 vectors the whole index is scored and filtered afterwards.
        """
        model = _embedder(self._model_name)
        vec = model.encode([query], normalize_embeddings=True).astype("float32")
        depth = len(self._chunks) if allowed_docs else min(k, len(self._chunks))
        scores, idxs = self._index.search(vec, depth)

        hits: list[Hit] = []
        for i, s in zip(idxs[0], scores[0]):
            if i < 0:
                continue
            c = self._chunks[int(i)]
            if allowed_docs and c["doc_id"] not in allowed_docs:
                continue
            hits.append(
                Hit(
                    chunk_id=c["chunk_id"],
                    doc_id=c["doc_id"],
                    section=c["section"],
                    heading=c["heading"],
                    text=c["text"],
                    token_count=c["token_count"],
                    score=float(s),
                    rank=len(hits) + 1,
                )
            )
            if len(hits) >= k:
                break
        return hits

    def chunk(self, chunk_id: str) -> dict[str, Any] | None:
        return self._by_id.get(chunk_id)

    def section_chunks(self, doc_id: str, section: str) -> list[dict[str, Any]]:
        """Every chunk of one section of one document — a control's evidence pool."""
        return [c for c in self._chunks if c["doc_id"] == doc_id and c["section"] == section]

    @property
    def chunk_ids(self) -> set[str]:
        return {c["chunk_id"] for c in self._chunks}

    def __len__(self) -> int:
        return len(self._chunks)


def build() -> None:
    import faiss

    cfg = load_pipeline()
    r = cfg["retrieval"]
    index_dir = ensure_dir(resolve(cfg["paths"]["index_dir"]))

    chunks = load_chunks()
    texts = [
        # Prefix the heading so a chunk carries its own context into the vector.
        # Bare CFR paragraph text often omits the subject entirely ('(b) Audit
        # controls.' appears only in the heading), which strands the chunk.
        f"{c['heading']}\n{c['text']}"
        for c in chunks
    ]

    print(f"[index] embedding {len(texts)} chunks with {r['embedding_model']} ...")
    model = _embedder(r["embedding_model"])
    vecs = model.encode(
        texts,
        batch_size=32,
        normalize_embeddings=r.get("normalize_embeddings", True),
        show_progress_bar=True,
    ).astype("float32")

    dim = vecs.shape[1]
    index = faiss.IndexFlatIP(dim) if r["index_type"] != "flat_l2" else faiss.IndexFlatL2(dim)
    index.add(vecs)

    faiss.write_index(index, str(index_dir / "corpus.faiss"))
    with (index_dir / "chunks.json").open("w", encoding="utf-8") as fh:
        json.dump(chunks, fh, ensure_ascii=False)
    (index_dir / "meta.json").write_text(
        json.dumps(
            {
                "embedding_model": r["embedding_model"],
                "index_type": r["index_type"],
                "dim": dim,
                "n_chunks": len(chunks),
                "normalized": r.get("normalize_embeddings", True),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[index] {len(chunks)} vectors, dim={dim} -> {index_dir}")


def load() -> Retriever:
    import faiss

    cfg = load_pipeline()
    index_dir = resolve(cfg["paths"]["index_dir"])
    idx_path = index_dir / "corpus.faiss"
    if not idx_path.exists():
        raise FileNotFoundError(f"{idx_path} missing — run `python -m src.index build` first")

    index = faiss.read_index(str(idx_path))
    with (index_dir / "chunks.json").open("r", encoding="utf-8") as fh:
        chunks = json.load(fh)
    meta = json.loads((index_dir / "meta.json").read_text(encoding="utf-8"))

    if index.ntotal != len(chunks):
        raise ValueError(
            f"index/chunk mismatch: {index.ntotal} vectors vs {len(chunks)} chunks — rebuild"
        )
    return Retriever(index, chunks, meta["embedding_model"])


def retrieve_evidence(
    retriever: Retriever | None = None,
    facets: list[dict[str, str]] | None = None,
    allowed_docs: set[str] | None = None,
    top_k: int | None = None,
) -> list[Hit]:
    """Retrieve evidence for the target functionality using the configured strategy.

    Faceted mode interleaves each facet's results round-robin rather than sorting
    the union by score. Sorting by score would defeat the purpose: the highest
    scores cluster in whichever document is largest, which is exactly the
    imbalance the facets exist to correct. Round-robin guarantees every facet
    contributes its best hit before any facet contributes its second.

    A case study passes its own facets and its knowledge-source allowlist; the
    defaults are the pipeline's e-prescribing facets over the whole corpus.
    """
    cfg = load_pipeline()
    r = cfg["retrieval"]
    retriever = retriever or load()
    top_k = top_k or r["top_k"]

    if r.get("strategy", "single") == "single" and facets is None:
        return retriever.search(build_query(), top_k, allowed_docs)

    per_facet = r.get("per_facet", 3)
    facet_hits: list[list[Hit]] = []
    for facet in facets or r["facets"]:
        hits = retriever.search(" ".join(facet["query"].split()), per_facet, allowed_docs)
        for h in hits:
            h.facet = facet["id"]
        facet_hits.append(hits)

    merged: list[Hit] = []
    seen: set[str] = set()
    for depth in range(per_facet):
        for hits in facet_hits:
            if depth >= len(hits):
                continue
            h = hits[depth]
            if h.chunk_id in seen:
                continue
            seen.add(h.chunk_id)
            merged.append(h)
            if len(merged) >= top_k:
                break
        if len(merged) >= top_k:
            break

    for rank, h in enumerate(merged, start=1):
        h.rank = rank
    return merged


SANITY_QUERIES = [
    "two-factor authentication and identity proofing before signing a controlled substance prescription",
    "checking a patient's recorded allergies and drug interactions before ordering a medication",
    "audit log recording who accessed or changed a record and when",
]


def sanity() -> None:
    """Retrieval has to be inspected, not assumed.

    If these three queries do not surface D06 (EPCS), D02 (AllergyIntolerance) and
    D04/D05 (audit controls) respectively, the index is miscalibrated and every
    downstream traceability claim inherits the fault.
    """
    retr = load()
    print(f"[sanity] index holds {len(retr)} chunks\n")
    for q in SANITY_QUERIES:
        print(f"QUERY: {q}")
        for h in retr.search(q, 5):
            preview = h.text[:110].replace("\n", " ")
            print(f"  {h.rank}. {h.score:.3f}  {h.chunk_id:<34} {h.heading[:46]}")
            print(f"        {preview}...")
        print()


def main() -> int:
    ap = argparse.ArgumentParser(description="FAISS index over corpus chunks")
    ap.add_argument("cmd", choices=["build", "sanity", "query"])
    ap.add_argument("text", nargs="?", default=None)
    ap.add_argument("-k", type=int, default=None)
    args = ap.parse_args()

    if args.cmd == "build":
        build()
    elif args.cmd == "sanity":
        sanity()
    else:
        q = args.text or build_query()
        k = args.k or load_pipeline()["retrieval"]["top_k"]
        for h in load().search(q, k):
            print(f"{h.rank:>2}. {h.score:.3f}  {h.chunk_id:<34} {h.heading[:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
