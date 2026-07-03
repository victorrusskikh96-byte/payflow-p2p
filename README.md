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
- PyJWT

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
the Auth module foundation, and the Wallets module foundation in place. Auth and
Wallets are implemented at the domain, application, infrastructure, and HTTP API
levels.

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
- JWT access token foundation.
- Opaque refresh tokens with only token hashes stored in PostgreSQL.
- Auth sessions through the `auth_sessions` table.
- Token pair application DTO.
- Issue token pair application use case.
- Refresh token pair application use case with refresh token rotation.
- Revoke refresh session application use case.
- Auth API endpoints.
- `POST /auth/register` and `POST /auth/login` return access and refresh tokens.
- Refresh token rotation is available through `POST /auth/refresh`.
- `POST /auth/logout` revokes the refresh session without storing raw refresh tokens.
- `GET /auth/me` uses a JWT access token from `Authorization: Bearer <token>`.
- Unit tests for the users domain.
- Unit tests for password policy, password hashing, access tokens, refresh tokens,
  auth sessions, and auth use cases.
- Integration tests for the users repository.
- Integration tests for auth registration and authentication flows.
- Integration tests for auth session repository and token pair rotation flows.
- E2E tests for auth health, register, login, refresh, logout, and current user API.
- Wallets module foundation.
- Wallet domain model.
- Wallet belongs to a user.
- Wallet has `currency` and `status`.
- Wallet statuses: `ACTIVE`, `BLOCKED`, `CLOSED`.
- SQLAlchemy wallets and wallet balance projection models.
- Alembic migration for the `wallets` and `wallet_balances` tables.
- Wallet repository interfaces.
- SQLAlchemy implementation of wallet repositories.
- Wallet application use cases for create, list own wallets, and get own wallet
  by id.
- Wallet API endpoints: `POST /wallets`, `GET /wallets/me`, and
  `GET /wallets/{wallet_id}`.
- Wallet endpoints require a valid JWT access token.
- Wallet balance projection is created with zero `available_amount_minor` and
  zero `locked_amount_minor`.
- E2E tests for wallet creation, authentication requirement, duplicate currency
  conflict, own wallet list, own wallet by id, and safe not found for another
  user's wallet.

Not implemented yet:

- Money movement.
- Ledger module.
- Deposits.
- Transfers.

Wallet balance projection is a read model for current wallet balance values. It
is not a ledger. Crediting, debiting, and transfer logic are intentionally not
implemented yet. Ledger will be the next stage.

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

- Ledger module foundation.
