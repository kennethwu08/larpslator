"""Test setup: placeholder API keys (set before main is imported, so the real .env can't fill them in) and a fixed
pairing code. No test calls a real API: speech to text (Scribe), the LLM (Featherless) and ElevenLabs voice are
replaced per test."""
import os
import sys
from pathlib import Path

import pytest

for key in ("FEATHERLESS_API_KEY", "ELEVENLABS_API_KEY"):
    os.environ[key] = "test-placeholder"
os.environ["SENTRY_DSN"] = ""
os.environ["LARPSLATOR_TOKEN"] = "testcode"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main  # noqa: E402


@pytest.fixture
def app_main(monkeypatch):
    """main with the network stubbed out (no LLM warm-up call at startup) and a fresh server state, so one
    test's sentences/clients don't leak into the next (the dashboard socket replays recent sentences)."""
    monkeypatch.setattr(main, "warm_up_llm", lambda: None)
    monkeypatch.setattr(main, "state", main.State())
    return main
