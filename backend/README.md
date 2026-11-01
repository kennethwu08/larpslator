# Backend

Badge mic audio → voice activity detection → speech to text (ElevenLabs Scribe) → **local ML** → Featherless LLM → ElevenLabs → back to the badge, with a live dashboard.

**The LLM only translates.** Everything else (detecting the field, tone, finding jargon, choosing each jargon word's translation, learning from 👍/👎, trimming the context pack, the LARP phrase upgrades) runs locally for free in `ml.py`. The LLM gets one short plain-text request per sentence:

```
Translate into Korean. Reply with the translation only.
Use these term translations: merge = 병합하다; branch = 브랜치; kernel = 커널
Context: Prof. Lee; Agenda: build system
Text: Can you merge my branch before the kernel build?
```

```
main.py               server + pipeline (VAD, speech to text, LLM, ElevenLabs, playback)
ml.py                 local ML: field, tone, jargon, learning from feedback
seeds.json            built-in fallback data, used per context until data/ has a file for it
static/dashboard.html dashboard (served at /)
test_pipeline.py      run a WAV file through the pipeline, no badge needed
contexts/             saved meeting context packs (JSON, one per pack)
```
Runtime files (gitignored): `state/term_stats.json` (what it learned), `cache/` (translations + audio), `logs/feedback.jsonl`.

## Run it

```bash
cp .env.example .env        # in the repo root; paste in your three API keys
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python serve.py        # http :8000 for the badge + https :8443 for other devices, one shared server
```

The first start downloads the `all-MiniLM-L6-v2` model (~90 MB, into `backend/.models/`), so do it before you're on venue Wi-Fi. After that the ML starts without internet. It runs on ONNX (`fastembed`), not PyTorch: ~3 ms per sentence and ~250 MB of RAM for the whole server.

`serve.py` prints the links. In short:
- Dashboard on this laptop: http://localhost:8000 (the backend's minimal test page is at `/reference`)
- Other devices (phone, second laptop): `https://<laptop-ip>:8443/?token=<pairing code>`, also under Session → Pair Another Device. Accept the certificate warning once.
- Badge: `ws://<laptop-ip>:8000/ws/badge?token=<pairing code>` in its `config.h`. Laptop and badge on the same network (the phone hotspot).
- Plain `uvicorn main:app --host 0.0.0.0 --port 8000` still works (no https port).

## Security

- **Pairing code.** Everything except this laptop's own browser needs it: the badge, phones, other laptops, and the HTTP API. Wrong or missing code: the WebSocket is closed with `4401`, HTTP returns `401`. Set it with `LARPSLATOR_TOKEN`, or one is generated once and saved in `state/pairing.json`.
- **Web pages can't hijack the local server.** A page from another site open on this laptop is rejected (checked by `Origin`), even though the laptop itself is trusted.
- **HTTPS for browsers** on `:8443` (self-signed certificate for this laptop's IP, made in `certs/` on first run and again when the IP changes). Phones need it for the microphone. The badge stays on plain `ws://` on `:8000` because TLS is heavy for an ESP32; the Wi-Fi itself (WPA2 hotspot) encrypts that hop.
- **Audio integrity.** Mic frames over 32 KB are dropped; odd-sized frames are realigned so 16-bit samples never shift. Each badge reports mic health (data rate, level, dropped frames) every 5 s; the dashboard shows it under About → Microphone ("Good · 256 kbps · −28 dB").
- **Faster drop detection.** WebSocket pings every 10 s (serve.py).

## Test without the badge

```bash
# make a sample (macOS), or use any WAV; it's converted to 16 kHz mono automatically
say -o sample.wav --data-format=LEI16@16000 "The kernel scheduler is preempting the thread. [[slnc 1200]] Can we review the agenda after lunch?"

python test_pipeline.py sample.wav --lang Korean --context "Prof. Lee; kernel = OS kernel"
python test_pipeline.py sample.wav --contexts math,larp      # only math checked, LARP on
```

It prints every stage's output and timing (field, tone, terms found, which context lines went to the LLM) and saves each translation as `out_<n>.wav`.

## Web audio fallback (if the badge fails)

The dashboard can be the translator itself: its **Web Audio** section uses the browser's mic and speaker, on the same
pipeline as the badge (same 16 kHz audio, voice detection, speech to text with ElevenLabs Scribe, local ML, Featherless
translation, ElevenLabs voice). Off by default.

- **Turn on:** `WEB_AUDIO_FALLBACK=1` in `.env`, restart. **Off:** remove it or set `0`.
- **Remove for good:** delete `web_audio.py`, `dashboard/js/web-audio.js`, `dashboard/js/pcm-worklet.js`, and the lines marked `WEB_AUDIO` in `main.py` and `dashboard/index.html`.
- The mic needs `localhost` or https (`https://<laptop-ip>:8443` with `serve.py`, or the cloudflared address).

**Test it:**
```bash
cd backend
WEB_AUDIO_FALLBACK=1 python serve.py
```
1. Open http://localhost:8000. A **Web Audio** section is above the conversation (without the flag it isn't there).
2. Press **Listen** and allow the microphone. The level meter moves when you talk.
3. Say a sentence and pause. The transcript, then the translation, appear in the section and in the conversation (labeled **Web** when a badge is also connected), and the translation plays through the speakers. The mic ignores the speakers until 300 ms after playback.
4. Press **Stop**: the sentence you were in the middle of is still translated.
5. Errors to try: block the mic in the site settings ("Microphone access was denied…"); stop the backend while listening (three reconnect tries, then "Lost the connection to the backend…").

**Automated tests:** `cd backend && python -m pytest tests` (feature flag on/off, listen → audio → stop through the real voice detector with mocked speech-to-text/LLM/TTS, a TTS failure not stopping the pipeline, the badge path).

## Badges

The backend controls the badge. The dashboard's **Badge** panel lists every badge online. **Connect** picks the one whose mic and buttons are used (the first one online is connected automatically). It shows the badge's language, contexts, LARP, listening state, voice, battery, Wi-Fi, latency, firmware and whether it confirmed the latest settings, and has Identify (blink), volume and Disconnect.

- Whenever anything changes on the dashboard, the backend pushes the badge a `config` message (language, contexts, LARP, listening, voice). The badge can show it on LEDs and confirms it with `config_v`.
- A ping every 5 s gives latency and battery. Dead connections are closed by uvicorn's own WebSocket pings.
- The panel shows the address for the badge's `config.h` (`ws://<this laptop's IP>:8000/ws/badge`), which changes with the network (hotspot).
- All badge info messages are optional, so firmware that only streams audio and buttons still works. Protocol: [../docs/messages.md](../docs/messages.md).

## Voice setup (do this first)

Translations are spoken in **the user's own voice**, cloned with ElevenLabs Instant Voice Cloning. Until setup is done, a stock voice is used and the dashboard shows a warning.

1. Open the dashboard, enter your name under **Your voice**, and press **Record on badge** or **Record in browser**.
2. Read the script shown, at your normal pace, somewhere quiet: about 60 s (minimum 20 s of speech).
3. Press **Stop & create voice**, then **▶ Play test** to check it sounds like you.

- The clone is multilingual (`eleven_flash_v2_5`), so it speaks Korean or Spanish in your voice. `similarity_boost` is 0.9 to stay close to you.
- It's saved in `state/voice.json` and reused on restart. Redoing setup replaces the old clone (and deletes it from ElevenLabs to free the slot).
- The voice id is shown on the dashboard. Put it in `.env` as `ELEVENLABS_VOICE_ID` to keep it if `state/` is cleared, or to share one voice across laptops.
- **Instant voice cloning needs a paid ElevenLabs plan (Starter or above).** On the free plan, setup fails with an error from ElevenLabs.
- "Record in browser" needs `localhost` or https (browsers block the mic on plain `http://<lan-ip>`). Otherwise use the badge.

## Contexts (the dashboard checkboxes)

Five contexts are built in: **Pickleball, Tennis, Computer science, Math** (fields) and **LARP mode** (a style).

- **Fields:** the backend only chooses between the checked fields (plus "general" for everyday talk). With one checked it always uses that field; with none checked it uses no jargon. Each field has its own glossary, so the same word is translated per field: "set" → 세트 in tennis, 집합 in math.
- **LARP mode** makes you sound more impressive while translating. Locally (free), it drops fillers ("um", "like,", "kind of") and upgrades weak phrases ("I think" → "I'm confident that", "pretty good" → "excellent"). Then one extra line in the same LLM request asks it to make the speaker sound like a seasoned expert in the detected field. No extra API call. The voice switches to a more confident delivery.
- **Data:** each context's content is read from `data/` (`glossaries/<context>.json`, `train.jsonl`, `larp.json`; formats in [../docs/messages.md](../docs/messages.md#data-files-read-from-data-at-startup-restart-the-backend-after-changing-them)). Until a file exists, `seeds.json` is used, and the dashboard shows `built-in` next to that checkbox. Restart the backend after changing `data/`.
- **Adding a context** later means adding it to `FIELDS` (or `STYLES`) in `ml.py` and putting its data in `data/`.

## How it works

1. **VAD.** `webrtcvad` checks every 30 ms frame. A sentence ends after 0.7 s of silence (or after 15 s). Blips under 0.4 s are dropped, because speech to text invents words for them. Push-to-talk release ends a sentence immediately.
2. **Speech to text: ElevenLabs Scribe** (`scribe_v2`, same key as the voice) transcribes the sentence and detects its language (Korean and Tamil too). The checked fields' jargon is sent as `keyterms` so it's spelled right ("kernel", not "colonel"). Featherless has no speech-to-text; a speech model run locally on the laptop was slower (2.9 s vs 0.6 s) and misheard jargon ("colonel" for "kernel") in testing.
3. **Local ML** (`ml.py`, ~10 ms on CPU):
   - **Field:** MiniLM sentence embedding → LogisticRegression, trained at startup on the training sentences and glossary terms. Unchecked fields are masked out. Smoothed over the conversation so one odd sentence doesn't flip it.
   - **Tone:** `?` → question, `!` → excited, otherwise the nearest tone prototype by embedding (neutral if nothing is close).
   - **Jargon:** glossary lookup for the detected field. Each term's translation is picked by Beta posterior mean over 👍/👎 counts, with the glossary's first option as the default.
   - **Context:** short packs are sent whole; long ones are cut down to the 5 lines most relevant to this sentence.
   - **LARP** (if checked): filler removal and phrase upgrades, shown on the dashboard as crossed-out original → upgraded text.
4. **Featherless** translates with an open model (`Mistral-Small-3.2-24B`, temperature 0) through the OpenAI SDK (Featherless uses the same API). Every reply is checked for the right script (Korean must contain Hangul and no Chinese, Spanish no Asian scripts, ...); a wrong-language reply or an error falls back to `Mistral-Nemo`. The model is warmed up at startup, because Featherless takes several seconds to load a model on first use. It's skipped when the speaker already uses the target language (unless LARP is on, which still polishes).
5. **ElevenLabs** (`eleven_flash_v2_5`, `pcm_16000`) speaks it. The tone sets `stability` and `style` (`TONE_SETTINGS` in `main.py`). Tone tags like `[excited]` are only added for `eleven_v3` models; other models would read them out loud.
6. **Playback.** Audio goes to the badge in 100 ms frames at about real time. New audio waits until the previous clip has finished plus 300 ms, and mic audio during that window is ignored.

**Caching:** identical translation requests and identical speech are cached on disk (`cache/`), so rehearsing the demo sentences doesn't burn credits. The dashboard shows "cached" for those stages.

**Errors:** if an API call fails, that sentence is skipped (shown in red on the dashboard) and listening continues.

## Feedback and learning

- 👍 (dashboard or badge): every jargon choice in that sentence gets a success.
- 👎 on the dashboard **chip** of a word (e.g. `branch → 나뭇가지`): that word gets a failure and the sentence is replayed with its next option.
- 👎 button (dashboard row or badge): the same, applied to the word the model is least sure about.
- One 👎 is enough to switch a word's default; the choice is remembered across restarts (`state/term_stats.json`). **Reset learning** on the dashboard clears it before a demo.
- The dashboard shows term accuracy and a rolling learning curve (last 5 ratings).

Every sentence logs its timing:
```
utt 3 | vad 0.4ms | stt 590ms | ml 11ms | llm 1400ms | elevenlabs 350ms | total 1351ms | cs/neutral | 'The kernel...' -> '커널이...' | terms {'kernel': '커널'}
```

## Deployment: run locally, share with cloudflared

The backend runs on the laptop (`python serve.py`, port 8000). For the demo, expose it with a Cloudflare tunnel:
```bash
cloudflared tunnel --url http://localhost:8000      # prints https://<random>.trycloudflare.com
```
- Open that https address on any device: the dashboard, the WebSockets (`wss://`) and the microphone work through it.
- Devices coming through the tunnel need the pairing code (`?token=<code>`), even though the tunnel connects from the laptop itself. Set `PUBLIC_URL=https://<random>.trycloudflare.com` in `.env` so Session → Pair Another Device shows tunnel links.
- A badge connecting through the tunnel needs TLS (`wss://…/ws/badge?token=<code>`, `beginSSL` in the firmware); on the same Wi-Fi as the laptop it can use `ws://<laptop-ip>:8000/ws/badge?token=<code>`.
- If the dashboard is hosted separately (e.g. on Vercel, serving only the `dashboard/` folder), open it with `?server=<random>.trycloudflare.com` so it talks to the laptop. Otherwise the dashboard always uses the address it was loaded from.

## Sentry

Set `SENTRY_DSN` (Sentry → Project Settings → Client Keys) in `.env`. Without it, Sentry is off and costs nothing.

- **Each failing service is its own issue.** Speech to text, local ML, translation (LLM), ElevenLabs, voice cloning and badge playback errors are reported with a `step` tag (`speech_to_text`, `local_ml`, `translation`, `elevenlabs`, `voice_clone`, `badge_playback`). A sentence's error is reported once. Using the fallback LLM is reported as a warning.
- **Traces:** each sentence is a trace (`translate sentence`) with a span per stage, so the Performance view shows which step is slow. `SENTRY_TRACES_SAMPLE_RATE` (default 0.2).
- **Unhandled server errors** are captured automatically (FastAPI integration). Log lines become breadcrumbs on issues, not issues of their own.
- **Dashboard:** `@sentry/browser` (in `dashboard/vendor/`) uses the same DSN via `/api/config`. It reports JavaScript errors, the WebSocket dropping, commands sent while disconnected, and rejected pairing codes.
- **Demo:** keep the Sentry Issues page open on a second screen and filter by `step` to see what broke.

## Data and evaluation

The backend reads `data/` at startup (restart after changes) and never writes to it. Formats: [../docs/messages.md](../docs/messages.md#data-files-read-from-data-at-startup-restart-the-backend-after-changing-them).

- **Both directions:** English speech → Korean/Tamil (`tennis.json`, `pickleball.json`, `selected/*.json`) and Korean speech → English (Kenneth's `cs.json` / `academia.json` entries like 실수 → real number, not "mistake"). `academia.json` is the math glossary.
- **Tamil** is a target language: 45 terms from the team's glossaries; ElevenLabs speaks it.
- The team's entries come first; the built-in ones add alternatives for 👎.

`python evaluate.py` compares a **plain translator** (same LLM, no glossary) with **Larpslator** on the team's test sets (`eval-ta.jsonl`, `CHECK.md`). Nov 1, 15 sentences each:

| Set | Plain | Larpslator |
|---|---|---|
| English → Tamil | 2/15 (13%) | **15/15 (100%)** |
| Korean → English | 14/15 (93%) | **15/15 (100%)** |

It measures whether the expected term appears, not overall quality, and the Tamil references are unreviewed drafts. `--limit 0` runs everything; `--auto` detects the field instead of using the sentence's own. Results go to `logs/eval-*.json`.

## Messages and data formats

See [../docs/messages.md](../docs/messages.md) for every WebSocket message (with examples), and the glossary / training-sentence formats read from `data/`.

## Optional settings (`.env`)

| Variable | Default |
|---|---|
| `LARPSLATOR_TOKEN` | the pairing code; generated and saved if empty |
| `SENTRY_DSN` / `SENTRY_TRACES_SAMPLE_RATE` | Sentry off if empty / `0.2` |
| `ELEVENLABS_VOICE_ID` | empty; voice setup on the dashboard sets the voice. Set this to reuse a clone (e.g. on another laptop) |
| `ELEVENLABS_MODEL` | `eleven_flash_v2_5` |
| `FEATHERLESS_MODEL` | `mistralai/Mistral-Small-3.2-24B-Instruct-2506` (any chat model on featherless.ai) |
| `FEATHERLESS_FALLBACK_MODEL` | `mistralai/Mistral-Nemo-Instruct-2407`, used if the main model errors or answers in the wrong language |
| `SENTRY_DSN` | empty = Sentry off |
| `SENTRY_ENVIRONMENT` | `local` |
| `PUBLIC_URL` | empty; the cloudflared https address, for the pairing links |
| `TARGET_LANGUAGE` | `Korean` |
