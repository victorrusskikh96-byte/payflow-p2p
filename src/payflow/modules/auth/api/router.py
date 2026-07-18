"""HTTP-маршруты модуля аутентификации."""

from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, status

from payflow.modules.auth.api.dependencies import (
    get_authenticate_user_use_case,
    get_current_user,
    get_issue_token_pair_use_case,
    get_refresh_token_pair_use_case,
    get_register_user_use_case,
    get_revoke_refresh_session_use_case,
)
from payflow.modules.auth.api.schemas import (
    CurrentUserResponse,
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    RegisterRequest,
    StatusResponse,
    TokenPairResponse,
)
from payflow.modules.auth.application import (
    AuthenticateUserUseCase,
    IssueTokenPairUseCase,
    RefreshTokenPairUseCase,
    RegisterUserUseCase,
    RevokeRefreshSessionUseCase,
    TokenPair,
)
from payflow.modules.auth.domain import (
    EmailAlreadyRegisteredError,
    ExpiredRefreshTokenError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    WeakPasswordError,
)
from payflow.modules.users.domain import User

router = APIRouter()


def _token_pair_to_response(token_pair: TokenPair) -> TokenPairResponse:
    return TokenPairResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        token_type=token_pair.token_type,
        access_expires_at=token_pair.access_expires_at,
        refresh_expires_at=token_pair.refresh_expires_at,
    )


def _user_to_current_user_response(user: User) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=user.id,
        email=user.email,
        status=user.status,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _raise_invalid_refresh_token_error(exc: Exception) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token.",
        headers={"WWW-Authenticate": "Bearer"},
    ) from exc


@router.get(
    "/health",
    response_model=StatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Проверить состояние Auth API",
    description="Возвращает простой статус доступности маршрутов аутентификации.",
    operation_id="auth_health_check",
)
async def auth_health_check() -> StatusResponse:
    """Возвращает состояние доступности Auth API.

    Returns:
        Текущий статус Auth API.
    """
    return StatusResponse(status="ok")


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Получить текущего пользователя",
    description="Возвращает профиль пользователя, связанного с JWT access token.",
    operation_id="get_current_user",
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> CurrentUserResponse:
    """Возвращает текущего пользователя по JWT access token.

    Args:
        current_user: Пользователь, полученный из access token.

    Returns:
        Данные текущего пользователя.
    """
    return _user_to_current_user_response(current_user)


@router.post(
    "/register",
    response_model=TokenPairResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Зарегистрировать пользователя",
    description=(
        "Создает пользователя с учетными данными и сразу возвращает пару "
        "access/refresh tokens."
    ),
    operation_id="register_user",
)
async def register(
    request: RegisterRequest,
    register_user: Annotated[
        RegisterUserUseCase,
        Depends(get_register_user_use_case),
    ],
    issue_token_pair: Annotated[
        IssueTokenPairUseCase,
        Depends(get_issue_token_pair_use_case),
    ],
) -> TokenPairResponse:
    """Регистрирует пользователя и возвращает пару токенов.

    Args:
        request: Данные регистрации пользователя.
        register_user: Use case регистрации пользователя.
        issue_token_pair: Use case выпуска пары токенов.

    Returns:
        Пара access и refresh tokens.

    Raises:
        HTTPException: Если email занят или пароль не проходит политику.
    """
    try:
        user = await register_user.execute(
            email=request.email,
            password=request.password,
        )
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered.",
        ) from exc
    except WeakPasswordError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Weak password.",
        ) from exc

    token_pair = await issue_token_pair.execute(user_id=user.id)
    return _token_pair_to_response(token_pair)


@router.post(
    "/refresh",
    response_model=TokenPairResponse,
    status_code=status.HTTP_200_OK,
    summary="Обновить пару токенов",
    description="Ротирует refresh token и возвращает новую пару токенов.",
    operation_id="refresh_token_pair",
)
async def refresh(
    request: RefreshTokenRequest,
    refresh_token_pair: Annotated[
        RefreshTokenPairUseCase,
        Depends(get_refresh_token_pair_use_case),
    ],
) -> TokenPairResponse:
    """Ротирует refresh token и возвращает новую пару токенов.

    Args:
        request: Данные с raw refresh token.
        refresh_token_pair: Use case обновления пары токенов.

    Returns:
        Новая пара access и refresh tokens.

    Raises:
        HTTPException: Если refresh token невалиден, истек или отозван.
    """
    try:
        token_pair = await refresh_token_pair.execute(
            refresh_token=request.refresh_token,
        )
    except (InvalidRefreshTokenError, ExpiredRefreshTokenError) as exc:
        _raise_invalid_refresh_token_error(exc)

    return _token_pair_to_response(token_pair)


@router.post(
    "/logout",
    response_model=StatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Выйти из текущей refresh-сессии",
    description="Отзывает refresh-сессию по переданному refresh token.",
    operation_id="logout_refresh_session",
)
async def logout(
    request: LogoutRequest,
    revoke_refresh_session: Annotated[
        RevokeRefreshSessionUseCase,
        Depends(get_revoke_refresh_session_use_case),
    ],
) -> StatusResponse:
    """Отзывает refresh-сессию по raw refresh token.

    Args:
        request: Данные с raw refresh token.
        revoke_refresh_session: Use case отзыва refresh-сессии.

    Returns:
        JSON-статус успешного logout.

    Raises:
        HTTPException: Если refresh token невалиден, истек или отозван.
    """
    try:
        await revoke_refresh_session.execute(refresh_token=request.refresh_token)
    except (InvalidRefreshTokenError, ExpiredRefreshTokenError) as exc:
        _raise_invalid_refresh_token_error(exc)

    return StatusResponse(status="ok")


@router.post(
    "/login",
    response_model=TokenPairResponse,
    status_code=status.HTTP_200_OK,
    summary="Войти по email и паролю",
    description="Проверяет учетные данные пользователя и возвращает пару токенов.",
    operation_id="login_user",
)
async def login(
    request: LoginRequest,
    authenticate_user: Annotated[
        AuthenticateUserUseCase,
        Depends(get_authenticate_user_use_case),
    ],
    issue_token_pair: Annotated[
        IssueTokenPairUseCase,
        Depends(get_issue_token_pair_use_case),
    ],
) -> TokenPairResponse:
    """Аутентифицирует пользователя и возвращает пару токенов.

    Args:
        request: Данные входа пользователя.
        authenticate_user: Use case аутентификации пользователя.
        issue_token_pair: Use case выпуска пары токенов.

    Returns:
        Пара access и refresh tokens.

    Raises:
        HTTPException: Если email или пароль не подходят для входа.
    """
    try:
        user = await authenticate_user.execute(
            email=request.email,
            password=request.password,
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    token_pair = await issue_token_pair.execute(user_id=user.id)
    return _token_pair_to_response(token_pair)
