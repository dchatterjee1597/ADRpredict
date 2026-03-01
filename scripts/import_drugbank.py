from __future__ import annotations

import argparse
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

TARGET_PATTERNS = [
    r"drug.*target.*interaction.*\.tsv(\.gz)?$",
    r"target.*interaction.*\.tsv(\.gz)?$",
]
STRUCTURE_PATTERNS = [
    r"structures.*smiles.*\.tsv(\.gz)?$",
    r"smiles.*\.tsv(\.gz)?$",
    r"structures.*\.tsv(\.gz)?$",
]


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def append_provenance(dst_dir: Path, lines: list[str]) -> None:
    dst_dir.mkdir(parents=True, exist_ok=True)
    prov = dst_dir / "README_source.txt"
    existing = prov.read_text(encoding="utf-8") if prov.exists() else ""
    header = f"\n\n=== Update {utc_stamp()} ===\n"
    prov.write_text(existing + header + "\n".join(lines) + "\n", encoding="utf-8")


def candidate_files(raw_dir: Path) -> list[Path]:
    return [
        p
        for p in raw_dir.iterdir()
        if p.is_file() and p.name not in {".gitkeep", "README_source.txt", "README_source.md"}
    ]


def find_by_patterns(files: list[Path], patterns: list[str]) -> Path | None:
    for pattern in patterns:
        rx = re.compile(pattern, flags=re.IGNORECASE)
        hits = [p for p in files if rx.search(p.name)]
        if hits:
            return sorted(hits, key=lambda p: p.stat().st_size, reverse=True)[0]
    return None


def load_table(path: Path) -> pd.DataFrame:
    compression = "gzip" if path.name.lower().endswith(".gz") else None
    df = pd.read_csv(path, sep="\t", dtype=str, low_memory=False, compression=compression)
    df = df.dropna(how="all").drop_duplicates()
    return df


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Import manually placed DrugCentral raw files to lightweight interim TSV tables. "
            "Script name is kept as import_drugbank.py for Makefile compatibility."
        )
    )
    parser.add_argument("--raw", default="data/raw/drugcentral", help="DrugCentral raw directory")
    parser.add_argument("--out", default="data/interim/drugcentral", help="DrugCentral interim output directory")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    raw_dir = (repo_root / args.raw).resolve()
    out_dir = (repo_root / args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not raw_dir.exists():
        print(f"[ERROR] Raw DrugCentral directory not found: {raw_dir}")
        return 2

    files = candidate_files(raw_dir)
    interaction_file = find_by_patterns(files, TARGET_PATTERNS)
    structures_file = find_by_patterns(files, STRUCTURE_PATTERNS)

    if interaction_file is None and structures_file is None:
        print(f"[ERROR] No matching DrugCentral files found in {raw_dir}")
        print("Expected at least one of:")
        print("- drug.target.interaction.tsv.gz (name may vary)")
        print("- structures.smiles.tsv or structures.smiles.tsv.gz (name may vary)")
        return 2

    targets_out = out_dir / "drugcentral_targets.tsv"
    structures_out = out_dir / "drugcentral_structures.tsv"
    generated: list[Path] = []

    if interaction_file is not None:
        df_targets = load_table(interaction_file)
        df_targets.to_csv(targets_out, sep="\t", index=False)
        generated.append(targets_out)
        print(f"[OK] Wrote {targets_out.relative_to(repo_root).as_posix()} rows={len(df_targets)}")
    else:
        print("[WARN] No interaction file matched; skipped drugcentral_targets.tsv")

    if structures_file is not None:
        df_structures = load_table(structures_file)
        df_structures.to_csv(structures_out, sep="\t", index=False)
        generated.append(structures_out)
        print(f"[OK] Wrote {structures_out.relative_to(repo_root).as_posix()} rows={len(df_structures)}")
    else:
        print("[WARN] No structures file matched; skipped drugcentral_structures.tsv")

    raw_lines = [
        "Dataset: DrugCentral (manual files)",
        "Homepage: https://drugcentral.org/",
        f"Raw directory: {raw_dir.relative_to(repo_root).as_posix()}",
        "Detected source files:",
    ]
    for src in [interaction_file, structures_file]:
        if src is not None:
            raw_lines.append(
                f"- {src.name}\tsha256={sha256_file(src)}\tbytes={src.stat().st_size}"
            )
    append_provenance(raw_dir, raw_lines)

    interim_lines = [
        "Derived tables from DrugCentral raw files",
        f"Output directory: {out_dir.relative_to(repo_root).as_posix()}",
        "Generated files:",
    ]
    for out_file in generated:
        row_count = max(0, sum(1 for _ in out_file.open("r", encoding="utf-8", errors="replace")) - 1)
        interim_lines.append(
            f"- {out_file.name}\tsha256={sha256_file(out_file)}\tbytes={out_file.stat().st_size}\trows={row_count}"
        )
    append_provenance(out_dir, interim_lines)

    print(f"[OK] Provenance updated in {raw_dir / 'README_source.txt'}")
    print(f"[OK] Provenance updated in {out_dir / 'README_source.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
