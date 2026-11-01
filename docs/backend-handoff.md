# Backend handoff: what's built, and what not to change

*Bernard (Role B), Nov 1. Branch `backend-pipeline`.*

The backend and a first version of the dashboard are done. This page says what exists, who owns what, and which choices are deliberate, so nobody "fixes" something that's like that on purpose. **If you want to change anything marked ⚠, ask in the group chat first.**

## What it does

```
badge mic ─► voice detection ─► Whisper ─► local ML ─► Featherless ─► ElevenLabs ─► badge speaker
           (laptop)             (OpenAI)   (laptop)   (LLM)       (user's cloned voice)
                                              └──► dashboard: transcript, field, jargon, learning curve
```

- **Contexts (checkboxes):** Pickleball, Tennis, Computer science, Math (fields) and LARP mode (style). The backend only detects among the checked fields, and translates jargon per field ("set" → 세트 in tennis, 집합 in math).
- **LARP mode:** drops filler words and upgrades weak phrases locally, then asks the LLM (same call) to make the speaker sound like an expert.
- **Learning:** 👍/👎 per sentence. 👎 on a word replays the sentence with that word's next translation; one 👎 changes the default from then on.
- **Voice:** translations are spoken in the user's own voice, cloned once at the start (voice setup on the dashboard).
- **Badge control:** the dashboard lists every badge online; **Connect** picks which one is used. The backend pushes it its settings (language, contexts, LARP, listening, voice) whenever they change, and shows its battery, Wi-Fi, latency, firmware and whether it confirmed the settings. Identify (blink), volume, disconnect.

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
| The LLM only gets a short plain-text prompt, no JSON, no tone | Cheapest and fastest. Field, tone, jargon and context trimming are all done locally for free; the LLM just translates. |
| Featherless model is Mistral Small 3.2, with Mistral Nemo as fallback | Benchmarked on 12 sentences: 0 wrong-language replies, ~1.4 s. Qwen 2.5 7B/14B drifted into English/Chinese on Korean. Replies are script-checked; wrong language → fallback model. |
| Repeated sentences don't call the LLM or ElevenLabs | Disk cache, so rehearsing the demo costs nothing. "cached" on the dashboard means 0 ms. |
| Picks the best-scoring translation, not random (no Thompson sampling) | The live demo has to be predictable. Exploration comes from 👎. |
| A 👎 changes only one word | Blaming every word flipped correct ones too. The dashboard lets you click the wrong word; the badge's 👎 blames the least certain one. |
| New audio waits until the badge finishes playing + 300 ms | The badge mutes its mic while playing; overlapping audio would be cut off or re-heard. |
| Server starts in **Stop** mode | Doesn't burn API credits until someone presses Listen. |
| A stock voice speaks until voice setup is done | The demo never goes silent; the dashboard shows a red "voice: stock (set up!)" warning. |
| `webrtcvad-wheels` instead of `webrtcvad` | The original doesn't install on Python 3.14. |
| One `.env` at the repo root | One place for keys; it's gitignored. |
| Other devices need a pairing code; this laptop doesn't | Anyone on the venue/hotspot Wi-Fi could otherwise control the badge or hear the conversation. Local pages from other sites are blocked by Origin. |
| Badge on plain `ws://:8000`, browsers on `https://:8443` | TLS is heavy on an ESP32; phones need https for the mic. One process (`serve.py`), shared state. |
| Starter data in `backend/seeds.json` | Fallback until `data/` is filled. The dashboard shows `built-in` or `data` next to each context. |

## Status

**Tested:** server, WebSockets, dashboard (mock and real), voice detection on real audio, local ML (field detection, jargon, LARP, learning), voice setup flow, error handling (an API failure skips one sentence and keeps listening), the ElevenLabs key (real Korean speech, 0.5 s).

**Evaluation (Nov 1, `python backend/evaluate.py`):** jargon right in English → Tamil: plain translator 13%, Larpslator 100%; Korean → English: 93% → 100% (15 sentences each, term presence).

**Not tested yet:** OpenAI (Whisper) with a real key, voice cloning with a real account, the badge (firmware not written yet), Render.

## To run

```bash
cp .env.example .env                    # paste OPENAI_API_KEY, FEATHERLESS_API_KEY, ELEVENLABS_API_KEY
cd backend && pip install -r requirements.txt
python serve.py                         # prints the dashboard links, badge address and pairing code
```
Dashboard: http://localhost:8000. Without keys or a badge: open `dashboard/index.html?mock=play`.

## Open items

| Who | What |
|---|---|
| Everyone | OpenAI key (Whisper) in `.env`; Featherless and ElevenLabs keys are in. ElevenLabs key needs **Voices → Write** permission for voice setup, and a paid plan (Starter+) for voice cloning. |
| A | Firmware per `docs/messages.md`. Connect to `ws://<laptop-ip>:8000/ws/badge?token=<pairing code>` (the code is on the dashboard: Session → Pair Another Device; without it the server closes the socket with 4401). Minimum: audio + `ptt` + `fb`. For the badge panel: send `hello` (stable `id` from the MAC), `state`, answer `ping`; handle `config`, `active`, `identify`, `volume`. For Render: `wss://` with `beginSSL`. |
| C + D | `data/` is wired in (both directions, Tamil, `academia.json` = math). Still open: a Tamil speaker reviews `TAMIL_REVIEW.md` items and a Korean speaker checks `CHECK.md`; Tamil/English-Korean entries have one option each, so add wrong-meaning alternatives for the 👎 demo; `data/README.md` still lists academia/med and mentions a `backend/translate.py` that doesn't exist (use `python backend/evaluate.py`); optional `train.jsonl`. |
| D | Style the dashboard for the projector; plain-vs-Larpslator comparison for the demo. |

More detail: [backend/README.md](../backend/README.md), [dashboard/README.md](../dashboard/README.md), [docs/messages.md](messages.md).
