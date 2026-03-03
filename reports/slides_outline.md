# Week4 Slides Outline

- Slide 1: Objective and Dataset Scope
  - Goal: Week4 minimal baselines with sparse target features.
  - Data sources: `data/processed/dataset_meta.json` and Week3 labels.

- Slide 2: Feature Construction (Targets-Based)
  - Sparse binary features from DrugCentral TARGET_NAME tokens.
  - Mention matrix shape, nnz, and coverage from dataset_meta.
  - Reference: `data/processed/dataset_meta.json`.

- Slide 3: Baseline Models and Evaluation Protocol
  - Models: LogisticRegression (liblinear) and LinearSVC, balanced class weights.
  - Single drug-level split with retry logic for ADR-positive coverage.
  - Metric table reference: `reports/results_baselines.csv`.

- Slide 4: Aggregate Performance
  - Compare mean ROC-AUC / PR-AUC / F1 across models.
  - Reference: `reports/results_summary.md`.

- Slide 5: ADR-wise ROC/PR Curves
  - Show per-ADR two-panel ROC+PR figures.
  - Figure: `reports/figures/roc_pr_c0004093_asthenia.png`
  - Figure: `reports/figures/roc_pr_c0011603_dermatitis.png`
  - Figure: `reports/figures/roc_pr_c0011991_diarrhoea.png`
  - Figure: `reports/figures/roc_pr_c0012833_dizziness.png`
  - Figure: `reports/figures/roc_pr_c0015230_rash.png`
  - Figure: `reports/figures/roc_pr_c0018681_headache.png`
  - Figure: `reports/figures/roc_pr_c0020517_hypersensitivity.png`
  - Figure: `reports/figures/roc_pr_c0027497_nausea.png`
  - Figure: `reports/figures/roc_pr_c0033774_pruritus.png`
  - Figure: `reports/figures/roc_pr_c0042963_vomiting.png`

- Slide 6: Logistic Regression Top Features
  - Highlight top positive and negative target coefficients per ADR.
  - Figure: `reports/figures/top_features_c0004093_asthenia.png`
  - Figure: `reports/figures/top_features_c0011603_dermatitis.png`
  - Figure: `reports/figures/top_features_c0011991_diarrhoea.png`
  - Figure: `reports/figures/top_features_c0012833_dizziness.png`
  - Figure: `reports/figures/top_features_c0015230_rash.png`
  - Figure: `reports/figures/top_features_c0018681_headache.png`
  - Figure: `reports/figures/top_features_c0020517_hypersensitivity.png`
  - Figure: `reports/figures/top_features_c0027497_nausea.png`
  - Figure: `reports/figures/top_features_c0033774_pruritus.png`
  - Figure: `reports/figures/top_features_c0042963_vomiting.png`

- Slide 7: Case Studies (Test Set)
  - Drug A/B/C risk examples from mean predicted ADR probabilities.
  - Reference: `reports/case_studies.md`.

- Slide 8: Interpreting PR-AUC under High Prevalence
  - Emphasize PR baseline ~ prevalence and show delta over baseline.
  - Figure: `reports/figures/pr_auc_vs_prevalence.png`.
  - Reference: `reports/results_pack.md`.

- Slide 9: Best Baseline Performance by ADR
  - Show best model per ADR using PR-AUC delta + ROC-AUC.
  - Figure: `reports/figures/delta_pr_auc_bar.png`.
  - Figure: `reports/figures/roc_auc_bar.png`.
  - Table: `reports/results_best_per_adr.csv`.

- Slide 10: Limitations and Next Steps
  - Sparse targets-only features are interpretable but incomplete.
  - Add structure features and calibration in Week5.
