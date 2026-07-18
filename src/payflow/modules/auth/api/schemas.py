"""Pydantic-схемы HTTP API модуля аутентификации."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from payflow.modules.users.domain import UserStatus

EmailField = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=320),
]
PasswordField = Annotated[str, Field(min_length=1)]


class RegisterRequest(BaseModel):
    """Описывает запрос на регистрацию пользователя."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "alice@example.com",
                "password": "StrongPass123",
            }
        }
    )

    email: EmailField
    password: PasswordField


class LoginRequest(BaseModel):
    """Описывает запрос на вход пользователя."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "alice@example.com",
                "password": "StrongPass123",
            }
        }
    )

    email: EmailField
    password: PasswordField


class RefreshTokenRequest(BaseModel):
    """Описывает запрос на обновление пары токенов."""

    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    """Описывает запрос на отзыв refresh-сессии."""

    refresh_token: str = Field(min_length=1)


class StatusResponse(BaseModel):
    """Описывает простой статусный ответ Auth API."""

    model_config = ConfigDict(json_schema_extra={"example": {"status": "ok"}})

    status: str


class TokenPairResponse(BaseModel):
    """Описывает ответ с парой access и refresh tokens."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "<jwt-access-token>",
                "refresh_token": "<opaque-refresh-token>",
                "token_type": "bearer",
                "access_expires_at": "2026-07-18T10:15:30+00:00",
                "refresh_expires_at": "2026-08-17T10:15:30+00:00",
            }
        }
    )

    access_token: str
    refresh_token: str
    token_type: str
    access_expires_at: datetime
    refresh_expires_at: datetime


class CurrentUserResponse(BaseModel):
    """Описывает ответ с данными текущего пользователя."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "11111111-1111-4111-8111-111111111111",
                "email": "alice@example.com",
                "status": "ACTIVE",
                "created_at": "2026-07-18T10:15:30+00:00",
                "updated_at": "2026-07-18T10:15:30+00:00",
            }
        }
    )

    id: UUID
    email: str
    status: UserStatus
    created_at: datetime
    updated_at: datetime
