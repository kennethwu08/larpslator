"""Larpslator backend: badge audio -> VAD -> Whisper -> local ML -> Gemini -> ElevenLabs -> badge.

Gemini only translates (and, in LARP mode, polishes in the same call). Field detection,
tone, jargon choice, context trimming, LARP phrase upgrades and learning from feedback
all run locally (ml.py), so they cost nothing.

Run:  uvicorn main:app --host 0.0.0.0 --port 8000   (from the backend/ folder)
"""
import asyncio
import hashlib
import io
import json
import logging
import os
import re
import time
import wave
from contextlib import asynccontextmanager
from pathlib import Path

import webrtcvad
from dotenv import load_dotenv
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from google import genai
from google.genai import types
from openai import OpenAI

HERE = Path(__file__).parent
load_dotenv(HERE.parent / ".env")
load_dotenv(HERE / ".env")  # a backend/.env also works (doesn't override the root one)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("larpslator")

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

GEMINI_MODEL = os.getenv("GEMINI_MODEL") or "gemini-2.5-flash-lite"
TTS_MODEL = os.getenv("ELEVENLABS_MODEL") or "eleven_flash_v2_5"
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID") or "JBFqnCBsd6RMkjVDRZzb"  # premade voice as a fallback
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

missing = [k for k in ("OPENAI_API_KEY", "GEMINI_API_KEY", "ELEVENLABS_API_KEY") if not os.getenv(k)]
if missing:
    raise SystemExit(f"Missing in .env: {', '.join(missing)} (see .env.example in the repo root)")

openai_client = OpenAI()  # reads OPENAI_API_KEY
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
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


def translate(text: str, target: str, terms: list[dict], context_lines: list[str],
              style: str = "") -> tuple[str, bool]:
    """The only Gemini call: a short plain-text translation request. Returns (translation, cached).

    `style` is the LARP instruction; it rides along in the same request, no extra call."""
    lines = [f"Translate into {target}. Reply with the translation only."]
    if style:
        lines.append(style)
    if terms:
        lines.append("Use these term translations: " + "; ".join(f"{t['match']} = {t['choice']}" for t in terms))
    if context_lines:
        lines.append("Context: " + "; ".join(context_lines))
    lines.append(f"Text: {text}")
    prompt = "\n".join(lines)

    key = hashlib.sha1(f"{GEMINI_MODEL}\n{prompt}".encode()).hexdigest()
    if key in _translation_cache:
        return _translation_cache[key], True

    config = types.GenerateContentConfig(temperature=0, max_output_tokens=400)
    if "2.5" in GEMINI_MODEL:
        config.thinking_config = types.ThinkingConfig(thinking_budget=0)  # thinking adds latency and cost
    r = gemini_client.models.generate_content(model=GEMINI_MODEL, contents=prompt, config=config)
    out = (r.text or "").strip()
    if not out:
        raise RuntimeError("Gemini returned an empty translation")
    _translation_cache[key] = out
    _translation_cache_file.write_text(json.dumps(_translation_cache, ensure_ascii=False))
    return out, False


def synthesize(text: str, tone: str) -> tuple[bytes, bool]:
    """Returns (16 kHz 16-bit mono PCM, cached). Repeated sentences cost no credits."""
    s = TONE_SETTINGS.get(tone, TONE_SETTINGS["neutral"])
    if TTS_MODEL.startswith("eleven_v3") and tone != "neutral":
        text = f"[{tone}] {text}"  # only v3 understands audio tags; other models would read them aloud
    path = CACHE_DIR / "tts" / (hashlib.sha1(f"{VOICE_ID}|{TTS_MODEL}|{tone}|{text}".encode()).hexdigest() + ".pcm")
    if path.exists():
        return path.read_bytes(), True
    audio = b"".join(eleven_client.text_to_speech.convert(
        voice_id=VOICE_ID,
        text=text,
        model_id=TTS_MODEL,
        output_format="pcm_16000",
        voice_settings=VoiceSettings(
            stability=s["stability"], style=s["style"], similarity_boost=0.75, use_speaker_boost=True
        ),
    ))
    path.write_bytes(audio)
    return audio, False


def translate_and_speak(r: dict, timing: dict):
    """Gemini + ElevenLabs for an analyzed sentence. Fills r["translation"] and r["audio"]."""
    t = time.perf_counter()
    larp = r.get("larp")
    if not larp and same_language(r["lang"], r["target"]):
        r["translation"], cached = r["source"], True   # nothing to translate: no Gemini call
    else:
        text = larp["text"] if larp else r["source"]   # LARP: send the locally upgraded wording
        style = ML.larp_instruction(r["domain"]) if larp else ""
        r["translation"], cached = translate(text, r["target"], r["terms"], r["context_lines"], style)
    timing["gemini"] = 0 if cached else round((time.perf_counter() - t) * 1000)

    t = time.perf_counter()
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

    t = time.perf_counter()
    source, lang = transcribe(pcm, ML.whisper_prompt(active))
    timing["whisper"] = round((time.perf_counter() - t) * 1000)
    r = {"source": source, "lang": lang, "target": target, "translation": "", "audio": b"", "timing_ms": timing}
    if not source:
        return r
    if on_transcript:
        on_transcript(source, lang)

    t = time.perf_counter()
    r.update(ML.analyze(source, target, context, active))
    timing["ml"] = round((time.perf_counter() - t) * 1000)

    translate_and_speak(r, timing)
    return r


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


# ---------------------------------------------------------------- server state
class State:
    def __init__(self):
        packs = list_contexts()
        self.listening = False
        self.target = DEFAULT_TARGET
        self.active = set(FIELDS)     # checked contexts: fields to choose between, plus "larp"
        self.context_name = packs[0]["name"] if packs else ""
        self.context = packs[0]["text"] if packs else ""   # reuse the most recent pack on restart
        self.badge: WebSocket | None = None
        self.dashboards: set[WebSocket] = set()
        self.segmenter = Segmenter()
        self.queue: asyncio.Queue = asyncio.Queue()
        self.mute_until = 0.0         # badge is playing (or just finished) until this time
        self.next_id = 1
        self.utterances: dict[int, dict] = {}
        self.last_id: int | None = None

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
                "context_name": self.context_name, "context": self.context,
                "languages": LANGUAGES, "packs": list_contexts()}


state = State()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(worker())
    log.info("ready: target=%s, gemini=%s, tts=%s, context pack=%r",
             state.target, GEMINI_MODEL, TTS_MODEL, state.context_name or None)
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)


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
        await state.badge.send_bytes(chunk)
        # Stay slightly ahead of playback so the badge buffer never runs dry or overflows.
        await asyncio.sleep(len(chunk) / (SAMPLE_RATE * 2) * 0.85)


def public(utt: dict) -> dict:
    """Utterance as sent to the dashboard (no audio, no internals)."""
    return {"t": "utterance", **{k: v for k, v in utt.items() if k not in ("audio", "rejected")}}


def log_timing(uid: int, r: dict):
    tm = r["timing_ms"]
    log.info("utt %d | vad %.1fms | whisper %sms | ml %sms | gemini %sms | elevenlabs %sms | total %sms | "
             "%s/%s | %r%s -> %r | terms %s",
             uid, tm.get("vad", 0), tm.get("whisper", "-"), tm.get("ml", "-"), tm["gemini"], tm["elevenlabs"],
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
    terms = [t for t in terms if t["choice"]]  # a term with no options left falls back to Gemini's choice
    if [t["choice"] for t in terms] == [t["choice"] for t in utt["terms"]]:
        await broadcast({"t": "error", "id": uid, "msg": f"no other translations left for '{blamed['term']}'"})
        return
    r = {**utt, "terms": terms}
    timing = {}
    await asyncio.to_thread(translate_and_speak, r, timing)
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
            await broadcast({"t": "error", "id": job[1] if job[0] == "retry" else None,
                             "msg": f"{type(e).__name__}: {e}"})


# ---------------------------------------------------------------- control messages
async def tell_badge_mode():
    if state.badge:
        await state.badge.send_json({"t": "mode", "domain": state.badge_mode()})


async def handle_control(msg: dict):
    """JSON messages from the dashboard and the badge's buttons."""
    t = msg.get("t")
    if t == "mode" and msg.get("state") in ("listen", "stop"):
        state.listening = msg["state"] == "listen"
        state.segmenter.reset()
    elif t == "toggle" and msg.get("id") in {**FIELDS, **STYLES}:  # a context checkbox
        state.active = (state.active | {msg["id"]}) if msg.get("on") else (state.active - {msg["id"]})
        await tell_badge_mode()
    elif t == "mode" and (msg.get("domain") == "auto" or msg.get("domain") in FIELDS):
        # Badge BOOT button: "auto" checks every field, a field name checks only that one. LARP is kept.
        fields = set(FIELDS) if msg["domain"] == "auto" else {msg["domain"]}
        state.active = fields | (state.active & set(STYLES))
        await tell_badge_mode()
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
    elif t == "hello":
        log.info("badge says hello")
        await tell_badge_mode()
        return
    else:
        log.warning("ignored message: %s", msg)
        return
    await broadcast(state.status())


async def receive_loop(ws: WebSocket, on_bytes=None):
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
            await handle_control(msg)


# ---------------------------------------------------------------- routes
@app.get("/")
async def dashboard():
    return FileResponse(HERE / "static" / "dashboard.html")


@app.websocket("/ws/badge")
async def badge_ws(ws: WebSocket):
    await ws.accept()
    state.badge = ws
    state.segmenter.reset()
    log.info("badge connected")
    await ws.send_json({"t": "mode", "domain": state.badge_mode()})
    await broadcast(state.status())

    async def on_audio(pcm: bytes):
        # Ignore mic audio while stopped or while the badge is playing a translation.
        if not state.listening or time.monotonic() < state.mute_until:
            return
        for sentence in state.segmenter.add(pcm):
            await state.queue.put(("sentence", *sentence))

    try:
        await receive_loop(ws, on_audio)
    except WebSocketDisconnect:
        pass
    finally:
        if state.badge is ws:
            state.badge = None
        log.info("badge disconnected")
        await broadcast(state.status())


@app.websocket("/ws/dashboard")
async def dashboard_ws(ws: WebSocket):
    await ws.accept()
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
