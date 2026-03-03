from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

SEED = 1337

try:
    from scipy import sparse
except Exception as exc:
    raise SystemExit(
        "Missing dependency: scipy. Install with:\n"
        "  pip install scipy\n"
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
    return clean


def read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() != ""]


def load_labels(labels_parquet: Path, labels_csv: Path) -> pd.DataFrame:
    if labels_parquet.exists():
        return pd.read_parquet(labels_parquet)
    ensure_exists(labels_csv, "labels_wide.csv (or parquet)")
    return pd.read_csv(labels_csv, dtype=str)


def resolve_adr_column(available_cols: list[str], adr_id: str, adr_term: str) -> str | None:
    adr_id_norm = slug(adr_id)
    term_norm = slug(adr_term)

    if adr_id in available_cols:
        return adr_id
    if adr_id_norm in available_cols:
        return adr_id_norm

    prefix_matches = sorted([c for c in available_cols if c.startswith(f"{adr_id_norm}__")])
    if prefix_matches:
        return prefix_matches[0]

    term_matches = sorted([c for c in available_cols if c.endswith(f"__{term_norm}")])
    if term_matches:
        return term_matches[0]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Build dataset metadata for Week 4.")
    parser.add_argument("--features_npz", default="data/processed/features_targets.npz")
    parser.add_argument(
        "--features_index", default="data/processed/features_targets_index.txt"
    )
    parser.add_argument("--labels_csv", default="data/processed/labels_wide.csv")
    parser.add_argument("--labels_parquet", default="data/processed/labels_wide.parquet")
    parser.add_argument("--adr_topk_csv", default="data/processed/adr_topk.csv")
    parser.add_argument("--out_json", default="data/processed/dataset_meta.json")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    features_npz = (repo_root / args.features_npz).resolve()
    features_index = (repo_root / args.features_index).resolve()
    labels_csv = (repo_root / args.labels_csv).resolve()
    labels_parquet = (repo_root / args.labels_parquet).resolve()
    adr_topk_csv = (repo_root / args.adr_topk_csv).resolve()
    out_json = (repo_root / args.out_json).resolve()

    ensure_exists(features_npz, "features_targets.npz")
    ensure_exists(features_index, "features_targets_index.txt")
    ensure_exists(adr_topk_csv, "adr_topk.csv")
    out_json.parent.mkdir(parents=True, exist_ok=True)

    X = sparse.load_npz(features_npz)
    feature_ids = read_lines(features_index)
    if X.shape[0] != len(feature_ids):
        raise ValueError(
            f"Row mismatch: features shape rows={X.shape[0]} but index lines={len(feature_ids)}"
        )

    labels = load_labels(labels_parquet, labels_csv)
    if "drugcentral_id" not in labels.columns:
        raise ValueError("labels_wide missing required 'drugcentral_id' column.")
    labels = labels.copy()
    labels["drugcentral_id"] = labels["drugcentral_id"].map(normalize_text)
    labels = labels[labels["drugcentral_id"] != ""]

    labels_ids = sorted(set(labels["drugcentral_id"].tolist()))
    features_ids = feature_ids
    features_id_set = set(features_ids)
    labels_id_set = set(labels_ids)
    intersection = sorted(features_id_set.intersection(labels_id_set))

    adr_topk = pd.read_csv(adr_topk_csv, dtype=str).fillna("")
    available_cols = [c for c in labels.columns if c != "drugcentral_id"]

    adr_entries = []
    label_lookup = labels.set_index("drugcentral_id")
    label_intersection = label_lookup.loc[intersection] if intersection else pd.DataFrame()

    for _, row in adr_topk.iterrows():
        adr_id = normalize_text(row.get("adr_id", ""))
        adr_term = normalize_text(row.get("adr_term", ""))
        col = resolve_adr_column(available_cols, adr_id=adr_id, adr_term=adr_term)
        positives_all = None
        positives_intersection = None
        if col is not None:
            s_all = pd.to_numeric(labels[col], errors="coerce").fillna(0).astype(int)
            positives_all = int((s_all > 0).sum())
            if not label_intersection.empty and col in label_intersection.columns:
                s_inter = pd.to_numeric(
                    label_intersection[col], errors="coerce"
                ).fillna(0).astype(int)
                positives_intersection = int((s_inter > 0).sum())
            else:
                positives_intersection = 0
        adr_entries.append(
            {
                "adr_id": adr_id,
                "adr_term": adr_term,
                "label_column": col,
                "positives_all": positives_all,
                "positives_intersection": positives_intersection,
            }
        )

    meta = {
        "seed": SEED,
        "features": {
            "n_rows": int(X.shape[0]),
            "n_cols": int(X.shape[1]),
            "nnz": int(X.nnz),
            "npz_path": features_npz.relative_to(repo_root).as_posix(),
            "index_path": features_index.relative_to(repo_root).as_posix(),
        },
        "labels": {
            "n_rows": int(len(labels)),
            "labels_path": (
                labels_parquet.relative_to(repo_root).as_posix()
                if labels_parquet.exists()
                else labels_csv.relative_to(repo_root).as_posix()
            ),
            "n_label_columns": int(len(available_cols)),
        },
        "intersection": {
            "n_intersection": int(len(intersection)),
            "features_only": int(len(features_id_set - labels_id_set)),
            "labels_only": int(len(labels_id_set - features_id_set)),
            "coverage_vs_features": (
                float(len(intersection) / len(features_ids)) if features_ids else 0.0
            ),
            "coverage_vs_labels": (
                float(len(intersection) / len(labels_ids)) if labels_ids else 0.0
            ),
        },
        "adrs": adr_entries,
    }

    out_json.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"[OK] Wrote {out_json.as_posix()}")
    print(
        f"[SUMMARY] features={X.shape} labels={len(labels)} "
        f"intersection={len(intersection)} seed={SEED}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
