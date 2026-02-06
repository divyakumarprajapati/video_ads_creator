# ── Video Ads Engine – Makefile ──────────────────────────────
#
# Quick-start commands for local development.
# Works on macOS (M1/M2/M3), Linux, and WSL.
#

.PHONY: help setup setup-lite db migrate seed run test clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ── Setup ──────────────────────────────────────────────────

setup: ## Full install (includes AI/ML packages – needs ~4GB disk, 16GB+ RAM)
	pip install -r requirements.txt
	@echo "\n✓ Full install complete"

setup-lite: ## Lightweight install (M1 8GB / no GPU – ~200MB disk)
	pip install -r requirements-lite.txt
	@echo "\n✓ Lite install complete (FFmpeg + Pillow + OpenAI)"

# ── Database ───────────────────────────────────────────────

db: ## Start PostgreSQL via Docker
	docker compose -f docker-compose.local.yml up -d
	@echo "Waiting for Postgres..."
	@sleep 3
	@echo "✓ Postgres running on localhost:5432"

migrate: ## Run Alembic migrations
	alembic upgrade head
	@echo "✓ Database migrated"

seed: ## Seed 108 video templates
	python3 scripts/seed_templates.py
	@echo "✓ Templates seeded"

# ── Run ────────────────────────────────────────────────────

run: ## Start the API server (development)
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# ── Test ───────────────────────────────────────────────────

test: ## Run all unit tests
	python3 -m pytest tests/unit/ -v

test-cov: ## Run tests with coverage report
	python3 -m pytest tests/ --cov=app --cov-report=term-missing

# ── Utility ────────────────────────────────────────────────

clean: ## Remove generated files and caches
	rm -rf output/ __pycache__ .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Cleaned"

# ── Compound targets ───────────────────────────────────────

quickstart: setup-lite db migrate seed run ## One-command M1 setup: install → db → migrate → seed → run
