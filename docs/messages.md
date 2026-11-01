# Message formats (change only as a team)

All JSON messages have a `"t"` field with the type. Audio is always raw PCM: 16 kHz, 16-bit, mono, little-endian.

## Pairing (security)
Every device except the laptop's own browser needs the **pairing code** (dashboard: Session → Pair Another Device):
- WebSockets: add `?token=<code>` to the URL, e.g. `ws://<laptop-ip>:8000/ws/badge?token=<code>`.
- HTTP API (`/api/voice`, `/api/voice/test`): `?token=<code>` or the header `X-Larpslator-Token: <code>`.
- Wrong or missing code: the socket is accepted and then closed with code **4401**; HTTP returns **401**.
- Ports (with `python serve.py`): `:8000` plain http/ws (the badge), `:8443` https/wss (browsers on other devices; phones need https for the mic).

Mic frames: any size up to 32 KB (bigger frames are dropped). Odd-sized frames are fine: the server keeps samples aligned.

## Badge -> server  (`ws://<laptop-ip>:8000/ws/badge`)
The dashboard shows the exact address under Badge → "How to connect a badge".
Everything except audio + `ptt` is optional: a badge that only streams audio and sends buttons still works.
Several badges can be online; only the one **connected** on the dashboard is used (the first one online is connected automatically).

- Binary frames: mic audio (512-sample chunks are fine; any size works). Only used from the connected badge.
- `{"t":"hello","id":"LC-7F3A","name":"Bernard's badge","fw":"0.3","battery":87,"rssi":-54,"volume":70}`:
  send first after connecting. `id` should stay the same across reboots (e.g. from the MAC address), so a
  rebooted badge is recognized and reconnected. All fields optional.
- `{"t":"state","battery":86,"rssi":-55,"volume":70,"playing":false,"muted":false,"config_v":4}`: whenever
  something changes (all fields optional). `config_v` = the `v` of the last `config` you applied; the
  dashboard then shows "synced ✓".
- `{"t":"pong","battery":86}`: reply to `ping` (gives the dashboard the latency; extra fields like `state`).
- `{"t":"ptt","state":"start"}`: talk button pressed (starts listening)
- `{"t":"ptt","state":"end"}`: talk button released (ends the sentence right away and stops listening)
- `{"t":"fb","val":1}` / `{"t":"fb","val":-1}`: thumbs up / down on the latest sentence. Up credits every jargon choice.
  Down blames the one term the model is least sure about and replays the sentence with that term's next option.
- `{"t":"mode","domain":"cs"}`: BOOT button cycles `auto` / `pickleball` / `tennis` / `cs` / `math`.
  `auto` checks every field; a field name checks only that field. LARP stays as it was.

## Server -> badge
- `{"t":"active","value":true}`: this badge is (or isn't) the connected one. Inactive badges can show an idle LED; their audio and buttons are ignored.
- `{"t":"config","v":4,"listening":true,"target":"Korean","fields":["tennis","math"],"larp":true,"domain":"auto","voice":"Bernard","voice_setup":false}`:
  everything the badge might show (LEDs/screen). Sent on connect and whenever anything changes; `v` goes up each time.
  `voice` is empty while a stock voice is used; `voice_setup` is true while the user is recording their voice sample.
- `{"t":"mode","domain":"cs"}`: same info for older firmware: the checked field if exactly one is checked, else `auto`.
- `{"t":"ping"}`: every 5 s; answer with `pong`.
- `{"t":"identify"}`: blink the LED / beep so the user can tell which badge this is.
- `{"t":"volume","value":70}`: speaker volume 0-100.
- `{"t":"name","value":"Bernard's Badge"}`: the user renamed the badge on the dashboard (store it if you like; the dashboard name wins either way).
- Binary frames: translated speech to play, sent in 100 ms frames (3200 bytes) at about real time.
  The server never starts a new clip until the previous one has finished plus 300 ms.
  The badge should mute its mic while playing; the server also ignores mic audio during that window.

## Dashboard -> server  (`ws://<laptop-ip>:8000/ws/dashboard`)
```json
{"t":"mode","state":"listen"}                      // or "stop"
{"t":"toggle","id":"larp","on":true}               // a context checkbox: pickleball | tennis | cs | math | larp
{"t":"lang","value":"Spanish"}                     // target language
{"t":"context","name":"CS lab","text":"Prof. Lee\nkernel = OS kernel\nAgenda: scheduler review"}
{"t":"fb","val":-1,"id":3,"term":"kernel"}        // id optional (default: latest sentence); term optional (default: least-sure term)
{"t":"reset"}                                      // forget learned term choices
{"t":"voice","action":"record","name":"Bernard"}   // voice setup: start recording the badge mic
{"t":"voice","action":"stop"}                      // ...stop and create the voice clone
{"t":"voice","action":"cancel"}
{"t":"badge","action":"connect","id":"LC-7F3A"}    // use this badge (id from status.badges)
{"t":"badge","action":"disconnect"}                // use no badge (it stays online)
{"t":"badge","action":"identify","id":"LC-7F3A"}   // make it blink
{"t":"badge","action":"volume","id":"LC-7F3A","value":70}
{"t":"badge","action":"rename","id":"LC-7F3A","name":"Bernard's Badge"}
```

## Voice setup over HTTP (browser microphone)
- `POST /api/voice?name=Bernard` with a WAV file as the body (any sample rate). Creates the clone; 400 with a reason if it's too short (<20 s) or fails.
- `GET /api/voice/test` returns a short WAV spoken in the current voice, to check it sounds right.

## Server -> dashboard
`status`: sent on connect and after every change
```json
{"t":"status","listening":true,"target":"Korean","badge":true,
 "contexts":[{"id":"pickleball","label":"Pickleball","kind":"field","on":true,"source":"data"},
             {"id":"tennis","label":"Tennis","kind":"field","on":true,"source":"built-in"},
             {"id":"cs","label":"Computer science","kind":"field","on":true,"source":"built-in"},
             {"id":"math","label":"Math","kind":"field","on":false,"source":"built-in"},
             {"id":"larp","label":"LARP mode","kind":"style","on":true,"source":"built-in"}],
 "context_name":"CS lab","context":"Prof. Lee\n...","languages":["Korean","Spanish","..."],
 "packs":[{"name":"CS lab","text":"...","saved_at":"2026-11-01 10:02:11"}],
 "voice":{"ready":true,"name":"Bernard","voice_id":"abc123"},"voice_recording":null}
```
- `pairing`: `{code, dashboard_url, badge_url}` for the "Pair Another Device" sheet (only sent to paired dashboards).
- `badges`: every badge online, with whatever it reported. `mic_kbps` (256 = full 16 kHz audio arriving), `mic_level_db`
  (loudest moment in the last 5 s, dBFS) and `audio_dropped` show whether the mic audio is good. `active` = the connected one. `config_synced` = it confirmed the latest `config`.
  `badge_config` = what was last pushed to the connected badge. `badge_url` = the address to put in the badge's `config.h`.
  `badge` (bool) = a badge is connected.
  ```json
  "badge":true,"badge_url":"ws://172.20.10.2:8000/ws/badge",
  "badge_config":{"v":4,"listening":true,"target":"Korean","fields":["tennis","math"],"larp":true,"domain":"auto","voice":"Bernard","voice_setup":false},
  "badges":[{"id":"LC-7F3A","active":true,"name":"Bernard's badge","fw":"0.3","battery":86,"rssi":-55,"volume":70,
             "ip":"172.20.10.4","rtt_ms":38,"seen_s_ago":0.4,"online_s":312,"config_synced":true,
             "mic_kbps":256,"mic_level_db":-28.5,"audio_dropped":0}]
  ```
- `voice.ready` is false until voice setup is done: translations then use a stock voice, and the app should push the user to set up.
  `voice_recording` is the seconds of speech recorded so far while a badge voice setup is running, else null.
- `contexts` is the list of checkboxes, in display order. `kind: "field"` is a subject (the backend detects which checked field
  each sentence belongs to; with exactly one checked, it always uses that one; with none checked, no jargon is used).
  `kind: "style"` is LARP mode. `source` says where that context's data came from: `data` (files in `data/`) or
  `built-in` (fallback in `backend/seeds.json`).
- The meeting context pack (`context_name`, `context`, `packs`) is the separate free-text notes box.

`transcript`: as soon as Whisper finishes, before the translation
```json
{"t":"transcript","id":3,"source":"The kernel is preempting the thread.","lang":"english"}
```

`utterance`: the finished sentence, sent again with `"retry":1,2,...` after a thumbs-down replay. Timings are in ms; 0 means cached (no API call).
`domain_probs` only includes the checked fields plus `general`. `larp` is null unless LARP mode is checked.
```json
{"t":"utterance","id":3,"retry":0,"source":"Um, I think the kernel is, like, preempting the thread.","lang":"english",
 "target":"Korean","translation":"커널이 스레드를 선점하고 있다고 확신합니다.","tone":"confident",
 "domain":"cs","domain_probs":{"cs":0.88,"general":0.03,"math":0.05,"pickleball":0.02,"tennis":0.02},
 "larp":{"text":"I'm confident that the kernel is preempting the thread.",
         "changes":[{"from":"like","to":""},{"from":"Um","to":""},{"from":"I think","to":"I'm confident that"}]},
 "terms":[{"term":"kernel","match":"kernel","pos":4,"domain":"cs","options":["커널","알맹이"],"choice":"커널"},
          {"term":"thread","match":"thread","pos":31,"domain":"cs","options":["스레드","실"],"choice":"스레드"}],
 "context_lines":["Prof. Lee","Agenda: scheduler review"],
 "timing_ms":{"vad":0.4,"whisper":620,"ml":11,"llm":1410,"elevenlabs":330,"total":1371}}
```

`feedback` (`term` is the term that was blamed on a 👎, else null)
```json
{"t":"feedback","id":3,"val":-1,"term":"kernel"}
```

`metrics`: term accuracy for the learning curve (only sentences that contained jargon). `curve` is a rolling average over the last `window` ratings.
```json
{"t":"metrics","n":6,"accuracy":0.67,"curve":[0,0.5,0.67,0.75,0.8,0.8],"window":5}
```

`badges`: every 5 s while a badge is online (battery, latency), and when a badge sends `state`. Same list as `status.badges`.
```json
{"t":"badges","badges":[{"id":"LC-7F3A","active":true,"battery":85,"rtt_ms":41,"...":"..."}]}
```

`voice_progress`: during voice setup (about once a second), then once when ElevenLabs is creating the voice
```json
{"t":"voice_progress","state":"recording","speech_s":25.5,"total_s":35.0}
{"t":"voice_progress","state":"creating"}
```

`error`: a sentence was skipped (API failure etc.); listening continues
```json
{"t":"error","id":3,"msg":"RateLimitError: ..."}
```

## Data files (read from `data/` at startup; restart the backend after changing them)
The contexts themselves are fixed in `backend/ml.py`: `pickleball`, `tennis`, `cs`, `math` (fields) and `larp` (style),
plus `general` as the classifier's everyday-speech class. For each one, a file in `data/` replaces the built-in fallback.

### Glossaries (`data/glossaries/<context>.json`, e.g. `tennis.json`)
Term -> candidate translations, best first. Either a list (one target language) or one list per language:
```json
{"kernel": {"Korean": ["커널", "알맹이"], "Spanish": ["núcleo", "grano"]},
 "thread": ["스레드", "실"]}
```
Pick terms a plain translator gets wrong, especially ones shared across contexts ("set" in tennis vs math, "serve", "court").

### Training sentences (`data/train.jsonl`)
One per line. For any context that has rows here, they replace the built-in sentences for that context:
```json
{"text": "She won the first set after a long deuce game.", "domain": "tennis"}
{"text": "Where should we get dinner tonight?", "domain": "general"}
```

### LARP (`data/larp.json`)
Any key given replaces the built-in one. `{field}` in `style` becomes the detected field's name. A filler with a
trailing comma (`"like,"`) is only removed when a comma follows it, so "I like tennis" is left alone.
```json
{"style": "Make the speaker sound like a confident, seasoned {field} expert: polished and impressive, same meaning, about the same length.",
 "fillers": ["um", "uh", "like,", "you know,", "kind of"],
 "upgrades": {"I think": "I'm confident that", "pretty good": "excellent", "look at": "examine"}}
```
