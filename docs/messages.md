# Message formats (agree on these before coding - change only as a team)

## Badge -> server  (/ws/badge)
- Binary frames: 16 kHz, 16-bit, mono PCM mic audio (512-sample chunks)
- `{"t":"hello"}`                         badge connected
- `{"t":"ptt","state":"start"}`           talk button pressed
- `{"t":"ptt","state":"end"}`             talk button released
- `{"t":"fb","val":1}` / `{"t":"fb","val":-1}`   thumbs up / down
- `{"t":"mode","domain":"cs"}`            BOOT button: auto / academia / cs / med

## Server -> badge
- `{"t":"mode","domain":"cs"}`            current domain
- Binary frames: 16 kHz, 16-bit, mono PCM audio to play

## Server -> dashboard  (/ws/dashboard)
Every event has `"id"` (utterance id) and `"ts"` (timestamp).
- `transcript`  original text
- `domain`      detected domain + probabilities
- `terms`       special words found
- `translation` context-aware translation AND the plain (no-context) translation
- `feedback`    thumbs up/down and the sentence it applied to
- `metrics`     term accuracy for the learning curve

Fill in one full example JSON for each event here before anyone starts coding.
