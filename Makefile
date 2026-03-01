PY ?= python

.PHONY: help setup download_sider import_drugbank catalog validate all clean test

help:
	@echo "Targets:"
	@echo "  setup          Install deps (requirements.txt) + editable package"
	@echo "  download_sider Download SIDER into data/raw/sider (public)"
	@echo "  import_drugbank Parse locally placed DrugCentral files into data/interim/drugcentral"
	@echo "  catalog        Build reports/data_catalog.(csv|md) from data/raw + data/interim"
	@echo "  validate       Sanity-check raw + interim outputs (fails loudly)"
	@echo "  all            download_sider -> import_drugbank -> catalog -> validate"
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

clean:
	$(PY) -c "import os; [os.remove(p) for p in ('reports/data_catalog.csv','reports/data_catalog.md') if os.path.exists(p)]"

test:
	$(PY) -m unittest -v
