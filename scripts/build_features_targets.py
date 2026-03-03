from __future__ import annotations

import argparse
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

try:
    from sklearn.feature_extraction.text import CountVectorizer
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


def normalize_target_token(value: object) -> str:
    text = normalize_text(value).lower()
    if text == "":
        return ""
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def detect_id_column(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    preferred = [c for c in cols if "drugcentral" in c.lower() and "id" in c.lower()]
    if preferred:
        return preferred[0]
    struct = [c for c in cols if "struct" in c.lower() and "id" in c.lower()]
    if struct:
        return struct[0]
    exact = [c for c in cols if c.lower() == "id"]
    if exact:
        return exact[0]
    return cols[0]


def detect_target_column(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    exact = [c for c in cols if c.lower() == "target_name"]
    if exact:
        return exact[0]
    both = [c for c in cols if "target" in c.lower() and "name" in c.lower()]
    if both:
        return both[0]
    loose = [c for c in cols if "target" in c.lower()]
    if loose:
        return loose[0]
    raise ValueError("Could not detect TARGET_NAME column in DrugCentral targets table.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build sparse target-based features.")
    parser.add_argument(
        "--targets_tsv",
        default="data/interim/drugcentral/drugcentral_targets.tsv",
    )
    parser.add_argument(
        "--out_npz",
        default="data/processed/features_targets.npz",
    )
    parser.add_argument(
        "--out_feature_names",
        default="data/processed/features_targets_feature_names.txt",
    )
    parser.add_argument(
        "--out_index",
        default="data/processed/features_targets_index.txt",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    targets_path = (repo_root / args.targets_tsv).resolve()
    out_npz = (repo_root / args.out_npz).resolve()
    out_feature_names = (repo_root / args.out_feature_names).resolve()
    out_index = (repo_root / args.out_index).resolve()

    ensure_exists(targets_path, "DrugCentral targets table")
    out_npz.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(targets_path, sep="\t", dtype=str)
    if df.empty:
        raise ValueError(f"Targets table is empty: {targets_path}")

    id_col = detect_id_column(df)
    target_col = detect_target_column(df)

    work = df[[id_col, target_col]].copy()
    work["drugcentral_id"] = work[id_col].map(normalize_text)
    work["target_token"] = work[target_col].map(normalize_target_token)
    work = work[(work["drugcentral_id"] != "") & (work["target_token"] != "")]
    if work.empty:
        raise ValueError("No valid (drugcentral_id, TARGET_NAME) rows found after cleaning.")

    grouped = (
        work.groupby("drugcentral_id", as_index=False)["target_token"]
        .agg(lambda vals: " ".join(sorted(set(vals))))
        .rename(columns={"target_token": "doc"})
        .sort_values("drugcentral_id", kind="mergesort")
        .reset_index(drop=True)
    )

    vectorizer = CountVectorizer(
        binary=True,
        tokenizer=str.split,
        preprocessor=None,
        token_pattern=None,
        lowercase=False,
    )
    X = vectorizer.fit_transform(grouped["doc"].tolist())
    X = sparse.csr_matrix(X)

    sparse.save_npz(out_npz, X)
    feature_names = vectorizer.get_feature_names_out().tolist()
    out_feature_names.write_text("\n".join(feature_names) + "\n", encoding="utf-8")
    out_index.write_text("\n".join(grouped["drugcentral_id"].tolist()) + "\n", encoding="utf-8")

    print(f"[OK] Wrote {out_npz.as_posix()}")
    print(f"[OK] Wrote {out_feature_names.as_posix()}")
    print(f"[OK] Wrote {out_index.as_posix()}")
    print(
        f"[SUMMARY] rows={X.shape[0]} cols={X.shape[1]} "
        f"nnz={int(X.nnz)} seed={SEED}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
