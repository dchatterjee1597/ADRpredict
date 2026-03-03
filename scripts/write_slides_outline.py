from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def ensure_exists(path: Path, description: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing required {description}: {path}")


def rel(repo_root: Path, path: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description="Write Week4 slides outline scaffold.")
    parser.add_argument("--results_csv", default="reports/results_baselines.csv")
    parser.add_argument("--summary_md", default="reports/results_summary.md")
    parser.add_argument("--case_studies_md", default="reports/case_studies.md")
    parser.add_argument("--dataset_meta_json", default="data/processed/dataset_meta.json")
    parser.add_argument("--figures_dir", default="reports/figures")
    parser.add_argument("--results_best_csv", default="reports/results_best_per_adr.csv")
    parser.add_argument("--results_pack_md", default="reports/results_pack.md")
    parser.add_argument("--out_md", default="reports/slides_outline.md")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    results_csv = (repo_root / args.results_csv).resolve()
    summary_md = (repo_root / args.summary_md).resolve()
    case_studies_md = (repo_root / args.case_studies_md).resolve()
    dataset_meta_json = (repo_root / args.dataset_meta_json).resolve()
    figures_dir = (repo_root / args.figures_dir).resolve()
    results_best_csv = (repo_root / args.results_best_csv).resolve()
    results_pack_md = (repo_root / args.results_pack_md).resolve()
    out_md = (repo_root / args.out_md).resolve()

    for path, desc in [
        (results_csv, "baseline results CSV"),
        (summary_md, "results summary markdown"),
        (case_studies_md, "case studies markdown"),
        (dataset_meta_json, "dataset_meta.json"),
        (figures_dir, "figures directory"),
    ]:
        ensure_exists(path, desc)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    results = pd.read_csv(results_csv)
    adr_slugs = (
        results["adr_slug"].dropna().astype(str).drop_duplicates().tolist()
        if "adr_slug" in results.columns
        else []
    )

    roc_paths = [figures_dir / f"roc_pr_{slug}.png" for slug in adr_slugs]
    top_feat_paths = [figures_dir / f"top_features_{slug}.png" for slug in adr_slugs]
    roc_paths = [p for p in roc_paths if p.exists()]
    top_feat_paths = [p for p in top_feat_paths if p.exists()]

    lines = [
        "# Week4 Slides Outline",
        "",
        "- Slide 1: Objective and Dataset Scope",
        "  - Goal: Week4 minimal baselines with sparse target features.",
        f"  - Data sources: `{rel(repo_root, dataset_meta_json)}` and Week3 labels.",
        "",
        "- Slide 2: Feature Construction (Targets-Based)",
        "  - Sparse binary features from DrugCentral TARGET_NAME tokens.",
        "  - Mention matrix shape, nnz, and coverage from dataset_meta.",
        f"  - Reference: `{rel(repo_root, dataset_meta_json)}`.",
        "",
        "- Slide 3: Baseline Models and Evaluation Protocol",
        "  - Models: LogisticRegression (liblinear) and LinearSVC, balanced class weights.",
        "  - Single drug-level split with retry logic for ADR-positive coverage.",
        f"  - Metric table reference: `{rel(repo_root, results_csv)}`.",
        "",
        "- Slide 4: Aggregate Performance",
        "  - Compare mean ROC-AUC / PR-AUC / F1 across models.",
        f"  - Reference: `{rel(repo_root, summary_md)}`.",
        "",
        "- Slide 5: ADR-wise ROC/PR Curves",
        "  - Show per-ADR two-panel ROC+PR figures.",
    ]
    for p in roc_paths:
        lines.append(f"  - Figure: `{rel(repo_root, p)}`")

    lines += [
        "",
        "- Slide 6: Logistic Regression Top Features",
        "  - Highlight top positive and negative target coefficients per ADR.",
    ]
    for p in top_feat_paths:
        lines.append(f"  - Figure: `{rel(repo_root, p)}`")

    lines += [
        "",
        "- Slide 7: Case Studies (Test Set)",
        "  - Drug A/B/C risk examples from mean predicted ADR probabilities.",
        f"  - Reference: `{rel(repo_root, case_studies_md)}`.",
        "",
        "- Slide 8: Interpreting PR-AUC under High Prevalence",
        "  - Emphasize PR baseline ~ prevalence and show delta over baseline.",
        f"  - Figure: `{rel(repo_root, figures_dir / 'pr_auc_vs_prevalence.png')}`.",
        f"  - Reference: `{rel(repo_root, results_pack_md)}`.",
        "",
        "- Slide 9: Best Baseline Performance by ADR",
        "  - Show best model per ADR using PR-AUC delta + ROC-AUC.",
        f"  - Figure: `{rel(repo_root, figures_dir / 'delta_pr_auc_bar.png')}`.",
        f"  - Figure: `{rel(repo_root, figures_dir / 'roc_auc_bar.png')}`.",
        f"  - Table: `{rel(repo_root, results_best_csv)}`.",
        "",
        "- Slide 10: Limitations and Next Steps",
        "  - Sparse targets-only features are interpretable but incomplete.",
        "  - Add structure features and calibration in Week5.",
    ]

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] Wrote {out_md.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
