# Payflow P2P

Payflow P2P is a fintech pet project for building a backend platform for P2P money transfers.

The initial architecture is a modular monolith: the codebase starts as one deployable application with explicit module boundaries. As the project grows, it is expected to evolve toward a microservices architecture.

## Stack

Current stack:

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic

Planned stack:

- Kafka
- Redis
- ClickHouse
- Prometheus
- Grafana
- CI/CD

## Project Structure

```text
src/payflow/        Application package
tests/unit/         Unit tests
tests/integration/  Integration tests
tests/e2e/          End-to-end tests
```

## Current Status

The project currently has the base persistence layer and the Users module foundation in place.

Implemented so far:

- Basic database infrastructure.
- PostgreSQL infrastructure through Docker Compose.
- Alembic migrations setup.
- Shared SQLAlchemy Base.
- Users module foundation.
- User domain model.
- User statuses: `ACTIVE`, `BLOCKED`, `PENDING_VERIFICATION`.
- SQLAlchemy users model.
- Alembic migration for the `users` table.
- Users repository interface.
- SQLAlchemy implementation of the users repository.
- Unit tests for the users domain.
- Integration tests for the users repository.

## Makefile Commands

Basic development commands:

- `make up` - start Docker Compose infrastructure.
- `make migrate` - apply Alembic migrations.
- `make test` - run tests.
- `make lint` - run Ruff linting.
- `make typecheck` - run mypy type checks.
- `make check` - run linting, type checks, and tests.
- `make down` - stop Docker Compose infrastructure.

Additional local command:

- `make run` - run the FastAPI app locally.

## Next Steps

- Auth module foundation.
- Password hashing.
- Register/login flows.
- JWT access and refresh tokens.
