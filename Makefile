# AEGIS AI — unified command surface across the pnpm (frontend) and Poetry (backend) ecosystems.
# This is the one place a developer needs to look, regardless of which half of the stack they're touching.

SHELL := /bin/bash
COMPOSE_FILE := infra/docker-compose/docker-compose.yml
SERVICES := ingestion-gateway anomaly-detection computer-vision predictive-risk-engine \
            digital-twin knowledge-graph rag-service agentic-orchestrator \
            incident-service notification-service identity-rbac audit-log \
            api-gateway realtime-gateway

.PHONY: help up down restart logs ps web install install-python lint test test-python test-web \
        migrate new-service reseed clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

up: ## Start every infra dependency + backend service via Docker Compose
	docker compose -f $(COMPOSE_FILE) up -d

down: ## Stop and remove all containers
	docker compose -f $(COMPOSE_FILE) down

restart: down up ## Restart the full local environment

logs: ## Tail logs from every container
	docker compose -f $(COMPOSE_FILE) logs -f

ps: ## Show container status
	docker compose -f $(COMPOSE_FILE) ps

web: ## Run the Next.js frontend in dev mode (outside Docker, for fast HMR)
	pnpm --filter web dev

install: ## Install frontend (pnpm) dependencies
	pnpm install

install-python: ## Install dependencies for libs/db and every Python service via Poetry
	(cd libs/db && poetry install) || exit 1
	@for svc in $(SERVICES); do \
		echo "==> services/$$svc"; \
		(cd services/$$svc && poetry install) || exit 1; \
	done

lint: ## Lint the frontend workspace
	pnpm run lint

test: test-web test-python ## Run the full test suite across both ecosystems

test-web: ## Run frontend tests
	pnpm run test

test-python: ## Run every Python service's test suite
	@for svc in $(SERVICES); do \
		echo "==> services/$$svc"; \
		(cd services/$$svc && poetry run pytest) || exit 1; \
	done

migrate: ## Run the consolidated Alembic migration chain (libs/db owns the entire schema)
	(cd libs/db && poetry run alembic upgrade head)

new-service: ## Scaffold a new service from libs/service-template (usage: make new-service NAME=my-service)
	@test -n "$(NAME)" || (echo "Usage: make new-service NAME=my-service" && exit 1)
	bash scripts/new-service.sh $(NAME)

reseed: ## Reseed demo data (DEVELOPMENT_ROADMAP.md M43)
	bash scripts/reseed-demo.sh

clean: ## Remove build artifacts and caches across both ecosystems
	pnpm run build -- --force || true
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf apps/web/.next apps/web/.turbo
