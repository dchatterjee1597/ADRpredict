# Predictive modelling of adverse drug reactions (ADRs) using bioinformatics + ML

This repo implements a **reproducible end-to-end pipeline** to predict whether a **drug is associated with a given ADR** (adverse drug reaction). The project is framed as **one-vs-rest binary classification per ADR**, while acknowledging the underlying **multi-label** nature (a drug can have many ADRs).

**Core idea:** use **DrugCentral drug–target associations** as fast, interpretable features, and **SIDER** as weak-supervision labels. The pipeline produces **report-ready tables and figures** (ROC/PR curves, coefficient-based interpretability, and a “results pack” that corrects PR-AUC interpretation under high prevalence).

---

## What you get

### Outputs (report-ready)
After running the pipeline, you will have:

- **Integration + labels**
  - `data/processed/sider_side_effects.(csv|parquet)`
  - `data/processed/id_map.(csv|parquet)`
  - `data/processed/labels_long.(csv|parquet)`
  - `data/processed/labels_wide.(csv|parquet)` (Top-K ADRs only)
  - `data/processed/adr_topk.csv`
  - `docs/data_dictionary.md`
  - `reports/week3_data_integration.md`
  - `reports/week3_mapping_debug.md`
  - `reports/figures/id_coverage.png`

- **Features + baselines**
  - `data/processed/features_targets.npz`
  - `data/processed/features_targets_feature_names.txt`
  - `data/processed/features_targets_index.txt`
  - `data/processed/dataset_meta.json`
  - `reports/results_baselines.csv`
  - `reports/results_summary.md`
  - `reports/case_studies.md`
  - `reports/figures/roc_pr_<adr>.png` (ROC+PR, two-panel per ADR)
  - `reports/figures/top_features_<adr>.png` (LogReg coefficients)

- **Results pack (defensible PR-AUC interpretation)**
  - `reports/results_pack.md`
  - `reports/results_best_per_adr.csv`
  - `reports/figures/pr_auc_vs_prevalence.png`
  - `reports/figures/delta_pr_auc_bar.png`
  - `reports/figures/roc_auc_bar.png`

- **Slide scaffold**
  - `reports/slides_outline.md`

---

## Data sources (public) + policy

### Data sources
- **SIDER** (labels): drug ↔ ADR associations (`meddra_all_se.tsv`).
- **DrugCentral** (features): drug ↔ target associations (interim extracted TSVs).

### Data policy
- `data/raw/**` is **git-ignored**. Do not commit raw data.
- Provenance is tracked via `README_source.txt` files in `data/raw/` and `data/interim/` where applicable.

### Expected local file locations
Place data here (folders may already exist):

- SIDER (unzipped TSVs):
  - `data/raw/sider/meddra_all_se.tsv`
  - (optional) other SIDER TSVs such as `drug_names.tsv`

- DrugCentral interim TSVs:
  - `data/interim/drugcentral/drugcentral_targets.tsv`
  - `data/interim/drugcentral/drugcentral_structures.tsv`


---

## Quickstart (Windows + PowerShell)

### 0) Create + activate a venv (recommended)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip

---

## Install dependencies

python -m pip install -r requirements.txt

## Run the full pipeline (recommended order)

make week3
make week4
make results_pack
make slides_outline

## Where to find results
Tables + narratives: 'reports/'
Figures: 'reports/figures/'
Processed datasets/features: 'data/processed/'