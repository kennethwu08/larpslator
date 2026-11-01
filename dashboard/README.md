# Dashboard (Role D)

The app people see during the demo: what the badge heard, the translation, which field and jargon the backend picked, the learning curve, and the controls. Plain HTML/CSS/JS, no build step.

## Run it

| How | Open | Needs |
|---|---|---|
| **Fake data** (start here) | `dashboard/index.html?mock=play` (double-click the file, then add `?mock=play` to the URL) | nothing |
| Fake data, idle | `index.html?mock` (press Listen yourself) | nothing |
| Real backend | `http://localhost:8000` (the backend serves this folder) | backend running, see [../backend/README.md](../backend/README.md) |
| Real backend on another laptop | `index.html?server=192.168.1.20:8000` | same Wi-Fi/hotspot |

The **MOCK DATA** pill in the header tells you which one you're looking at. The backend's own minimal test page is at `http://localhost:8000/reference`.

## Files

```
index.html          layout (restyle/rearrange freely)
css/style.css       all styling; colors are variables at the top
js/app.js           UI: renders events, wires up buttons (edit freely)
js/api.js           backend client: the ONLY code that knows the protocol  ⚠ don't change without the backend
js/mock.js          fake backend with the same API, for ?mock                ⚠ keep in sync with api.js
vendor/chart.umd.js Chart.js 4.4.1, kept locally so it works on bad Wi-Fi
```

## Rules

- **Change the look all you want** (`index.html`, `css/style.css`, `js/app.js`).
- **Don't build JSON or open sockets in `app.js`.** Use `larp.*` methods and events. If you need something the API doesn't have, ask whoever owns the backend: it changes `api.js`, `mock.js`, the backend and [../docs/messages.md](../docs/messages.md) together.
- Keep `?mock` working: it's how anyone can work on the UI without keys or a badge.

## API (`js/api.js`)

```js
const larp = Larp.connect();   // real backend, or the mock with ?mock

// events: every server message type from docs/messages.md, plus "open" / "close"
larp.on("status", m => ...);        // listening, target, contexts[], badge, voice, packs...
larp.on("transcript", m => ...);    // { id, source, lang }: what was heard, before translation
larp.on("utterance", u => ...);     // full result: translation, domain, domain_probs, terms[], larp, timing_ms
larp.on("feedback", m => ...);      // { id, val, term }
larp.on("metrics", m => ...);       // { n, accuracy, curve[], window }: learning curve
larp.on("badges", m => ...);        // every 5 s: badges online (battery, Wi-Fi, latency, in sync)
larp.on("voice_progress", m => ...);
larp.on("error", m => ...);         // { id, msg }: a sentence was skipped; listening continues

// commands
larp.setListening(true | false)
larp.setLanguage("Spanish")
larp.toggleContext("tennis" | "pickleball" | "cs" | "math" | "larp", true | false)
larp.saveNotes(name, text)                      // meeting notes (names, jargon, agenda)
larp.feedback(utteranceId, 1 | -1, term?)       // 👎 with a term = "this word is wrong"
larp.resetLearning()
larp.voiceRecordOnBadge(name) / larp.voiceStop() / larp.voiceCancel()
await larp.voiceUpload(wavBlob, name)           // with Larp.recordMicrophone()
larp.voiceTestUrl()                             // <audio> src in the user's voice (null in mock)
larp.connectBadge(id) / larp.disconnectBadge()  // which badge is used (ids from status.badges)
larp.identifyBadge(id)                          // blink it
larp.setBadgeVolume(id, 0-100)
```

The exact fields of every event, with examples, are in [../docs/messages.md](../docs/messages.md).

## Ideas / TODO for the demo

- Big fonts and high contrast for the projector (the 90-second demo script relies on the conversation, special words and learning curve being readable from the back).
- The comparison "plain translator vs Larpslator" view from the plan isn't in the backend (it would double the Gemini calls). Easiest: hard-code the plain-translator mistakes for the demo sentences.
- Show the LARP changes (`utterance.larp.changes`) more visibly when LARP is on.
