"""Assemble figures and markdown tables for the writeup.

    python -m src.report

Every figure and table is generated from the CSVs in outputs/, never retyped.
Figures land in figures/ and tables in report/tables.md, which report.md includes.
Stages whose inputs are missing are skipped with a notice rather than failing, so
this can be run at any point during the build.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.colors import ListedColormap

from . import ensure_dir, load_pipeline, resolve

DOC_IDS = [f"D0{i}" for i in range(1, 7)]
PALETTE = {"rule": "#4C72B0", "llm": "#DD8452", "accent": "#55A868", "warn": "#C44E52"}


def _save(fig, path: Path) -> None:
    ensure_dir(path.parent)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[report] {path}")


def fig_corpus(cfg, fig_dir: Path) -> None:
    man_path = resolve(cfg["paths"]["manifest"])
    if not man_path.exists():
        return
    man = pd.read_csv(man_path)
    if "n_chunks" not in man or man["n_chunks"].isna().all():
        return
    fig, ax = plt.subplots(figsize=(8, 3.6))
    labels = [f"{r.doc_id}\n{str(r.doc_type)[:14]}" for r in man.itertuples()]
    ax.bar(labels, man["n_chunks"].fillna(0).astype(int), color=PALETTE["rule"])
    ax.set_ylabel("chunks")
    ax.set_title("Corpus composition by source document")
    ax.grid(axis="y", alpha=0.3)
    _save(fig, fig_dir / "corpus_composition.png")


def fig_traceability(out_dir: Path, fig_dir: Path) -> None:
    path = out_dir / "traceability_matrix.csv"
    if not path.exists():
        return
    tm = pd.read_csv(path).fillna("")
    docs = [c for c in tm.columns if c not in ("req_id", "type")]
    if not docs:
        return

    codes = {"": 0, "D": 1, "I": 2}
    mat = tm[docs].apply(lambda col: col.map(lambda v: codes.get(str(v).strip(), 0)))

    fig, ax = plt.subplots(figsize=(max(5, len(docs) * 1.1), max(4, len(tm) * 0.26)))
    cmap = ListedColormap(["#EEEEEE", PALETTE["accent"], PALETTE["llm"]])
    ax.imshow(mat.values, cmap=cmap, vmin=0, vmax=2, aspect="auto")

    ax.set_xticks(range(len(docs)), docs)
    ax.set_yticks(range(len(tm)), tm["req_id"], fontsize=7)
    ax.set_title("Traceability: requirements x source documents")
    for spine in ax.spines.values():
        spine.set_visible(False)
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=PALETTE["accent"], label="D — direct"),
        plt.Rectangle((0, 0), 1, 1, color=PALETTE["llm"], label="I — inferred"),
        plt.Rectangle((0, 0), 1, 1, color="#EEEEEE", label="no link"),
    ]
    ax.legend(handles=handles, bbox_to_anchor=(1.02, 1), loc="upper left", frameon=False)
    _save(fig, fig_dir / "traceability_matrix.png")

    coverage = (mat > 0).sum(axis=0)
    fig, ax = plt.subplots(figsize=(7, 3.4))
    colors = [PALETTE["warn"] if v == 0 else PALETTE["rule"] for v in coverage]
    ax.bar(docs, coverage.values, color=colors)
    ax.set_ylabel("requirements citing")
    ax.set_title("Per-document coverage (red = uncited source)")
    ax.grid(axis="y", alpha=0.3)
    _save(fig, fig_dir / "document_coverage.png")


def fig_validation(out_dir: Path, fig_dir: Path) -> None:
    path = out_dir / "validation_29148.csv"
    if not path.exists():
        return
    val = pd.read_csv(path)
    grouped = val.groupby("attribute").agg(
        rule=("rule_score", "mean"), llm=("llm_score", "mean")
    ).sort_values("rule")

    fig, ax = plt.subplots(figsize=(9, 4.2))
    x = range(len(grouped))
    width = 0.38
    ax.bar([i - width / 2 for i in x], grouped["rule"], width,
           label="rule-based", color=PALETTE["rule"])
    if grouped["llm"].notna().any():
        ax.bar([i + width / 2 for i in x], grouped["llm"].fillna(0), width,
               label="LLM critic", color=PALETTE["llm"])
    ax.set_xticks(list(x), grouped.index, rotation=30, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("pass rate")
    ax.set_title("ISO/IEC/IEEE 29148 pass rate by attribute")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.3)
    _save(fig, fig_dir / "validation_29148.png")

    scored = val[val["agreement"].isin(["agree", "disagree"])]
    if len(scored):
        agree = scored.assign(a=scored["agreement"].eq("agree")).groupby("attribute")["a"].mean()
        fig, ax = plt.subplots(figsize=(9, 3.6))
        ax.bar(agree.index, agree.values, color=PALETTE["accent"])
        ax.axhline(agree.mean(), ls="--", c="grey", label=f"overall {agree.mean():.0%}")
        ax.set_xticks(range(len(agree)), agree.index, rotation=30, ha="right")
        ax.set_ylim(0, 1.05)
        ax.set_ylabel("scorer agreement")
        ax.set_title("Rule-based vs LLM critic agreement")
        ax.legend(frameon=False)
        ax.grid(axis="y", alpha=0.3)
        _save(fig, fig_dir / "scorer_agreement.png")


def fig_sdlc(out_dir: Path, fig_dir: Path) -> None:
    runs_path = out_dir / "sdlc_runs.csv"
    if runs_path.exists():
        runs = pd.read_csv(runs_path).fillna("")
        ok = runs[runs["recommended_canonical"].ne("") & runs["recommended_canonical"].ne("unknown")]
        if len(ok):
            pivot = pd.crosstab(ok["framing"], ok["recommended_canonical"])
            fig, ax = plt.subplots(figsize=(8, 4))
            pivot.plot(kind="bar", stacked=True, ax=ax, colormap="tab20")
            ax.set_ylabel("runs")
            ax.set_xlabel("")
            ax.set_title("SDLC recommendation by prompt framing (framing sensitivity)")
            ax.legend(title="", bbox_to_anchor=(1.02, 1), loc="upper left", frameon=False)
            plt.setp(ax.get_xticklabels(), rotation=0)
            ax.grid(axis="y", alpha=0.3)
            _save(fig, fig_dir / "sdlc_by_framing.png")

    an_path = out_dir / "sdlc_analysis.csv"
    if an_path.exists():
        an = pd.read_csv(an_path)
        if len(an) and an["score"].notna().any():
            pivot = an.pivot_table(index="criterion", columns="framing", values="score", aggfunc="mean")
            fig, ax = plt.subplots(figsize=(7.5, 4.6))
            im = ax.imshow(pivot.values, cmap="RdYlGn_r", vmin=1, vmax=5, aspect="auto")
            ax.set_xticks(range(len(pivot.columns)), pivot.columns, rotation=15)
            ax.set_yticks(range(len(pivot.index)), pivot.index, fontsize=8)
            for i in range(pivot.shape[0]):
                for j in range(pivot.shape[1]):
                    v = pivot.values[i, j]
                    if pd.notna(v):
                        ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=8)
            ax.set_title("Mean criterion score (1-5) by framing")
            fig.colorbar(im, ax=ax, shrink=0.8)
            _save(fig, fig_dir / "sdlc_criteria.png")


def _md_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if max_rows and len(df) > max_rows:
        df = df.head(max_rows)
    header = "| " + " | ".join(str(c) for c in df.columns) + " |"
    sep = "|" + "|".join("---" for _ in df.columns) + "|"
    rows = [
        "| " + " | ".join(str(v).replace("|", "\\|").replace("\n", " ") for v in r) + " |"
        for r in df.itertuples(index=False)
    ]
    return "\n".join([header, sep, *rows])


def write_tables(cfg, out_dir: Path) -> None:
    parts: list[str] = ["# Generated tables", "", "_Regenerate with `python -m src.report`._", ""]

    man_path = resolve(cfg["paths"]["manifest"])
    if man_path.exists():
        man = pd.read_csv(man_path)
        cols = [c for c in ["doc_id", "title", "publisher", "year", "license", "doc_type", "n_chunks"] if c in man]
        parts += ["## Corpus manifest", "", _md_table(man[cols]), ""]

    for title, name, cols, limit in [
        ("Requirements", "requirements.csv",
         ["req_id", "type", "nfr_category", "statement", "priority", "risk_class", "volatility", "derived"], None),
        ("Per-requirement reasoning (sample)", "requirements_reasoning.csv",
         ["req_id", "inference_type", "reasoning"], 6),
        ("Metrics summary", "metrics_summary.csv", ["section", "metric", "value", "detail"], None),
        ("Hallucination audit", "hallucination_audit.csv",
         ["req_id", "cited_entity", "entity_type", "verdict", "severity"], None),
        ("SDLC runs", "sdlc_runs.csv",
         ["run_id", "model", "framing", "trial", "recommended_sdlc", "recommended_canonical"], None),
    ]:
        path = out_dir / name
        if not path.exists():
            continue
        df = pd.read_csv(path).fillna("")
        use = [c for c in cols if c in df.columns] or list(df.columns)
        parts += [f"## {title}", "", _md_table(df[use], limit), ""]

    val_path = out_dir / "validation_29148.csv"
    if val_path.exists():
        val = pd.read_csv(val_path)
        summary = val.groupby("attribute").agg(
            rule_pass=("rule_score", "mean"), llm_pass=("llm_score", "mean")
        ).round(2).reset_index()
        parts += ["## 29148 pass rate by attribute", "", _md_table(summary), ""]

        disagreements = val[val["agreement"] == "disagree"]
        if len(disagreements):
            parts += [
                "## Scorer disagreements (adjudication candidates)", "",
                _md_table(disagreements[["req_id", "attribute", "rule_score", "llm_score", "note"]], 12),
                "",
            ]

    report_dir = ensure_dir(resolve("report"))
    (report_dir / "tables.md").write_text("\n".join(parts), encoding="utf-8")
    print(f"[report] {report_dir / 'tables.md'}")


def main() -> int:
    cfg = load_pipeline()
    out_dir = resolve(cfg["paths"]["outputs"])
    fig_dir = ensure_dir(resolve(cfg["paths"]["figures"]))

    fig_corpus(cfg, fig_dir)
    fig_traceability(out_dir, fig_dir)
    fig_validation(out_dir, fig_dir)
    fig_sdlc(out_dir, fig_dir)
    write_tables(cfg, out_dir)

    produced = sorted(p.name for p in fig_dir.glob("*.png"))
    print(f"\n[report] {len(produced)} figure(s): {', '.join(produced) or 'none'}")
    if not produced:
        print("[report] (run the pipeline stages first — figures follow their CSVs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
