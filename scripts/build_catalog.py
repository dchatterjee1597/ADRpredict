from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

TABULAR_SUFFIXES = (".tsv", ".csv", ".txt", ".tsv.gz", ".csv.gz", ".txt.gz")
IGNORE_NAMES = {".gitkeep", "README_source.txt", "README_source.md"}


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def utc_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_tabular(path: Path) -> bool:
    name = path.name.lower()
    return any(name.endswith(suf) for suf in TABULAR_SUFFIXES)


def open_text(path: Path):
    if path.name.lower().endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def delimiter_for(path: Path) -> str:
    name = path.name.lower()
    if ".csv" in name:
        return ","
    return "\t"


def schema_hint(path: Path) -> tuple[int | None, str | None]:
    if not is_tabular(path):
        return None, None
    try:
        with open_text(path) as f:
            first = f.readline().rstrip("\n")
    except Exception:
        return None, None
    if not first:
        return None, None

    delim = delimiter_for(path)
    cols = next(csv.reader([first], delimiter=delim))
    cols = [c.strip() for c in cols]
    if len(cols) == 0:
        return None, None
    return len(cols), ", ".join(cols)


def row_count(path: Path, max_bytes: int) -> int | None:
    if not is_tabular(path):
        return None
    if path.stat().st_size > max_bytes:
        return None
    try:
        with open_text(path) as f:
            n = sum(1 for _ in f)
    except Exception:
        return None
    return max(0, n - 1)


def collect_rows(repo_root: Path, roots: list[Path], max_bytes_for_rowcount: int) -> list[dict]:
    out = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.name in IGNORE_NAMES:
                continue
            n_cols, columns = schema_hint(path)
            out.append(
                {
                    "path": path.relative_to(repo_root).as_posix(),
                    "dataset_root": root.relative_to(repo_root).as_posix(),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                    "mtime_utc": utc_mtime(path),
                    "ext": "".join(path.suffixes).lower(),
                    "row_count": row_count(path, max_bytes_for_rowcount),
                    "n_cols": n_cols,
                    "columns": columns,
                }
            )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build data catalog from data/raw and data/interim with checksums and schema hints."
    )
    parser.add_argument("--raw", default="data/raw", help="Raw data root")
    parser.add_argument("--interim", default="data/interim", help="Interim data root")
    parser.add_argument("--out_csv", default="reports/data_catalog.csv", help="CSV output path")
    parser.add_argument("--out_md", default="reports/data_catalog.md", help="Markdown output path")
    parser.add_argument(
        "--max_bytes_for_rowcount",
        type=int,
        default=250_000_000,
        help="Skip row counting for files larger than this threshold",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    roots = [(repo_root / args.raw).resolve(), (repo_root / args.interim).resolve()]
    out_csv = (repo_root / args.out_csv).resolve()
    out_md = (repo_root / args.out_md).resolve()
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    rows = collect_rows(repo_root, roots, args.max_bytes_for_rowcount)
    df = pd.DataFrame(rows, columns=["path", "dataset_root", "size_bytes", "sha256", "mtime_utc", "ext", "row_count", "n_cols", "columns"])
    if not df.empty:
        df = df.sort_values(["dataset_root", "path"]).reset_index(drop=True)

    df.to_csv(out_csv, index=False)

    lines = ["# Data Catalog", ""]
    lines.append(
        f"- Generated UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"
    )
    lines.append("- Scanned roots:")
    for root in roots:
        rel = root.relative_to(repo_root).as_posix()
        lines.append(f"  - {rel}")
    lines.append(f"- Files indexed: {len(df)}")
    lines.append("")

    if df.empty:
        lines.append("_No files found in scanned roots._")
    else:
        view = df.copy()
        view["columns"] = view["columns"].fillna("")
        view["columns"] = view["columns"].map(lambda s: s if len(s) <= 160 else f"{s[:160]}...")
        lines.append(view.to_markdown(index=False))

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[OK] Wrote {out_csv.relative_to(repo_root).as_posix()}")
    print(f"[OK] Wrote {out_md.relative_to(repo_root).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
