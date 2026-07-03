"""DTO token pair для application-слоя аутентификации."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class TokenPair:
    """Описывает пару access и refresh tokens для выдачи клиенту."""

    access_token: str
    refresh_token: str
    token_type: str
    access_expires_at: datetime
    refresh_expires_at: datetime
