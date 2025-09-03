.PHONY: up down logs db-migrate dev-api dev-web

up: ## Start all services
	docker compose up -d --build

down: ## Stop all services
	docker compose down

logs: ## Show logs for all services
	docker compose logs -f

db-migrate: ## Run database migrations
	docker compose exec api bash -c "cd /app && alembic upgrade head"

dev-api: ## Start API in development mode
	docker compose up api

dev-web: ## Start web in development mode
	docker compose up web

ingest: ## Run ingestion worker
	docker compose exec api python -m apps.ingest.worker

embed-once: ## Run embedding for unembed articles
	docker compose exec api python -m apps.ingest.embedder