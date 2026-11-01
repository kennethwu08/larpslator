"""The badge's audio path after the audio-client refactor (it now shares feed_audio/play_to with the browser)."""
import json
import time

import numpy as np
from fastapi.testclient import TestClient

from test_web_audio import TOKEN, voice_like


def test_badge_sentence_is_translated_and_played_back_to_the_badge(app_main, monkeypatch):
    monkeypatch.setenv("WEB_AUDIO_FALLBACK", "0")  # badge works with browser audio off
    monkeypatch.setattr(app_main, "transcribe", lambda pcm, prompt="": ("Can you merge my branch?", "english"))
    monkeypatch.setattr(app_main, "translate", lambda *a, **k: ("제 브랜치를 병합해 줄 수 있나요?", False))
    tts = (np.arange(1600) % 100).astype(np.int16).tobytes()
    monkeypatch.setattr(app_main, "synthesize", lambda text, tone, voice_id="": (tts, False))

    with TestClient(app_main.app) as client:
        with client.websocket_connect("/ws/dashboard" + TOKEN) as dash, \
                client.websocket_connect("/ws/badge" + TOKEN) as badge:
            badge.send_text(json.dumps({"t": "hello", "id": "TEST-BADGE"}))
            dash.send_text(json.dumps({"t": "mode", "state": "listen"}))
            time.sleep(0.2)  # the hello and listen are handled before audio arrives
            audio = voice_like(1.2)
            for i in range(0, len(audio), 1024):  # the badge's 512-sample frames
                badge.send_bytes(audio[i:i + 1024])
            dash.send_text(json.dumps({"t": "mode", "state": "stop"}))  # Stop ends the sentence right away

            utt, deadline = None, time.time() + 10
            while time.time() < deadline and not utt:
                m = dash.receive_json()
                assert m["t"] != "error", m
                if m["t"] == "utterance":
                    utt = m
            assert utt["client"] == "badge" and utt["client_id"] == "TEST-BADGE"
            assert utt["translation"] == "제 브랜치를 병합해 줄 수 있나요?"

            played = b""
            while len(played) < len(tts):
                msg = badge.receive()
                if msg.get("bytes"):
                    played += msg["bytes"]
            assert played == tts


def test_badge_audio_ignored_while_not_listening(app_main, monkeypatch):
    calls = []
    monkeypatch.setattr(app_main, "transcribe", lambda pcm, prompt="": (calls.append(1) or "x", "english"))
    with TestClient(app_main.app) as client:
        with client.websocket_connect("/ws/badge" + TOKEN) as badge:
            badge.send_text(json.dumps({"t": "hello", "id": "TEST-QUIET"}))
            audio = voice_like(1.5)
            for i in range(0, len(audio), 1024):
                badge.send_bytes(audio[i:i + 1024])
            badge.send_bytes(b"\0" * 32000)  # 1 s of silence would end a sentence if one had started
            time.sleep(0.5)
    assert calls == []
