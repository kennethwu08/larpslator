"""Speech to text (ElevenLabs Scribe), a web session with only the network clients mocked (the real transcribe() and
translate() code runs), and Sentry tagging (client=web, step=...) through a capture transport."""
import json
import time
import types

import numpy as np
import pytest
import sentry_sdk
from fastapi.testclient import TestClient

from test_web_audio import TOKEN, voice_like


class FakeScribe:
    """Stands in for eleven_client.speech_to_text: records each call, returns a fixed text and language code."""

    def __init__(self, text="She won the first set after a long deuce game.", code="eng"):
        self.text, self.code, self.calls = text, code, []

    def convert(self, **kw):
        self.calls.append(kw)
        return types.SimpleNamespace(text=self.text, language_code=self.code)


def fake_eleven(scribe, tts_convert=lambda **kw: iter([b"\0\0"])):
    """The ElevenLabs client as the pipeline uses it: speech_to_text.convert and text_to_speech.convert."""
    return types.SimpleNamespace(speech_to_text=scribe, text_to_speech=types.SimpleNamespace(convert=tts_convert))


def fake_featherless(reply):
    """Stands in for llm_client.chat.completions.create; records the requests."""
    calls = []

    def create(**kw):
        calls.append(kw)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=reply))])
    return create, calls


# ------------------------------------------------------------------ transcribe()
def test_transcribe_sends_keyterms_and_scribe_settings(app_main, monkeypatch):
    scribe = FakeScribe()
    monkeypatch.setattr(app_main, "eleven_client", fake_eleven(scribe))
    text, lang = app_main.transcribe(b"\0" * 3200, ["set", "deuce"])
    assert (text, lang) == ("She won the first set after a long deuce game.", "english")
    kw = scribe.calls[0]
    assert kw["model_id"] == app_main.STT_MODEL == "scribe_v2"
    assert kw["keyterms"] == ["set", "deuce"]
    assert kw["tag_audio_events"] is False
    name, wav, mime = kw["file"]
    assert mime == "audio/wav" and wav[:4] == b"RIFF"  # the 16 kHz PCM is sent as a WAV


def test_transcribe_without_keyterms_leaves_them_out(app_main, monkeypatch):
    scribe = FakeScribe()
    monkeypatch.setattr(app_main, "eleven_client", fake_eleven(scribe))
    app_main.transcribe(b"\0" * 3200, [])
    assert "keyterms" not in scribe.calls[0]


@pytest.mark.parametrize("code, name", [("eng", "english"), ("kor", "korean"), ("tam", "tamil"),
                                        ("ENG", "english"), ("spa", "spanish"), ("xyz", "xyz"), ("", "")])
def test_transcribe_maps_language_codes(app_main, monkeypatch, code, name):
    monkeypatch.setattr(app_main, "eleven_client", fake_eleven(FakeScribe(code=code)))
    assert app_main.transcribe(b"\0" * 3200)[1] == name


def test_pipeline_keyterms_are_the_checked_fields_english_jargon(app_main, monkeypatch):
    scribe = FakeScribe()
    monkeypatch.setattr(app_main, "eleven_client", fake_eleven(scribe))
    create, _ = fake_featherless("그녀는 긴 듀스 끝에 첫 세트를 따냈다.")
    monkeypatch.setattr(app_main.llm_client.chat.completions, "create", create)
    monkeypatch.setattr(app_main, "synthesize", lambda text, tone: (b"\0\0", False))
    app_main.run_pipeline(b"\0" * 32000, "Korean", "", 0.0, {"tennis"}, client="web")
    terms = scribe.calls[0]["keyterms"]
    assert "deuce" in terms and "set" in terms
    assert all(not any("가" <= ch <= "힣" for ch in t) for t in terms)  # English terms only


# ------------------------------------------------------------------ a web session, network clients mocked
def test_web_session_with_mocked_scribe_and_featherless(app_main, monkeypatch, tmp_path):
    """listen -> audio -> stop through the real VAD, transcribe(), local ML and translate(); only the Scribe and
    Featherless clients (and the TTS client) are fakes."""
    monkeypatch.setenv("WEB_AUDIO_FALLBACK", "1")
    scribe = FakeScribe()
    tts = np.zeros(1600, dtype=np.int16).tobytes()
    monkeypatch.setattr(app_main, "eleven_client", fake_eleven(scribe, lambda **kw: iter([tts])))
    create, llm_calls = fake_featherless("그녀는 긴 듀스 끝에 첫 세트를 따냈다.")
    monkeypatch.setattr(app_main.llm_client.chat.completions, "create", create)
    monkeypatch.setattr(app_main, "_translation_cache", {})
    monkeypatch.setattr(app_main, "CACHE_DIR", tmp_path)
    (app_main.CACHE_DIR / "tts").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(app_main, "_translation_cache_file", app_main.CACHE_DIR / "translations.json")

    with TestClient(app_main.app) as client:
        with client.websocket_connect("/ws/dashboard" + TOKEN) as dash, \
                client.websocket_connect("/ws/web" + TOKEN) as web:
            web.receive_json()
            dash.send_text(json.dumps({"t": "toggle", "id": "pickleball", "on": False}))
            web.send_text(json.dumps({"t": "mode", "state": "listen"}))
            audio = voice_like(1.2)
            for i in range(0, len(audio), 3200):
                web.send_bytes(audio[i:i + 3200])
            web.send_text(json.dumps({"t": "mode", "state": "stop"}))
            got, deadline = {}, time.time() + 10
            while time.time() < deadline and "utterance" not in got:
                m = dash.receive_json()
                if m["t"] in ("transcript", "utterance", "error"):
                    got[m["t"]] = m
            assert "error" not in got, got.get("error")
            assert got["transcript"]["client"] == "web" and got["transcript"]["lang"] == "english"
            u = got["utterance"]
            assert u["client"] == "web" and u["translation"] == "그녀는 긴 듀스 끝에 첫 세트를 따냈다."
            assert u["domain"] == "tennis" and {t["match"] for t in u["terms"]} >= {"set", "deuce"}
            assert u["timing_ms"]["stt"] >= 0 and "whisper" not in u["timing_ms"]
            played = b""
            while len(played) < len(tts):
                played += web.receive_bytes()
    # what actually went to the services
    assert scribe.calls and "deuce" in scribe.calls[0]["keyterms"]
    prompt = llm_calls[0]["messages"][1]["content"]
    assert llm_calls[0]["model"] == app_main.LLM_MODEL and "Translate into Korean." in prompt
    assert "deuce = 듀스" in prompt and "She won the first set" in prompt


# ------------------------------------------------------------------ Sentry tags
@pytest.fixture
def sentry_events(app_main):
    """Sentry with the app's own settings (main.init_sentry), sending to a list instead of the network."""
    events = []

    class Collect(sentry_sdk.transport.Transport):
        def capture_envelope(self, envelope):
            for item in envelope.items:
                if item.type in ("event", "transaction"):
                    events.append(item.payload.json)
    app_main.init_sentry("https://public@example.ingest.sentry.io/1", transport=Collect, traces_sample_rate=1.0)
    yield events
    sentry_sdk.init()  # back to off


def tags_of(event):
    t = event.get("tags") or {}
    return dict(t) if isinstance(t, list) else t


def test_tts_failure_in_web_session_reaches_sentry_tagged_client_web(app_main, monkeypatch, sentry_events, tmp_path):
    monkeypatch.setenv("WEB_AUDIO_FALLBACK", "1")
    monkeypatch.setattr(app_main, "translate", lambda *a, **k: ("안녕하세요.", False))

    def broken_tts(**kw):
        raise RuntimeError("quota_exceeded")
    monkeypatch.setattr(app_main, "eleven_client", fake_eleven(FakeScribe(text="Hello there.", code="eng"), broken_tts))
    monkeypatch.setattr(app_main, "CACHE_DIR", tmp_path)  # empty cache: the TTS call really happens
    (tmp_path / "tts").mkdir()

    with TestClient(app_main.app) as client:
        with client.websocket_connect("/ws/dashboard" + TOKEN) as dash, \
                client.websocket_connect("/ws/web" + TOKEN) as web:
            web.receive_json()
            web.send_text(json.dumps({"t": "mode", "state": "listen"}))
            audio = voice_like(1.0)
            for i in range(0, len(audio), 3200):
                web.send_bytes(audio[i:i + 3200])
            web.send_text(json.dumps({"t": "mode", "state": "stop"}))
            deadline = time.time() + 10
            while time.time() < deadline:
                m = dash.receive_json()
                if m["t"] == "error":
                    assert m["client"] == "web" and "quota_exceeded" in m["msg"]
                    break
    sentry_sdk.flush()
    errors = [e for e in sentry_events if e.get("type") != "transaction"]
    assert len(errors) == 1, "reported once, not again by the worker"
    assert tags_of(errors[0]).get("step") == "elevenlabs" and tags_of(errors[0]).get("client") == "web"
    traces = [e for e in sentry_events if e.get("type") == "transaction"]
    assert traces and tags_of(traces[0]).get("client") == "web"
    assert [s["op"] for s in traces[0]["spans"]][:2] == ["pipeline.speech_to_text", "pipeline.local_ml"]
