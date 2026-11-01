"""Browser audio fallback: the dashboard acts as the translator's mic and speaker if the badge hardware fails.

On with WEB_AUDIO_FALLBACK=1 (default off). This module is the only place the flag is checked: when it's off,
GET /api/web-audio returns 404 (the dashboard then hides its Web Audio section) and /ws/web refuses connections.

The browser is just another audio client on the same pipeline as the badge: it sends 16 kHz 16-bit mono PCM as
binary frames and gets the translation's audio back in the same format (main.web_client_ws).

To remove the feature: delete this file, dashboard/js/web-audio.js and dashboard/js/pcm-worklet.js, and the lines
marked "WEB_AUDIO" in backend/main.py and dashboard/index.html.
"""
import os

from fastapi import APIRouter, HTTPException, WebSocket

CHUNK_MS = 100  # what the dashboard sends per frame (the badge sends ~32 ms; any size works)


def enabled() -> bool:
    return os.getenv("WEB_AUDIO_FALLBACK") == "1"


def router(handle_web_client, sample_rate: int, resume_after_s: float) -> APIRouter:
    """Routes for the fallback. `handle_web_client(ws)` runs a connected browser on the shared pipeline."""
    r = APIRouter()

    @r.get("/api/web-audio")
    async def web_audio_info():
        if not enabled():
            raise HTTPException(404, "web audio fallback is off (set WEB_AUDIO_FALLBACK=1)")
        return {"enabled": True, "websocket": "/ws/web", "sample_rate": sample_rate, "format": "pcm_s16le_mono",
                "chunk_ms": CHUNK_MS, "resume_after_ms": round(resume_after_s * 1000)}

    @r.websocket("/ws/web")
    async def web_audio_ws(ws: WebSocket):
        if not enabled():
            await ws.close(code=4404, reason="web audio fallback is off")  # handshake refused
            return
        await handle_web_client(ws)

    return r
