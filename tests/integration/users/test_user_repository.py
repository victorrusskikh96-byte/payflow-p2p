from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from payflow.modules.users.domain import User, UserStatus
from payflow.modules.users.infrastructure.models import UserModel
from payflow.modules.users.infrastructure.repositories import SQLAlchemyUserRepository


async def test_create_user_in_postgresql(async_session: AsyncSession) -> None:
    repository = SQLAlchemyUserRepository(async_session)
    user = User(email="NewUser@example.com")

    created_user = await repository.create(user)

    stored_user = await async_session.get(UserModel, created_user.id)
    assert stored_user is not None
    assert stored_user.id == created_user.id
    assert stored_user.email == "newuser@example.com"
    assert stored_user.status == UserStatus.ACTIVE.value


async def test_get_user_by_id(async_session: AsyncSession) -> None:
    repository = SQLAlchemyUserRepository(async_session)
    created_user = await repository.create(User(email="by-id@example.com"))

    found_user = await repository.get_by_id(created_user.id)

    assert found_user == created_user


async def test_get_user_by_id_returns_none_when_missing(
    async_session: AsyncSession,
) -> None:
    repository = SQLAlchemyUserRepository(async_session)

    found_user = await repository.get_by_id(uuid4())

    assert found_user is None


async def test_get_user_by_email(async_session: AsyncSession) -> None:
    repository = SQLAlchemyUserRepository(async_session)
    created_user = await repository.create(User(email="by-email@example.com"))

    found_user = await repository.get_by_email("BY-EMAIL@example.com")

    assert found_user == created_user


async def test_get_user_by_email_returns_none_when_missing(
    async_session: AsyncSession,
) -> None:
    repository = SQLAlchemyUserRepository(async_session)

    found_user = await repository.get_by_email("missing@example.com")

    assert found_user is None


async def test_email_unique_constraint(async_session: AsyncSession) -> None:
    repository = SQLAlchemyUserRepository(async_session)
    await repository.create(User(email="unique@example.com"))

    with pytest.raises(IntegrityError):
        await repository.create(User(email="UNIQUE@example.com"))


async def test_exists_by_email(async_session: AsyncSession) -> None:
    repository = SQLAlchemyUserRepository(async_session)

    assert not await repository.exists_by_email("exists@example.com")

    await repository.create(User(email="exists@example.com"))

    assert await repository.exists_by_email("EXISTS@example.com")
