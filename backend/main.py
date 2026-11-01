"""Larpslator backend: badge audio -> VAD -> Whisper -> local ML -> Featherless LLM -> ElevenLabs -> badge.

The LLM only translates (and, in LARP mode, polishes in the same call). Field detection,
tone, jargon choice, context trimming, LARP phrase upgrades and learning from feedback
all run locally (ml.py), so they cost nothing.

Run:  uvicorn main:app --host 0.0.0.0 --port 8000   (from the backend/ folder)
"""
import asyncio
import contextlib
import hashlib
import io
import json
import logging
import os
import math
import re
import secrets
import socket
import time
import wave
from contextlib import asynccontextmanager, contextmanager
from urllib.parse import urlparse
from pathlib import Path

import numpy as np
import sentry_sdk
import webrtcvad
from dotenv import load_dotenv
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from openai import OpenAI

HERE = Path(__file__).parent
load_dotenv(HERE.parent / ".env")
load_dotenv(HERE / ".env")  # a backend/.env also works (doesn't override the root one)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("larpslator")

# Sentry (on when SENTRY_DSN is set): unhandled FastAPI errors are captured automatically; pipeline failures are
# reported with a "step" tag (whisper / translation / elevenlabs / ...) so each failing service is its own issue,
# and each sentence is a trace with one span per stage. Without a DSN all sentry_sdk calls are no-ops.
if os.getenv("SENTRY_DSN"):
    from sentry_sdk.integrations.logging import LoggingIntegration
    sentry_sdk.init(dsn=os.environ["SENTRY_DSN"], environment=os.getenv("SENTRY_ENVIRONMENT") or "local",
                    traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE") or 0.2), send_default_pii=False,
                    # Log lines become breadcrumbs, not issues: errors are reported once, with their step tag.
                    integrations=[LoggingIntegration(level=logging.INFO, event_level=None)])
    log.info("Sentry on (%s)", os.getenv("SENTRY_ENVIRONMENT") or "local")


def report(e: Exception, step: str = "", **context):
    """Send a handled error to Sentry, tagged with the pipeline step. Each exception is reported once."""
    if getattr(e, "_larp_reported", False):
        return
    with sentry_sdk.new_scope() as scope:
        if step:
            scope.set_tag("step", step)
        for k, v in context.items():
            scope.set_extra(k, v)
        sentry_sdk.capture_exception(e)
    try:
        e._larp_reported = True
    except AttributeError:
        pass


def warn(message: str, step: str, **context):
    """A problem that didn't stop the sentence (e.g. the fallback LLM had to be used)."""
    with sentry_sdk.new_scope() as scope:
        scope.set_tag("step", step)
        for k, v in context.items():
            scope.set_extra(k, v)
        sentry_sdk.capture_message(message, level="warning")


@contextmanager
def stage(name: str):
    """One pipeline step: a span in the sentence's trace, and its errors reported with the step's name."""
    with sentry_sdk.start_span(op=f"pipeline.{name}", name=name):
        try:
            yield
        except Exception as e:
            report(e, step=name)
            raise

# ---------------------------------------------------------------- config
SAMPLE_RATE = 16000
FRAME_MS = 30                                      # webrtcvad accepts 10/20/30 ms frames
FRAME_BYTES = SAMPLE_RATE * FRAME_MS // 1000 * 2   # 960 bytes of 16-bit mono
SILENCE_END_MS = 700                               # this much silence ends a sentence
PREROLL_MS = 300                                   # audio kept from before speech starts
MIN_SPEECH_MS = 400                                # shorter blips are dropped (Whisper hallucinates on them)
MAX_SENTENCE_MS = 15000                            # force a cut on very long speech
RESUME_AFTER_PLAYBACK_S = 0.3                      # badge unmutes this long after playback ends
SEND_CHUNK_BYTES = 3200                            # 100 ms of audio per WebSocket frame

# Translation LLM on Featherless (OpenAI-compatible API). Picked by benchmark on Nov 1: Mistral Small 3.2 made no
# wrong-language replies in 12 test sentences at ~1.4 s; Qwen 2.5 7B/14B drifted into English/Chinese on Korean.
LLM_MODEL = os.getenv("FEATHERLESS_MODEL") or "mistralai/Mistral-Small-3.2-24B-Instruct-2506"
LLM_FALLBACK = os.getenv("FEATHERLESS_FALLBACK_MODEL") or "mistralai/Mistral-Nemo-Instruct-2407"
# Characters each target language must (or must not) contain, to catch replies in the wrong language.
HANGUL, HAN, KANA, TAMIL = r"[\uac00-\ud7a3]", r"[\u4e00-\u9fff]", r"[\u3040-\u30ff]", r"[\u0b80-\u0bff]"
SCRIPT_RULES = {  # target: (must contain, must not contain)
    "Korean": (HANGUL, HAN), "Japanese": (KANA, HANGUL), "Mandarin Chinese": (HAN, HANGUL + "|" + KANA),
    "Tamil": (TAMIL, HAN + "|" + HANGUL),
}
LATIN_FORBIDDEN = HAN + "|" + HANGUL + "|" + KANA     # Spanish, French, German, English...
TTS_MODEL = os.getenv("ELEVENLABS_MODEL") or "eleven_flash_v2_5"
STOCK_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # premade ElevenLabs voice, used only until the user's voice is set up
MIN_SAMPLE_SPEECH_S = 20                 # voice setup: least speech accepted; ~60 s sounds much more like you
MAX_SAMPLE_S = 120
DEFAULT_TARGET = os.getenv("TARGET_LANGUAGE") or "Korean"

LANGUAGES = ["Korean", "Spanish", "French", "Mandarin Chinese", "Japanese", "German", "English"]
# Lower stability = more expressive; higher style = more exaggerated delivery.
TONE_SETTINGS = {
    "neutral":  {"stability": 0.50, "style": 0.00},
    "excited":  {"stability": 0.30, "style": 0.60},
    "calm":     {"stability": 0.75, "style": 0.00},
    "serious":  {"stability": 0.65, "style": 0.20},
    "question": {"stability": 0.40, "style": 0.30},
    "confident": {"stability": 0.45, "style": 0.45},  # LARP mode
}

CONTEXT_DIR = HERE / "contexts"
LOG_DIR = HERE / "logs"
CACHE_DIR = HERE / "cache"
for d in (CONTEXT_DIR, LOG_DIR, CACHE_DIR / "tts"):
    d.mkdir(parents=True, exist_ok=True)

missing = [k for k in ("OPENAI_API_KEY", "FEATHERLESS_API_KEY", "ELEVENLABS_API_KEY") if not os.getenv(k)]
if missing:
    raise SystemExit(f"Missing in .env: {', '.join(missing)} (see .env.example in the repo root)")

openai_client = OpenAI()  # reads OPENAI_API_KEY
# Featherless speaks the OpenAI API, so the same SDK works with a different base URL.
llm_client = OpenAI(api_key=os.getenv("FEATHERLESS_API_KEY"), base_url="https://api.featherless.ai/v1",
                    timeout=25, max_retries=1)
eleven_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

from ml import FIELDS, STYLES, LocalML  # noqa: E402  (slow import: loads torch)
ML = LocalML()


# ---------------------------------------------------------------- VAD
class Segmenter:
    """Feeds raw PCM through webrtcvad and returns finished sentences as PCM bytes."""

    def __init__(self, aggressiveness: int = 2):
        self.vad = webrtcvad.Vad(aggressiveness)
        self.reset()

    def reset(self):
        self.buf = b""
        self.preroll: list[bytes] = []
        self.frames: list[bytes] = []
        self.in_speech = False
        self.silence_ms = 0
        self.speech_ms = 0
        self.vad_s = 0.0  # CPU time spent in VAD for the current sentence

    def add(self, pcm: bytes) -> list[tuple[bytes, float]]:
        """Returns a list of (sentence_pcm, vad_seconds)."""
        self.buf += pcm
        done = []
        while len(self.buf) >= FRAME_BYTES:
            frame, self.buf = self.buf[:FRAME_BYTES], self.buf[FRAME_BYTES:]
            t = time.perf_counter()
            speech = self.vad.is_speech(frame, SAMPLE_RATE)
            self.vad_s += time.perf_counter() - t

            if not self.in_speech:
                self.preroll = (self.preroll + [frame])[-(PREROLL_MS // FRAME_MS):]
                if speech:
                    self.in_speech = True
                    self.frames = list(self.preroll)
                    self.speech_ms = self.silence_ms = 0
                continue

            self.frames.append(frame)
            if speech:
                self.speech_ms += FRAME_MS
                self.silence_ms = 0
            else:
                self.silence_ms += FRAME_MS
            if self.silence_ms >= SILENCE_END_MS or len(self.frames) * FRAME_MS >= MAX_SENTENCE_MS:
                if sentence := self._finish():
                    done.append(sentence)
        return done

    def flush(self) -> tuple[bytes, float] | None:
        """End the current sentence now (end of file, or push-to-talk released)."""
        return self._finish() if self.in_speech else None

    def _finish(self) -> tuple[bytes, float] | None:
        pcm, speech_ms, vad_s = b"".join(self.frames), self.speech_ms, self.vad_s
        self.in_speech, self.frames, self.preroll, self.vad_s = False, [], [], 0.0
        if speech_ms < MIN_SPEECH_MS:
            return None
        return pcm, vad_s


# ---------------------------------------------------------------- pipeline stages
def pcm_to_wav(pcm: bytes) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return out.getvalue()


def transcribe(pcm: bytes, prompt: str = "") -> tuple[str, str]:
    """Returns (text, detected_language). The prompt lists jargon so Whisper spells it right."""
    r = openai_client.audio.transcriptions.create(
        model="whisper-1",
        file=("speech.wav", pcm_to_wav(pcm), "audio/wav"),
        response_format="verbose_json",
        prompt=prompt,
    )
    return r.text.strip(), (getattr(r, "language", "") or "").lower()


def same_language(whisper_lang: str, target: str) -> bool:
    # Whisper says "english", "korean", "chinese"...; targets are "English", "Mandarin Chinese"...
    return bool(whisper_lang) and whisper_lang in target.lower()


_translation_cache_file = CACHE_DIR / "translations.json"
try:
    _translation_cache: dict = json.loads(_translation_cache_file.read_text())
except (OSError, json.JSONDecodeError):
    _translation_cache = {}


def translation_system_prompt(target: str) -> str:
    # The "never write Chinese or English" line stops open models from drifting into commentary.
    other = "" if target in ("Mandarin Chinese", "English") else " Never write Chinese or English."
    return (f"You translate the user's text into {target}. Reply with the {target} translation only, on one line: "
            f"no quotes, notes, explanations or romanization.{other}")


def in_target_language(text: str, target: str) -> bool:
    must, must_not = SCRIPT_RULES.get(target, (None, LATIN_FORBIDDEN))
    if not text or re.search(must_not, text):
        return False
    if must is None:
        return True
    # Non-Latin targets: mostly target script. Some English is fine (names, "API"); a half-translated
    # "SHE won the first 세트 after a long 듀스 game." is not.
    native, latin = len(re.findall(must, text)), len(re.findall(r"[A-Za-z]", text))
    return native > 0 and latin <= 0.4 * (native + latin)


def translate(text: str, target: str, terms: list[dict], context_lines: list[str],
              style: str = "") -> tuple[str, bool]:
    """The only LLM call: a short plain-text translation request. Returns (translation, cached).

    `style` is the LARP instruction; it rides along in the same request, no extra call.
    Tries LLM_MODEL, then LLM_FALLBACK if it errors or answers in the wrong language."""
    system = translation_system_prompt(target)
    lines = [f"Translate into {target}."]
    if style:
        lines.append(style)
    if terms:
        lines.append("Use these term translations: " + "; ".join(f"{t['match']} = {t['choice']}" for t in terms))
    if context_lines:
        lines.append("Context: " + "; ".join(context_lines))
    lines.append(f"Text: {text}")
    prompt = "\n".join(lines)

    key = hashlib.sha1(f"{LLM_MODEL}\n{system}\n{prompt}".encode()).hexdigest()
    if key in _translation_cache:
        return _translation_cache[key], True

    problem = "no model tried"
    for model in dict.fromkeys([LLM_MODEL, LLM_FALLBACK]):  # dedupe if both are the same
        try:
            r = llm_client.chat.completions.create(
                model=model, temperature=0, max_tokens=400,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            )
        except Exception as e:
            problem = f"{model}: {type(e).__name__}: {e}"
            log.warning("LLM %s", problem)
            continue
        out = clean_output(r.choices[0].message.content or "", target)
        if in_target_language(out, target):
            if model != LLM_MODEL:
                log.info("translated by fallback model %s", model)
                warn(f"Translation used the fallback model ({problem[:120]})", "translation", target=target)
            _translation_cache[key] = out
            _translation_cache_file.write_text(json.dumps(_translation_cache, ensure_ascii=False))
            return out, False
        problem = f"{model} answered in the wrong language: {out[:80]!r}"
        log.warning("LLM %s", problem)
    raise RuntimeError(f"translation failed ({problem})")


def warm_up_llm():
    """Featherless loads a model on first use (several seconds); do that at startup, not on the first sentence."""
    t = time.perf_counter()
    try:
        translate("Hello.", DEFAULT_TARGET, [], [])
        log.info("LLM %s warmed up in %.1f s", LLM_MODEL, time.perf_counter() - t)
    except Exception as e:
        log.warning("LLM warm-up failed (translations will retry): %s", e)


def clean_output(text: str, target: str = "") -> str:
    """Models sometimes add a label, quotes, reasoning or a note; keep just the translation line."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if target:  # prefer the first line that's actually in the target language
        lines = [l for l in lines if in_target_language(l, target)] or lines
    text = lines[0] if lines else ""
    text = re.sub(r"^(translation|번역|traducción)\s*[:：]\s*", "", text, flags=re.IGNORECASE)
    if len(text) >= 2 and text[0] in "\"'“「" and text[-1] in "\"'”」":
        text = text[1:-1].strip()
    return text


# ---------------------------------------------------------------- the user's voice
class Voice:
    """Whose voice ElevenLabs speaks in: the user's own clone once voice setup is done.

    Saved to state/voice.json. ELEVENLABS_VOICE_ID in .env is used if no setup was done here
    (e.g. on Render, whose disk is wiped on restart). Otherwise a stock voice, flagged on the dashboard.
    """
    FILE = HERE / "state" / "voice.json"

    def __init__(self):
        try:
            saved = json.loads(self.FILE.read_text())
        except (OSError, json.JSONDecodeError):
            saved = {}
        env_id = os.getenv("ELEVENLABS_VOICE_ID")
        self.id = saved.get("voice_id") or env_id or STOCK_VOICE_ID
        self.name = saved.get("name") or ("from .env" if env_id else "")
        self.created_here = bool(saved.get("voice_id"))   # only clones made here get deleted on re-setup

    @property
    def is_users(self) -> bool:
        return self.id != STOCK_VOICE_ID

    def info(self) -> dict:
        return {"ready": self.is_users, "name": self.name, "voice_id": self.id}

    def clone(self, name: str, wav: bytes) -> dict:
        """ElevenLabs Instant Voice Clone from a WAV recording. Replaces the previous clone made here."""
        r = eleven_client.voices.ivc.create(
            name=f"Larpslator - {name}", files=[("voice-setup.wav", wav, "audio/wav")],
            remove_background_noise=True, description="Created by Larpslator voice setup",
        )
        if self.created_here and self.id != r.voice_id:
            try:
                eleven_client.voices.delete(self.id)  # free the voice slot
            except Exception as e:
                log.warning("couldn't delete old voice %s: %s", self.id, e)
        self.id, self.name, self.created_here = r.voice_id, name, True
        self.FILE.parent.mkdir(exist_ok=True)
        self.FILE.write_text(json.dumps({"voice_id": self.id, "name": name}))
        log.info("voice setup done: %r -> %s", name, self.id)
        return self.info()


VOICE = Voice()
if not VOICE.is_users:
    log.warning("no user voice yet: translations use a stock voice until voice setup is done on the dashboard")


def synthesize(text: str, tone: str) -> tuple[bytes, bool]:
    """Returns (16 kHz 16-bit mono PCM, cached), spoken in the user's voice. Repeats cost no credits."""
    s = TONE_SETTINGS.get(tone, TONE_SETTINGS["neutral"])
    if TTS_MODEL.startswith("eleven_v3") and tone != "neutral":
        text = f"[{tone}] {text}"  # only v3 understands audio tags; other models would read them aloud
    voice_id = VOICE.id
    path = CACHE_DIR / "tts" / (hashlib.sha1(f"{voice_id}|{TTS_MODEL}|{tone}|{text}".encode()).hexdigest() + ".pcm")
    if path.exists():
        return path.read_bytes(), True
    audio = b"".join(eleven_client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id=TTS_MODEL,   # flash v2.5 is multilingual, so the clone speaks Korean/Spanish in your voice
        output_format="pcm_16000",
        voice_settings=VoiceSettings(
            # High similarity so it sounds like the user rather than a generic voice.
            stability=s["stability"], style=s["style"], similarity_boost=0.9, use_speaker_boost=True
        ),
    ))
    path.write_bytes(audio)
    return audio, False


def translate_and_speak(r: dict, timing: dict):
    """LLM + ElevenLabs for an analyzed sentence. Fills r["translation"] and r["audio"]."""
    t = time.perf_counter()
    larp = r.get("larp")
    with stage("translation"):
        if not larp and same_language(r["lang"], r["target"]):
            r["translation"], cached = r["source"], True   # nothing to translate: no LLM call
        else:
            text = larp["text"] if larp else r["source"]   # LARP: send the locally upgraded wording
            style = ML.larp_instruction(r["domain"]) if larp else ""
            r["translation"], cached = translate(text, r["target"], r["terms"], r["context_lines"], style)
    timing["llm"] = 0 if cached else round((time.perf_counter() - t) * 1000)

    t = time.perf_counter()
    with stage("elevenlabs"):
        r["audio"], cached = synthesize(r["translation"], r["tone"])
    timing["elevenlabs"] = 0 if cached else round((time.perf_counter() - t) * 1000)
    timing["total"] = round(sum(v for k, v in timing.items() if k != "total"))


def run_pipeline(pcm: bytes, target: str, context: str, vad_s: float = 0.0,
                 active: set[str] | None = None, on_transcript=None) -> dict:
    """Runs one sentence through every stage. Raises on API errors; callers decide to skip.

    `active` is the set of checked contexts (fields and "larp"); default: all fields, no LARP.
    Returns {"source", "lang", "target", "domain", "domain_probs", "tone", "terms",
             "context_lines", "larp", "translation", "audio", "timing_ms"}. Cached stages report 0 ms.
    """
    active = set(FIELDS) if active is None else active
    timing = {"vad": round(vad_s * 1000, 1)}
    with sentry_sdk.start_transaction(op="utterance", name="translate sentence") as tx:
        tx.set_tag("target", target)
        t = time.perf_counter()
        with stage("whisper"):
            source, lang = transcribe(pcm, ML.whisper_prompt(active))
        timing["whisper"] = round((time.perf_counter() - t) * 1000)
        r = {"source": source, "lang": lang, "target": target, "translation": "", "audio": b"", "timing_ms": timing}
        if not source:
            return r
        if on_transcript:
            on_transcript(source, lang)

        t = time.perf_counter()
        with stage("local_ml"):
            r.update(ML.analyze(source, target, context, active))
        timing["ml"] = round((time.perf_counter() - t) * 1000)
        tx.set_tag("domain", r["domain"])

        translate_and_speak(r, timing)
        return r


def retranslate(r: dict, timing: dict):
    """The thumbs-down replay, as its own trace."""
    with sentry_sdk.start_transaction(op="utterance", name="retry after feedback"):
        translate_and_speak(r, timing)


# ---------------------------------------------------------------- context packs + feedback
def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "untitled"


def save_context(name: str, text: str) -> dict:
    pack = {"name": name, "text": text, "saved_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (CONTEXT_DIR / f"{slug(name)}.json").write_text(json.dumps(pack, indent=2, ensure_ascii=False))
    return pack


def list_contexts() -> list[dict]:
    packs = []
    for p in CONTEXT_DIR.glob("*.json"):
        try:
            packs.append(json.loads(p.read_text()))
        except (OSError, json.JSONDecodeError):
            log.warning("skipping unreadable context pack %s", p.name)
    return sorted(packs, key=lambda p: p.get("saved_at", ""), reverse=True)


def log_feedback(val: int, utt: dict | None):
    entry = {"ts": time.time(), "val": val, "id": utt and utt["id"], "source": utt and utt["source"],
             "translation": utt and utt["translation"],
             "terms": utt and {t["term"]: t["choice"] for t in utt["terms"]}}
    with open(LOG_DIR / "feedback.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    log.info("feedback %+d on utterance %s", val, entry["id"])


# ---------------------------------------------------------------- badges
BADGE_PING_S = 5           # heartbeat: latency + battery refresh; dead sockets are closed by uvicorn's own pings
BADGE_INFO_KEYS = {"name", "fw", "battery", "rssi", "volume", "playing", "muted", "ip", "mac", "uptime_s", "free_heap"}
MAX_AUDIO_FRAME = 32768    # bytes; anything bigger is not a mic frame (the badge sends ~1 KB)


def lan_ip() -> str:
    """This laptop's address on the current network (hotspot), for the badge's config.h."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # sends nothing; just picks the outgoing interface
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


class Badge:
    """One badge on /ws/badge. Whatever it reports about itself (all optional) goes in `info`."""

    def __init__(self, ws: WebSocket, n: int):
        self.ws = ws
        self.id = f"badge-{n}"               # replaced by the id the badge sends in hello
        self.info = {"ip": ws.client.host if ws.client else ""}
        self.connected_at = time.time()
        self.last_seen = time.monotonic()
        self.rtt_ms: int | None = None
        self.config_ack: int | None = None   # last config version the badge confirmed
        self.ping_sent = 0.0
        self.carry = b""          # odd byte left over from the last frame (keeps 16-bit samples aligned)
        self.audio_bytes = 0      # since the last heartbeat
        self.peak_rms = 0.0
        self.mic_kbps: int | None = None
        self.mic_level_db: float | None = None
        self.audio_dropped = 0

    def take_audio(self, data: bytes) -> bytes:
        """Check a mic frame: drop oversized ones, keep samples aligned, measure rate and loudness."""
        if len(data) > MAX_AUDIO_FRAME:
            self.audio_dropped += 1
            return b""
        data = self.carry + data
        self.carry, data = (data[-1:], data[:-1]) if len(data) % 2 else (b"", data)
        if data:
            self.audio_bytes += len(data)
            samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
            self.peak_rms = max(self.peak_rms, float(np.sqrt(np.mean(samples * samples))))
        return data

    def roll_audio_stats(self, seconds: float):
        """Heartbeat: turn the counters into kbps (16 kHz 16-bit mono = 256) and a level in dBFS."""
        self.mic_kbps = round(self.audio_bytes * 8 / 1000 / seconds)
        self.mic_level_db = round(20 * math.log10(self.peak_rms / 32768), 1) if self.peak_rms > 1 else None
        self.audio_bytes, self.peak_rms = 0, 0.0

    def report(self, msg: dict):
        """Keep the fields the badge reports about itself (known keys, short scalar values)."""
        for k in BADGE_INFO_KEYS & msg.keys():
            v = msg[k]
            if isinstance(v, (int, float, bool)) or v is None:
                self.info[k] = v
            elif isinstance(v, str):
                self.info[k] = v[:60]
        if isinstance(msg.get("config_v"), int):
            self.config_ack = msg["config_v"]

    def public(self, active: bool, config_v: int) -> dict:
        return {"id": self.id, "active": active, **self.info, "rtt_ms": self.rtt_ms,
                "seen_s_ago": round(time.monotonic() - self.last_seen, 1),
                "online_s": round(time.time() - self.connected_at),
                "config_synced": self.config_ack == config_v,
                "mic_kbps": self.mic_kbps, "mic_level_db": self.mic_level_db, "audio_dropped": self.audio_dropped}


# ---------------------------------------------------------------- pairing (who may connect)
# Devices other than this laptop (badge, phone, other laptops) need the pairing code: as ?token=... on the URL or
# an X-Larpslator-Token header. Set LARPSLATOR_TOKEN to choose it; otherwise one is made once and saved.
PAIRING_FILE = HERE / "state" / "pairing.json"
CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"   # no 0/o/1/l/i, easy to type on a phone


def load_pairing_code() -> str:
    if os.getenv("LARPSLATOR_TOKEN"):
        return os.environ["LARPSLATOR_TOKEN"]
    try:
        return json.loads(PAIRING_FILE.read_text())["code"]
    except (OSError, json.JSONDecodeError, KeyError):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
        PAIRING_FILE.parent.mkdir(exist_ok=True)
        PAIRING_FILE.write_text(json.dumps({"code": code}))
        return code


PAIRING_CODE = load_pairing_code()


def authorized(conn) -> bool:
    """Request or WebSocket. This laptop's own browser is trusted, unless a web page from somewhere else is
    trying to reach the local server (checked by Origin). Everyone else needs the pairing code."""
    given = conn.query_params.get("token") or conn.headers.get("x-larpslator-token") or ""
    if given and secrets.compare_digest(given.encode(), PAIRING_CODE.encode()):
        return True
    host = conn.client.host if conn.client else ""
    if os.getenv("LARPSLATOR_REQUIRE_TOKEN") or not (host == "::1" or host.startswith("127.")):
        return False
    origin = conn.headers.get("origin")
    return origin in (None, "null") or urlparse(origin).hostname in ("localhost", "127.0.0.1", "::1")


def require_pairing(request: Request):
    if not authorized(request):
        raise HTTPException(401, "pairing code required")


def pairing_info() -> dict:
    ip, port = lan_ip(), os.getenv("PORT") or "8000"
    https = os.getenv("LARPSLATOR_HTTPS_PORT")
    page = f"https://{ip}:{https}" if https else f"http://{ip}:{port}"
    return {"code": PAIRING_CODE, "dashboard_url": f"{page}/?token={PAIRING_CODE}",
            "badge_url": f"ws://{ip}:{port}/ws/badge?token={PAIRING_CODE}"}


# ---------------------------------------------------------------- server state
class State:
    def __init__(self):
        packs = list_contexts()
        self.listening = False
        self.target = DEFAULT_TARGET
        self.active = set(FIELDS)     # checked contexts: fields to choose between, plus "larp"
        self.context_name = packs[0]["name"] if packs else ""
        self.context = packs[0]["text"] if packs else ""   # reuse the most recent pack on restart
        self.badges: dict[str, Badge] = {}      # every badge online, by id
        self.active_badge: str | None = None    # the one the dashboard connected; only its mic and buttons count
        self.badge_seq = 0
        self.badge_names: dict[str, str] = {}   # names given on the dashboard; win over what the badge reports
        self.config_v = 0                       # bumped whenever badge_config() changes
        self.last_config: dict | None = None
        self.dashboards: set[WebSocket] = set()
        self.segmenter = Segmenter()
        self.queue: asyncio.Queue = asyncio.Queue()
        self.mute_until = 0.0         # badge is playing (or just finished) until this time
        self.next_id = 1
        self.utterances: dict[int, dict] = {}
        self.last_id: int | None = None
        self.recording: dict | None = None   # voice setup in progress: {"name", "pcm", "speech_ms", "vad"}

    @property
    def badge(self) -> WebSocket | None:
        """The connected (active) badge's socket, if it's online."""
        b = self.badges.get(self.active_badge or "")
        return b.ws if b else None

    def badge_config(self) -> dict:
        """What the badge should be doing and can show on its LEDs/screen. Pushed whenever it changes."""
        return {"listening": self.listening, "target": self.target,
                "fields": [d for d in FIELDS if d in self.active], "larp": "larp" in self.active,
                "domain": self.badge_mode(), "voice": VOICE.name if VOICE.is_users else "",
                "voice_setup": self.recording is not None}

    def badges_info(self) -> list[dict]:
        out = []
        for b in self.badges.values():
            info = b.public(b.id == self.active_badge, self.config_v)
            if b.id in self.badge_names:
                info["name"] = self.badge_names[b.id]
            out.append(info)
        return out

    def badge_mode(self) -> str:
        fields = [d for d in FIELDS if d in self.active]
        return fields[0] if len(fields) == 1 else "auto"

    def status(self) -> dict:
        contexts = [{"id": k, "label": v, "kind": "field", "on": k in self.active, "source": ML.source[k]}
                    for k, v in FIELDS.items()]
        contexts += [{"id": k, "label": v, "kind": "style", "on": k in self.active, "source": ML.source[k]}
                     for k, v in STYLES.items()]
        return {"t": "status", "listening": self.listening, "target": self.target,
                "contexts": contexts, "badge": self.badge is not None,
                "badges": self.badges_info(), "badge_config": {"v": self.config_v, **self.badge_config()},
                "badge_url": pairing_info()["badge_url"], "pairing": pairing_info(),
                "context_name": self.context_name, "context": self.context,
                "languages": LANGUAGES, "packs": list_contexts(), "voice": VOICE.info(),
                "voice_recording": self.recording and round(self.recording["speech_ms"] / 1000, 1)}


state = State()


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [asyncio.create_task(worker()), asyncio.create_task(badge_heartbeat()),
             asyncio.create_task(asyncio.to_thread(warm_up_llm))]
    log.info("ready: target=%s, llm=%s (fallback %s), tts=%s, context pack=%r",
             state.target, LLM_MODEL, LLM_FALLBACK, TTS_MODEL, state.context_name or None)
    yield
    for task in tasks:
        task.cancel()


app = FastAPI(lifespan=lifespan)
# The dashboard may be opened from another origin (a file, a dev server); let it call /api.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
DASHBOARD_DIR = HERE.parent / "dashboard"


async def broadcast(msg: dict):
    for ws in list(state.dashboards):
        try:
            await ws.send_json(msg)
        except Exception:
            state.dashboards.discard(ws)


async def send_audio_to_badge(pcm: bytes):
    """Sends audio paced at about real time, never overlapping earlier playback."""
    # Wait until the badge has finished the previous clip (plus its resume delay).
    await asyncio.sleep(max(0.0, state.mute_until - time.monotonic()))
    if state.badge is None:
        return
    duration = len(pcm) / (SAMPLE_RATE * 2)
    state.mute_until = time.monotonic() + duration + RESUME_AFTER_PLAYBACK_S
    state.segmenter.reset()  # drop any half-heard sentence; the badge mic is muted now
    for i in range(0, len(pcm), SEND_CHUNK_BYTES):
        chunk = pcm[i:i + SEND_CHUNK_BYTES]
        ws = state.badge
        if ws is None:
            log.warning("badge went offline during playback")
            return
        try:
            await ws.send_bytes(chunk)
        except Exception as e:
            log.warning("playback to badge failed: %s", e)
            report(e, step="badge_playback")
            return
        # Stay slightly ahead of playback so the badge buffer never runs dry or overflows.
        await asyncio.sleep(len(chunk) / (SAMPLE_RATE * 2) * 0.85)


def public(utt: dict) -> dict:
    """Utterance as sent to the dashboard (no audio, no internals)."""
    return {"t": "utterance", **{k: v for k, v in utt.items() if k not in ("audio", "rejected")}}


def log_timing(uid: int, r: dict):
    tm = r["timing_ms"]
    log.info("utt %d | vad %.1fms | whisper %sms | ml %sms | llm %sms | elevenlabs %sms | total %sms | "
             "%s/%s | %r%s -> %r | terms %s",
             uid, tm.get("vad", 0), tm.get("whisper", "-"), tm.get("ml", "-"), tm["llm"], tm["elevenlabs"],
             tm["total"], r["domain"], r["tone"], r["source"],
             f" =larp=> {r['larp']['text']!r}" if r.get("larp") else "", r["translation"],
             {t["match"]: t["choice"] for t in r["terms"]} or "-")


async def process_sentence(pcm: bytes, vad_s: float):
    uid = state.next_id
    state.next_id += 1
    loop = asyncio.get_running_loop()

    def on_transcript(source, lang):  # runs in the pipeline thread; show text before translation finishes
        asyncio.run_coroutine_threadsafe(
            broadcast({"t": "transcript", "id": uid, "source": source, "lang": lang}), loop)

    r = await asyncio.to_thread(run_pipeline, pcm, state.target, state.context, vad_s,
                                set(state.active), on_transcript)
    if not r["source"]:
        log.info("utterance %d: empty transcript, skipped", uid)
        return
    log_timing(uid, r)
    utt = {"id": uid, "retry": 0, "rejected": {}, **r}
    state.utterances[uid] = utt
    state.last_id = uid
    await broadcast(public(utt))
    await send_audio_to_badge(r["audio"])


async def retry_with_next_option(uid: int, blamed: dict):
    """After a thumbs down: same sentence, next-best option for the blamed term, spoken again."""
    utt = state.utterances.get(uid)
    if not utt:
        return
    utt["rejected"].setdefault(blamed["term"], []).append(blamed["choice"])
    terms = ML.find_terms(utt["source"], utt["domain"], utt["target"], utt["rejected"])
    terms = [t for t in terms if t["choice"]]  # a term with no options left falls back to the LLM's choice
    if [t["choice"] for t in terms] == [t["choice"] for t in utt["terms"]]:
        await broadcast({"t": "error", "id": uid, "msg": f"no other translations left for '{blamed['term']}'"})
        return
    r = {**utt, "terms": terms}
    timing = {}
    await asyncio.to_thread(retranslate, r, timing)
    r["timing_ms"], r["retry"] = timing, utt["retry"] + 1
    state.utterances[uid] = r
    log_timing(uid, r)
    await broadcast(public(r))
    await send_audio_to_badge(r["audio"])


async def worker():
    """Processes queued jobs one at a time, in order, so audio never overlaps."""
    while True:
        job = await state.queue.get()
        try:
            if job[0] == "sentence":
                await process_sentence(job[1], job[2])
            elif job[0] == "retry":
                await retry_with_next_option(job[1], job[2])
        except Exception as e:
            log.error("%s skipped: %s: %s", job[0], type(e).__name__, e)
            report(e, step="pipeline")  # no-op if a stage already reported it
            await broadcast({"t": "error", "id": job[1] if job[0] == "retry" else None,
                             "msg": f"{type(e).__name__}: {e}"})


# ---------------------------------------------------------------- control messages
async def send_to_badge(badge: Badge, msg: dict):
    try:
        await badge.ws.send_json(msg)
    except Exception as e:
        log.warning("couldn't reach %s: %s", badge.id, e)


async def sync_badge(force: bool = False):
    """Push the config to the connected badge when it changed (or when forced, e.g. on connect)."""
    cfg = state.badge_config()
    if cfg != state.last_config:
        state.config_v += 1
        state.last_config = cfg
        force = True
    b = state.badges.get(state.active_badge or "")
    if b and force:
        await send_to_badge(b, {"t": "config", "v": state.config_v, **cfg})
        await send_to_badge(b, {"t": "mode", "domain": cfg["domain"]})  # older firmware only knows "mode"


async def state_changed():
    await sync_badge()
    await broadcast(state.status())


async def activate_badge(badge_id: str | None):
    """Make this badge the connected one (None = none). The others stay online but are ignored."""
    previous = state.badges.get(state.active_badge or "")
    state.active_badge = badge_id
    state.segmenter.reset()
    state.mute_until = 0.0
    if previous and previous.id != badge_id:
        await send_to_badge(previous, {"t": "active", "value": False})
    if badge := state.badges.get(badge_id or ""):
        log.info("connected to %s", badge.id)
        await send_to_badge(badge, {"t": "active", "value": True})
        await sync_badge(force=True)


async def handle_badge_command(msg: dict):
    """Dashboard controls for badges: connect / disconnect / identify / rename / volume."""
    action, badge = msg.get("action"), state.badges.get(msg.get("id") or state.active_badge or "")
    if action == "connect" and badge:
        await activate_badge(badge.id)
    elif action == "disconnect":
        await activate_badge(None)
    elif action == "identify" and badge:
        await send_to_badge(badge, {"t": "identify"})   # badge blinks its LED / beeps
    elif action == "rename" and badge and isinstance(msg.get("name"), str) and msg["name"].strip():
        state.badge_names[badge.id] = msg["name"].strip()[:40]
        await send_to_badge(badge, {"t": "name", "value": state.badge_names[badge.id]})
    elif action == "volume" and badge and isinstance(msg.get("value"), (int, float)):
        badge.info["volume"] = max(0, min(100, int(msg["value"])))
        await send_to_badge(badge, {"t": "volume", "value": badge.info["volume"]})


async def handle_badge_message(badge: Badge, msg: dict):
    """JSON from a badge: its own hello/state/pong, else buttons (only from the connected badge)."""
    badge.last_seen = time.monotonic()
    t = msg.get("t")
    if t == "hello":
        new_id = str(msg.get("id") or badge.id)[:40]
        if new_id != badge.id:
            if stale := state.badges.pop(new_id, None):  # the same badge's old socket, from before a reboot
                with contextlib.suppress(Exception):
                    await stale.ws.close()
            state.badges.pop(badge.id, None)
            if state.active_badge == badge.id:
                state.active_badge = new_id
            badge.id = new_id
            state.badges[new_id] = badge
        badge.report(msg)
        log.info("badge hello: %s %s", badge.id, badge.info)
        if state.badge is None:
            state.active_badge = badge.id  # nothing connected yet: take this one
        await send_to_badge(badge, {"t": "active", "value": badge.id == state.active_badge})
        if badge.id == state.active_badge:
            await sync_badge(force=True)
        await broadcast(state.status())
    elif t in ("state", "pong"):
        if t == "pong" and badge.ping_sent:
            badge.rtt_ms = round((time.monotonic() - badge.ping_sent) * 1000)
        badge.report(msg)
        if t == "state":
            await broadcast({"t": "badges", "badges": state.badges_info()})
    elif badge.id == state.active_badge:
        await handle_control(msg)  # ptt, fb, mode (BOOT button)


async def badge_heartbeat():
    """Every few seconds: ping badges (latency, battery) and refresh the dashboard's badge panel."""
    while True:
        await asyncio.sleep(BADGE_PING_S)
        for b in list(state.badges.values()):
            b.roll_audio_stats(BADGE_PING_S)
            b.ping_sent = time.monotonic()
            await send_to_badge(b, {"t": "ping"})
        if state.badges:
            await broadcast({"t": "badges", "badges": state.badges_info()})


async def handle_control(msg: dict):
    """JSON messages from the dashboard, and button messages from the connected badge."""
    t = msg.get("t")
    if t == "mode" and msg.get("state") in ("listen", "stop"):
        state.listening = msg["state"] == "listen"
        state.segmenter.reset()
    elif t == "toggle" and msg.get("id") in {**FIELDS, **STYLES}:  # a context checkbox
        state.active = (state.active | {msg["id"]}) if msg.get("on") else (state.active - {msg["id"]})
    elif t == "mode" and (msg.get("domain") == "auto" or msg.get("domain") in FIELDS):
        # Badge BOOT button: "auto" checks every field, a field name checks only that one. LARP is kept.
        fields = set(FIELDS) if msg["domain"] == "auto" else {msg["domain"]}
        state.active = fields | (state.active & set(STYLES))
    elif t == "ptt":  # push-to-talk from the badge: release ends the sentence immediately
        if msg.get("state") == "start":
            state.listening = True
            state.segmenter.reset()
        elif msg.get("state") == "end":
            if sentence := state.segmenter.flush():
                await state.queue.put(("sentence", *sentence))
            state.listening = False
    elif t == "fb" and msg.get("val") in (1, -1):
        uid = msg.get("id") or state.last_id  # the badge's buttons apply to the latest sentence
        utt = state.utterances.get(uid)
        log_feedback(msg["val"], utt)
        blamed = None
        if utt and msg["val"] > 0:
            ML.feedback(utt["terms"], 1, utt["target"])
        elif utt:
            # 👎 changes one word: the one clicked on the dashboard, else the one we're least sure about.
            blamed = next((t for t in utt["terms"] if t["term"] == msg.get("term")), None) \
                or ML.weakest(utt["terms"], utt["target"])
            if blamed:
                ML.feedback([blamed], -1, utt["target"])
                await state.queue.put(("retry", uid, blamed))
        await broadcast({"t": "feedback", "id": uid, "val": msg["val"], "term": blamed and blamed["term"]})
        await broadcast(ML.metrics())
        return
    elif t == "context":
        state.context = msg.get("text", "")
        state.context_name = msg.get("name") or state.context_name or "default"
        save_context(state.context_name, state.context)
        log.info("context pack %r saved (%d chars)", state.context_name, len(state.context))
    elif t == "lang" and msg.get("value"):
        state.target = msg["value"]
    elif t == "reset":  # forget learned term choices (for a clean demo)
        ML.reset()
        await broadcast(ML.metrics())
    elif t == "voice":
        await handle_voice(msg)
    elif t == "badge":
        await handle_badge_command(msg)
    else:
        log.warning("ignored message: %s", msg)
        return
    await state_changed()


async def handle_voice(msg: dict):
    """Voice setup from the badge mic: record -> (read the script) -> stop -> ElevenLabs clone."""
    action = msg.get("action")
    if action == "record":
        if state.badge is None:
            await broadcast({"t": "error", "id": None, "msg": "voice setup: the badge isn't connected (record in the browser instead)"})
            return
        state.listening = False  # don't translate the setup reading
        state.recording = {"name": (msg.get("name") or "My voice").strip(), "pcm": bytearray(),
                           "speech_ms": 0, "vad": webrtcvad.Vad(2), "started": time.monotonic()}
        log.info("voice setup: recording from the badge")
    elif action == "cancel":
        state.recording = None
    elif action == "stop" and state.recording:
        rec, state.recording = state.recording, None
        await finish_voice_setup(rec["name"], pcm_to_wav(bytes(rec["pcm"])), rec["speech_ms"] / 1000)


async def finish_voice_setup(name: str, wav: bytes, speech_s: float) -> str | None:
    """Creates the clone. Returns an error message, or None on success."""
    error = None
    if speech_s < MIN_SAMPLE_SPEECH_S:
        error = (f"voice setup: only {speech_s:.0f} s of speech, need at least {MIN_SAMPLE_SPEECH_S} s "
                 "(about 60 s sounds best). Try again.")
    else:
        await broadcast({"t": "voice_progress", "state": "creating"})
        try:
            await asyncio.to_thread(VOICE.clone, name, wav)
        except Exception as e:
            log.error("voice setup failed: %s", e)
            report(e, step="voice_clone")
            error = f"voice setup failed: {type(e).__name__}: {e}"
    if error:
        await broadcast({"t": "error", "id": None, "msg": error})
    await state_changed()
    return error


async def record_voice_sample(pcm: bytes):
    """Badge audio during voice setup: keep it all, count the seconds that are actual speech."""
    rec = state.recording
    rec["pcm"] += pcm
    whole = len(pcm) // FRAME_BYTES * FRAME_BYTES
    for i in range(0, whole, FRAME_BYTES):
        if rec["vad"].is_speech(pcm[i:i + FRAME_BYTES], SAMPLE_RATE):
            rec["speech_ms"] += FRAME_MS
    seconds = len(rec["pcm"]) / (SAMPLE_RATE * 2)
    if int(seconds) != int((len(rec["pcm"]) - len(pcm)) / (SAMPLE_RATE * 2)):  # about once a second
        await broadcast({"t": "voice_progress", "state": "recording",
                         "speech_s": round(rec["speech_ms"] / 1000, 1), "total_s": round(seconds, 1)})
    if seconds >= MAX_SAMPLE_S:
        await handle_voice({"action": "stop"})


def wav_seconds(wav: bytes) -> float:
    """Length of an uploaded WAV (browser recording), for the minimum-length check."""
    try:
        with wave.open(io.BytesIO(wav)) as w:
            return w.getnframes() / w.getframerate()
    except (wave.Error, EOFError, ZeroDivisionError):
        raise HTTPException(400, "send a WAV file")


async def receive_loop(ws: WebSocket, on_bytes=None, on_json=handle_control):
    while True:
        m = await ws.receive()
        if m["type"] == "websocket.disconnect":
            raise WebSocketDisconnect(m.get("code", 1000))
        if m.get("bytes") is not None:
            if on_bytes:
                await on_bytes(m["bytes"])
        elif m.get("text"):
            try:
                msg = json.loads(m["text"])
            except json.JSONDecodeError:
                log.warning("bad JSON: %r", m["text"][:100])
                continue
            await on_json(msg)


# ---------------------------------------------------------------- routes
@app.get("/health")
async def health():
    """For Render's health check (and a quick "is it up?")."""
    return {"ok": True, "badge": state.badge is not None}


@app.get("/api/config")
async def client_config():
    """What the dashboard needs before connecting. The Sentry DSN is public by design (it can only send events)."""
    return {"sentry_dsn": os.getenv("SENTRY_DSN") or "", "environment": os.getenv("SENTRY_ENVIRONMENT") or "local"}


@app.post("/api/voice", dependencies=[Depends(require_pairing)])
async def upload_voice(request: Request, name: str = "My voice"):
    """Voice setup from the browser mic: the dashboard POSTs a WAV recording here."""
    wav = await request.body()
    if len(wav) > 20_000_000:
        raise HTTPException(413, "recording too long")
    error = await finish_voice_setup(name.strip() or "My voice", wav, wav_seconds(wav))
    if error:
        raise HTTPException(400, error)
    return VOICE.info()


@app.get("/api/voice/test", dependencies=[Depends(require_pairing)])
async def test_voice(text: str = ""):
    """Speak a short line in the current voice so the user can check it sounds like them."""
    line = text or {"Korean": "안녕하세요, 이제 제 목소리로 통역합니다.", "Spanish": "Hola, ahora traduzco con mi propia voz."}.get(
        state.target, "Hi, this is my voice, now translating for me.")
    try:
        pcm, _ = await asyncio.to_thread(synthesize, line, "neutral")
    except Exception as e:
        report(e, step="elevenlabs")
        raise HTTPException(502, f"{type(e).__name__}: {e}")
    return Response(pcm_to_wav(pcm), media_type="audio/wav")


@app.get("/reference")
async def reference_dashboard():
    """The backend's own minimal test page. The team's app (dashboard/) is served at /."""
    return FileResponse(HERE / "static" / "dashboard.html")


@app.websocket("/ws/badge")
async def badge_ws(ws: WebSocket):
    await ws.accept()
    if not authorized(ws):
        log.warning("badge from %s rejected: wrong or missing pairing code", ws.client.host if ws.client else "?")
        await ws.close(code=4401, reason="pairing code required")
        return
    state.badge_seq += 1
    badge = Badge(ws, state.badge_seq)
    state.badges[badge.id] = badge
    log.info("badge online: %s from %s", badge.id, badge.info["ip"])
    if state.badge is None:
        await activate_badge(badge.id)  # first badge online is connected automatically
    else:
        await send_to_badge(badge, {"t": "active", "value": False})
    await broadcast(state.status())

    async def on_audio(pcm: bytes):
        badge.last_seen = time.monotonic()
        pcm = badge.take_audio(pcm)
        if not pcm or badge.id != state.active_badge:
            return  # online but not the connected badge
        if state.recording:
            await record_voice_sample(pcm)
            return
        # Ignore mic audio while stopped or while the badge is playing a translation.
        if not state.listening or time.monotonic() < state.mute_until:
            return
        for sentence in state.segmenter.add(pcm):
            await state.queue.put(("sentence", *sentence))

    try:
        await receive_loop(ws, on_audio, lambda msg: handle_badge_message(badge, msg))
    except WebSocketDisconnect:
        pass
    finally:
        # The active id is kept, so the same badge reconnecting (same hello id) is connected again.
        if state.badges.get(badge.id) is badge:
            del state.badges[badge.id]
        log.info("badge offline: %s", badge.id)
        await broadcast(state.status())


@app.websocket("/ws/dashboard")
async def dashboard_ws(ws: WebSocket):
    await ws.accept()
    if not authorized(ws):
        # Accept-then-close so the browser sees the code (a refused handshake looks like any network error).
        await ws.close(code=4401, reason="pairing code required")
        return
    state.dashboards.add(ws)
    await ws.send_json(state.status())
    await ws.send_json(ML.metrics())
    for utt in list(state.utterances.values())[-50:]:
        await ws.send_json(public(utt))
    try:
        await receive_loop(ws)
    except WebSocketDisconnect:
        pass
    finally:
        state.dashboards.discard(ws)


# Last, so the routes above win: the team's dashboard app at /, or the reference page if it's missing.
if (DASHBOARD_DIR / "index.html").exists():
    app.mount("/", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard")
else:
    app.add_api_route("/", reference_dashboard)
