# Results Pack

- PR-AUC baseline is approximately class prevalence; use `pr_auc_delta = pr_auc - prevalence_test` for defensible lift over baseline.
- High prevalence can make raw PR-AUC look strong even with limited incremental signal.
- Mean ROC-AUC by model:
  - LogisticRegression: 0.6316
  - LinearSVC: 0.6231
- Top 3 ADRs by PR-AUC delta:
|adr_id|adr_term|pr_auc_delta|model|
|---|---|---|---|
|C0011991|Diarrhoea|0.0927|LogisticRegression|
|C0004093|Asthenia|0.0924|LogisticRegression|
|C0033774|Pruritus|0.0903|LogisticRegression|
- Top 3 ADRs by ROC-AUC:
|adr_id|adr_term|roc_auc|model|
|---|---|---|---|
|C0011991|Diarrhoea|0.6791|LogisticRegression|
|C0033774|Pruritus|0.6676|LogisticRegression|
|C0004093|Asthenia|0.6624|LogisticRegression|
- Coverage caveat: modeling set intersection size is 895 (coverage_vs_features=0.3459605720912254, coverage_vs_labels=1.0).
- Week3 ID mapping coverage and label construction choices can propagate noise into Week4 baselines.
- ADR labels are weak supervision from SIDER and may include indication/reporting biases.
