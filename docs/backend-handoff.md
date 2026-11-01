# Backend handoff: what's built, and what not to change

*Bernard (Role B), Nov 1. Branch `backend-pipeline`.*

The backend and a first version of the dashboard are done. This page says what exists, who owns what, and which choices are deliberate, so nobody "fixes" something that's like that on purpose. **If you want to change anything marked ⚠, ask in the group chat first.**

## What it does

```
badge mic ─► voice detection ─► Whisper ─► local ML ─► Gemini ─► ElevenLabs ─► badge speaker
           (laptop)             (OpenAI)   (laptop)   (Google)  (user's cloned voice)
                                              └──► dashboard: transcript, field, jargon, learning curve
```

- **Contexts (checkboxes):** Pickleball, Tennis, Computer science, Math (fields) and LARP mode (style). The backend only detects among the checked fields, and translates jargon per field ("set" → 세트 in tennis, 집합 in math).
- **LARP mode:** drops filler words and upgrades weak phrases locally, then asks Gemini (same call) to make the speaker sound like an expert.
- **Learning:** 👍/👎 per sentence. 👎 on a word replays the sentence with that word's next translation; one 👎 changes the default from then on.
- **Voice:** translations are spoken in the user's own voice, cloned once at the start (voice setup on the dashboard).

## Who owns what

| Path | Owner | Rule |
|---|---|---|
| `backend/` | Bernard (B) | ⚠ Don't edit. Ask for changes. |
| `docs/messages.md` | Whole team | ⚠ The contract between badge, backend and dashboard. Change only together: one change means updating the backend, `dashboard/js/api.js`, `dashboard/js/mock.js` and the firmware. |
| `dashboard/js/api.js`, `dashboard/js/mock.js` | Bernard (B) | ⚠ Protocol layer. Don't edit for UI work. |
| `dashboard/index.html`, `css/`, `js/app.js` | D | Change freely: layout, styling, new views. |
| `data/` | D + C | Fill in freely, in the formats from `docs/messages.md` (section "Data files"). Keep the file names. Restart the backend to load changes. |
| `firmware/` | A | Must follow `docs/messages.md`: 16 kHz 16-bit mono PCM, the JSON messages, `ws://<laptop>:8000/ws/badge`. |
| `render.yaml`, `.env.example` | Bernard (B) | ⚠ |

## Deliberate choices (please don't "fix")

| Looks like | Why it's on purpose |
|---|---|
| Embeddings via `fastembed` (ONNX), not `sentence-transformers` / PyTorch | PyTorch crashed on macOS 14 (Apple GPU backend), used 527 MB (over Render's 512 MB free tier) and is a 1.2 GB install. ONNX: same model, 250 MB, 3 ms/sentence, starts offline. |
| Gemini only gets a short plain-text prompt, no JSON, no tone | Cheapest and fastest. Field, tone, jargon and context trimming are all done locally for free; Gemini just translates. |
| Repeated sentences don't call Gemini or ElevenLabs | Disk cache, so rehearsing the demo costs nothing. "cached" on the dashboard means 0 ms. |
| Picks the best-scoring translation, not random (no Thompson sampling) | The live demo has to be predictable. Exploration comes from 👎. |
| A 👎 changes only one word | Blaming every word flipped correct ones too. The dashboard lets you click the wrong word; the badge's 👎 blames the least certain one. |
| New audio waits until the badge finishes playing + 300 ms | The badge mutes its mic while playing; overlapping audio would be cut off or re-heard. |
| Server starts in **Stop** mode | Doesn't burn API credits until someone presses Listen. |
| A stock voice speaks until voice setup is done | The demo never goes silent; the dashboard shows a red "voice: stock (set up!)" warning. |
| `webrtcvad-wheels` instead of `webrtcvad` | The original doesn't install on Python 3.14. |
| One `.env` at the repo root | One place for keys; it's gitignored. |
| Starter data in `backend/seeds.json` | Fallback until `data/` is filled. The dashboard shows `built-in` or `data` next to each context. |

## Status

**Tested:** server, WebSockets, dashboard (mock and real), voice detection on real audio, local ML (field detection, jargon, LARP, learning), voice setup flow, error handling (an API failure skips one sentence and keeps listening), the ElevenLabs key (real Korean speech, 0.5 s).

**Not tested yet:** OpenAI (Whisper) and Gemini with real keys, voice cloning with a real account, the badge (firmware not written yet), Render.

## To run

```bash
cp .env.example .env                    # paste OPENAI_API_KEY, GEMINI_API_KEY, ELEVENLABS_API_KEY
cd backend && pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```
Dashboard: http://localhost:8000. Without keys or a badge: open `dashboard/index.html?mock=play`.

## Open items

| Who | What |
|---|---|
| Everyone | OpenAI and Gemini keys in `.env`. ElevenLabs key needs **Voices → Write** permission for voice setup, and a paid plan (Starter+) for voice cloning. |
| A | Firmware per `docs/messages.md`. For Render: `wss://` with `beginSSL`. |
| C + D | Fill `data/glossaries/<context>.json`, `data/train.jsonl`, `data/larp.json`. Have someone who reads Korean/Spanish check the translations. `data/README.md` still lists the old domains. |
| D | Style the dashboard for the projector; plain-vs-Larpslator comparison for the demo. |

More detail: [backend/README.md](../backend/README.md), [dashboard/README.md](../dashboard/README.md), [docs/messages.md](messages.md).
