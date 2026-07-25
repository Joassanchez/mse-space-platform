.PHONY: up down worker test lint seed migrate migration setup

.env:
	@echo "📋 Creando .env desde .env.example..."
	cp .env.example .env
	@echo "✅ .env creado. Editalo para agregar tus API keys."

setup: .env
	docker compose build

up: .env
	docker compose up -d

down:
	docker compose down

worker:
	docker compose up -d worker

test:
	docker compose run --rm api pytest tests/ -v

lint:
	docker compose run --rm api ruff check .

seed:
	docker compose exec api python -c "from argplant.modules.agronomy.seed_data import load_agronomy_seeds; from argplant.modules.economy.seed_data import load_economy_seeds; load_agronomy_seeds(); load_economy_seeds()"

migrate:
	docker compose run --rm api alembic upgrade head

migration:
	docker compose run --rm api alembic revision --autogenerate -m "$(name)"
