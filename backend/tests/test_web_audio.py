"""Web audio fallback: the feature flag, and a browser client going through the shared pipeline."""
import json
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

TOKEN = "?token=testcode"


def voice_like(seconds: float) -> bytes:
    """16 kHz 16-bit mono that webrtcvad treats as speech: pitch harmonics with syllable-rate loudness."""
    sr = 16000
    t = np.arange(int(sr * seconds)) / sr
    phase = 2 * np.pi * np.cumsum(140 + 15 * np.sin(2 * np.pi * 3 * t)) / sr
    voice = sum(np.sin(k * phase) / k for k in range(1, 25))
    return (voice * (0.55 + 0.45 * np.sin(2 * np.pi * 4 * t)) * 3000).astype(np.int16).tobytes()


# ------------------------------------------------------------------ feature flag
def test_flag_off_hides_the_fallback(app_main, monkeypatch):
    monkeypatch.setenv("WEB_AUDIO_FALLBACK", "0")
    with TestClient(app_main.app) as client:
        assert client.get("/api/web-audio").status_code == 404
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws/web" + TOKEN) as ws:
                ws.receive_json()
        with client.websocket_connect("/ws/dashboard" + TOKEN) as dash:
            assert dash.receive_json()["web_audio"]["enabled"] is False


def test_flag_on_serves_the_endpoints(app_main, monkeypatch):
    monkeypatch.setenv("WEB_AUDIO_FALLBACK", "1")
    with TestClient(app_main.app) as client:
        r = client.get("/api/web-audio")
        assert r.status_code == 200
        assert r.json()["sample_rate"] == 16000 and r.json()["websocket"] == "/ws/web"
        with client.websocket_connect("/ws/web" + TOKEN) as ws:
            hello = ws.receive_json()
            assert hello["t"] == "hello" and hello["client"] == "web" and hello["resume_after_ms"] == 300


def test_on_by_default_so_the_website_works_without_the_badge(app_main, monkeypatch):
    monkeypatch.delenv("WEB_AUDIO_FALLBACK", raising=False)
    with TestClient(app_main.app) as client:
        assert client.get("/api/web-audio").status_code == 200
        with client.websocket_connect("/ws/dashboard" + TOKEN) as dash:
            assert dash.receive_json()["web_audio"]["enabled"] is True


def test_web_socket_needs_the_pairing_code(app_main, monkeypatch):
    monkeypatch.setenv("WEB_AUDIO_FALLBACK", "1")
    with TestClient(app_main.app) as client:  # the test client isn't localhost, so it needs the code
        with pytest.raises(WebSocketDisconnect) as e:
            with client.websocket_connect("/ws/web?token=wrong") as ws:
                ws.receive_json()
        assert e.value.code == 4401


# ------------------------------------------------------------------ the pipeline
def test_listen_audio_stop_gives_transcript_translation_and_audio(app_main, monkeypatch):
    """listen -> audio chunks -> stop: the real VAD cuts a sentence, mocked speech-to-text/LLM/TTS translate it, the
    dashboard gets a transcript and translation tagged client=web, and the audio comes back to the browser."""
    monkeypatch.setenv("WEB_AUDIO_FALLBACK", "1")
    heard = []
    monkeypatch.setattr(app_main, "transcribe", lambda pcm, prompt="": (heard.append(len(pcm)) or "She won the first set.", "english"))
    monkeypatch.setattr(app_main, "translate", lambda text, target, terms, ctx, style="": ("그녀가 첫 세트를 이겼다.", False))
    tts = np.zeros(1600, dtype=np.int16).tobytes()  # 0.1 s of "speech"
    monkeypatch.setattr(app_main, "synthesize", lambda text, tone, voice_id="": (tts, False))

    with TestClient(app_main.app) as client:
        with client.websocket_connect("/ws/dashboard" + TOKEN) as dash, \
                client.websocket_connect("/ws/web" + TOKEN) as web:
            assert web.receive_json()["t"] == "hello"
            web.send_text(json.dumps({"t": "mode", "state": "listen"}))
            audio = voice_like(1.2)
            for i in range(0, len(audio), 3200):        # 100 ms frames, like the dashboard
                web.send_bytes(audio[i:i + 3200])
            web.send_text(json.dumps({"t": "mode", "state": "stop"}))  # ends the sentence

            got = {}
            deadline = time.time() + 10
            while time.time() < deadline and "utterance" not in got:
                m = dash.receive_json()
                if m["t"] in ("transcript", "utterance", "error"):
                    got[m["t"]] = m
            assert "error" not in got, got.get("error")
            assert got["transcript"]["source"] == "She won the first set." and got["transcript"]["client"] == "web"
            u = got["utterance"]
            assert u["translation"] == "그녀가 첫 세트를 이겼다." and u["client"] == "web"
            assert u["client_id"].startswith("web-")
            assert heard and heard[0] >= 16000 * 2 * 0.8  # the VAD passed (most of) the 1.2 s sentence on

            played = b""
            while len(played) < len(tts):                 # the translation comes back to the browser
                played += web.receive_bytes()
            assert played == tts


def test_bad_utterance_does_not_stop_the_pipeline(app_main, monkeypatch):
    """A TTS failure on one sentence is reported (client=web) and the next sentence still goes through."""
    monkeypatch.setenv("WEB_AUDIO_FALLBACK", "1")
    monkeypatch.setattr(app_main, "transcribe", lambda pcm, prompt="": ("Hello there.", "english"))
    monkeypatch.setattr(app_main, "translate", lambda *a, **k: ("안녕하세요.", False))
    calls = []

    def flaky_tts(text, tone, voice_id=""):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("quota_exceeded")
        return np.zeros(320, dtype=np.int16).tobytes(), False
    monkeypatch.setattr(app_main, "synthesize", flaky_tts)
    reported = []
    monkeypatch.setattr(app_main, "report", lambda e, step="", client="", **kw: reported.append((step, client)))

    with TestClient(app_main.app) as client:
        with client.websocket_connect("/ws/dashboard" + TOKEN) as dash, \
                client.websocket_connect("/ws/web" + TOKEN) as web:
            web.receive_json()
            for _ in range(2):
                web.send_text(json.dumps({"t": "mode", "state": "listen"}))
                audio = voice_like(1.0)
                for i in range(0, len(audio), 3200):
                    web.send_bytes(audio[i:i + 3200])
                web.send_text(json.dumps({"t": "mode", "state": "stop"}))
                time.sleep(0.3)
            seen = []
            deadline = time.time() + 10
            while time.time() < deadline and "utterance" not in seen:
                m = dash.receive_json()
                if m["t"] in ("error", "utterance"):
                    seen.append(m["t"])
                    if m["t"] == "error":
                        assert m["client"] == "web"
                        assert isinstance(m["id"], int)  # the dashboard can mark that sentence as failed
            assert seen == ["error", "utterance"]
            assert ("pipeline", "web") in reported
