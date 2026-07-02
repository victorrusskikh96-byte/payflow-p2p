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
