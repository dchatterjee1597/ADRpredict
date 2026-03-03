# Week 3 Mapping Debug

## Status

- success: True
- error: 

## Detected Candidate Columns

### structures
- id_col: `ID`
- stitch_cols: []
- pubchem_cols: []
- name_cols: []
- synonym_cols: []

### targets
- id_col: `STRUCT_ID`
- stitch_cols: []
- pubchem_cols: []
- name_cols: ['DRUG_NAME', 'TARGET_NAME']
- synonym_cols: []

## Non-Null Counts + Sample Values (head 20)

### structures
- `ID`: non_null=4099
  sample=['5392', '5393', '5394', '5395', '5396', '5375', '5376', '5377', '5378', '5280', '5283', '5285', '5260', '5261', '5262', '5253', '5254', '5255', '5229', '5231']

### targets
- `DRUG_NAME`: non_null=19149
  sample=['levobupivacaine', 'levobupivacaine', 'levobupivacaine', 'levobupivacaine', 'levobupivacaine', 'levobupivacaine', 'levobupivacaine', 'levobupivacaine', '(S)-nicardipine', '(S)-nitrendipine', '(S)-nitrendipine', '(S)-nitrendipine', '(S)-nitrendipine', '(S)-nitrendipine', '(S)-nitrendipine', 'levdobutamine', 'aminopterin', 'aminopterin', 'aminopterin', 'aminopterin']
- `STRUCT_ID`: non_null=19149
  sample=['4', '4', '4', '4', '4', '4', '4', '4', '5', '6', '6', '6', '6', '6', '6', '13', '21', '21', '21', '21']
- `TARGET_NAME`: non_null=19149
  sample=['Potassium voltage-gated channel subfamily H member 2', 'Sodium channel protein type 1 subunit alpha', 'Sodium channel protein type 4 subunit alpha', 'Prostaglandin E2 receptor EP1 subtype', 'Cytochrome P450 2D6', '5-hydroxytryptamine receptor 3A', 'Potassium voltage-gated channel subfamily D member 3', 'Potassium voltage-gated channel subfamily A member 5', 'Voltage-gated L-type calcium channel', 'Intermediate conductance calcium-activated potassium channel protein 4', 'Voltage-dependent L-type calcium channel subunit alpha-1D', 'Voltage-dependent L-type calcium channel subunit alpha-1F', 'Voltage-dependent L-type calcium channel subunit alpha-1C', 'Voltage-dependent L-type calcium channel subunit alpha-1S', 'Voltage-dependent L-type calcium channel subunit alpha-1C', 'Beta-1 adrenergic receptor', 'Dihydrofolate reductase', 'Dihydrofolate reductase', 'Dihydrofolate reductase', 'Folylpoly-gamma-glutamate synthetase']

## Dictionary Sizes

- stitch_to_dc: 0
- pubchem_to_dc: 0
- name_to_dc: 4743

## Coverage Summary

- total_sider_keys: 1430
- mapped_sider_keys: 930
- method_counts: {'name_exact': 930, 'unmapped': 500}
