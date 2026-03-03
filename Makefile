PY ?= python
PYTHON ?= python
ifeq ($(OS),Windows_NT)
ifneq ("$(wildcard .venv/Scripts/python.exe)","")
PYTHON := .venv/Scripts/python.exe
endif
endif

.PHONY: help setup download_sider import_drugbank catalog validate all clean test clean_sider map_ids build_labels data_dictionary week3 labels_wide features_targets dataset_meta train_baselines week4 results_pack week4_pack slides_outline

help:
	@echo "Targets:"
	@echo "  setup          Install deps (requirements.txt) + editable package"
	@echo "  download_sider Download SIDER into data/raw/sider (public)"
	@echo "  import_drugbank Parse locally placed DrugCentral files into data/interim/drugcentral"
	@echo "  catalog        Build reports/data_catalog.(csv|md) from data/raw + data/interim"
	@echo "  validate       Sanity-check raw + interim outputs (fails loudly)"
	@echo "  all            download_sider -> import_drugbank -> catalog -> validate"
	@echo "  clean_sider    Clean SIDER side effects into data/processed"
	@echo "  map_ids        Map SIDER drug IDs to DrugCentral IDs"
	@echo "  build_labels   Build Week-3 ADR label tables + report figure"
	@echo "  data_dictionary Write docs/data_dictionary.md for Week-3 outputs"
	@echo "  week3          clean_sider -> map_ids -> build_labels -> data_dictionary"
	@echo "  features_targets Build sparse target-based features"
	@echo "  dataset_meta   Build data/processed/dataset_meta.json"
	@echo "  train_baselines Train Week4 baselines + evaluation outputs"
	@echo "  week4          features_targets -> dataset_meta -> train_baselines"
	@echo "  results_pack   Build interpretation-ready Week4 result pack"
	@echo "  week4_pack     week4 -> results_pack -> slides_outline"
	@echo "  slides_outline Write reports/slides_outline.md scaffold"
	@echo "  clean          Remove generated catalogs"
	@echo "  test           Run lightweight smoke tests"

setup:
	$(PY) -m pip install -U pip
	$(PY) -m pip install -r requirements.txt
	$(PY) -m pip install -e .

download_sider:
	$(PY) scripts/download_sider.py

import_drugbank:
	$(PY) scripts/import_drugbank.py

catalog:
	$(PY) scripts/build_catalog.py

validate:
	$(PY) scripts/validate_raw_data.py

all: download_sider import_drugbank catalog validate

clean_sider:
	$(PYTHON) scripts/clean_sider.py

map_ids:
	$(PYTHON) scripts/map_ids.py

build_labels: clean_sider map_ids
	$(PYTHON) scripts/build_labels.py

data_dictionary:
	$(PYTHON) scripts/write_data_dictionary.py

week3: clean_sider map_ids build_labels data_dictionary

labels_wide:
	$(PYTHON) -c "import os,sys; ok=os.path.exists('data/processed/labels_wide.parquet') or os.path.exists('data/processed/labels_wide.csv'); print('[OK] labels_wide found' if ok else 'Missing labels_wide.(parquet|csv) in data/processed'); sys.exit(0 if ok else 1)"

features_targets:
	$(PYTHON) scripts/build_features_targets.py

dataset_meta: features_targets labels_wide
	$(PYTHON) scripts/build_dataset_meta.py

train_baselines: dataset_meta
	$(PYTHON) scripts/train_baselines.py

week4: features_targets dataset_meta train_baselines

results_pack:
	$(PYTHON) scripts/summarize_results_pack.py

week4_pack: week4 results_pack slides_outline

slides_outline: train_baselines
	$(PYTHON) scripts/write_slides_outline.py

clean:
	$(PY) -c "import os; [os.remove(p) for p in ('reports/data_catalog.csv','reports/data_catalog.md') if os.path.exists(p)]"

test:
	$(PY) -m unittest -v
