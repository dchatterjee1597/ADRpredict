from __future__ import annotations

from pathlib import Path

# repo root is: <root>/src/adr_predictor/config.py -> parents[2] = <root>
REPO_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"

REPORTS_DIR = REPO_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

DEFAULT_RANDOM_SEED = 1337
