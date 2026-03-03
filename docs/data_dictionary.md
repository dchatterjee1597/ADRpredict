# Data Dictionary (Week 3)

## `data/processed/sider_side_effects.csv`
Cleaned SIDER side-effect rows used for integration.

- `stitch_id`: canonical SIDER/STITCH drug identifier.
- `stitch_flat`: flat STITCH identifier when available.
- `stitch_stereo`: stereo STITCH identifier when available.
- `umls_cui`: UMLS concept identifier when present.
- `meddra_id`: MedDRA identifier when present.
- `adr_id_guess`: fallback ADR ID parsed from source rows.
- `adr_term`: ADR term text.

## `data/processed/id_map.csv`
Deterministic mapping from SIDER drug IDs to DrugCentral IDs.

- `stitch_id`: SIDER/STITCH drug identifier.
- `sider_drug_name`: SIDER drug name (if available).
- `pubchem_cid`: PubChem CID extracted from SIDER STITCH ID (if parseable).
- `drugcentral_id`: mapped DrugCentral ID (empty if unmapped).
- `mapping_method`: `pubchem`, `name_exact`, or `unmapped`.
- `n_matches`: number of candidate DrugCentral IDs before deterministic tie-break.

## `data/processed/labels_long.csv`
Positive ADR labels in long format for mapped DrugCentral drugs.

- `drugcentral_id`: DrugCentral identifier.
- `adr_id`: ADR identifier (UMLS CUI, else MedDRA ID, else fallback text ID).
- `adr_term`: ADR term text.
- `label`: binary label (`1` for known positive).
- `source`: source dataset (`SIDER`).

## `data/processed/adr_topk.csv`
Selected top ADRs for modeling.

- `adr_id`: ADR identifier.
- `adr_term`: ADR term text.
- `positives`: number of unique drugs positive for this ADR.
- `prevalence`: `positives / total_mapped_drugs`.
- `chosen_k`: final selected K after threshold and auto-reduction rules.

## `data/processed/labels_wide.csv`
Wide-format binary label matrix for chosen top-K ADRs.

- `drugcentral_id`: row index key in column form.
- ADR columns: safe column names derived from `adr_id` and slugged `adr_term`; values are `0/1`.
