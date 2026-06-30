.PHONY: help backend-install backend-test backend-lint backend-format backend-check \
        frontend-install frontend-test frontend-build frontend-typecheck \
        migrate-upgrade migrate-downgrade migrate-revision migrate-history \
        dev-backend dev-frontend

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-30s\033[0m %s\n", $$1, $$2}'

# ── Backend ──────────────────────────────────────────────────────────────────

backend-install: ## Install backend Python dependencies
	cd backend && pip install -r requirements.txt -r requirements-dev.txt

backend-test: ## Run backend tests
	cd backend && PYTHONPATH=$$PWD python -m pytest -q

backend-lint: ## Lint backend with ruff
	cd backend && python -m ruff check app/

backend-format: ## Format backend with black
	cd backend && python -m black app/

backend-check: ## Run lint + format check + tests
	cd backend && python -m ruff check app/ && python -m black --check app/ && PYTHONPATH=$$PWD python -m pytest -q

dev-backend: ## Start backend dev server
	cd backend && uvicorn app.main:app --reload

# ── Database migrations (Alembic) ─────────────────────────────────────────────

migrate-upgrade: ## Apply all pending migrations (alembic upgrade head)
	cd backend && alembic upgrade head

migrate-downgrade: ## Roll back one migration (alembic downgrade -1)
	cd backend && alembic downgrade -1

migrate-revision: ## Generate a new migration (MSG= required)
	cd backend && alembic revision --autogenerate -m "$(MSG)"

migrate-history: ## Show migration history
	cd backend && alembic history --verbose

# ── Frontend ─────────────────────────────────────────────────────────────────

frontend-install: ## Install frontend Node dependencies
	cd frontend && npm ci

frontend-typecheck: ## Run TypeScript type check
	cd frontend && npx tsc --noEmit

frontend-test: ## Run frontend tests
	cd frontend && npm test

frontend-build: ## Build frontend
	cd frontend && npm run build

dev-frontend: ## Start frontend dev server
	cd frontend && npm run dev
