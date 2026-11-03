.PHONY: help up down restart ps logs test lint seed migrate run

help:
	@echo "Project Udyam Digital - CLI Commands"
	@echo "  make up        - Start Postgres, Redis, MinIO"
	@echo "  make down      - Stop all containers"
	@echo "  make ps        - Check container status"
	@echo "  make run       - Run FastAPI dev server"
	@echo "  make test      - Run pytest suite"
	@echo "  make lint      - Run ruff linter"
	@echo "  make seed      - Run DB seed script"
	@echo "  make migrate   - Run Alembic migrations"

up:
	docker compose up -d postgres redis minio minio-init

down:
	docker compose down

restart:
	docker compose restart

ps:
	docker compose ps

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --app-dir backend

test:
	pytest backend/tests -v

lint:
	ruff check backend

seed:
	python -m backend.app.db.seed

migrate:
	cd backend && alembic upgrade head
