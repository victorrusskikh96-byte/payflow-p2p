# PayFlow P2P

PayFlow P2P - pet-проект приближенного к production финтех-бэкенда для P2P
денежных переводов.

Проект создан для практики backend-архитектуры, безопасности аутентификации,
движения денежных средств и инфраструктурных паттернов, которые часто
используются в финансовых системах. Он начинается как модульный монолит с
явными границами модулей и чистой/слоистой архитектурой, оставляя пространство
для будущего выделения сервисов, если система будет развиваться в сторону
микросервисов.

## Цели проекта

- Построить backend-архитектуру, приближенную к production, с понятными слоями
  domain, application, infrastructure и API.
- Смоделировать денежные операции с явными границами wallet, ledger и
  transaction.
- Реализовать JWT access tokens и аутентификацию через opaque refresh tokens.
- Использовать транзакции PostgreSQL для сценариев, чувствительных к
  консистентности.
- Ввести ledger и double-entry accounting как финансовое ядро системы.
- Использовать модульный монолит как первый этап перед возможным выделением
  микросервисов.
- Покрыть основное поведение unit, integration и end-to-end тестами.
- Поддерживать видимое качество кода через линтинг и статическую проверку
  типов.
- Подготовить проект к будущей инфраструктуре: Kafka, Redis, ClickHouse,
  Prometheus, Grafana и CI/CD.

## Текущие возможности

- Эндпоинт проверки работоспособности.
- Домен Users и хранение в PostgreSQL.
- Учетные данные Auth хранятся отдельно от users.
- Хеширование паролей через Argon2.
- Сценарии регистрации и входа.
- JWT access tokens.
- Opaque refresh tokens с хранением только хеша.
- Ротация refresh tokens.
- Auth sessions и отзыв сессий.
- Эндпоинты Auth API для register, login, refresh, logout и current user.
- Домен Wallet и хранение.
- Проекция баланса wallet.
- Ledger transactions и неизменяемые ledger entries.
- Валидация double-entry accounting.
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

Установить Python-зависимости:

```bash
uv sync
```

Запустить локальную инфраструктуру:

```bash
make up
```

Применить миграции базы данных:

```bash
make migrate
```

Запустить FastAPI-приложение:

```bash
make run
```

Запустить проверки во время разработки:

```bash
make test
make lint
make typecheck
make check
```

Остановить локальную инфраструктуру:

```bash
make down
```

Очистить локальные кеши Python и инструментов:

```bash
make clean
```

## Обзор архитектуры

PayFlow P2P начинается как модульный монолит. Код деплоится и запускается как
одно FastAPI-приложение, при этом бизнес-области разделены на модули с четкими
границами.

Каждый реализованный модуль следует одной внутренней структуре:

- `api` - тонкий слой FastAPI, который обрабатывает HTTP-схемы, зависимости и
  вызывает сценарии слоя application.
- `application` - сценарии, границы транзакций и интерфейсы, такие как
  repositories, token services, hashers и external adapters.
- `domain` - бизнес-сущности, value objects, правила и domain exceptions.
- `infrastructure` - SQLAlchemy models, реализации repositories, mappers,
  transaction managers и adapters для внешних систем.

Слой `domain` намеренно не зависит от FastAPI, SQLAlchemy, Redis, Kafka и
внешних API. Это сохраняет бизнес-правила тестируемыми и не дает деталям
фреймворков или инфраструктуры попасть в основную модель.

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
  |-- future Transfers
  |-- future Payments
  `-- future Analytics
  |
  v
PostgreSQL
```

## Ответственность модулей

- Users Module: идентичность пользователя, email и статус пользователя.
- Auth Module: credentials, password hash, JWT access token, refresh sessions,
  ротация refresh token и отзыв сессий.
- Wallets Module: wallets пользователя, currency, статус wallet и проекция
  баланса.
- Ledger Module: неизменяемые финансовые записи, ledger transactions, ledger
  entries и валидация double-entry accounting.
- Future Transfers Module: жизненный цикл P2P transfer, идемпотентность и
  оркестрация ledger posting.
- Future Payments Module: deposits, withdrawals, provider adapters и webhooks.

## Как модули работают вместе

Auth использует Users во время регистрации и аутентификации: Users владеет
идентичностью пользователя, а Auth владеет credentials, password hashes, access
tokens и refresh sessions.

Wallets использует Users, чтобы создать wallet для конкретного пользователя.
Ledger концептуально использует Wallets, записывая финансовые движения по
`wallet_id`. Future Transfers будет использовать Users, Wallets и Ledger для
оркестрации P2P движения денег. Future Payments будет использовать Wallets и
Ledger для обработки deposits, withdrawals и callbacks от providers.

PostgreSQL является источником истины для постоянного состояния. Redis может
быть добавлен позже для cache, rate limiting, locks или краткоживущей
координации, но он не должен быть источником истины для денег. Ledger является
источником истины для движения денег, а `wallet_balances` - это проекция
текущего состояния wallet.

## Основные процессы

### A. Регистрация/вход

1. Клиент отправляет email и password.
2. Auth проверяет password по password policy или сохраненным credential.
3. Users создает идентичность пользователя.
4. Auth сохраняет password hash отдельно от пользователя.
5. Auth выпускает JWT access token и opaque refresh token.
6. Raw refresh token не хранится в базе данных. Хранится только его hash.

### B. Создание wallet

1. Аутентифицированный пользователь вызывает create wallet.
2. Wallets проверяет, что пользователь существует.
3. Wallets создает wallet для запрошенной currency.
4. Wallets создает начальную balance projection с `0` available и `0` locked.

### C. Ledger posting

1. Сценарий application получает `operation_id`, `operation_type` и entries.
2. Ledger проверяет, что transaction сбалансирована.
3. Общая сумма `DEBIT` должна быть равна общей сумме `CREDIT`.
4. Смешивание currencies внутри одной ledger transaction отклоняется.
5. Ledger records сохраняются как неизменяемые записи.

## Сценарии использования

### Успешный сценарий: регистрация пользователя, создание wallet и валидный ledger posting

1. Пользователь регистрируется с email и password.
2. Auth создает user identity и credentials.
3. Пользователь получает access и refresh tokens.
4. Пользователь создает RUB wallet.
5. Wallet balance projection начинается с нуля.
6. Ledger transaction публикуется со сбалансированными `DEBIT` и `CREDIT`
   entries.
7. Ledger transaction принимается и коммитится.

Публичные API для deposit и transfer пока не реализованы. Ledger posting уже
реализован на уровнях domain и application.

### Неуспешный сценарий: несбалансированная ledger transaction

1. Слой application пытается опубликовать ledger transaction.
2. Сумма `DEBIT` равна `10000`.
3. Сумма `CREDIT` равна `9000`.
4. Ledger обнаруживает, что transaction не сбалансирована.
5. Transaction отклоняется.
6. Невалидные ledger records не сохраняются.

Дополнительные ошибочные сценарии включают дублирование wallet currency для
одного и того же пользователя, invalid password, а также invalid или expired
refresh token.

## Обзор API

Текущие публичные HTTP-эндпоинты:

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

Публичных HTTP endpoints для ledger пока нет. Ledger posting сейчас доступен на
уровнях domain и application и покрыт тестами.

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
- Базовая основа токенов.
- Auth API.
- Wallets.
- Базовая основа Ledger.

Пока не реализовано:

- Обновление wallet balance projection из ledger entries.
- Зачисление и списание для wallet balances.
- Deposits.
- Оркестрация P2P transfers.

Wallet balance projection - это read model для текущих значений баланса wallet.
Это не ledger. Сценарий ledger posting создает только ledger records и пока не
обновляет wallet balance projection.

## План развития

Дальше:

- Внутренняя операция deposit.
- P2P transfers.
- Идемпотентность.
- Outbox pattern.
- Kafka.
- Redis.
- Адаптер платежного провайдера.
- Аналитика ClickHouse.
- Prometheus/Grafana.
- CI/CD.
