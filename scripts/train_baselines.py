from __future__ import annotations

import argparse
from pathlib import Path
import re

import numpy as np
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

try:
    from scipy import sparse
except Exception as exc:
    raise SystemExit(
        "Missing dependency: scipy. Install with:\n"
        "  pip install scipy\n"
        f"Original error: {exc}"
    )

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (
        average_precision_score,
        f1_score,
        precision_recall_curve,
        precision_score,
        recall_score,
        roc_auc_score,
        roc_curve,
    )
    from sklearn.model_selection import train_test_split
    from sklearn.svm import LinearSVC
except Exception as exc:
    raise SystemExit(
        "Missing dependency: scikit-learn. Install with:\n"
        "  pip install scikit-learn\n"
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


def read_lines(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() != ""]


def load_labels(labels_parquet: Path, labels_csv: Path) -> pd.DataFrame:
    if labels_parquet.exists():
        return pd.read_parquet(labels_parquet)
    ensure_exists(labels_csv, "labels_wide.csv (or labels_wide.parquet)")
    return pd.read_csv(labels_csv, dtype=str)


def resolve_adr_column(available_cols: list[str], adr_id: str, adr_term: str) -> str | None:
    adr_id_norm = slug(adr_id)
    term_norm = slug(adr_term)

    if adr_id in available_cols:
        return adr_id
    if adr_id_norm in available_cols:
        return adr_id_norm
    pref = sorted([c for c in available_cols if c.startswith(f"{adr_id_norm}__")])
    if pref:
        return pref[0]
    term_pref = sorted([c for c in available_cols if c.endswith(f"__{term_norm}")])
    if term_pref:
        return term_pref[0]
    return None


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


def choose_split(y: np.ndarray, test_size: float, max_retries: int = 50) -> tuple[np.ndarray, np.ndarray, int]:
    n = y.shape[0]
    adr_indices = list(range(y.shape[1]))
    modelable = [
        j for j in adr_indices if int(y[:, j].sum()) >= 2 and int(y[:, j].sum()) <= (n - 2)
    ]
    if not modelable:
        raise ValueError("No modelable ADR columns (need both positive and negative labels).")

    for i in range(max_retries):
        split_seed = SEED + i
        train_idx, test_idx = train_test_split(
            np.arange(n),
            test_size=test_size,
            random_state=split_seed,
            shuffle=True,
        )
        ok = True
        for j in modelable:
            if int(y[train_idx, j].sum()) < 1 or int(y[test_idx, j].sum()) < 1:
                ok = False
                break
        if ok:
            return train_idx, test_idx, split_seed
    raise RuntimeError(
        "Could not find a valid train/test split after 50 retries where each ADR has >=1 positive "
        "in both train and test."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Train Week4 sparse baselines.")
    parser.add_argument("--features_npz", default="data/processed/features_targets.npz")
    parser.add_argument(
        "--features_index", default="data/processed/features_targets_index.txt"
    )
    parser.add_argument(
        "--feature_names", default="data/processed/features_targets_feature_names.txt"
    )
    parser.add_argument("--labels_csv", default="data/processed/labels_wide.csv")
    parser.add_argument("--labels_parquet", default="data/processed/labels_wide.parquet")
    parser.add_argument("--adr_topk_csv", default="data/processed/adr_topk.csv")
    parser.add_argument("--dataset_meta_json", default="data/processed/dataset_meta.json")
    parser.add_argument("--out_results_csv", default="reports/results_baselines.csv")
    parser.add_argument("--out_summary_md", default="reports/results_summary.md")
    parser.add_argument("--out_case_studies_md", default="reports/case_studies.md")
    parser.add_argument("--figures_dir", default="reports/figures")
    parser.add_argument("--test_size", type=float, default=0.2)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    features_npz = (repo_root / args.features_npz).resolve()
    features_index = (repo_root / args.features_index).resolve()
    feature_names_path = (repo_root / args.feature_names).resolve()
    labels_csv = (repo_root / args.labels_csv).resolve()
    labels_parquet = (repo_root / args.labels_parquet).resolve()
    adr_topk_csv = (repo_root / args.adr_topk_csv).resolve()
    dataset_meta_json = (repo_root / args.dataset_meta_json).resolve()
    out_results_csv = (repo_root / args.out_results_csv).resolve()
    out_summary_md = (repo_root / args.out_summary_md).resolve()
    out_case_md = (repo_root / args.out_case_studies_md).resolve()
    figures_dir = (repo_root / args.figures_dir).resolve()

    for path, desc in [
        (features_npz, "features_targets.npz"),
        (features_index, "features_targets_index.txt"),
        (feature_names_path, "features_targets_feature_names.txt"),
        (adr_topk_csv, "adr_topk.csv"),
        (dataset_meta_json, "dataset_meta.json"),
    ]:
        ensure_exists(path, desc)
    out_results_csv.parent.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    X_all = sparse.load_npz(features_npz).tocsr()
    feat_ids = read_lines(features_index)
    feat_names = read_lines(feature_names_path)
    if X_all.shape[0] != len(feat_ids):
        raise ValueError("features row count does not match features_targets_index.txt.")
    if X_all.shape[1] != len(feat_names):
        raise ValueError("features col count does not match feature names file.")

    labels = load_labels(labels_parquet, labels_csv)
    if "drugcentral_id" not in labels.columns:
        raise ValueError("labels_wide missing required column: drugcentral_id")
    labels["drugcentral_id"] = labels["drugcentral_id"].map(normalize_text)
    labels = labels[labels["drugcentral_id"] != ""].copy()
    labels = labels.drop_duplicates(subset=["drugcentral_id"], keep="first")
    labels = labels.set_index("drugcentral_id")

    common_ids = [dc for dc in feat_ids if dc in labels.index]
    if not common_ids:
        raise ValueError("No intersection between features index and labels_wide drugcentral_id.")
    row_pos = {dc: i for i, dc in enumerate(feat_ids)}
    common_pos = np.array([row_pos[dc] for dc in common_ids], dtype=int)
    X = X_all[common_pos].tocsr()
    labels_sub = labels.loc[common_ids].copy()

    adr_topk = pd.read_csv(adr_topk_csv, dtype=str).fillna("")
    available_label_cols = list(labels_sub.columns)
    adr_specs: list[dict[str, str]] = []
    for _, row in adr_topk.iterrows():
        adr_id = normalize_text(row.get("adr_id", ""))
        adr_term = normalize_text(row.get("adr_term", ""))
        col = resolve_adr_column(available_label_cols, adr_id=adr_id, adr_term=adr_term)
        if col is None:
            continue
        adr_specs.append(
            {
                "adr_id": adr_id,
                "adr_term": adr_term,
                "adr_slug": slug(f"{adr_id}_{adr_term}"),
                "label_column": col,
            }
        )
    if not adr_specs:
        raise ValueError("No ADR columns from adr_topk were found in labels_wide.")

    y_cols = [spec["label_column"] for spec in adr_specs]
    y_df = labels_sub[y_cols].apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)
    y = y_df.values

    train_idx, test_idx, split_seed = choose_split(y, test_size=args.test_size, max_retries=50)
    X_train = X[train_idx]
    X_test = X[test_idx]
    y_train_all = y[train_idx, :]
    y_test_all = y[test_idx, :]
    test_ids = [common_ids[i] for i in test_idx]

    all_results: list[dict[str, object]] = []
    logreg_test_scores: dict[str, np.ndarray] = {}

    for j, spec in enumerate(adr_specs):
        y_train = y_train_all[:, j]
        y_test = y_test_all[:, j]
        positives_overall = int(y[:, j].sum())
        positives_train = int(y_train.sum())
        positives_test = int(y_test.sum())

        if len(np.unique(y_train)) < 2 or len(np.unique(y_test)) < 2:
            for model_name in ["LogisticRegression", "LinearSVC"]:
                all_results.append(
                    {
                        "adr_id": spec["adr_id"],
                        "adr_term": spec["adr_term"],
                        "adr_slug": spec["adr_slug"],
                        "label_column": spec["label_column"],
                        "model": model_name,
                        "prevalence_overall": float(positives_overall / len(y)),
                        "prevalence_test": float(positives_test / len(y_test)),
                        "roc_auc": np.nan,
                        "pr_auc": np.nan,
                        "f1": np.nan,
                        "precision": np.nan,
                        "recall": np.nan,
                        "n_train": int(len(train_idx)),
                        "n_test": int(len(test_idx)),
                        "positives_train": positives_train,
                        "positives_test": positives_test,
                        "split_seed": split_seed,
                        "status": "skipped_single_class",
                    }
                )
            continue

        curve_payload: dict[str, dict[str, np.ndarray | float]] = {}

        lr = LogisticRegression(
            class_weight="balanced",
            solver="liblinear",
            max_iter=2000,
            random_state=SEED,
        )
        lr.fit(X_train, y_train)
        lr_scores = lr.predict_proba(X_test)[:, 1]
        lr_pred = (lr_scores >= 0.5).astype(int)

        lr_roc_auc = float(roc_auc_score(y_test, lr_scores))
        lr_pr_auc = float(average_precision_score(y_test, lr_scores))
        lr_f1 = float(f1_score(y_test, lr_pred, zero_division=0))
        lr_precision = float(precision_score(y_test, lr_pred, zero_division=0))
        lr_recall = float(recall_score(y_test, lr_pred, zero_division=0))
        lr_fpr, lr_tpr, _ = roc_curve(y_test, lr_scores)
        lr_pr_prec, lr_pr_rec, _ = precision_recall_curve(y_test, lr_scores)
        curve_payload["LogisticRegression"] = {
            "fpr": lr_fpr,
            "tpr": lr_tpr,
            "pr_precision": lr_pr_prec,
            "pr_recall": lr_pr_rec,
            "roc_auc": lr_roc_auc,
            "pr_auc": lr_pr_auc,
        }
        logreg_test_scores[spec["adr_slug"]] = lr_scores
        all_results.append(
            {
                "adr_id": spec["adr_id"],
                "adr_term": spec["adr_term"],
                "adr_slug": spec["adr_slug"],
                "label_column": spec["label_column"],
                "model": "LogisticRegression",
                "prevalence_overall": float(positives_overall / len(y)),
                "prevalence_test": float(positives_test / len(y_test)),
                "roc_auc": lr_roc_auc,
                "pr_auc": lr_pr_auc,
                "f1": lr_f1,
                "precision": lr_precision,
                "recall": lr_recall,
                "n_train": int(len(train_idx)),
                "n_test": int(len(test_idx)),
                "positives_train": positives_train,
                "positives_test": positives_test,
                "split_seed": split_seed,
                "status": "ok",
            }
        )

        svc = LinearSVC(class_weight="balanced", random_state=SEED)
        svc.fit(X_train, y_train)
        svc_scores = svc.decision_function(X_test)
        svc_pred = (svc_scores >= 0.0).astype(int)

        svc_roc_auc = float(roc_auc_score(y_test, svc_scores))
        svc_pr_auc = float(average_precision_score(y_test, svc_scores))
        svc_f1 = float(f1_score(y_test, svc_pred, zero_division=0))
        svc_precision = float(precision_score(y_test, svc_pred, zero_division=0))
        svc_recall = float(recall_score(y_test, svc_pred, zero_division=0))
        svc_fpr, svc_tpr, _ = roc_curve(y_test, svc_scores)
        svc_pr_prec, svc_pr_rec, _ = precision_recall_curve(y_test, svc_scores)
        curve_payload["LinearSVC"] = {
            "fpr": svc_fpr,
            "tpr": svc_tpr,
            "pr_precision": svc_pr_prec,
            "pr_recall": svc_pr_rec,
            "roc_auc": svc_roc_auc,
            "pr_auc": svc_pr_auc,
        }
        all_results.append(
            {
                "adr_id": spec["adr_id"],
                "adr_term": spec["adr_term"],
                "adr_slug": spec["adr_slug"],
                "label_column": spec["label_column"],
                "model": "LinearSVC",
                "prevalence_overall": float(positives_overall / len(y)),
                "prevalence_test": float(positives_test / len(y_test)),
                "roc_auc": svc_roc_auc,
                "pr_auc": svc_pr_auc,
                "f1": svc_f1,
                "precision": svc_precision,
                "recall": svc_recall,
                "n_train": int(len(train_idx)),
                "n_test": int(len(test_idx)),
                "positives_train": positives_train,
                "positives_test": positives_test,
                "split_seed": split_seed,
                "status": "ok",
            }
        )

        roc_pr_path = figures_dir / f"roc_pr_{spec['adr_slug']}.png"
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        for model_name, payload in curve_payload.items():
            axes[0].plot(
                payload["fpr"],
                payload["tpr"],
                label=f"{model_name} (AUC={payload['roc_auc']:.3f})",
                linewidth=1.8,
            )
            axes[1].plot(
                payload["pr_recall"],
                payload["pr_precision"],
                label=f"{model_name} (AP={payload['pr_auc']:.3f})",
                linewidth=1.8,
            )
        axes[0].plot([0, 1], [0, 1], linestyle="--", color="gray", linewidth=1)
        axes[0].set_title(f"ROC - {spec['adr_term']}")
        axes[0].set_xlabel("False Positive Rate")
        axes[0].set_ylabel("True Positive Rate")
        axes[0].legend(loc="lower right", fontsize=8)
        axes[0].grid(alpha=0.25)

        axes[1].set_title(f"Precision-Recall - {spec['adr_term']}")
        axes[1].set_xlabel("Recall")
        axes[1].set_ylabel("Precision")
        axes[1].legend(loc="lower left", fontsize=8)
        axes[1].grid(alpha=0.25)

        fig.tight_layout()
        fig.savefig(roc_pr_path, dpi=300)
        plt.close(fig)

        coef = lr.coef_[0]
        top_pos_idx = np.argsort(coef)[-15:][::-1]
        top_neg_idx = np.argsort(coef)[:15]
        pos_names = [feat_names[idx] for idx in top_pos_idx]
        neg_names = [feat_names[idx] for idx in top_neg_idx]
        pos_vals = coef[top_pos_idx]
        neg_vals = coef[top_neg_idx]

        tf_path = figures_dir / f"top_features_{spec['adr_slug']}.png"
        fig2, axes2 = plt.subplots(1, 2, figsize=(14, 8))
        axes2[0].barh(range(len(neg_names)), neg_vals, color="#dc2626")
        axes2[0].set_yticks(range(len(neg_names)))
        axes2[0].set_yticklabels(neg_names, fontsize=8)
        axes2[0].invert_yaxis()
        axes2[0].set_title(f"Top Negative Coefs - {spec['adr_term']}")
        axes2[0].set_xlabel("Coefficient")
        axes2[0].grid(axis="x", alpha=0.25)

        axes2[1].barh(range(len(pos_names)), pos_vals, color="#2563eb")
        axes2[1].set_yticks(range(len(pos_names)))
        axes2[1].set_yticklabels(pos_names, fontsize=8)
        axes2[1].invert_yaxis()
        axes2[1].set_title(f"Top Positive Coefs - {spec['adr_term']}")
        axes2[1].set_xlabel("Coefficient")
        axes2[1].grid(axis="x", alpha=0.25)

        fig2.tight_layout()
        fig2.savefig(tf_path, dpi=300)
        plt.close(fig2)

    results = pd.DataFrame(all_results)
    results = results.sort_values(
        ["adr_id", "model"], kind="mergesort"
    ).reset_index(drop=True)
    results.to_csv(out_results_csv, index=False)

    ok_results = results[results["status"] == "ok"].copy()
    summary_rows = (
        ok_results.groupby("model", as_index=False)[["roc_auc", "pr_auc", "f1", "precision", "recall"]]
        .mean(numeric_only=True)
        .round(4)
        .sort_values("model", kind="mergesort")
    )
    best_rows = (
        ok_results.sort_values(["adr_id", "pr_auc"], ascending=[True, False], kind="mergesort")
        .drop_duplicates(subset=["adr_id"], keep="first")
        [["adr_id", "adr_term", "model", "pr_auc", "roc_auc", "f1"]]
        .reset_index(drop=True)
    )
    summary_lines = [
        "# Week4 Baseline Results Summary",
        "",
        f"- Seed: {SEED}",
        f"- Split seed used: {split_seed}",
        f"- Samples (intersection): {len(common_ids)}",
        f"- Train/Test sizes: {len(train_idx)}/{len(test_idx)}",
        f"- ADRs evaluated: {len(adr_specs)}",
        "",
        "## Mean Metrics by Model",
        "",
        markdown_table(summary_rows),
        "",
        "## Best Model Per ADR (by PR-AUC)",
        "",
        markdown_table(best_rows.round(4)),
        "",
        f"- Full results CSV: {out_results_csv.relative_to(repo_root).as_posix()}",
    ]
    out_summary_md.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    if not logreg_test_scores:
        case_lines = [
            "# Week4 Case Studies",
            "",
            "No case studies generated (no successful LogisticRegression ADR models).",
        ]
        out_case_md.write_text("\n".join(case_lines) + "\n", encoding="utf-8")
    else:
        prob_df = pd.DataFrame(logreg_test_scores, index=test_ids).sort_index()
        mean_probs = prob_df.mean(axis=1)
        sorted_ids = mean_probs.sort_values(kind="mergesort").index.tolist()

        chosen_ids = []
        if sorted_ids:
            chosen_ids.append(sorted_ids[-1])  # highest
        if len(sorted_ids) >= 2:
            chosen_ids.append(sorted_ids[len(sorted_ids) // 2])  # median-ish
        if len(sorted_ids) >= 3:
            chosen_ids.append(sorted_ids[0])  # lowest
        chosen_ids = list(dict.fromkeys(chosen_ids))

        bucket_map = {}
        if chosen_ids:
            bucket_map[chosen_ids[0]] = "A_high_risk"
        if len(chosen_ids) > 1:
            bucket_map[chosen_ids[1]] = "B_mid_risk"
        if len(chosen_ids) > 2:
            bucket_map[chosen_ids[2]] = "C_low_risk"

        case_df = prob_df.loc[chosen_ids].copy()
        case_df.insert(0, "mean_pred_prob", mean_probs.loc[chosen_ids].round(4))
        case_df.insert(0, "risk_bucket", [bucket_map[c] for c in chosen_ids])
        case_df.insert(0, "drugcentral_id", chosen_ids)
        case_df = case_df.reset_index(drop=True).round(4)

        case_lines = [
            "# Week4 Case Studies",
            "",
            "Selected test-set drugs from Logistic Regression predictions:",
            "- Drug A: highest mean predicted probability across ADRs",
            "- Drug B: median mean predicted probability",
            "- Drug C: lowest mean predicted probability",
            "",
            markdown_table(case_df),
        ]
        out_case_md.write_text("\n".join(case_lines) + "\n", encoding="utf-8")

    print(f"[OK] Wrote {out_results_csv.as_posix()}")
    print(f"[OK] Wrote {out_summary_md.as_posix()}")
    print(f"[OK] Wrote {out_case_md.as_posix()}")
    print(
        f"[SUMMARY] rows={len(results)} adrs={len(adr_specs)} "
        f"train={len(train_idx)} test={len(test_idx)} seed={SEED}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
