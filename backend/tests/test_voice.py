"""Each device speaks in its own voice: a clone set up on one browser is never used for another device's sentences."""
import json
import time

import numpy as np
from fastapi.testclient import TestClient

from test_web_audio import TOKEN, voice_like

MINE = "VoiceOfDeviceA123"


def say_one_sentence(web, dash):
    web.send_text(json.dumps({"t": "mode", "state": "listen"}))
    audio = voice_like(1.2)
    for i in range(0, len(audio), 3200):
        web.send_bytes(audio[i:i + 3200])
    web.send_text(json.dumps({"t": "mode", "state": "stop"}))
    deadline = time.time() + 10
    while time.time() < deadline:
        m = dash.receive_json()
        assert m["t"] != "error", m
        if m["t"] == "utterance":
            assert "voice_id" not in m  # not sent to dashboards
            return


def test_a_voice_belongs_to_the_device_that_set_it_up(app_main, monkeypatch):
    monkeypatch.delenv("WEB_AUDIO_FALLBACK", raising=False)
    monkeypatch.setattr(app_main, "transcribe", lambda pcm, keyterms=None: ("Hello there.", "english"))
    monkeypatch.setattr(app_main, "translate", lambda *a, **k: ("안녕하세요.", False))
    voices = []
    tts = np.zeros(800, dtype=np.int16).tobytes()
    monkeypatch.setattr(app_main, "synthesize", lambda text, tone, voice_id="": (voices.append(voice_id) or tts, False))

    with TestClient(app_main.app) as client:
        with client.websocket_connect("/ws/dashboard" + TOKEN) as dash:
            with client.websocket_connect(f"/ws/web{TOKEN}&voice={MINE}") as a:
                a.receive_json()
                say_one_sentence(a, dash)
            with client.websocket_connect("/ws/web" + TOKEN) as b:   # someone else's phone, no voice set up
                b.receive_json()
                say_one_sentence(b, dash)
                b.send_text(json.dumps({"t": "my_voice", "id": "bad id!"}))  # junk is ignored
                time.sleep(0.6)  # the mic is muted until just after the translation finished playing
                say_one_sentence(b, dash)
    assert voices == [MINE, "", ""]  # "" = the standard voice


def test_forgetting_only_deletes_clones_made_here(app_main, monkeypatch, tmp_path):
    monkeypatch.setattr(app_main, "CLONES_FILE", tmp_path / "clones.json")
    (tmp_path / "clones.json").write_text(json.dumps([MINE]))
    deleted = []
    monkeypatch.setattr(app_main.eleven_client.voices, "delete", lambda vid: deleted.append(vid))
    with TestClient(app_main.app) as client:
        assert client.delete(f"/api/voice/{MINE}" + TOKEN).status_code == 200
        assert client.delete("/api/voice/SomeoneElsesVoice1" + TOKEN).status_code == 200
    assert deleted == [MINE] and app_main.clones_made_here() == []


def test_clone_request_sends_labels_as_a_dict(app_main, monkeypatch, tmp_path):
    """The SDK sends labels="null" when they're left out, and ElevenLabs answers 400 invalid_labels."""
    monkeypatch.setattr(app_main, "CLONES_FILE", tmp_path / "clones.json")
    sent = {}

    def fake_request(path, method, data=None, files=None, **kw):
        sent.update(data)
        raise RuntimeError("stop before the network")
    monkeypatch.setattr(app_main.eleven_client.voices.ivc._raw_client._client_wrapper.httpx_client, "request", fake_request)
    try:
        app_main.create_clone("Kenneth", b"RIFF")
    except RuntimeError:
        pass
    assert json.loads(sent["labels"]) == {}


def test_a_sentence_can_be_replayed_any_number_of_times(app_main):
    app_main.state.utterances[7] = {"id": 7, "audio": b"\1\0" * 1600}
    with TestClient(app_main.app) as client:
        for _ in range(3):
            r = client.get("/api/utterance/7/audio" + TOKEN)
            assert r.status_code == 200 and r.headers["content-type"] == "audio/wav" and r.content[:4] == b"RIFF"
        assert client.get("/api/utterance/8/audio" + TOKEN).status_code == 404
        assert client.get("/api/utterance/7/audio", headers={"cf-connecting-ip": "1.2.3.4"}).status_code == 401
