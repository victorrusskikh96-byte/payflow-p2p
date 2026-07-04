"""Окружение Alembic для запуска синхронных и асинхронных миграций."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from payflow.core.config import settings
from payflow.modules.auth.infrastructure import models as auth_models
from payflow.modules.ledger.infrastructure import models as ledger_models
from payflow.modules.users.infrastructure import models as users_models
from payflow.modules.wallets.infrastructure import models as wallets_models
from payflow.shared.infrastructure.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
_ = auth_models, ledger_models, users_models, wallets_models


def get_database_url() -> str:
    """Возвращает строку подключения к базе данных для Alembic.

    Returns:
        URL базы данных из настроек приложения.
    """
    return settings.database_url


def run_migrations_offline() -> None:
    """Запускает миграции Alembic без подключения к базе данных."""
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Выполняет миграции Alembic на активном соединении.

    Args:
        connection: Синхронное SQLAlchemy-соединение.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Создает асинхронный engine и запускает миграции Alembic."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Запускает онлайн-миграции через асинхронный event loop."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
