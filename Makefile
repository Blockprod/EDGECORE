# EDGECORE — Developer shortcuts
# Requires GNU Make (or nmake-compatible) and the venv activated.
# Windows: use `make` via Git-for-Windows / WSL, or run the commands directly.

PYTHON = venv\Scripts\python.exe

.PHONY: test test-statistical test-regression qa build

# Run only the slow statistical robustness tests (P3)
test-statistical:
	$(PYTHON) -m pytest tests/statistical/ -q -m slow

# Run PnL regression tests against committed snapshots (P4)
test-regression:
	$(PYTHON) -m pytest tests/regression/ -q

# Full QA: statistical + regression + lint + typing (P2-P4 scope) + full suite
qa: test-statistical test-regression
	$(PYTHON) -m ruff check .
	$(PYTHON) -m pyright data/feature_store.py models/spread.py tests/statistical/test_strategy_robustness.py tests/regression/test_pnl_regression.py tests/regression/conftest.py
	$(PYTHON) -m pytest tests/ -q

# Run the complete test suite
test:
	$(PYTHON) -m pytest tests/ -q

# Recompile Cython extensions
build:
	$(PYTHON) setup.py build_ext --inplace
