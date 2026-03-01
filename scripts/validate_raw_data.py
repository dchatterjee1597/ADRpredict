from __future__ import annotations

import argparse
import gzip
from pathlib import Path
from typing import Optional

import pandas as pd


def find_first(sider_dir: Path, candidates: list[str]) -> Optional[Path]:
    for name in candidates:
        p = sider_dir / name
        if p.exists():
            return p
    # fallback: any file that starts with meddra_all_se.tsv
    hits = sorted([p for p in sider_dir.iterdir() if p.is_file() and p.name.lower().startswith("meddra_all_se.tsv")])
    return hits[0] if hits else None


def read_sample(path: Path, nrows: int = 300) -> pd.DataFrame:
    name = path.name.lower()
    if name.endswith(".gz"):
        return pd.read_table(path, sep="\t", header=None, nrows=nrows, dtype=str, compression="gzip")
    return pd.read_table(path, sep="\t", header=None, nrows=nrows, dtype=str)


def validate_sider(sider_dir: Path, failures: list[str], warnings: list[str]) -> dict:
    summary = {"sider_dir": str(sider_dir), "sider_present": False}

    if not sider_dir.exists():
        failures.append(f"SIDER directory missing: {sider_dir}")
        return summary

    required_path = find_first(sider_dir, ["meddra_all_se.tsv.gz", "meddra_all_se.tsv"])
    if required_path is None:
        found = [p.name for p in sorted(sider_dir.iterdir()) if p.is_file()]
        failures.append("Missing required SIDER file: meddra_all_se.tsv.gz (or meddra_all_se.tsv)")
        warnings.append(f"Files found in data/raw/sider: {found}")
        return summary

    try:
        sample = read_sample(required_path, nrows=500)
        if sample.empty:
            failures.append(f"SIDER required file is empty/unreadable: {required_path}")
        if sample.shape[1] < 4:
            failures.append(f"SIDER required file has too few columns ({sample.shape[1]}): {required_path}")
    except Exception as e:
        failures.append(f"Failed reading SIDER required file {required_path}: {e}")
        return summary

    summary["sider_present"] = True
    summary["sider_required_file"] = required_path.name
    summary["sider_required_cols_sample"] = int(sample.shape[1])

    # Optional: label side effects
    label = sider_dir / "meddra_all_label_se.tsv.gz"
    if label.exists():
        try:
            lbl = read_sample(label, nrows=200)
            if lbl.empty or lbl.shape[1] < 4:
                warnings.append(f"SIDER optional label file looks odd: {label.name}")
            summary["sider_label_cols_sample"] = int(lbl.shape[1])
        except Exception as e:
            warnings.append(f"Could not read optional {label.name}: {e}")
    else:
        warnings.append("Optional SIDER file not found: meddra_all_label_se.tsv.gz")

    return summary


def validate_drugcentral(repo_root: Path, failures: list[str], warnings: list[str]) -> dict:
    raw_dir = (repo_root / "data/raw/drugcentral").resolve()
    if not raw_dir.exists():
        raw_fallback = (repo_root / "data/raw/drugbank").resolve()
        if raw_fallback.exists():
            warnings.append("data/raw/drugcentral not found; using fallback data/raw/drugbank")
            raw_dir = raw_fallback

    interim_dir = (repo_root / "data/interim/drugcentral").resolve()
    interim_dir.mkdir(parents=True, exist_ok=True)

    targets = interim_dir / "drugcentral_targets.tsv"
    structures = interim_dir / "drugcentral_structures.tsv"

    summary = {
        "drugcentral_raw_dir": str(raw_dir),
        "drugcentral_interim_dir": str(interim_dir),
    }

    if not targets.exists() and not structures.exists():
        failures.append(f"Missing DrugCentral interim outputs in {interim_dir} (run python scripts/import_drugbank.py)")
        return summary

    if targets.exists():
        try:
            df_t = pd.read_table(targets, dtype=str, nrows=200)
            if df_t.empty:
                failures.append(f"{targets.name} is empty")
        except Exception as e:
            failures.append(f"Failed reading {targets.name}: {e}")
    else:
        warnings.append("DrugCentral interim missing: drugcentral_targets.tsv")

    if structures.exists():
        try:
            df_s = pd.read_table(structures, dtype=str, nrows=200)
            if df_s.empty:
                failures.append(f"{structures.name} is empty")
            if not any("smiles" in c.lower() for c in df_s.columns):
                warnings.append("drugcentral_structures.tsv has no column containing 'smiles' (schema may vary).")
        except Exception as e:
            failures.append(f"Failed reading {structures.name}: {e}")
    else:
        warnings.append("DrugCentral interim missing: drugcentral_structures.tsv")

    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate Week-2 raw + interim datasets (fails loudly).")
    ap.add_argument("--raw_sider", default="data/raw/sider", help="SIDER raw directory")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    sider_dir = (repo_root / args.raw_sider).resolve()

    failures: list[str] = []
    warnings: list[str] = []

    sider_summary = validate_sider(sider_dir, failures, warnings)
    dc_summary = validate_drugcentral(repo_root, failures, warnings)

    print("Validation summary")
    print(f"- SIDER dir: {sider_summary.get('sider_dir')}")
    print(f"- DrugCentral interim dir: {dc_summary.get('drugcentral_interim_dir')}")
    print(f"- Warnings: {len(warnings)}")
    print(f"- Errors: {len(failures)}\n")

    if warnings:
        print("Warnings:")
        for w in warnings:
            print(f"- {w}")
        print()

    if failures:
        print("Errors:")
        for e in failures:
            print(f"- {e}")
        return 1

    print("[OK] All Week-2 validation checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())