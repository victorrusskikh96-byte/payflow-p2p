# PayFlow P2P

PayFlow P2P - pet-проект приближенного к production финтех-бэкенда для P2P
денежных переводов.

Проект построен как модульный монолит на FastAPI с явными границами модулей,
чистой слоистой архитектурой и финансовым ядром на базе ledger. Деньги не
хранятся во внешних кешах: PostgreSQL остается источником истины для
постоянного состояния, ledger фиксирует движение средств, а `wallet_balances`
является атомарно обновляемой проекцией текущего баланса.

## Цели проекта

- Построить backend-архитектуру с понятными слоями `domain`, `application`,
  `infrastructure` и `api`.
- Смоделировать P2P-переводы через wallet, ledger transaction и immutable
  ledger entries.
- Реализовать JWT access tokens и аутентификацию через opaque refresh tokens.
- Использовать PostgreSQL transactions и row-level locking для сценариев,
  чувствительных к консистентности.
- Ввести double-entry accounting как основу финансовых операций.
- Покрыть основное поведение unit, integration и end-to-end тестами.
- Поддерживать качество кода через ruff и mypy.

## Текущие возможности

- Health endpoints приложения и Auth API.
- Users domain и хранение пользователей в PostgreSQL.
- Auth credentials отдельно от users.
- Хеширование паролей через Argon2.
- Регистрация, вход, refresh и logout.
- JWT access tokens.
- Opaque refresh tokens с хранением только хеша.
- Ротация refresh tokens и отзыв refresh sessions.
- Current user dependency для JWT-защищенных endpoints.
- Wallets module: создание кошельков, список своих кошельков и получение
  своего кошелька по id.
- Wallet balance projection с `available` и `locked` суммами.
- Ledger module: ledger transactions, immutable ledger entries и проверка
  double-entry accounting.
- Internal deposit operation на application level.
- P2P transfers module с публичными JWT-защищенными HTTP endpoints.
- P2P transfer через Ledger:
  - `DEBIT` sender wallet;
  - `CREDIT` recipient wallet.
- Атомарное обновление wallet balance projection вместе с ledger transaction.
- Sender balance уменьшается после успешного перевода.
- Recipient balance увеличивается после успешного перевода.
- Проверка, что пользователь переводит только со своего wallet.
- Отклонение перевода при недостаточном балансе.
- Отклонение перевода между одним и тем же wallet.
- Идемпотентность P2P-перевода по `operation_id`.
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

## Структура проекта

```text
src/payflow/        Пакет приложения
tests/unit/         Unit-тесты
tests/integration/  Integration-тесты
tests/e2e/          End-to-end тесты
```

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

## Обзор архитектуры

PayFlow P2P запускается как одно FastAPI-приложение, но бизнес-области
разделены на модули с независимыми слоями.

- `api` - тонкий FastAPI-слой: HTTP-схемы, dependencies, mapping ошибок в
  HTTP-коды и вызов use cases.
- `application` - сценарии, границы транзакций, orchestration и интерфейсы
  repositories/services.
- `domain` - сущности, value objects, инварианты и domain exceptions.
- `infrastructure` - SQLAlchemy models, repositories, mappers, transaction
  managers и реализации технических интерфейсов.

```text
Client
  |
  v
FastAPI API
  |
  v
Modules
  |-- Users
  |-- Auth
  |-- Wallets
  |-- Ledger
  |-- Transfers
  `-- Payments
  |
  v
PostgreSQL
```

## Ответственность модулей

- Users Module: идентичность пользователя, email, статус пользователя и
  хранение user records.
- Auth Module: credentials, password hash, JWT access token, refresh sessions,
  ротация refresh token, отзыв сессий и current user dependency.
- Wallets Module: wallets пользователя, currency, статус wallet и balance
  projection.
- Ledger Module: неизменяемые финансовые записи, ledger transactions, ledger
  entries и валидация balanced double-entry transaction.
- Transfers Module: жизненный цикл P2P transfer, проверка sender wallet
  ownership, идемпотентность по `operation_id`, создание ledger transaction и
  атомарное обновление балансов.
- Payments Module: внутренний application-level сценарий internal deposit.
  Публичный external payment provider не реализован.

## Как модули работают вместе

Auth использует Users при регистрации, входе и получении текущего пользователя.
Users владеет идентичностью, Auth владеет credentials, token issuing и refresh
sessions.

Wallets использует Users, чтобы создать wallet для конкретного пользователя, и
создает начальную balance projection с нулевыми значениями.

Ledger концептуально использует wallet identifiers и фиксирует движение денег
как immutable records. Каждая финансовая операция должна быть сбалансирована:
сумма `DEBIT` равна сумме `CREDIT`, а currencies внутри transaction не
смешиваются.

Transfers связывает Auth, Wallets и Ledger. API получает текущего пользователя
из JWT, application layer проверяет, что sender wallet принадлежит этому
пользователю, блокирует balance rows, создает balanced ledger transaction и
обновляет projections в одной PostgreSQL transaction.

`wallet_balances` - read model для текущих значений баланса. Это не ledger.
Ledger остается журналом движения денег, а projection нужна для быстрого чтения
и проверки доступного баланса. Projection обновляется атомарно вместе с ledger
records.

## Основные процессы

### A. Регистрация и вход

1. Клиент отправляет email и password.
2. Auth проверяет password policy или сохраненные credentials.
3. Users создает идентичность пользователя.
4. Auth сохраняет password hash отдельно от пользователя.
5. Auth выпускает JWT access token и opaque refresh token.
6. Raw refresh token не хранится в базе. Хранится только его hash.

### B. Создание wallet

1. Аутентифицированный пользователь вызывает `POST /wallets`.
2. Wallets проверяет, что пользователь существует и доступен.
3. Wallets создает wallet в запрошенной currency.
4. Wallets создает balance projection с `0` available и `0` locked.

### C. Ledger posting

1. Application use case получает `operation_id`, `operation_type` и entries.
2. Ledger проверяет balanced transaction.
3. Общая сумма `DEBIT` должна быть равна общей сумме `CREDIT`.
4. Смешивание currencies внутри одной transaction отклоняется.
5. Ledger records сохраняются как immutable entries.

### D. Internal Deposit

Internal deposit - внутренний application-level сценарий. Он не является
публичным payment provider API и не моделирует интеграцию с внешним
провайдером.

1. Операция принимает source funding wallet и target user wallet.
2. Ledger создает balanced transaction:
   - `DEBIT` source wallet;
   - `CREDIT` target wallet.
3. Wallets обновляет balance projection:
   - source `available` уменьшается;
   - target `available` увеличивается.
4. Source balance блокируется на уровне строки.
5. Если source wallet не имеет достаточного available balance, операция
   отклоняется.
6. Ledger posting и обновление balances выполняются атомарно.

CREDIT wallet entry увеличивает balance projection.
DEBIT wallet entry уменьшает balance projection.

P2P transfer:
DEBIT sender wallet
CREDIT recipient wallet

### E. P2P Transfer

1. Аутентифицированный пользователь вызывает `POST /transfers`.
2. API берет `sender_user_id` только из JWT current user.
3. Application layer проверяет:
   - sender wallet существует;
   - sender wallet принадлежит текущему пользователю;
   - recipient wallet существует;
   - wallets активны;
   - wallets и request currency совпадают;
   - sender и recipient wallets различаются;
   - `operation_id` еще не использован;
   - sender wallet имеет достаточный available balance.
4. Sender и recipient balance rows блокируются в стабильном порядке.
5. Transfers создает P2P transfer record.
6. Ledger создает balanced transaction:
   - `DEBIT` sender wallet;
   - `CREDIT` recipient wallet.
7. Wallet balance projection обновляется атомарно:
   - sender balance уменьшается;
   - recipient balance увеличивается.
8. Transfer получает статус `COMPLETED` и `ledger_transaction_id`.
9. При ошибке частичные изменения не сохраняются.

## Сценарии использования

### Успешный P2P-перевод

1. Пользователь регистрируется и получает access token.
2. Пользователь создает wallet.
3. Recipient имеет wallet в той же currency.
4. Sender wallet имеет достаточный available balance.
5. Пользователь вызывает `POST /transfers`.
6. Transfers создает balanced ledger transaction:
   `DEBIT` sender wallet и `CREDIT` recipient wallet.
7. Balance projections обновляются в той же PostgreSQL transaction.
8. Sender available balance уменьшается.
9. Recipient available balance увеличивается.

### Недостаточный баланс

1. Пользователь вызывает `POST /transfers`.
2. Sender wallet найден и принадлежит текущему пользователю.
3. Available balance меньше суммы перевода.
4. Операция отклоняется.
5. Ledger transaction не создается.
6. Balance projections не изменяются.

### Попытка перевода с чужого wallet

1. Пользователь вызывает `POST /transfers` и передает чужой `sender_wallet_id`.
2. Application layer сравнивает owner wallet с current user.
3. Операция отклоняется безопасной ошибкой.
4. Деньги и ledger records не меняются.

### Повторный operation_id

1. Клиент повторяет `POST /transfers` с уже использованным `operation_id`.
2. Application layer обнаруживает существующий transfer.
3. Операция отклоняется конфликтом.
4. Повторное движение денег не создается.

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

`POST /transfers` требует JWT access token. `sender_user_id` не принимается из
request body и всегда берется из current user dependency. Если transfer не
найден или принадлежит другому пользователю, API возвращает безопасный `404`.

Публичных HTTP endpoints для ledger нет. Ledger posting доступен через
application layer реализованных финансовых сценариев.

## Тестирование

Тестовый набор разделен по уровню поведения:

- `tests/unit` проверяет domain rules и application use cases без внешней
  инфраструктуры.
- `tests/integration` проверяет PostgreSQL repositories, mappings,
  transactions, constraints и поведение базы данных.
- `tests/e2e` проверяет FastAPI endpoints через HTTP-сценарии.

Запустить полный тестовый набор:

```bash
make test
```

## Статус проекта

Готово:

- Настройка проекта.
- Инфраструктура базы данных.
- Users.
- Auth.
- Auth API.
- Wallets.
- Wallets API.
- Ledger.
- Internal deposit operation на application level.
- Transfers domain, repository и use case.
- Transfers API.
- P2P transfer через balanced ledger transaction.
- Атомарное обновление balance projection при P2P transfer.
- E2E tests для Auth, Wallets и Transfers endpoints.

Пока не реализовано:

- Публичный deposit API.
- External payment provider adapter.
- Outbox pattern.
- Kafka events.
- Redis caching/rate limiting.
- ClickHouse analytics.
- Prometheus/Grafana.
- CI/CD.

## План развития

Roadmap Next:

- Outbox pattern.
- Kafka events.
- Redis caching/rate limiting.
- Payments provider adapter.
- ClickHouse analytics.
- Prometheus/Grafana.
- CI/CD.
