# Backend

Badge mic audio → voice activity detection → Whisper → **local ML** → Featherless LLM → ElevenLabs → back to the badge, with a live dashboard.

**The LLM only translates.** Everything else (detecting the field, tone, finding jargon, choosing each jargon word's translation, learning from 👍/👎, trimming the context pack, the LARP phrase upgrades) runs locally for free in `ml.py`. The LLM (on Featherless) gets one short plain-text request per sentence:

```
Translate into Korean. Reply with the translation only.
Use these term translations: merge = 병합하다; branch = 브랜치; kernel = 커널
Context: Prof. Lee; Agenda: build system
Text: Can you merge my branch before the kernel build?
```

```
main.py               server + pipeline (VAD, Whisper, LLM, ElevenLabs, playback)
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
uvicorn main:app --host 0.0.0.0 --port 8000
```

The first start downloads the `all-MiniLM-L6-v2` model (~90 MB, into `backend/.models/`), so do it before you're on venue Wi-Fi. After that the ML starts without internet. It runs on ONNX (`fastembed`), not PyTorch: ~3 ms per sentence and ~250 MB of RAM for the whole server.

- Dashboard: http://localhost:8000
- Badge connects to `ws://<laptop-ip>:8000/ws/badge` (find the IP with `ipconfig getifaddr en0` on macOS). The laptop and badge must be on the same network (the phone hotspot).

## Test without the badge

```bash
# make a sample (macOS), or use any WAV; it's converted to 16 kHz mono automatically
say -o sample.wav --data-format=LEI16@16000 "The kernel scheduler is preempting the thread. [[slnc 1200]] Can we review the agenda after lunch?"

python test_pipeline.py sample.wav --lang Korean --context "Prof. Lee; kernel = OS kernel"
python test_pipeline.py sample.wav --contexts math,larp      # only math checked, LARP on
```

It prints every stage's output and timing (field, tone, terms found, which context lines went to the LLM) and saves each translation as `out_<n>.wav`.

## Contexts (the dashboard checkboxes)

Five contexts are built in: **Pickleball, Tennis, Computer science, Math** (fields) and **LARP mode** (a style).

- **Fields:** the backend only chooses between the checked fields (plus "general" for everyday talk). With one checked it always uses that field; with none checked it uses no jargon. Each field has its own glossary, so the same word is translated per field: "set" → 세트 in tennis, 집합 in math.
- **LARP mode** makes you sound more impressive while translating. Locally (free), it drops fillers ("um", "like,", "kind of") and upgrades weak phrases ("I think" → "I'm confident that", "pretty good" → "excellent"). Then one extra line in the same LLM request asks it to make the speaker sound like a seasoned expert in the detected field. No extra API call. The voice switches to a more confident delivery.
- **Data:** each context's content is read from `data/` (`glossaries/<context>.json`, `train.jsonl`, `larp.json`; formats in [../docs/messages.md](../docs/messages.md#data-files-read-from-data-at-startup-restart-the-backend-after-changing-them)). Until a file exists, `seeds.json` is used, and the dashboard shows `built-in` next to that checkbox. Restart the backend after changing `data/`.
- **Adding a context** later means adding it to `FIELDS` (or `STYLES`) in `ml.py` and putting its data in `data/`.

## How it works

1. **VAD.** `webrtcvad` checks every 30 ms frame. A sentence ends after 0.7 s of silence (or after 15 s). Blips under 0.4 s are dropped, because Whisper makes up text for them. Push-to-talk release ends a sentence immediately.
2. **Whisper** (`whisper-1`) transcribes the sentence and detects its language. Its `prompt` lists the current field's jargon so terms are spelled right, which costs nothing extra.
3. **Local ML** (`ml.py`, ~10 ms on CPU):
   - **Field:** MiniLM sentence embedding → LogisticRegression, trained at startup on the training sentences and glossary terms. Unchecked fields are masked out. Smoothed over the conversation so one odd sentence doesn't flip it.
   - **Tone:** `?` → question, `!` → excited, otherwise the nearest tone prototype by embedding (neutral if nothing is close).
   - **Jargon:** glossary lookup for the detected field. Each term's translation is picked by Beta posterior mean over 👍/👎 counts, with the glossary's first option as the default.
   - **Context:** short packs are sent whole; long ones are cut down to the 5 lines most relevant to this sentence.
   - **LARP** (if checked): filler removal and phrase upgrades, shown on the dashboard as crossed-out original → upgraded text.
4. **Featherless** (`Qwen/Qwen2.5-7B-Instruct` by default, temperature 0) translates. Featherless uses the OpenAI API format, so it goes through the `openai` SDK with a different base URL. Open models sometimes add a label, quotes or a note; those are stripped. It's skipped when the speaker already uses the target language (unless LARP is on, which still polishes).
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
utt 3 | vad 0.4ms | whisper 610ms | ml 11ms | llm 380ms | elevenlabs 350ms | total 1351ms | cs/neutral | 'The kernel...' -> '커널이...' | terms {'kernel': '커널'}
```

## Host it on Render (optional)

`render.yaml` in the repo root is a Render Blueprint: in Render, **New → Blueprint**, pick this repo, paste the keys it asks for. The dashboard is then at `https://<service>.onrender.com` and the badge connects to `wss://<service>.onrender.com/ws/badge`.

- **Free tier sleeps after 15 minutes idle,** and waking takes about a minute. Open `/health` a few minutes before the demo (and keep the dashboard tab open, so its WebSocket keeps it awake).
- **Disk is wiped on every restart/deploy:** saved context packs, learned term choices and caches start over. Put context packs you need into the repo's `backend/contexts/`.
- **The badge needs TLS for `wss://`** (port 443): the firmware must use `beginSSL` instead of `begin`. Keep the laptop server as the backup.
- The whole server uses ~250 MB of RAM, so it fits the free 512 MB instance.

## Sentry (optional)

Set `SENTRY_DSN` and every crash, plus every skipped sentence (API errors), shows up in Sentry with its traceback, so you don't have to watch the terminal during the demo. Leave it empty to turn Sentry off.

## Messages and data formats

See [../docs/messages.md](../docs/messages.md) for every WebSocket message (with examples), and the glossary / training-sentence formats read from `data/`.

## Optional settings (`.env`)

| Variable | Default |
|---|---|
| `ELEVENLABS_VOICE_ID` | a premade voice; set this to your cloned voice |
| `ELEVENLABS_MODEL` | `eleven_flash_v2_5` |
| `FEATHERLESS_MODEL` | `Qwen/Qwen2.5-7B-Instruct` (any chat model on featherless.ai; Qwen is strong at Korean/Chinese/Japanese) |
| `SENTRY_DSN` | empty = Sentry off |
| `SENTRY_ENVIRONMENT` | `local` (`render` on Render) |
| `TARGET_LANGUAGE` | `Korean` |
