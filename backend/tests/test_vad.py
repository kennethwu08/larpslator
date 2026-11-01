"""Voice detection: a sentence ends ~0.4 s after the speaker stops, even with background noise, and noise alone
never becomes a sentence."""
import numpy as np

from test_web_audio import voice_like

SR, CHUNK = 16000, 3200  # the browser sends 100 ms chunks


def noise(seconds: float, rms: float, seed: int = 0) -> bytes:
    return (np.random.default_rng(seed).normal(0, rms, int(SR * seconds))).clip(-32768, 32767).astype(np.int16).tobytes()


def ms_until_sentence(seg, after: bytes) -> int | None:
    """Feeds `after` in 100 ms chunks; ms of it consumed when the sentence came out (None = never)."""
    for i in range(0, len(after), CHUNK):
        if seg.add(after[i:i + CHUNK]):
            return (i + CHUNK) * 1000 // (SR * 2)
    return None


def test_sentence_ends_within_half_a_second_of_silence(app_main):
    seg = app_main.Segmenter()
    assert seg.add(voice_like(1.5)) == []
    assert ms_until_sentence(seg, b"\0" * SR * 2) <= 500


def test_sentence_ends_quickly_even_with_background_noise(app_main):
    seg = app_main.Segmenter()
    seg.add(noise(2, 300))                       # a noisy room before anyone talks
    speech = np.frombuffer(voice_like(1.5), np.int16).astype(np.int32)
    talk = np.frombuffer(noise(1.5, 300, seed=1), np.int16) + speech
    assert seg.add(talk.clip(-32768, 32767).astype(np.int16).tobytes()) == []
    assert ms_until_sentence(seg, noise(3, 300, seed=2)) <= 600


def test_steady_noise_alone_is_never_a_sentence(app_main):
    # (A sudden jump in the noise level can still make one sentence before the gate adapts, ~1.5 s; speech to
    # text then usually hears nothing, and empty transcripts are skipped.)
    for level in (150, 400, 1200, 3000):
        seg = app_main.Segmenter()
        assert ms_until_sentence(seg, noise(4, level, seed=level)) is None, level
        assert seg.flush() is None


def test_short_bumps_are_ignored(app_main):
    seg = app_main.Segmenter()
    click = (np.ones(480) * 8000).astype(np.int16).tobytes()  # one 30 ms bump
    assert ms_until_sentence(seg, b"\0" * 6400 + click + b"\0" * SR * 2) is None
