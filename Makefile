.PHONY: bootstrap demo lab local-demo stop test web-test mobile-test apk contracts reset-demo
PYTHON := .venv/bin/python
export PYTHONPATH := services/backend:.
bootstrap:
	python3 -m venv .bootstrap
	.bootstrap/bin/pip install uv==0.8.22
	.bootstrap/bin/uv sync --frozen --python 3.12
	npm --prefix apps/web ci --no-audit --no-fund
demo:
	$(PYTHON) scripts/compose.py DEMO
lab:
	$(PYTHON) scripts/compose.py LAB
local-demo:
	$(PYTHON) scripts/local.py start
product:
	$(PYTHON) scripts/product.py start
product-stop:
	$(PYTHON) scripts/product.py stop
product-postgres-test:
	$(PYTHON) scripts/product.py exec $(PYTHON) scripts/verify_product_postgres.py
product-web-test:
	$(PYTHON) scripts/product.py exec $(PYTHON) scripts/product_e2e.py
product-test:
	.venv/bin/pytest services/backend/product_tests -q
stop:
	$(PYTHON) scripts/local.py stop
test:
	.venv/bin/pytest -q
	npm --prefix apps/web run build
web-test:
	cd apps/web && npm run test:e2e
mobile-test:
	cd apps/mobile && flutter analyze && flutter test
apk:
	cd apps/mobile && flutter build apk --debug
contracts:
	$(PYTHON) -m app.cli openapi
	cd apps/web && npx openapi-typescript ../../packages/contracts/openapi.json -o ../../packages/contracts/api.d.ts
reset-demo:
	$(PYTHON) scripts/reset_demo.py
