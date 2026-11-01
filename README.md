# Larpslator

A clip-on live translator that gets jargon right because it knows what field you're talking about.

Regular translators don't know the context, so technical words come out wrong: "kernel" in a CS lecture isn't a corn kernel, and a patient who "presented with a fever" didn't give a presentation. Larpslator figures out what field the conversation is in (CS, medicine, academia) and translates the jargon the way people in that field actually use it.

## What it does
- **Push-to-talk badge:** hold the button, speak, and hear the translation out loud
- **Knows the context:** detects which field you're talking about, or you can pick it with a button
- **Gets jargon right:** uses a glossary for each field so technical terms are translated correctly
- **Learns from you:** thumbs up / thumbs down buttons teach it which translation of a word you want, and it improves as you use it
- **Live dashboard:** shows the conversation, the detected field, the special words it found, and a plain translation side by side with the context-aware one

## How it works
Badge (ESP32) → speech-to-text → field detection → context-aware translation → ElevenLabs voice → back to the badge, with everything shown live on the dashboard.

Built at LarpHacks 2026 (Toronto).
By Bernard Kim, Justin Cen, Sharvesh Kandavel and Kenneth Wu
