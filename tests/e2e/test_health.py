"""E2E-тест проверки health endpoint."""

from httpx import ASGITransport, AsyncClient

from payflow.main import create_app


async def test_health_check() -> None:
    """Проверяет успешный ответ `/health` со статусом ok."""
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
