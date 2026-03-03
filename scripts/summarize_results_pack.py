from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

SEED = 1337

try:
    import matplotlib.pyplot as plt
except Exception as exc:
    raise SystemExit(
        "Missing dependency: matplotlib. Install with:\n"
        "  pip install matplotlib\n"
        f"Original error: {exc}"
    )


def ensure_exists(path: Path, description: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing required {description}: {path}")


def normalize_text(value: object) -> str:
    text = "" if value is None else str(value).strip()
    return "" if text.lower() in {"", "nan", "none"} else text


def slug(text: str) -> str:
    clean = re.sub(r"[^\w\s-]", "", normalize_text(text).lower())
    clean = re.sub(r"[-\s]+", "_", clean).strip("_")
    return clean[:60] if clean else "adr"


def markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._"
    cols = list(df.columns)
    lines = [
        "|" + "|".join(cols) + "|",
        "|" + "|".join(["---"] * len(cols)) + "|",
    ]
    for _, row in df.iterrows():
        lines.append("|" + "|".join(str(row[c]) for c in cols) + "|")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Week4 results pack summaries and figures.")
    parser.add_argument("--results_csv", default="reports/results_baselines.csv")
    parser.add_argument("--dataset_meta_json", default="data/processed/dataset_meta.json")
    parser.add_argument("--out_best_csv", default="reports/results_best_per_adr.csv")
    parser.add_argument("--out_md", default="reports/results_pack.md")
    parser.add_argument("--figures_dir", default="reports/figures")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    results_csv = (repo_root / args.results_csv).resolve()
    meta_json = (repo_root / args.dataset_meta_json).resolve()
    out_best_csv = (repo_root / args.out_best_csv).resolve()
    out_md = (repo_root / args.out_md).resolve()
    figures_dir = (repo_root / args.figures_dir).resolve()

    ensure_exists(results_csv, "results_baselines.csv")
    ensure_exists(meta_json, "dataset_meta.json")
    out_best_csv.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(results_csv)
    if df.empty:
        raise ValueError(f"Empty results file: {results_csv}")

    required = ["adr_id", "adr_term", "model", "prevalence_test", "roc_auc", "pr_auc", "f1", "precision", "recall"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"results_baselines missing required columns: {missing}")

    if "status" in df.columns:
        df = df[df["status"] == "ok"].copy()
    for c in ["prevalence_test", "roc_auc", "pr_auc", "f1", "precision", "recall"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["prevalence_test", "roc_auc", "pr_auc"]).copy()
    if df.empty:
        raise ValueError("No valid result rows after filtering for numeric metrics.")

    if "adr_slug" not in df.columns:
        df["adr_slug"] = df.apply(
            lambda r: slug(f"{normalize_text(r['adr_id'])}_{normalize_text(r['adr_term'])}"),
            axis=1,
        )
    else:
        df["adr_slug"] = df["adr_slug"].map(normalize_text)
        blank = df["adr_slug"] == ""
        df.loc[blank, "adr_slug"] = df.loc[blank].apply(
            lambda r: slug(f"{normalize_text(r['adr_id'])}_{normalize_text(r['adr_term'])}"),
            axis=1,
        )

    df["pr_auc_delta"] = df["pr_auc"] - df["prevalence_test"]

    best = (
        df.sort_values(
            ["adr_id", "pr_auc_delta", "roc_auc", "model"],
            ascending=[True, False, False, True],
            kind="mergesort",
        )
        .drop_duplicates(subset=["adr_id"], keep="first")
        .sort_values(["adr_id"], kind="mergesort")
        .reset_index(drop=True)
    )

    best_out = best[
        ["adr_id", "adr_term", "model", "prevalence_test", "roc_auc", "pr_auc", "pr_auc_delta", "f1", "precision", "recall"]
    ].copy()
    best_out.to_csv(out_best_csv, index=False)

    # Figure 1: PR-AUC vs prevalence (best model per ADR)
    fig1_path = figures_dir / "pr_auc_vs_prevalence.png"
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(best["prevalence_test"], best["pr_auc"], color="#2563eb", alpha=0.9)
    for _, row in best.iterrows():
        ax.annotate(
            row["adr_slug"],
            (row["prevalence_test"], row["pr_auc"]),
            textcoords="offset points",
            xytext=(4, 4),
            fontsize=7,
        )
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", linewidth=1.2, label="PR baseline y=x")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Prevalence (test)")
    ax.set_ylabel("PR-AUC")
    ax.set_title("PR-AUC vs Prevalence (Best Model per ADR)")
    ax.grid(alpha=0.25)
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(fig1_path, dpi=300)
    plt.close(fig)

    # Figure 2: PR-AUC delta bar
    fig2_path = figures_dir / "delta_pr_auc_bar.png"
    best_delta = best.sort_values(
        ["pr_auc_delta", "adr_slug"], ascending=[False, True], kind="mergesort"
    ).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = ["#16a34a" if v >= 0 else "#dc2626" for v in best_delta["pr_auc_delta"]]
    ax.bar(best_delta["adr_slug"], best_delta["pr_auc_delta"], color=colors)
    ax.axhline(0.0, color="black", linewidth=1)
    ax.set_ylabel("PR-AUC delta (PR-AUC - prevalence_test)")
    ax.set_title("Lift Over Prevalence Baseline by ADR")
    ax.tick_params(axis="x", rotation=55)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(fig2_path, dpi=300)
    plt.close(fig)

    # Figure 3: ROC-AUC bar
    fig3_path = figures_dir / "roc_auc_bar.png"
    best_roc = best.sort_values(
        ["roc_auc", "adr_slug"], ascending=[False, True], kind="mergesort"
    ).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(best_roc["adr_slug"], best_roc["roc_auc"], color="#0891b2")
    ax.set_ylim(0, 1)
    ax.set_ylabel("ROC-AUC")
    ax.set_title("Best ROC-AUC by ADR")
    ax.tick_params(axis="x", rotation=55)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(fig3_path, dpi=300)
    plt.close(fig)

    with meta_json.open("r", encoding="utf-8") as f:
        meta = json.load(f)
    inter = meta.get("intersection", {})
    n_inter = inter.get("n_intersection", "NA")
    cov_feat = inter.get("coverage_vs_features", "NA")
    cov_lbl = inter.get("coverage_vs_labels", "NA")

    mean_roc = (
        df.groupby("model", as_index=False)["roc_auc"]
        .mean()
        .sort_values(["roc_auc", "model"], ascending=[False, True], kind="mergesort")
        .reset_index(drop=True)
    )
    top_delta = best_delta.head(3)[["adr_id", "adr_term", "pr_auc_delta", "model"]].copy()
    top_roc = best_roc.head(3)[["adr_id", "adr_term", "roc_auc", "model"]].copy()
    for col in ["pr_auc_delta", "roc_auc"]:
        if col in top_delta.columns:
            top_delta[col] = top_delta[col].round(4)
        if col in top_roc.columns:
            top_roc[col] = top_roc[col].round(4)

    md_lines = [
        "# Results Pack",
        "",
        "- PR-AUC baseline is approximately class prevalence; use `pr_auc_delta = pr_auc - prevalence_test` for defensible lift over baseline.",
        "- High prevalence can make raw PR-AUC look strong even with limited incremental signal.",
        "- Mean ROC-AUC by model:",
    ]
    for _, row in mean_roc.iterrows():
        md_lines.append(f"  - {row['model']}: {float(row['roc_auc']):.4f}")

    md_lines += [
        "- Top 3 ADRs by PR-AUC delta:",
        markdown_table(top_delta),
        "- Top 3 ADRs by ROC-AUC:",
        markdown_table(top_roc),
        "- Coverage caveat: modeling set intersection size is "
        f"{n_inter} (coverage_vs_features={cov_feat}, coverage_vs_labels={cov_lbl}).",
        "- Week3 ID mapping coverage and label construction choices can propagate noise into Week4 baselines.",
        "- ADR labels are weak supervision from SIDER and may include indication/reporting biases.",
    ]
    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"[OK] Wrote {out_best_csv.as_posix()}")
    print(f"[OK] Wrote {out_md.as_posix()}")
    print(f"[OK] Wrote {fig1_path.as_posix()}")
    print(f"[OK] Wrote {fig2_path.as_posix()}")
    print(f"[OK] Wrote {fig3_path.as_posix()}")
    print(
        f"[SUMMARY] adrs={len(best)} models={sorted(df['model'].unique().tolist())} seed={SEED}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
