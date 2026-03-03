from __future__ import annotations

import argparse
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SEED = 1337


def ensure_exists(path: Path, description: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing required {description}: {path}")


def normalize_text(value: object) -> str:
    text = "" if value is None else str(value).strip()
    return "" if text.lower() in {"nan", "none"} else text


def choose_adr_id(row: pd.Series) -> str:
    direct = normalize_text(row.get("adr_id", ""))
    umls = normalize_text(row.get("umls_cui", ""))
    meddra = normalize_text(row.get("meddra_id", ""))
    term = normalize_text(row.get("adr_term", ""))
    if direct != "":
        return direct
    if umls != "":
        return umls
    if meddra != "":
        return meddra
    return term


def slug(text: str) -> str:
    clean = re.sub(r"[^\w\s-]", "", text.strip().lower())
    clean = re.sub(r"[-\s]+", "_", clean).strip("_")
    return clean[:48] if clean else "adr"


def make_safe_adr_columns(topk: pd.DataFrame) -> dict[str, str]:
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for _, row in topk.iterrows():
        adr_id = str(row["adr_id"])
        adr_term = str(row["adr_term"])
        base = f"{slug(adr_id)}__{slug(adr_term)}"
        base = base[:80] if len(base) > 80 else base
        candidate = base
        i = 2
        while candidate in used:
            candidate = f"{base}_{i}"
            i += 1
        used.add(candidate)
        mapping[adr_id] = candidate
    return mapping


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


def write_coverage_figure(id_map: pd.DataFrame, fig_path: Path) -> tuple[int, int]:
    fig_path.parent.mkdir(parents=True, exist_ok=True)
    total = len(id_map)
    mapped = int(id_map["drugcentral_id"].fillna("").astype(str).str.strip().ne("").sum())
    success_rate = (mapped / total) if total else 0.0

    by_method = (
        id_map[id_map["mapping_method"] != "unmapped"]["mapping_method"]
        .value_counts()
        .sort_index()
    )
    methods = list(by_method.index)
    values = list(by_method.values)

    labels = methods + ["overall_success_rate"]
    bars = values + [success_rate * total]
    colors = ["#3b82f6"] * len(values) + ["#16a34a"]

    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(labels))
    ax.bar(x, bars, color=colors)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylabel("Count (methods) / scaled success bar")
    ax.set_title("SIDER -> DrugCentral Mapping Coverage")
    ax.grid(axis="y", alpha=0.25)
    ax.text(
        0.02,
        0.95,
        f"Mapped: {mapped}/{total} ({success_rate:.1%})",
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=10,
    )
    fig.tight_layout()
    fig.savefig(fig_path, dpi=300)
    plt.close(fig)
    return mapped, total


def write_week3_report(
    report_path: Path,
    fig_rel_path: str,
    id_map: pd.DataFrame,
    adr_topk: pd.DataFrame,
    requested_k: int,
    chosen_k: int,
    min_pos: int,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    total = len(id_map)
    mapped = int(id_map["drugcentral_id"].fillna("").astype(str).str.strip().ne("").sum())
    coverage = (mapped / total) if total else 0.0
    by_method = id_map["mapping_method"].value_counts().sort_index()

    lines = [
        "# Week 3 Data Integration Summary",
        "",
        "## ID Mapping Coverage",
        "",
        f"- Total SIDER drugs: {total}",
        f"- Mapped to DrugCentral: {mapped}",
        f"- Overall success rate: {coverage:.3f}",
        "",
        "| mapping_method | n_drugs |",
        "|---|---:|",
    ]
    for method, count in by_method.items():
        lines.append(f"| {method} | {int(count)} |")

    lines += [
        "",
        f"![ID coverage plot]({fig_rel_path})",
        "",
        "## Top ADR Labels",
        "",
        f"- Requested K: {requested_k}",
        f"- Chosen K: {chosen_k}",
        f"- Minimum positives per ADR: {min_pos}",
        "",
    ]
    if adr_topk.empty:
        lines.append("_No ADRs passed the current thresholds._")
    else:
        lines += [
            "| adr_id | adr_term | positives | prevalence | chosen_k |",
            "|---|---|---:|---:|---:|",
        ]
        for _, row in adr_topk.iterrows():
            lines.append(
                f"| {row['adr_id']} | {row['adr_term']} | {int(row['positives'])} | "
                f"{float(row['prevalence']):.4f} | {int(row['chosen_k'])} |"
            )

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Week 3 ADR labels from SIDER + ID map.")
    parser.add_argument("--sider_clean_csv", default="data/processed/sider_side_effects.csv")
    parser.add_argument("--id_map_csv", default="data/processed/id_map.csv")
    parser.add_argument("--labels_long_csv", default="data/processed/labels_long.csv")
    parser.add_argument("--adr_topk_csv", default="data/processed/adr_topk.csv")
    parser.add_argument("--labels_wide_csv", default="data/processed/labels_wide.csv")
    parser.add_argument("--report_md", default="reports/week3_data_integration.md")
    parser.add_argument("--coverage_png", default="reports/figures/id_coverage.png")
    parser.add_argument("--topk", type=int, default=10)
    parser.add_argument("--min_positives_per_adr", type=int, default=30)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    sider_path = (repo_root / args.sider_clean_csv).resolve()
    id_map_path = (repo_root / args.id_map_csv).resolve()
    labels_long_path = (repo_root / args.labels_long_csv).resolve()
    adr_topk_path = (repo_root / args.adr_topk_csv).resolve()
    labels_wide_path = (repo_root / args.labels_wide_csv).resolve()
    report_path = (repo_root / args.report_md).resolve()
    coverage_path = (repo_root / args.coverage_png).resolve()

    ensure_exists(sider_path, "clean SIDER side effects file")
    ensure_exists(id_map_path, "ID map file")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    coverage_path.parent.mkdir(parents=True, exist_ok=True)
    labels_long_path.parent.mkdir(parents=True, exist_ok=True)

    sider = pd.read_csv(sider_path, dtype=str)
    id_map = pd.read_csv(id_map_path, dtype=str)
    if sider.empty:
        raise ValueError(f"No rows in {sider_path}")
    if id_map.empty:
        raise ValueError(f"No rows in {id_map_path}")
    for col in ["sider_key", "drugcentral_id"]:
        if col not in id_map.columns:
            raise ValueError(f"'{col}' column missing in {id_map_path}")
    for col in ["stitch_flat", "stitch_stereo"]:
        if col not in sider.columns:
            raise ValueError(f"'{col}' column missing in {sider_path}")

    id_map["drugcentral_id"] = id_map["drugcentral_id"].fillna("").astype(str).str.strip()
    mapped_count = int((id_map["drugcentral_id"] != "").sum())
    if mapped_count == 0:
        lines = [
            "# Week 3 Data Integration Summary",
            "",
            "## ID Mapping Coverage",
            "",
            f"- Total SIDER keys: {len(id_map)}",
            "- Mapped to DrugCentral: 0",
            "- Overall success rate: 0.000",
            "",
            "## Label Build Status",
            "",
            "Labels could not be built because SIDER to DrugCentral mapping coverage is zero.",
            "See `reports/week3_mapping_debug.md` for detected columns and mapping diagnostics.",
        ]
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        raise ValueError(
            "No SIDER keys mapped to DrugCentral IDs; labels cannot be built. "
            "See reports/week3_mapping_debug.md."
        )

    sider["sider_key"] = sider["stitch_flat"].fillna("").astype(str).str.strip()
    empty_key = sider["sider_key"] == ""
    sider.loc[empty_key, "sider_key"] = (
        sider.loc[empty_key, "stitch_stereo"].fillna("").astype(str).str.strip()
    )

    mapped = id_map[id_map["drugcentral_id"] != ""].copy()
    mapped = mapped.sort_values(["sider_key", "drugcentral_id"], kind="mergesort")
    mapped = mapped.drop_duplicates(subset=["sider_key"], keep="first")

    work = sider.merge(mapped[["sider_key", "drugcentral_id"]], on="sider_key", how="inner")
    if work.empty:
        raise ValueError("No SIDER rows matched mapped DrugCentral IDs; cannot build labels.")

    work["adr_id"] = work.apply(choose_adr_id, axis=1).map(normalize_text)
    work["adr_term"] = work["adr_term"].map(normalize_text)
    work = work[(work["adr_id"] != "") & (work["adr_term"] != "")]
    work["label"] = 1
    work["source"] = "SIDER"

    labels_long = work[
        ["drugcentral_id", "adr_id", "adr_term", "label", "source"]
    ].copy()
    labels_long = labels_long.sort_values(
        ["drugcentral_id", "adr_id", "adr_term"], kind="mergesort"
    )
    labels_long = labels_long.drop_duplicates(subset=["drugcentral_id", "adr_id"], keep="first")
    labels_long = labels_long.reset_index(drop=True)
    write_with_optional_parquet(labels_long, labels_long_path)

    total_drugs = labels_long["drugcentral_id"].nunique()
    adr_stats = (
        labels_long.groupby(["adr_id", "adr_term"], as_index=False)["drugcentral_id"]
        .nunique()
        .rename(columns={"drugcentral_id": "positives"})
    )
    adr_stats = adr_stats.sort_values(
        ["positives", "adr_id", "adr_term"], ascending=[False, True, True], kind="mergesort"
    )
    eligible = adr_stats[adr_stats["positives"] >= args.min_positives_per_adr].copy()

    if len(eligible) >= args.topk:
        chosen_k = args.topk
    elif len(eligible) >= 5:
        chosen_k = 5
    else:
        chosen_k = len(eligible)

    topk = eligible.head(chosen_k).copy()
    topk["prevalence"] = topk["positives"] / max(total_drugs, 1)
    topk["chosen_k"] = chosen_k
    topk = topk[["adr_id", "adr_term", "positives", "prevalence", "chosen_k"]]
    topk.to_csv(adr_topk_path, index=False)
    print(f"[OK] Wrote {adr_topk_path.as_posix()}")

    mapped_drugs = sorted(labels_long["drugcentral_id"].unique().tolist())
    col_map = make_safe_adr_columns(topk)
    selected_ids = set(topk["adr_id"].tolist())
    wide_pairs = labels_long[labels_long["adr_id"].isin(selected_ids)][
        ["drugcentral_id", "adr_id", "label"]
    ].copy()
    if topk.empty:
        labels_wide = pd.DataFrame({"drugcentral_id": mapped_drugs})
    else:
        wide = (
            wide_pairs.pivot_table(
                index="drugcentral_id",
                columns="adr_id",
                values="label",
                aggfunc="max",
                fill_value=0,
            )
            .astype(int)
            .reset_index()
        )
        labels_wide = pd.DataFrame({"drugcentral_id": mapped_drugs}).merge(
            wide, on="drugcentral_id", how="left"
        )
        labels_wide = labels_wide.fillna(0)
        rename_cols = {adr_id: col_map[adr_id] for adr_id in wide.columns if adr_id in col_map}
        labels_wide = labels_wide.rename(columns=rename_cols)
        for c in labels_wide.columns:
            if c != "drugcentral_id":
                labels_wide[c] = labels_wide[c].astype(int)
    write_with_optional_parquet(labels_wide, labels_wide_path)

    mapped_count, total_count = write_coverage_figure(id_map, coverage_path)
    print(f"[OK] Wrote {coverage_path.as_posix()}")

    fig_rel = coverage_path.relative_to(report_path.parent).as_posix()
    write_week3_report(
        report_path=report_path,
        fig_rel_path=fig_rel,
        id_map=id_map,
        adr_topk=topk,
        requested_k=args.topk,
        chosen_k=chosen_k,
        min_pos=args.min_positives_per_adr,
    )
    print(f"[OK] Wrote {report_path.as_posix()}")
    print(
        f"[SUMMARY] labels_long={len(labels_long)} "
        f"topk_rows={len(topk)} labels_wide_shape={labels_wide.shape} "
        f"mapped={mapped_count}/{total_count} seed={SEED}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
