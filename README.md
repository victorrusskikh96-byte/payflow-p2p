# PayFlow P2P

PayFlow P2P - pet-проект приближенного к production финтех-бэкенда для P2P
денежных переводов.

Проект остается modular monolith на FastAPI. Финансовая область собрана в один
внутренний модуль `Financial Core`, а не вынесена в отдельный микросервис.
Внутри `Financial Core` находятся Wallets, Ledger / финансовая история,
Payments, Transfers, обновление балансов кошельков и инфраструктурная таблица
PostgreSQL `outbox_events`.

PostgreSQL является источником истины для постоянного состояния и денежных
данных. Ledger является источником истины по финансовым операциям, а
`wallet_balances` - атомарно обновляемая проекция текущего баланса. Внешние
инфраструктурные компоненты не должны становиться источником истины для денег.
Redis и Kafka не являются источником истины для денег.

Outbox в текущей архитектуре - не отдельное приложение, не самостоятельный
сервис и не бизнес-модуль. Это таблица `outbox_events` и infrastructure
mechanism внутри `Financial Core`. Она нужна, чтобы атомарно сохранить событие
вместе с бизнес-операцией в одной PostgreSQL transaction и подготовить данные
для возможной будущей внешней доставки. На текущем этапе события наружу не
публикуются.

## Текущая функциональность

- Health endpoints приложения и Auth API.
- Users domain и хранение пользователей в PostgreSQL.
- Auth credentials отдельно от users.
- Argon2 password hashing.
- JWT access tokens и opaque refresh tokens.
- Ротация refresh tokens и отзыв refresh sessions.
- Current user dependency для JWT-защищенных endpoints.
- `POST /wallets`, `GET /wallets/me`, `GET /wallets/{wallet_id}`.
- `POST /transfers`, `GET /transfers/me`, `GET /transfers/{transfer_id}`.
- Financial Core с Wallets, Ledger, Payments, Transfers, wallet balance updates
  и таблицей `outbox_events`.
- Wallet balance projection с `available` и `locked` суммами.
- Ledger transactions, immutable ledger entries и double-entry accounting.
- Internal deposit operation как внутренний application-level сценарий.
- P2P transfers через balanced ledger transaction.
- Идемпотентность P2P-перевода по `operation_id`.
- Row-level locking для balance rows в сценариях изменения баланса.
- Атомарная запись строк `outbox_events` без внешней публикации событий.
- Unit, integration и end-to-end тесты для реализованных сценариев.

## Технологический стек

| Область | Технологии |
| --- | --- |
| Backend | Python, FastAPI |
| База данных | PostgreSQL |
| ORM / миграции | SQLAlchemy async, Alembic |
| Auth | JWT access tokens, opaque refresh tokens, Argon2 |
| Тестирование | pytest, httpx |
| Качество | ruff, mypy |
| Локальная инфраструктура | Docker Compose, Makefile |

## Локальная разработка

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

## Локальное ручное тестирование через Postman

Для проверки successful P2P transfer локально можно использовать dev-only
команду `dev-deposit`. Это не публичный endpoint, не admin API и не production
payment provider. Команда доступна только в `local`, `dev`, `development`,
`test` или `testing` окружении и завершается ошибкой в production-like
окружениях.

Flow:

1. Запустить backend:

   ```bash
   make up
   make migrate
   make run
   ```

2. Зарегистрировать Alice и Bob через Postman: `POST /auth/register`.
3. Создать Alice и Bob RUB wallets через Postman: `POST /wallets`.
4. Сохранить `alice_wallet_id` и `bob_wallet_id` в Postman environment.
5. Пополнить wallet Alice локальной dev-only командой:

   ```bash
   make dev-deposit wallet_id=<alice_wallet_id> amount=100000 currency=RUB
   ```

   При необходимости можно передать идемпотентный идентификатор операции:

   ```bash
   make dev-deposit wallet_id=<alice_wallet_id> amount=100000 currency=RUB operation_id=<uuid>
   ```

6. Через Postman выполнить P2P transfer Alice -> Bob: `POST /transfers`.
7. Проверить balances через `GET /wallets/me` для Alice и Bob.
8. При необходимости проверить Ledger и `outbox_events` напрямую в PostgreSQL.

`dev-deposit` предназначен только для ручного локального тестирования. Целевой
wallet не пополняется прямым изменением `wallet_balances`: команда открывает
обычный database/application context и вызывает `InternalDepositUseCase`
Financial Core. Поэтому Ledger / финансовая история, balance projection и
строка `outbox_events` создаются тем же application flow, что и внутренняя
операция internal deposit.

## Обзор архитектуры

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
      |-- wallet balance updates
      `-- PostgreSQL table: outbox_events
  |
  v
PostgreSQL
```

`outbox_events` находится внутри PostgreSQL-схемы финансового ядра. Это не
отдельное приложение, не отдельный сервис и не самостоятельный бизнес-модуль.
На текущем этапе нет runtime-компонента, который публикует события наружу.

## Financial Core

`Financial Core` расположен в `src/payflow/modules/financial_core/` и включает:

- Wallets.
- Ledger / финансовую историю.
- Payments.
- Transfers.
- Wallet balance updates.
- Таблицу PostgreSQL `outbox_events`.

Ledger не переименован в History в коде намеренно. `Ledger` точнее описывает
бухгалтерскую модель: ledger transaction и ledger entries. Для пользователя те
же данные могут быть представлены как история операций, но внутри финансового
ядра это Ledger.

Финансовые операции выполняются атомарно. Use cases Financial Core сохраняют
Ledger / финансовую историю, изменения `wallet_balances` и строку
`outbox_events` в одной PostgreSQL transaction. Если на любом шаге возникает
ошибка, transaction откатывается целиком: деньги не списываются частично,
ledger records не остаются в промежуточном состоянии, а outbox event не
создается для неуспешной операции.

PostgreSQL является источником истины для финансового состояния. Ledger хранит
неизменяемую финансовую историю, `wallet_balances` хранит атомарно обновляемую
проекцию текущего баланса, а `outbox_events` является infrastructure/helper
mechanism внутри Financial Core. Redis, Kafka и другие внешние
инфраструктурные компоненты не являются источником истины для денег.

Пользовательские wallets моделируются как liability accounts платформы, то есть
как обязательства платформы перед пользователями. Для wallet entries используется
следующая accounting convention:

- `CREDIT` wallet увеличивает balance projection.
- `DEBIT` wallet уменьшает balance projection.

`outbox_events` - обычная PostgreSQL-таблица внутри `Financial Core`. Use cases
создают строки в этой таблице в той же transaction, что и бизнес-операцию.
Назначение Outbox в текущей версии:

- атомарно сохранить событие вместе с бизнес-операцией;
- не публиковать событие наружу на текущем этапе;
- подготовить события для будущей внешней доставки, если она понадобится.

Сейчас `outbox_events` используется для событий:

- `wallet.created`.
- `internal_deposit.completed`.
- `p2p_transfer.completed`.

Kafka publisher для `outbox_events` пока не реализован. Outbox не публикует
события наружу в текущей версии.

## Failure Scenarios

Financial Core контролируемо отклоняет операции в следующих сценариях:

- Недостаточно средств на sender wallet.
- Повторный `operation_id`.
- Попытка перевода с чужого wallet.
- Перевод на тот же wallet.
- Несовпадение валют sender и recipient wallets.
- Заблокированный или закрытый wallet.
- Ошибка создания ledger records.
- Ошибка обновления `wallet_balances`.
- Ошибка создания строки `outbox_events`.

Для этих сценариев применяется единое правило надежности: PostgreSQL
transaction откатывается целиком. Деньги не списываются частично, ledger
records не сохраняются частично, outbox event не создается при неуспешной
операции, а API возвращает контролируемую ошибку.

## Ответственность модулей

- Auth: credentials, password hash, JWT access token, refresh sessions, ротация
  refresh token, logout и current user dependency.
- Users: идентичность пользователя, email, статус пользователя и хранение user
  records.
- Financial Core: все финансовые сценарии и данные, включая Wallets, Ledger,
  Payments, Transfers, wallet balance updates и `outbox_events`.
- Wallets внутри Financial Core: кошельки пользователя, currency, статус wallet
  и balance projection. Пользовательские wallets моделируются как liability
  accounts платформы.
- Ledger внутри Financial Core: бухгалтерский журнал финансовых операций,
  ledger transactions и immutable ledger entries. В коде Ledger остается
  Ledger, потому что это бухгалтерский журнал; в пользовательском интерфейсе он
  может отображаться как история операций.
- Payments внутри Financial Core: внутренние платежные сценарии, сейчас -
  internal deposit operation. External payment provider adapter не реализован.
- Transfers внутри Financial Core: P2P transfer, проверка sender wallet
  ownership, идемпотентность по `operation_id`, ledger posting и атомарное
  обновление balance projection.
- `outbox_events` внутри Financial Core: инфраструктурная PostgreSQL-таблица
  для атомарной записи событий рядом с бизнес-операциями. Это не отдельное
  приложение, не самостоятельный сервис и не отдельный бизнес-модуль.

## Взаимодействие модулей

Auth использует Users при регистрации, входе и получении текущего пользователя.
Users владеет пользовательской идентичностью, Auth владеет credentials, token
issuing и refresh sessions.

Financial Core выполняет финансовые операции в том же backend-приложении. API
layer получает current user из Auth, затем вызывает use cases Financial Core.
Use cases проверяют бизнес-правила, создают ledger records, обновляют
`wallet_balances` и сохраняют строку `outbox_events` в одной PostgreSQL
transaction.

Wallets создают пользовательские liability accounts платформы. Ledger фиксирует
движение денег как immutable records и остается источником истины по финансовым
операциям. Balance projection нужна для быстрого чтения текущего available и
locked balance, но не заменяет Ledger.

Accounting convention для wallet entries:

- `CREDIT` wallet увеличивает balance projection.
- `DEBIT` wallet уменьшает balance projection.
- P2P transfer создает `DEBIT` sender wallet и `CREDIT` recipient wallet.

Outbox используется application layer финансовых сценариев только как запись в
таблицу `outbox_events`. API layer не создает события напрямую. Если PostgreSQL
transaction откатывается, строка `outbox_events` тоже не сохраняется. В текущей
версии сохраненные события не доставляются во внешние системы.

## Use Cases

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
5. Financial Core создает строку `outbox_events` с событием `wallet.created` в
   той же PostgreSQL transaction.
6. Событие не публикуется наружу в текущей версии.

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
6. Создается строка `outbox_events` с событием `internal_deposit.completed` в
   той же PostgreSQL transaction.
7. Событие не публикуется наружу в текущей версии.

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
9. Создается строка `outbox_events` с событием `p2p_transfer.completed` в той
   же PostgreSQL transaction.
10. При ошибке частичные изменения и строка `outbox_events` не сохраняются.
11. Событие не публикуется наружу в текущей версии.

### Failed P2P transfer: insufficient funds

1. Пользователь пытается отправить сумму больше available balance.
2. Financial Core проверяет баланс отправителя.
3. Операция отклоняется.
4. Sender balance не меняется.
5. Recipient balance не меняется.
6. Ledger transaction не создается.
7. Outbox event не создается.
8. API возвращает контролируемую ошибку.

## Структура проекта

```text
src/payflow/
  api/
    router.py                         Главный HTTP router приложения
  core/                               Конфигурация и database entrypoints
  devtools/                           Dev-only CLI-инструменты для локальной проверки
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
      application/
        events.py                     Helpers и write-port для outbox_events
        wallets/                      Wallet use cases и repository ports
        ledger/                       Ledger posting use cases
        payments/                     Internal deposit use cases
        transfers/                    P2P transfer use cases
      infrastructure/
        models.py                     SQLAlchemy tables Financial Core
        repositories/                 SQLAlchemy repositories, включая outbox_events
        mappers/                      Domain <-> ORM mapping
        transactions.py               SQLAlchemy transaction manager
tests/
  unit/                               Unit-тесты domain и use cases
  integration/                        Repository и database tests
  e2e/                                HTTP API сценарии
alembic/                              Миграции PostgreSQL
```

Старые финансовые пакеты `wallets`, `ledger`, `payments`, `transfers` и
`outbox` удалены из `src/payflow/modules/`. Финансовая бизнес-логика, API слой
и инфраструктурная работа с `outbox_events` живут внутри `financial_core`.

## Обзор API

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

Публичных HTTP endpoints для Ledger, Payments и `outbox_events` пока нет. Они
доступны только через application layer реализованных финансовых сценариев.

## Тестирование

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
- Таблица PostgreSQL `outbox_events` внутри Financial Core.
- Сохранение строк `outbox_events` в одной transaction с `wallet.created`,
  `internal_deposit.completed` и `p2p_transfer.completed`.
- Failure scenarios review - done.
- E2E tests для Auth, Wallets и Transfers endpoints.

Пока не реализовано:

- Публичный deposit API.
- External payment provider adapter.
- Внешняя доставка событий из `outbox_events`.
- Redis caching/rate limiting.
- ClickHouse analytics.
- Prometheus/Grafana.
- CI/CD.

## Roadmap

Next:

- Foundation для external payment provider adapter.
- Future integrations вокруг платежных сценариев.
- Публичный deposit API после формирования adapter foundation.

Возможные будущие шаги:

- Конкурентные тесты для row-level locking и операций с двумя wallets.
- Idempotency review для публичных финансовых endpoints.
- Внешняя доставка событий из `outbox_events`, если появится продуктовая или
  интеграционная потребность.
- Публикатор Kafka для `outbox_events` пока не реализован. Kafka остается
  возможным future step, а не текущей функциональностью и не ближайшей
  обязательной задачей.
- Redis caching/rate limiting при появлении конкретной потребности.
- Если в будущем появятся Redis или Kafka, они не должны становиться источником
  истины для денег.
- ClickHouse analytics.
- Prometheus/Grafana.
- CI/CD.
