# Message formats (change only as a team)

All JSON messages have a `"t"` field with the type. Audio is always raw PCM: 16 kHz, 16-bit, mono, little-endian.

## Badge -> server  (`ws://<laptop-ip>:8000/ws/badge`)
- Binary frames: mic audio (512-sample chunks are fine; any size works)
- `{"t":"hello"}`: badge connected (the server replies with the current `mode`)
- `{"t":"ptt","state":"start"}`: talk button pressed (starts listening)
- `{"t":"ptt","state":"end"}`: talk button released (ends the sentence right away and stops listening)
- `{"t":"fb","val":1}` / `{"t":"fb","val":-1}`: thumbs up / down on the latest sentence. Up credits every jargon choice.
  Down blames the one term the model is least sure about and replays the sentence with that term's next option.
- `{"t":"mode","domain":"cs"}`: BOOT button cycles `auto` / `academia` / `cs` / `med` / `general`

## Server -> badge
- `{"t":"mode","domain":"cs"}`: current field, sent on connect and whenever it changes
- Binary frames: translated speech to play, sent in 100 ms frames (3200 bytes) at about real time.
  The server never starts a new clip until the previous one has finished plus 300 ms.
  The badge should mute its mic while playing; the server also ignores mic audio during that window.

## Dashboard -> server  (`ws://<laptop-ip>:8000/ws/dashboard`)
```json
{"t":"mode","state":"listen"}                      // or "stop"
{"t":"mode","domain":"med"}                        // auto | academia | cs | med | general
{"t":"lang","value":"Spanish"}                     // target language
{"t":"context","name":"CS lab","text":"Prof. Lee\nkernel = OS kernel\nAgenda: scheduler review"}
{"t":"fb","val":-1,"id":3,"term":"kernel"}        // id optional (default: latest sentence); term optional (default: least-sure term)
{"t":"reset"}                                      // forget learned term choices
```

## Server -> dashboard
`status`: sent on connect and after every change
```json
{"t":"status","listening":true,"target":"Korean","domain_mode":"auto","badge":true,
 "context_name":"CS lab","context":"Prof. Lee\n...","languages":["Korean","Spanish","..."],
 "domain_modes":["auto","academia","cs","med","general"],
 "packs":[{"name":"CS lab","text":"...","saved_at":"2026-11-01 10:02:11"}]}
```

`transcript`: as soon as Whisper finishes, before the translation
```json
{"t":"transcript","id":3,"source":"The kernel is preempting the thread.","lang":"english"}
```

`utterance`: the finished sentence, sent again with `"retry":1,2,...` after a thumbs-down replay. Timings are in ms; 0 means cached (no API call).
```json
{"t":"utterance","id":3,"retry":0,"source":"The kernel is preempting the thread.","lang":"english",
 "target":"Korean","translation":"커널이 스레드를 선점하고 있습니다.","tone":"neutral",
 "domain":"cs","domain_probs":{"academia":0.05,"cs":0.88,"general":0.03,"med":0.04},
 "terms":[{"term":"kernel","match":"kernel","pos":4,"domain":"cs","options":["커널","알맹이"],"choice":"커널"},
          {"term":"thread","match":"thread","pos":31,"domain":"cs","options":["스레드","실"],"choice":"스레드"}],
 "context_lines":["Prof. Lee","Agenda: scheduler review"],
 "timing_ms":{"vad":0.4,"whisper":620,"ml":11,"gemini":410,"elevenlabs":330,"total":1371}}
```

`feedback` (`term` is the term that was blamed on a 👎, else null)
```json
{"t":"feedback","id":3,"val":-1,"term":"kernel"}
```

`metrics`: term accuracy for the learning curve (only sentences that contained jargon). `curve` is a rolling average over the last `window` ratings.
```json
{"t":"metrics","n":6,"accuracy":0.67,"curve":[0,0.5,0.67,0.75,0.8,0.8],"window":5}
```

`error`: a sentence was skipped (API failure etc.); listening continues
```json
{"t":"error","id":3,"msg":"RateLimitError: ..."}
```

## Glossary files (`data/glossaries/<domain>.json`)
Term -> candidate translations, best first. Either a list (one target language) or one list per language:
```json
{"kernel": {"Korean": ["커널", "알맹이"], "Spanish": ["núcleo", "grano"]},
 "thread": ["스레드", "실"]}
```
Files here are merged on top of the built-in seeds in `backend/seeds.json`.

## Training sentences (`data/train.jsonl`)
One per line, added to the domain classifier at startup:
```json
{"text": "The patient presented with a fever.", "domain": "med"}
```
