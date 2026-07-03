"""Pydantic-схемы HTTP API модуля аутентификации."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from payflow.modules.users.domain import UserStatus

EmailField = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=320),
]
PasswordField = Annotated[str, Field(min_length=1)]


class RegisterRequest(BaseModel):
    """Описывает запрос на регистрацию пользователя."""

    email: EmailField
    password: PasswordField


class LoginRequest(BaseModel):
    """Описывает запрос на вход пользователя."""

    email: EmailField
    password: PasswordField


class RefreshTokenRequest(BaseModel):
    """Описывает запрос на обновление пары токенов."""

    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    """Описывает запрос на отзыв refresh-сессии."""

    refresh_token: str = Field(min_length=1)


class TokenPairResponse(BaseModel):
    """Описывает ответ с парой access и refresh tokens."""

    access_token: str
    refresh_token: str
    token_type: str
    access_expires_at: datetime
    refresh_expires_at: datetime


class CurrentUserResponse(BaseModel):
    """Описывает ответ с данными текущего пользователя."""

    id: UUID
    email: str
    status: UserStatus
    created_at: datetime
    updated_at: datetime
