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
- Argon2 password hashing

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

The project currently has the base persistence layer, the Users module foundation,
and the Auth module foundation in place.

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
- Auth module foundation.
- Auth credentials domain model and repository interface.
- SQLAlchemy auth credentials model and repository implementation.
- Alembic migration for the `auth_credentials` table.
- Password hashing through Argon2.
- Register and authenticate application use cases.
- `password_hash` is stored separately from `users` in `auth_credentials`.
- Unit tests for the users domain.
- Unit tests for password policy, password hashing, and auth use cases.
- Integration tests for the users repository.
- Integration tests for auth registration and authentication flows.

Not implemented yet:

- JWT access tokens.
- Auth HTTP endpoints.

## Makefile Commands

Basic development commands:

- `make up` - start Docker Compose infrastructure.
- `make run` - run the FastAPI app locally.
- `make migrate` - apply Alembic migrations.
- `make revision m="message"` - create a new Alembic revision.
- `make test` - run tests.
- `make lint` - run Ruff linting.
- `make format` - format code with Ruff.
- `make typecheck` - run mypy type checks.
- `make check` - run linting, type checks, and tests.
- `make down` - stop Docker Compose infrastructure.
- `make clean` - remove local Python/tool caches.

## Next Steps

- JWT authentication.
