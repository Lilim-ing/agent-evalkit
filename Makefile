.PHONY: demo negative test compliance

PY ?= python

demo:
	$(PY) -m evalkit.cli run evals/cases.yaml -o reports/baseline

negative:
	$(PY) -m evalkit.cli run evals/negative_controls.yaml -o reports/negative || true

test:
	$(PY) -m pytest

compliance:
	$(PY) scripts/compliance_check.py .
