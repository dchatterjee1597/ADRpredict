# Week4 Baseline Results Summary

- Seed: 1337
- Split seed used: 1337
- Samples (intersection): 895
- Train/Test sizes: 716/179
- ADRs evaluated: 10

## Mean Metrics by Model

|model|roc_auc|pr_auc|f1|precision|recall|
|---|---|---|---|---|---|
|LinearSVC|0.6231|0.8559|0.8037|0.8524|0.7617|
|LogisticRegression|0.6316|0.8638|0.7887|0.847|0.7388|

## Best Model Per ADR (by PR-AUC)

|adr_id|adr_term|model|pr_auc|roc_auc|f1|
|---|---|---|---|---|---|
|C0004093|Asthenia|LogisticRegression|0.8634|0.6624|0.75|
|C0011603|Dermatitis|LogisticRegression|0.8978|0.6215|0.8211|
|C0011991|Diarrhoea|LogisticRegression|0.8749|0.6791|0.7656|
|C0012833|Dizziness|LinearSVC|0.8592|0.5996|0.7956|
|C0015230|Rash|LogisticRegression|0.8959|0.5973|0.7885|
|C0018681|Headache|LogisticRegression|0.8633|0.5861|0.8293|
|C0020517|Hypersensitivity|LogisticRegression|0.7092|0.5895|0.6897|
|C0027497|Nausea|LogisticRegression|0.9325|0.6605|0.8787|
|C0033774|Pruritus|LogisticRegression|0.8277|0.6676|0.7603|
|C0042963|Vomiting|LogisticRegression|0.9167|0.6619|0.8252|

- Full results CSV: reports/results_baselines.csv
