"""Running behind a cloudflared tunnel: every request reaches the server from 127.0.0.1, so trust must not rely on
the address alone; and the pairing links can point at the tunnel instead of the LAN."""
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

LOCAL = ("127.0.0.1", 50000)
# What cloudflared adds when it forwards a visitor's request.
TUNNEL = {"cf-connecting-ip": "203.0.113.7", "x-forwarded-for": "203.0.113.7"}


def test_this_laptop_is_trusted_without_a_code(app_main):
    with TestClient(app_main.app, client=LOCAL) as client:
        with client.websocket_connect("/ws/dashboard") as ws:
            assert ws.receive_json()["t"] == "status"


@pytest.mark.parametrize("header", ["cf-connecting-ip", "x-forwarded-for", "forwarded", "x-real-ip"])
def test_tunnel_visitors_need_the_code_even_from_127_0_0_1(app_main, header):
    with TestClient(app_main.app, client=LOCAL) as client:
        with pytest.raises(WebSocketDisconnect) as e:
            with client.websocket_connect("/ws/dashboard", headers={header: "203.0.113.7"}) as ws:
                ws.receive_json()
        assert e.value.code == 4401
        r = client.get("/api/voice/test", headers={header: "203.0.113.7"})
        assert r.status_code == 401


def test_tunnel_visitors_with_the_code_get_in(app_main):
    with TestClient(app_main.app, client=LOCAL) as client:
        with client.websocket_connect("/ws/dashboard?token=testcode",
                                      headers={**TUNNEL, "origin": "https://abc.trycloudflare.com"}) as ws:
            assert ws.receive_json()["t"] == "status"


def test_public_url_makes_the_pairing_links_point_at_the_tunnel(app_main, monkeypatch):
    monkeypatch.setenv("PUBLIC_URL", "https://abc.trycloudflare.com/")
    info = app_main.pairing_info()
    assert info["dashboard_url"] == "https://abc.trycloudflare.com/?token=testcode"
    assert info["badge_url"] == "wss://abc.trycloudflare.com/ws/badge?token=testcode"


def test_without_public_url_the_links_use_the_lan(app_main, monkeypatch):
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    monkeypatch.delenv("LARPSLATOR_HTTPS_PORT", raising=False)
    info = app_main.pairing_info()
    assert info["dashboard_url"].startswith("http://") and ":8000/?token=testcode" in info["dashboard_url"]
    assert info["badge_url"].startswith("ws://") and info["badge_url"].endswith(":8000/ws/badge?token=testcode")
