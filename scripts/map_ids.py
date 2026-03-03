from __future__ import annotations

import argparse
import re
import traceback
from pathlib import Path

import pandas as pd

SEED = 1337


def ensure_exists(path: Path, description: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing required {description}: {path}")


def normalize_text(value: object) -> str:
    text = "" if value is None else str(value).strip()
    return "" if text.lower() in {"", "nan", "none"} else text


def normalize_stitch(value: object) -> str:
    return re.sub(r"\s+", "", normalize_text(value))


def normalize_pubchem_digits(value: object) -> str:
    text = normalize_text(value)
    if text == "":
        return ""
    digits = re.sub(r"\D+", "", text)
    if digits == "":
        return ""
    digits = digits.lstrip("0")
    return digits if digits != "" else "0"


def normalize_name(value: object) -> str:
    text = normalize_text(value).lower()
    if text == "":
        return ""
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def dc_sort_key(dc_id: str) -> tuple[int, int | str]:
    s = normalize_text(dc_id)
    if s.isdigit():
        return (0, int(s))
    return (1, s)


def keep_smallest(mapping: dict[str, str], key: str, dc_id: str) -> None:
    if key == "" or dc_id == "":
        return
    current = mapping.get(key)
    if current is None or dc_sort_key(dc_id) < dc_sort_key(current):
        mapping[key] = dc_id


def detect_id_column(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    preferred = [
        c for c in cols if ("drugcentral" in c.lower() and "id" in c.lower())
    ]
    if preferred:
        return preferred[0]
    fallback = [c for c in cols if c.lower() == "id" or c.lower().endswith("_id")]
    if fallback:
        return fallback[0]
    return cols[0]


def detect_candidate_columns(df: pd.DataFrame) -> dict[str, list[str]]:
    cols = list(df.columns)
    return {
        "stitch": [c for c in cols if "stitch" in c.lower()],
        "pubchem": [c for c in cols if "pubchem" in c.lower() and "cid" in c.lower()],
        "name": [
            c
            for c in cols
            if (
                "name" in c.lower()
                or "drug_name" in c.lower()
                or "title" in c.lower()
            )
        ],
        "synonym": [c for c in cols if ("syn" in c.lower() or "alias" in c.lower())],
    }


def read_drugcentral_minimal(path: Path) -> pd.DataFrame:
    header_df = pd.read_csv(path, sep="\t", dtype=str, nrows=0)
    cols = list(header_df.columns)
    if not cols:
        return pd.DataFrame()
    id_col = detect_id_column(header_df)
    cand = detect_candidate_columns(header_df)
    usecols = [id_col] + cand["stitch"] + cand["pubchem"] + cand["name"] + cand["synonym"]
    # deterministic, preserve first occurrence order
    seen: set[str] = set()
    ordered_usecols: list[str] = []
    for c in usecols:
        if c not in seen:
            ordered_usecols.append(c)
            seen.add(c)
    df = pd.read_csv(path, sep="\t", dtype=str, usecols=ordered_usecols)
    df["dc_id"] = df[id_col].fillna("").astype(str).str.strip()
    return df


def sample_col_values(df: pd.DataFrame, col: str, n: int = 20) -> list[str]:
    values = df[col].fillna("").astype(str)
    out = [v for v in values.tolist() if v.strip() != ""]
    return out[:n]


def non_null_count(df: pd.DataFrame, col: str) -> int:
    s = df[col].fillna("").astype(str).str.strip()
    return int((s != "").sum())


def write_debug_markdown(debug_path: Path, debug: dict) -> None:
    debug_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "# Week 3 Mapping Debug",
        "",
        "## Status",
        "",
        f"- success: {debug.get('success', False)}",
        f"- error: {debug.get('error', '')}",
        "",
        "## Detected Candidate Columns",
        "",
    ]
    for table_name in ["structures", "targets"]:
        t = debug["tables"].get(table_name, {})
        lines.append(f"### {table_name}")
        lines.append(f"- id_col: `{t.get('id_col', '')}`")
        lines.append(f"- stitch_cols: {t.get('stitch_cols', [])}")
        lines.append(f"- pubchem_cols: {t.get('pubchem_cols', [])}")
        lines.append(f"- name_cols: {t.get('name_cols', [])}")
        lines.append(f"- synonym_cols: {t.get('synonym_cols', [])}")
        lines.append("")

    lines.extend(
        [
            "## Non-Null Counts + Sample Values (head 20)",
            "",
        ]
    )
    for table_name in ["structures", "targets"]:
        t = debug["tables"].get(table_name, {})
        lines.append(f"### {table_name}")
        counts = t.get("non_null_counts", {})
        samples = t.get("samples", {})
        if not counts:
            lines.append("- No candidate columns.")
            lines.append("")
            continue
        for col in sorted(counts):
            lines.append(f"- `{col}`: non_null={counts[col]}")
            lines.append(f"  sample={samples.get(col, [])}")
        lines.append("")

    ds = debug.get("dict_sizes", {})
    lines.extend(
        [
            "## Dictionary Sizes",
            "",
            f"- stitch_to_dc: {ds.get('stitch_to_dc', 0)}",
            f"- pubchem_to_dc: {ds.get('pubchem_to_dc', 0)}",
            f"- name_to_dc: {ds.get('name_to_dc', 0)}",
            "",
            "## Coverage Summary",
            "",
            f"- total_sider_keys: {debug.get('total_sider_keys', 0)}",
            f"- mapped_sider_keys: {debug.get('mapped_sider_keys', 0)}",
            f"- method_counts: {debug.get('method_counts', {})}",
        ]
    )
    debug_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_sider_drug_level(sider_path: Path) -> pd.DataFrame:
    if sider_path.suffix.lower() == ".parquet":
        df = pd.read_parquet(sider_path)
    else:
        df = pd.read_csv(sider_path, dtype=str)
    for col in ["stitch_flat", "stitch_stereo", "pubchem_cid_numeric", "drug_name"]:
        if col not in df.columns:
            df[col] = ""
    work = df[["stitch_flat", "stitch_stereo", "pubchem_cid_numeric", "drug_name"]].copy()
    work["stitch_flat"] = work["stitch_flat"].map(normalize_stitch)
    work["stitch_stereo"] = work["stitch_stereo"].map(normalize_stitch)
    work["pubchem_cid_numeric"] = work["pubchem_cid_numeric"].map(normalize_pubchem_digits)
    work["drug_name"] = work["drug_name"].map(normalize_text)
    work = work.drop_duplicates(
        subset=["stitch_flat", "stitch_stereo", "pubchem_cid_numeric", "drug_name"]
    )
    work["sider_key"] = work["stitch_flat"].where(
        work["stitch_flat"] != "", work["stitch_stereo"]
    )
    work = work[work["sider_key"] != ""].copy()
    work["drug_name_norm"] = work["drug_name"].map(normalize_name)
    return work.sort_values(["sider_key"], kind="mergesort").reset_index(drop=True)


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


def build_dictionaries(
    structures: pd.DataFrame, targets: pd.DataFrame, debug: dict
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    stitch_to_dc: dict[str, str] = {}
    pubchem_to_dc: dict[str, str] = {}
    name_to_dc: dict[str, str] = {}

    for table_name, df in [("structures", structures), ("targets", targets)]:
        if df.empty:
            debug["tables"][table_name] = {
                "id_col": "",
                "stitch_cols": [],
                "pubchem_cols": [],
                "name_cols": [],
                "synonym_cols": [],
                "non_null_counts": {},
                "samples": {},
            }
            continue

        id_col = detect_id_column(df)
        cand = detect_candidate_columns(df)
        all_cands = [id_col] + cand["stitch"] + cand["pubchem"] + cand["name"] + cand["synonym"]
        non_nulls = {c: non_null_count(df, c) for c in all_cands}
        samples = {c: sample_col_values(df, c, n=20) for c in all_cands}
        debug["tables"][table_name] = {
            "id_col": id_col,
            "stitch_cols": cand["stitch"],
            "pubchem_cols": cand["pubchem"],
            "name_cols": cand["name"],
            "synonym_cols": cand["synonym"],
            "non_null_counts": non_nulls,
            "samples": samples,
        }

        dc_ids = df["dc_id"].fillna("").astype(str).str.strip()

        if table_name == "structures":
            for col in cand["stitch"]:
                vals = df[col].fillna("").astype(str)
                for dc_id, raw in zip(dc_ids, vals):
                    if dc_id == "":
                        continue
                    stitch = normalize_stitch(raw)
                    keep_smallest(stitch_to_dc, stitch, dc_id)

        for col in cand["pubchem"]:
            vals = df[col].fillna("").astype(str)
            for dc_id, raw in zip(dc_ids, vals):
                if dc_id == "":
                    continue
                key = normalize_pubchem_digits(raw)
                keep_smallest(pubchem_to_dc, key, dc_id)

        for col in cand["name"]:
            vals = df[col].fillna("").astype(str)
            for dc_id, raw in zip(dc_ids, vals):
                if dc_id == "":
                    continue
                key = normalize_name(raw)
                keep_smallest(name_to_dc, key, dc_id)

        for col in cand["synonym"]:
            vals = df[col].fillna("").astype(str)
            for dc_id, raw in zip(dc_ids, vals):
                if dc_id == "":
                    continue
                text = normalize_text(raw)
                if text == "":
                    continue
                tokens = re.split(r"[|;,]", text)
                token_count = 0
                for tok in tokens:
                    if token_count >= 50:
                        break
                    norm = normalize_name(tok)
                    if len(norm) < 3:
                        continue
                    keep_smallest(name_to_dc, norm, dc_id)
                    token_count += 1

    debug["dict_sizes"] = {
        "stitch_to_dc": len(stitch_to_dc),
        "pubchem_to_dc": len(pubchem_to_dc),
        "name_to_dc": len(name_to_dc),
    }
    return stitch_to_dc, pubchem_to_dc, name_to_dc


def map_sider(
    sider_drugs: pd.DataFrame,
    stitch_to_dc: dict[str, str],
    pubchem_to_dc: dict[str, str],
    name_to_dc: dict[str, str],
) -> pd.DataFrame:
    rows = []
    for _, r in sider_drugs.iterrows():
        sider_key = r["sider_key"]
        stitch_flat = r["stitch_flat"]
        stitch_stereo = r["stitch_stereo"]
        pubchem = r["pubchem_cid_numeric"]
        name_norm = r["drug_name_norm"]

        drugcentral_id = ""
        method = "unmapped"
        n_matches = 0

        if stitch_flat in stitch_to_dc:
            drugcentral_id = stitch_to_dc[stitch_flat]
            method = "stitch"
            n_matches = 1
        elif stitch_stereo in stitch_to_dc:
            drugcentral_id = stitch_to_dc[stitch_stereo]
            method = "stitch"
            n_matches = 1
        elif pubchem in pubchem_to_dc:
            drugcentral_id = pubchem_to_dc[pubchem]
            method = "pubchem"
            n_matches = 1
        elif name_norm in name_to_dc:
            drugcentral_id = name_to_dc[name_norm]
            method = "name_exact"
            n_matches = 1

        rows.append(
            {
                "sider_key": sider_key,
                "drugcentral_id": drugcentral_id,
                "mapping_method": method,
                "n_matches": n_matches,
            }
        )

    out = pd.DataFrame(rows)
    out = out.sort_values(["sider_key", "drugcentral_id"], kind="mergesort")
    out = out.drop_duplicates(subset=["sider_key"], keep="first").reset_index(drop=True)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Map SIDER IDs to DrugCentral IDs.")
    parser.add_argument(
        "--sider_clean_csv", default="data/processed/sider_side_effects.csv"
    )
    parser.add_argument(
        "--drugcentral_structures",
        default="data/interim/drugcentral/drugcentral_structures.tsv",
    )
    parser.add_argument(
        "--drugcentral_targets",
        default="data/interim/drugcentral/drugcentral_targets.tsv",
    )
    parser.add_argument("--out_csv", default="data/processed/id_map.csv")
    parser.add_argument("--debug_md", default="reports/week3_mapping_debug.md")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    structures_path = (repo_root / args.drugcentral_structures).resolve()
    targets_path = (repo_root / args.drugcentral_targets).resolve()
    out_csv = (repo_root / args.out_csv).resolve()
    debug_md = (repo_root / args.debug_md).resolve()

    debug = {
        "success": False,
        "error": "",
        "tables": {},
        "dict_sizes": {},
        "total_sider_keys": 0,
        "mapped_sider_keys": 0,
        "method_counts": {},
    }

    try:
        ensure_exists(structures_path, "DrugCentral structures file")
        ensure_exists(targets_path, "DrugCentral targets file")

        structures = read_drugcentral_minimal(structures_path)
        targets = read_drugcentral_minimal(targets_path)

        sider_parquet = (repo_root / "data/processed/sider_side_effects.parquet").resolve()
        sider_csv = (repo_root / args.sider_clean_csv).resolve()
        sider_path = sider_parquet if sider_parquet.exists() else sider_csv
        ensure_exists(sider_path, "cleaned SIDER file (csv/parquet)")
        sider_drugs = load_sider_drug_level(sider_path)

        stitch_to_dc, pubchem_to_dc, name_to_dc = build_dictionaries(
            structures, targets, debug
        )
        out = map_sider(sider_drugs, stitch_to_dc, pubchem_to_dc, name_to_dc)
        write_with_optional_parquet(out, out_csv)

        mapped_count = int((out["drugcentral_id"] != "").sum())
        total = len(out)
        method_counts = out["mapping_method"].value_counts().to_dict()

        debug["success"] = True
        debug["total_sider_keys"] = total
        debug["mapped_sider_keys"] = mapped_count
        debug["method_counts"] = method_counts

        print(f"[OK] Wrote {out_csv.as_posix()}")
        print(
            f"[SUMMARY] mapped={mapped_count}/{total} "
            f"coverage={(mapped_count / total if total else 0.0):.3f} "
            f"methods={method_counts} seed={SEED}"
        )
        return 0
    except Exception as exc:
        debug["error"] = f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}"
        raise
    finally:
        try:
            write_debug_markdown(debug_md, debug)
            print(f"[OK] Wrote {debug_md.as_posix()}")
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
