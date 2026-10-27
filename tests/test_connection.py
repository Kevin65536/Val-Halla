import asyncio
import json
import pytest
import httpx
from src.api.onebot import OneBotAPI
from src.runtime.napcat import NapCatRuntime


def test_recovered_login_does_not_need_status_poll(app_client):
    client, bot, _ = app_client
    bot.online = False
    assert not client.get("/api/status").json()["connected"]
    bot.online = True
    assert client.post("/api/backup", json={"group_id": 123}).status_code == 200


def test_wrong_account_is_blocked(app_client):
    client, bot, _ = app_client
    bot.user_id = 98765
    assert client.get("/api/status").json()["stage"] == "wrong_account"
    assert client.post("/api/backup", json={"group_id": 123}).status_code == 503


def test_backup_validation_and_cross_origin(app_client):
    client, _, _ = app_client
    assert (
        client.post(
            "/api/backup", json={"group_id": 123, "backup_type": "invalid"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/runtime/start",
            json={},
            headers={"Origin": "https://unrelated.example"},
        ).status_code
        == 403
    )
    assert client.post("/api/runtime/start", data={"x": 1}).status_code == 415
    assert (
        client.get("/api/health", headers={"Host": "unrelated.example"}).status_code
        == 400
    )


def test_offline_history_and_local_assets(app_client):
    client, bot, _ = app_client
    bot.online = False
    assert client.get("/backups").status_code == 200
    assert client.get("/api/backups").status_code == 200
    assert client.get("/static/vendor/alpine.min.js").status_code == 200
    page = client.get("/").text
    assert "cdn.jsdelivr" not in page and "cdn.tailwindcss" not in page
    assert "/api/runtime/qrcode" in page


async def test_napcat_auth_refresh_and_qr(config, monkeypatch):
    config.runtime.mode = "native"
    config.runtime.management_token = "private-token"
    runtime = NapCatRuntime(config)
    calls = []
    attempts = {"status": 0}

    async def respond(request):
        path = request.url.path
        calls.append(path)
        if path == "/api/auth/login":
            assert "private-token" not in request.content.decode()
            return httpx.Response(
                200, json={"code": 0, "data": {"Credential": "session-token"}}
            )
        assert request.headers["authorization"] == "Bearer session-token"
        if path.endswith("CheckLoginStatus"):
            attempts["status"] += 1
            if attempts["status"] == 1:
                return httpx.Response(401)
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "isLogin": False,
                        "loginPhase": "waiting_qrcode",
                        "qrcodeurl": "https://qq.example/qr",
                    },
                },
            )
        return httpx.Response(
            200, json={"code": 0, "data": {"qrcode": "https://qq.example/qr"}}
        )

    await runtime.client.aclose()
    runtime.client = httpx.AsyncClient(
        base_url="http://127.0.0.1", transport=httpx.MockTransport(respond)
    )
    (runtime.directory).mkdir()
    (runtime.directory / "node.exe").touch()
    try:
        result = await runtime.status()
        assert result["stage"] == "waiting_qr" and result["qr_available"]
        assert calls.count("/api/auth/login") == 2
        assert "private-token" not in json.dumps(
            result
        ) and "session-token" not in json.dumps(result)
        assert await runtime.qrcode() == "https://qq.example/qr"
    finally:
        await runtime.close()


async def test_websocket_total_deadline_survives_event_stream(monkeypatch):
    client = OneBotAPI(timeout=0.03)

    class FakeSocket:
        closed = False

        async def send(self, _):
            pass

        async def recv(self):
            await asyncio.sleep(0.003)
            return '{"post_type":"message"}'

        async def close(self):
            self.closed = True

    socket = FakeSocket()

    async def connect():
        return socket

    monkeypatch.setattr(client, "_connect_websocket", connect)
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(client.get_login_info(), 0.5)
    assert socket.closed
