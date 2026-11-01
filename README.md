# Larpslator

A clip-on live translator that gets jargon right because it knows what field you're talking about.
Built at LarpHacks 2026 (Toronto).

## How it works
Badge (ESP32) -> laptop backend (speech-to-text, domain detection, translation, ElevenLabs voice, live learning) -> web dashboard.

## Folders (one owner each, so nobody edits the same files)
| Folder | Owner | What's in it |
|---|---|---|
| `firmware/` | A: Hardware | ESP32 code (buttons, mic, speaker, WebSocket) |
| `backend/` | B: Backend (+ C for `domain.py`, `learner.py`, `terms.py`) | FastAPI server and pipeline |
| `dashboard/` | D: Dashboard | `index.html` (plain JS + Chart.js) |
| `data/` | D + C | glossaries, training sentences, evaluation set |
| `docs/` | everyone | message formats (`messages.md`) |

## Run the backend
```
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env    # then put your real keys in .env
uvicorn server:app --host 0.0.0.0 --port 8000
```
`--host 0.0.0.0` lets the ESP32 reach the laptop over the hotspot.

## Team
- A: Hardware & firmware: 
- B: Backend pipeline: 
- C: Machine learning: 
- D: Dashboard, data & pitch: 
