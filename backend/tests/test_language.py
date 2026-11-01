"""English is the primary language: other languages are translated into English, English into the chosen one."""
import pytest


@pytest.mark.parametrize("spoken, text, expected", [
    ("tamil", "வணக்கம், எப்படி இருக்கிறீர்கள்?", "English"),
    ("korean", "안녕하세요, 잘 지내세요?", "English"),
    ("english", "Hello, how are you?", "Korean"),
    ("", "Hello, how are you?", "Korean"),  # language not detected: treated as English
])
def test_target_language(app_main, monkeypatch, spoken, text, expected):
    asked = []
    monkeypatch.setattr(app_main, "transcribe", lambda pcm, keyterms=None: (text, spoken))
    monkeypatch.setattr(app_main, "translate", lambda t, target, *a, **k: (asked.append(target) or "ok", False))
    monkeypatch.setattr(app_main, "synthesize", lambda text, tone, voice_id="": (b"\0\0", False))
    r = app_main.run_pipeline(b"\0" * 3200, "Korean", "")
    assert r["target"] == expected and asked == [expected]


def test_english_is_not_a_choice(app_main):
    assert "English" not in app_main.LANGUAGES
