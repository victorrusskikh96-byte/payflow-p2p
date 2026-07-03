"""E2E-тест проверки health endpoint Auth API."""

from httpx import ASGITransport, AsyncClient

from payflow.main import create_app


async def test_auth_health_check() -> None:
    """Проверяет успешный ответ `/auth/health` со статусом ok."""
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/auth/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
