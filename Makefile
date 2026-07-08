.PHONY: up run migrate revision dev-deposit test lint format typecheck check down clean

# Project and infrastructure
up:
	docker compose up -d

run:
	uv run uvicorn payflow.main:app --reload

migrate:
	uv run alembic upgrade head

revision:
	uv run alembic revision --autogenerate -m "$(m)"

dev-deposit:
ifndef wallet_id
	$(error wallet_id is required)
endif
ifndef amount
	$(error amount is required)
endif
ifndef currency
	$(error currency is required)
endif
	uv run python -m payflow.devtools.internal_deposit --wallet-id "$(wallet_id)" --amount-minor "$(amount)" --currency "$(currency)" $(if $(operation_id),--operation-id "$(operation_id)")

# Tests and checks
test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy

check: lint typecheck test

# Stop and cleanup
down:
	docker compose down

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .mypy_cache
