class UsersDomainError(Exception):
    """Base exception for users domain errors."""


class EmptyUserEmailError(UsersDomainError):
    """Raised when a user email is empty after normalization."""
