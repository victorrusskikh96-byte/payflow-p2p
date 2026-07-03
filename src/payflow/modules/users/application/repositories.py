from typing import Protocol
from uuid import UUID

from payflow.modules.users.domain import User


class UserRepository(Protocol):
    async def create(self, user: User) -> User:
        """Persist a new user."""

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Return a user by id if it exists."""

    async def get_by_email(self, email: str) -> User | None:
        """Return a user by email if it exists."""

    async def exists_by_email(self, email: str) -> bool:
        """Return whether a user with the given email exists."""
