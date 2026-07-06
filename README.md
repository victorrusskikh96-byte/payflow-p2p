# PayFlow P2P

PayFlow P2P - pet-проект приближенного к production финтех-бэкенда для P2P
денежных переводов.

Проект остается modular monolith на FastAPI. Финансовая область собрана в один
внутренний модуль `Financial Core`, а не вынесена в отдельный микросервис.
Внутри `Financial Core` находятся Wallets, Ledger / финансовая история,
Payments, Transfers и инфраструктурная таблица outbox events.

PostgreSQL является источником истины для постоянного состояния. Ledger является
источником истины по финансовым операциям, а `wallet_balances` - атомарно
обновляемая проекция текущего баланса. Outbox events сохраняются в PostgreSQL в
той же transaction, что и породившая их бизнес-операция. Kafka пока не
реализован.

## Current Features

- Health endpoints приложения и Auth API.
- Users domain и хранение пользователей в PostgreSQL.
- Auth credentials отдельно от users.
- Argon2 password hashing.
- JWT access tokens и opaque refresh tokens.
- Ротация refresh tokens и отзыв refresh sessions.
- Current user dependency для JWT-защищенных endpoints.
- `POST /wallets`, `GET /wallets/me`, `GET /wallets/{wallet_id}`.
- `POST /transfers`, `GET /transfers/me`, `GET /transfers/{transfer_id}`.
- Financial Core с Wallets, Ledger, Payments, Transfers и Outbox events table.
- Wallet balance projection с `available` и `locked` суммами.
- Ledger transactions, immutable ledger entries и double-entry accounting.
- Internal deposit operation как внутренний application-level сценарий.
- P2P transfers через balanced ledger transaction.
- Идемпотентность P2P-перевода по `operation_id`.
- Row-level locking для balance rows в сценариях изменения баланса.
- Outbox pattern foundation без внешнего publisher.
- Unit, integration и end-to-end тесты для реализованных сценариев.

## Technology Stack

| Область | Технологии |
| --- | --- |
| Backend | Python, FastAPI |
| База данных | PostgreSQL |
| ORM / миграции | SQLAlchemy async, Alembic |
| Auth | JWT access tokens, opaque refresh tokens, Argon2 |
| Тестирование | pytest, httpx |
| Качество | ruff, mypy |
| Локальная инфраструктура | Docker Compose, Makefile |

## Local Development

Требования:

- Python 3.12+.
- uv.
- Docker.
- Docker Compose.

Установить зависимости:

```bash
uv sync
```

Запустить локальную инфраструктуру:

```bash
make up
```

Применить миграции:

```bash
make migrate
```

Запустить приложение:

```bash
make run
```

Запустить проверки:

```bash
make test
make lint
make typecheck
make check
```

Остановить инфраструктуру:

```bash
make down
```

## Architecture Overview

PayFlow P2P запускается как одно FastAPI-приложение. Модули разделены
внутренними границами и слоями, но деплоятся вместе как modular monolith.
`Financial Core` - внутренний модуль приложения, а не отдельный сервис и не
микросервис.

Слои приложения:

- `api` - FastAPI routers, HTTP-схемы, dependencies и mapping ошибок в
  HTTP-коды.
- `application` - use cases, orchestration, транзакционные границы и интерфейсы
  repositories.
- `domain` - сущности, value objects, инварианты и domain exceptions.
- `infrastructure` - SQLAlchemy models, repositories, mappers и transaction
  managers.

```text
Client
  |
  v
FastAPI API
  |
  v
Modules
  |-- Auth
  |-- Users
  `-- Financial Core
      |-- Wallets
      |-- Ledger / финансовая история
      |-- Payments
      |-- Transfers
      `-- Outbox events table
  |
  v
PostgreSQL
```

## Module Responsibilities

- Auth: credentials, password hash, JWT access token, refresh sessions, ротация
  refresh token, logout и current user dependency.
- Users: идентичность пользователя, email, статус пользователя и хранение user
  records.
- Financial Core: все финансовые сценарии и данные, включая Wallets, Ledger,
  Payments, Transfers и Outbox events table.
- Wallets внутри Financial Core: кошельки пользователя, currency, статус wallet
  и balance projection. Пользовательские wallets моделируются как liability
  accounts платформы, то есть обязательства платформы перед пользователями.
- Ledger внутри Financial Core: бухгалтерский журнал финансовых операций,
  ledger transactions и immutable ledger entries. В коде Ledger остается
  Ledger, потому что это бухгалтерский журнал; в пользовательском интерфейсе он
  может отображаться как история операций.
- Payments внутри Financial Core: внутренние платежные сценарии, сейчас -
  internal deposit operation. External payment provider adapter не реализован.
- Transfers внутри Financial Core: P2P transfer, проверка sender wallet
  ownership, идемпотентность по `operation_id`, ledger posting и атомарное
  обновление balance projection.
- Outbox внутри Financial Core: infrastructure table `outbox_events` для
  атомарной записи событий рядом с бизнес-операцией. Это не отдельный
  бизнес-сервис.

## How Modules Work Together

Auth использует Users при регистрации, входе и получении текущего пользователя.
Users владеет пользовательской идентичностью, Auth владеет credentials, token
issuing и refresh sessions.

Financial Core выполняет финансовые операции в том же backend-сервисе. API слой
получает current user из Auth, затем вызывает use cases Financial Core. Use
cases проверяют бизнес-правила, создают ledger records, обновляют
`wallet_balances` и сохраняют outbox event в одной PostgreSQL transaction.

Wallets создают пользовательские liability accounts платформы. Ledger фиксирует
движение денег как immutable records и остается источником истины по финансовым
операциям. Balance projection нужна для быстрого чтения текущего available и
locked balance, но не заменяет Ledger.

Accounting convention для wallet entries:

- `CREDIT` wallet увеличивает balance projection.
- `DEBIT` wallet уменьшает balance projection.
- P2P transfer создает `DEBIT` sender wallet и `CREDIT` recipient wallet.

Outbox используется application layer финансовых сценариев. API layer не
создает события напрямую. Если PostgreSQL transaction откатывается, outbox event
тоже не сохраняется.

## Financial Core

`Financial Core` расположен в `src/payflow/modules/financial_core/` и включает:

- Wallets.
- Ledger / финансовая история.
- Payments.
- Transfers.
- Outbox events table.

Ledger не переименован в History в коде намеренно. `Ledger` точнее описывает
бухгалтерскую модель: ledger transaction и ledger entries. Для пользователя те
же данные могут быть представлены как история операций, но внутри финансового
ядра это Ledger.

Outbox - часть infrastructure слоя Financial Core. Сейчас реализованы доменная
модель outbox event, SQLAlchemy model, repository и запись событий в рамках
финансовых transactions. Kafka publisher, worker и внешняя публикация событий в
текущем runtime не реализованы.

Текущие outbox events:

- `wallet.created`.
- `internal_deposit.completed`.
- `p2p_transfer.completed`.

## Main Processes

### Регистрация и вход

1. Клиент отправляет email и password.
2. Auth проверяет password policy или сохраненные credentials.
3. Users создает идентичность пользователя.
4. Auth сохраняет password hash отдельно от пользователя.
5. Auth выпускает JWT access token и opaque refresh token.
6. Raw refresh token не хранится в базе. Хранится только его hash.

### Создание wallet

1. Аутентифицированный пользователь вызывает `POST /wallets`.
2. Financial Core проверяет, что пользователь существует и доступен.
3. Financial Core создает wallet в запрошенной currency.
4. Financial Core создает balance projection с `0` available и `0` locked.
5. Financial Core создает outbox event `wallet.created` в той же PostgreSQL
   transaction.

### Ledger posting

1. Application use case получает `operation_id`, `operation_type` и entries.
2. Ledger проверяет balanced transaction.
3. Общая сумма `DEBIT` должна быть равна общей сумме `CREDIT`.
4. Смешивание currencies внутри одной transaction отклоняется.
5. Ledger records сохраняются как immutable entries.

### Internal deposit

Internal deposit - внутренний application-level сценарий Financial Core. Он не
является публичным payment provider API и не моделирует интеграцию с внешним
провайдером.

1. Операция принимает source funding wallet и target user wallet.
2. Ledger создает balanced transaction: `DEBIT` source wallet и `CREDIT` target
   wallet.
3. Balance projection обновляется атомарно: source уменьшается, target
   увеличивается.
4. Source и target balance rows блокируются в стабильном порядке по
   `wallet_id`.
5. Если source wallet не имеет достаточного available balance, операция
   отклоняется.
6. Создается outbox event `internal_deposit.completed` в той же PostgreSQL
   transaction.

### P2P transfer

1. Аутентифицированный пользователь вызывает `POST /transfers`.
2. API берет `sender_user_id` только из JWT current user.
3. Financial Core проверяет sender wallet, ownership, recipient wallet, status,
   currency, разные wallet ids, уникальность `operation_id` и достаточность
   available balance.
4. Sender и recipient balance rows блокируются в стабильном порядке.
5. Transfers создает P2P transfer record.
6. Ledger создает balanced transaction: `DEBIT` sender wallet и `CREDIT`
   recipient wallet.
7. Wallet balance projection обновляется атомарно.
8. Transfer получает статус `COMPLETED` и `ledger_transaction_id`.
9. Создается outbox event `p2p_transfer.completed` в той же PostgreSQL
   transaction.
10. При ошибке частичные изменения и outbox event не сохраняются.

## Project Structure

```text
src/payflow/
  api/
    router.py                         Главный HTTP router приложения
  core/                               Конфигурация и database entrypoints
  modules/
    auth/                             Auth module
    users/                            Users module
    financial_core/
      api/
        wallets.py                    Wallets HTTP API
        transfers.py                  Transfers HTTP API
      domain/
        wallets/                      Wallet entities и balance projection
        ledger/                       Ledger transactions и entries
        payments/                     Payments domain namespace
        transfers/                    Transfer entity и rules
        outbox/                       Outbox event model
      application/
        wallets/                      Wallet use cases и repository ports
        ledger/                       Ledger posting use cases
        payments/                     Internal deposit use cases
        transfers/                    P2P transfer use cases
        outbox/                       Event factory и repository ports
      infrastructure/
        models.py                     SQLAlchemy tables Financial Core
        repositories/                 SQLAlchemy repositories
        mappers/                      Domain <-> ORM mapping
        transactions.py               SQLAlchemy transaction manager
tests/
  unit/                               Unit-тесты domain и use cases
  integration/                        Repository и database tests
  e2e/                                HTTP API сценарии
alembic/                              Миграции PostgreSQL
```

Старые финансовые пакеты `wallets`, `ledger`, `payments`, `transfers` и
`outbox` удалены из `src/payflow/modules/`. Финансовая бизнес-логика и API
слой живут внутри `financial_core`.

## API Overview

Публичные HTTP endpoints:

- `GET /health` - проверка работоспособности приложения.
- `GET /auth/health` - проверка работоспособности Auth API.
- `POST /auth/register` - зарегистрировать пользователя и выпустить token pair.
- `POST /auth/login` - аутентифицировать пользователя и выпустить token pair.
- `POST /auth/refresh` - ротировать refresh token и выпустить новую token pair.
- `POST /auth/logout` - отозвать refresh session.
- `GET /auth/me` - вернуть текущего пользователя по access token.
- `POST /wallets` - создать wallet для текущего пользователя.
- `GET /wallets/me` - вернуть wallets текущего пользователя.
- `GET /wallets/{wallet_id}` - вернуть wallet по id для текущего пользователя.
- `POST /transfers` - создать P2P transfer от текущего пользователя.
- `GET /transfers/me` - вернуть исходящие transfers текущего пользователя.
- `GET /transfers/{transfer_id}` - вернуть transfer текущего пользователя по id.

Публичных HTTP endpoints для Ledger, Payments и Outbox пока нет. Они доступны
через application layer реализованных финансовых сценариев.

## Testing

Тестовый набор разделен по уровню поведения:

- `tests/unit` проверяет domain rules и application use cases без внешней
  инфраструктуры.
- `tests/integration` проверяет PostgreSQL repositories, mappings,
  transactions, constraints и поведение базы данных.
- `tests/e2e` проверяет FastAPI endpoints через HTTP-сценарии.

Запуск:

```bash
make test
make lint
make typecheck
make check
```

## Project Status

Готово:

- Базовая структура проекта.
- Users и Auth.
- Auth API.
- Financial Core как единый внутренний финансовый модуль.
- Wallets domain/application/infrastructure/API внутри Financial Core.
- Ledger как бухгалтерский журнал и финансовая история операций.
- Internal deposit operation внутри Financial Core.
- Transfers domain/application/infrastructure/API внутри Financial Core.
- P2P transfer через balanced ledger transaction.
- Атомарное обновление wallet balance projection.
- Outbox events table внутри Financial Core.
- Сохранение outbox events в одной transaction с `wallet.created`,
  `internal_deposit.completed` и `p2p_transfer.completed`.
- E2E tests для Auth, Wallets и Transfers endpoints.

Пока не реализовано:

- Публичный deposit API.
- External payment provider adapter.
- Kafka publisher for outbox events.
- Redis caching/rate limiting.
- ClickHouse analytics.
- Prometheus/Grafana.
- CI/CD.

## Roadmap

Ближайший этап - Financial Core hardening:

- Review транзакционных границ финансовых use cases.
- Дополнительные failure scenarios для Ledger, Transfers и Outbox.
- Конкурентные тесты для row-level locking и операций с двумя wallets.
- Idempotency review для публичных финансовых endpoints.
- Проверка наблюдаемости ошибок без добавления Prometheus/Grafana в текущий
  runtime.

Будущие шаги после hardening:

- Публичный deposit API.
- External payment provider adapter.
- Kafka publisher for outbox events как future step, не немедленный следующий
  этап.
- Redis caching/rate limiting при появлении конкретной потребности.
- ClickHouse analytics.
- Prometheus/Grafana.
- CI/CD.
