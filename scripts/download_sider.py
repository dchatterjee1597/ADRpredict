from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.exceptions import SSLError
from tqdm import tqdm


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def write_provenance(dst_dir: Path, lines: list[str]) -> None:
    prov = dst_dir / "README_source.txt"
    existing = prov.read_text(encoding="utf-8") if prov.exists() else ""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = f"\n\n=== Update {stamp} ===\n"
    prov.write_text(existing + header + "\n".join(lines) + "\n", encoding="utf-8")


def any_present(dst_dir: Path, candidates: list[str]) -> bool:
    return any((dst_dir / c).exists() for c in candidates)


def download_file(url: str, out_path: Path, timeout: int, verify_ssl: bool) -> bool:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        return True  # never overwrite

    with requests.get(
        url,
        stream=True,
        timeout=timeout,
        headers={"User-Agent": "adr-ml-ingestion/0.1"},
        verify=verify_ssl,
    ) as r:
        if r.status_code != 200:
            return False

        total = int(r.headers.get("Content-Length", "0"))
        tmp = out_path.with_suffix(out_path.suffix + ".part")

        with tmp.open("wb") as f, tqdm(
            total=total if total > 0 else None,
            unit="B",
            unit_scale=True,
            desc=out_path.name,
            leave=False,
        ) as pbar:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))

        tmp.replace(out_path)

    return True


def main() -> int:
    ap = argparse.ArgumentParser(
        description="SIDER download/provenance (never overwrites; supports manual/unzipped files)."
    )
    ap.add_argument("--dst", default="data/raw/sider", help="Destination directory")
    ap.add_argument("--manual", action="store_true", help="Do not download; write instructions to README_source.txt")
    ap.add_argument("--insecure", action="store_true", help="Disable SSL verification (only if you accept the risk)")
    ap.add_argument("--timeout", type=int, default=60, help="Request timeout seconds")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    dst_dir = (repo_root / args.dst).resolve()
    dst_dir.mkdir(parents=True, exist_ok=True)

    # Accept either gz or unzipped TSV as "present"
    required_variants = [
        ["meddra_all_se.tsv.gz", "meddra_all_se.tsv"],
    ]
    optional_variants = [
        ["drug_names.tsv.gz", "drug_names.tsv"],
        ["meddra_freq.tsv.gz", "meddra_freq.tsv"],
        ["meddra_all_indications.tsv.gz", "meddra_all_indications.tsv"],
        ["meddra_all_label_se.tsv.gz", "meddra_all_label_se.tsv"],
    ]

    base_urls = [
        "https://sideeffects.embl.de/media/download",
        "http://sideeffects.embl.de/media/download",
    ]

    if args.manual:
        lines = [
            "Dataset: SIDER (Side Effect Resource)",
            "Homepage: https://sideeffects.embl.de/",
            "Manual mode selected (no automated download).",
            f"Place files into: {dst_dir.as_posix()}",
            "Required (either is acceptable):",
            "  - meddra_all_se.tsv.gz  OR  meddra_all_se.tsv",
            "Optional (either gz or tsv):",
            "  - drug_names.tsv(.gz)",
            "  - meddra_freq.tsv(.gz)",
            "  - meddra_all_indications.tsv(.gz)",
            "  - meddra_all_label_se.tsv(.gz)",
        ]
        write_provenance(dst_dir, lines)
        print(f"[OK] Manual instructions written to {dst_dir / 'README_source.txt'}")
        return 0

    # If required file already exists locally (gz or tsv), do NOT touch network.
    if all(any_present(dst_dir, variants) for variants in required_variants):
        present = [p for p in dst_dir.iterdir() if p.is_file() and p.name not in {".gitkeep", "README_source.txt"}]
        lines = [
            "Dataset: SIDER (Side Effect Resource)",
            "Homepage: https://sideeffects.embl.de/",
            "Required files already present locally; no download attempted.",
            f"SSL verify: {'DISABLED (--insecure)' if args.insecure else 'enabled'}",
            "Files present (sha256, bytes):",
        ]
        for p in sorted(present, key=lambda x: x.name.lower()):
            lines.append(f"  - {p.name}\tsha256={sha256_file(p)}\tbytes={p.stat().st_size}")
        write_provenance(dst_dir, lines)
        print(f"[OK] SIDER present; provenance updated: {dst_dir / 'README_source.txt'}")
        return 0

    # Otherwise attempt download of canonical gz filenames (server-hosted)
    verify_ssl = not args.insecure

    required_canonical = ["meddra_all_se.tsv.gz"]
    optional_canonical = ["drug_names.tsv.gz", "meddra_freq.tsv.gz", "meddra_all_indications.tsv.gz", "meddra_all_label_se.tsv.gz"]

    missing_required = []

    for filename in required_canonical + optional_canonical:
        out_path = dst_dir / filename
        if out_path.exists():
            continue

        ok = False
        for base in base_urls:
            url = f"{base}/{filename}"
            try:
                ok = download_file(url, out_path, timeout=args.timeout, verify_ssl=verify_ssl)
            except SSLError as e:
                print(f"[ERROR] SSL error fetching {url}: {e}")
                print("Your network is intercepting TLS (self-signed cert).")
                print("Since you already downloaded SIDER manually, keep files in data/raw/sider and rerun.")
                print("Or write provenance only: python scripts/download_sider.py --manual")
                print("Or (if you accept the risk): python scripts/download_sider.py --insecure")
                return 2
            if ok:
                break

        if filename in required_canonical and not ok:
            missing_required.append(filename)

    if missing_required:
        print("[ERROR] Missing required SIDER files after download attempts:")
        for m in missing_required:
            print(f"  - {m}")
        print("Use manual mode if your network blocks downloads:")
        print("  python scripts/download_sider.py --manual")
        return 2

    # log provenance
    present = [p for p in dst_dir.iterdir() if p.is_file() and p.name not in {"README_source.txt", ".gitkeep"}]
    lines = [
        "Dataset: SIDER (Side Effect Resource)",
        "Homepage: https://sideeffects.embl.de/",
        "Base URLs attempted:",
        *[f"  - {b}" for b in base_urls],
        f"SSL verify: {'DISABLED (--insecure)' if args.insecure else 'enabled'}",
        "Files present (sha256, bytes):",
    ]
    for p in sorted(present, key=lambda x: x.name.lower()):
        lines.append(f"  - {p.name}\tsha256={sha256_file(p)}\tbytes={p.stat().st_size}")
    write_provenance(dst_dir, lines)

    print(f"[OK] SIDER ready in {dst_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())