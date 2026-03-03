from __future__ import annotations

import argparse
import gzip
import re
from pathlib import Path

import pandas as pd

SEED = 1337


def ensure_exists(path: Path, description: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing required {description}: {path}")


def list_sider_files(sider_dir: Path) -> list[Path]:
    return sorted([p for p in sider_dir.iterdir() if p.is_file()])


def select_side_effects_file(sider_dir: Path) -> Path:
    files = list_sider_files(sider_dir)
    def is_tsv_like(path: Path) -> bool:
        name = path.name.lower()
        return name.endswith(".tsv") or name.endswith(".tsv.gz")

    primary = [
        p
        for p in files
        if "meddra_all_se" in p.name.lower()
        and "label" not in p.name.lower()
        and is_tsv_like(p)
    ]
    if primary:
        return primary[0]

    secondary = [
        p
        for p in files
        if "meddra_all_label_se" in p.name.lower()
        and is_tsv_like(p)
    ]
    if secondary:
        return secondary[0]

    listed = ", ".join(p.name for p in files) if files else "<none>"
    raise FileNotFoundError(
        "No SIDER side-effects TSV found. Expected file containing "
        "'meddra_all_se' (without 'label') or fallback 'meddra_all_label_se'. "
        f"Files found: {listed}"
    )


def count_raw_rows(path: Path) -> int:
    if path.name.lower().endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    with path.open("r", encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def normalize_text(value: object) -> str:
    text = "" if value is None else str(value).strip()
    return "" if text.lower() in {"", "nan", "none"} else text


def has_header_row(first_row: list[str]) -> bool:
    joined = " ".join(str(v).strip().lower() for v in first_row if v is not None)
    hints = ["stitch", "meddra", "umls", "side effect", "term", "name", "cui"]
    return any(h in joined for h in hints)


def extract_pubchem_digits(value: object) -> str:
    text = normalize_text(value)
    if text == "":
        return ""
    text_no_space = re.sub(r"\s+", "", text)
    m = re.match(r"^CID(?:m|s)?(\d+)$", text_no_space, flags=re.IGNORECASE)
    if m:
        digits = m.group(1)
    elif re.fullmatch(r"\d+", text_no_space):
        digits = text_no_space
    else:
        return ""
    digits = digits.lstrip("0")
    return digits if digits != "" else "0"


def parse_side_effects(path: Path) -> pd.DataFrame:
    probe = pd.read_csv(path, sep="\t", header=None, dtype=str, nrows=1)
    first_row = probe.iloc[0].fillna("").tolist() if not probe.empty else []
    header = 0 if has_header_row(first_row) else None
    raw = pd.read_csv(path, sep="\t", header=header, dtype=str)
    if raw.empty:
        raise ValueError(f"SIDER file is empty: {path}")

    if header is None:
        n_cols = raw.shape[1]
        if n_cols >= 6:
            stitch_flat = raw.iloc[:, 0]
            stitch_stereo = raw.iloc[:, 1]
            adr_id = raw.iloc[:, 4]
            adr_term = raw.iloc[:, 5]
        elif n_cols == 4:
            stitch_flat = raw.iloc[:, 0]
            stitch_stereo = raw.iloc[:, 1]
            adr_id = raw.iloc[:, 2]
            adr_term = raw.iloc[:, 3]
        elif n_cols == 3:
            stitch_flat = raw.iloc[:, 0]
            stitch_stereo = raw.iloc[:, 0]
            adr_id = raw.iloc[:, 1]
            adr_term = raw.iloc[:, 2]
        else:
            stitch_flat = raw.iloc[:, 0]
            stitch_stereo = raw.iloc[:, 0]
            adr_id = raw.iloc[:, 1] if n_cols > 2 else ""
            adr_term = raw.iloc[:, -1]
    else:
        colmap = {str(c).lower(): c for c in raw.columns}

        def pick_column(*patterns: str) -> pd.Series | str:
            for pattern in patterns:
                for lc, original in colmap.items():
                    if pattern in lc:
                        return raw[original]
            return ""

        stitch_flat = pick_column("stitch_flat", "stitch flat")
        stitch_stereo = pick_column("stitch_stereo", "stitch stereo", "stitch")
        adr_id = pick_column("umls", "cui", "meddra")
        adr_term = pick_column("term", "side_effect_name", "side effect")

        if isinstance(stitch_flat, str):
            stitch_flat = raw.iloc[:, 0]
        if isinstance(stitch_stereo, str):
            stitch_stereo = raw.iloc[:, 1] if raw.shape[1] > 1 else raw.iloc[:, 0]
        if isinstance(adr_id, str):
            adr_id = raw.iloc[:, 2] if raw.shape[1] > 2 else ""
        if isinstance(adr_term, str):
            adr_term = raw.iloc[:, -1]

    out = pd.DataFrame(
        {
            "stitch_flat": pd.Series(stitch_flat).map(normalize_text),
            "stitch_stereo": pd.Series(stitch_stereo).map(normalize_text),
            "adr_id": pd.Series(adr_id).map(normalize_text),
            "adr_term": pd.Series(adr_term).map(normalize_text),
        }
    )
    out["stitch_flat"] = out["stitch_flat"].map(lambda x: re.sub(r"\s+", "", x))
    out["stitch_stereo"] = out["stitch_stereo"].map(lambda x: re.sub(r"\s+", "", x))
    out["adr_term"] = out["adr_term"].map(lambda x: re.sub(r"\s+", " ", x).strip())
    out = out[(out["stitch_flat"] != "") | (out["stitch_stereo"] != "")]
    out = out[out["adr_term"] != ""]

    out["pubchem_cid_numeric"] = out["stitch_flat"].map(extract_pubchem_digits)
    fill_from_stereo = out["pubchem_cid_numeric"] == ""
    out.loc[fill_from_stereo, "pubchem_cid_numeric"] = out.loc[
        fill_from_stereo, "stitch_stereo"
    ].map(extract_pubchem_digits)

    out = out.sort_values(
        ["stitch_flat", "stitch_stereo", "adr_id", "adr_term"], kind="mergesort"
    )
    out = out.drop_duplicates(
        subset=["stitch_flat", "stitch_stereo", "adr_id", "adr_term"], keep="first"
    )
    return out.reset_index(drop=True)


def add_drug_names(out: pd.DataFrame, sider_dir: Path) -> pd.DataFrame:
    names_files = sorted(
        [p for p in sider_dir.iterdir() if p.is_file() and "drug_names" in p.name.lower()]
    )
    out = out.copy()
    out["drug_name"] = ""
    if not names_files:
        return out

    names = pd.read_csv(names_files[0], sep="\t", header=None, dtype=str)
    if names.shape[1] < 2:
        return out
    names = names.iloc[:, :2].copy()
    names.columns = ["stitch", "drug_name"]
    names["stitch"] = names["stitch"].map(normalize_text).map(lambda x: re.sub(r"\s+", "", x))
    names["drug_name"] = names["drug_name"].map(normalize_text)
    names = names[names["stitch"] != ""]
    names = names.sort_values(["stitch", "drug_name"], kind="mergesort").drop_duplicates(
        subset=["stitch"], keep="first"
    )

    lookup = names.set_index("stitch")["drug_name"].to_dict()
    out["drug_name"] = out["stitch_flat"].map(lookup)
    fill_mask = out["drug_name"].fillna("") == ""
    out.loc[fill_mask, "drug_name"] = out.loc[fill_mask, "stitch_stereo"].map(lookup)
    out["drug_name"] = out["drug_name"].fillna("")
    return out


def write_with_optional_parquet(df: pd.DataFrame, csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)
    parquet_path = csv_path.with_suffix(".parquet")
    try:
        import pyarrow  # noqa: F401

        df.to_parquet(parquet_path, index=False)
        print(f"[OK] Wrote {parquet_path.as_posix()}")
    except Exception:
        print(
            f"[INFO] Skipping parquet for {csv_path.name} "
            "(pyarrow not available or parquet write failed)."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean SIDER side effects for Week 3.")
    parser.add_argument("--sider_dir", default="data/raw/sider")
    parser.add_argument("--out_csv", default="data/processed/sider_side_effects.csv")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    sider_dir = (repo_root / args.sider_dir).resolve()
    out_csv = (repo_root / args.out_csv).resolve()
    ensure_exists(sider_dir, "SIDER directory")

    selected = select_side_effects_file(sider_dir)
    raw_rows = count_raw_rows(selected)
    print(f"[INFO] Selected SIDER side-effects file: {selected.as_posix()}")
    print(f"[INFO] Raw row count: {raw_rows}")

    cleaned = parse_side_effects(selected)
    cleaned = add_drug_names(cleaned, sider_dir)
    write_with_optional_parquet(cleaned, out_csv)

    print(f"[OK] Wrote {out_csv.as_posix()}")
    print(
        f"[SUMMARY] rows={len(cleaned)} unique_stitch_flat={cleaned['stitch_flat'].nunique()} "
        f"unique_stitch_stereo={cleaned['stitch_stereo'].nunique()} seed={SEED}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
