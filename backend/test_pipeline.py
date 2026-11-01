"""Send a WAV file through the full pipeline (no server or badge needed) and print each stage.

Usage:
  python test_pipeline.py sample.wav
  python test_pipeline.py sample.wav --lang Spanish --context "Prof. Lee; kernel = OS kernel"
  python test_pipeline.py sample.wav --context-file contexts/cs-lab.json

Each translated sentence is written to out_<n>.wav so you can listen to it.
"""
import argparse
import json
import time
import wave
from pathlib import Path

import numpy as np

import main


def load_wav_16k_mono(path: str) -> bytes:
    """Reads a WAV and converts it to 16 kHz 16-bit mono PCM if needed."""
    with wave.open(path, "rb") as w:
        rate, channels, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if width != 2:
        raise SystemExit(f"{path}: need 16-bit WAV, got {width * 8}-bit")
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    if rate != main.SAMPLE_RATE:
        n = int(len(audio) * main.SAMPLE_RATE / rate)
        audio = np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio)
        print(f"(resampled {rate} Hz -> {main.SAMPLE_RATE} Hz)")
    return audio.astype(np.int16).tobytes()


def stage(name: str, value: str = ""):
    print(f"  {name:<12} {value}")


def main_cli():
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("--lang", default=main.DEFAULT_TARGET, help="target language (default: %(default)s)")
    ap.add_argument("--context", default="", help="meeting context text")
    ap.add_argument("--context-file", help="saved context pack JSON")
    ap.add_argument("--contexts", default=",".join(main.FIELDS),
                    help="checked contexts, comma-separated: %s, larp (default: all fields)" % ", ".join(main.FIELDS))
    args = ap.parse_args()

    context = args.context
    if args.context_file:
        context = json.loads(Path(args.context_file).read_text())["text"]

    active = {c.strip() for c in args.contexts.split(",") if c.strip()}
    pcm = load_wav_16k_mono(args.wav)
    print(f"\nInput: {args.wav}, {len(pcm) / 2 / main.SAMPLE_RATE:.1f}s · target: {args.lang} · "
          f"context: {len(context)} chars · checked: {', '.join(sorted(active))}\n")

    # VAD: feed in 100 ms chunks like the badge would, then flush the tail.
    seg = main.Segmenter()
    t = time.perf_counter()
    sentences = []
    for i in range(0, len(pcm), 3200):
        sentences += seg.add(pcm[i:i + 3200])
    if tail := seg.flush():
        sentences.append(tail)
    print(f"VAD: {len(sentences)} sentence(s) in {(time.perf_counter() - t) * 1000:.0f}ms\n")
    if not sentences:
        print("No speech found. Is the file silent, or very quiet?")
        return

    for n, (sentence_pcm, vad_s) in enumerate(sentences, 1):
        print(f"Sentence {n} ({len(sentence_pcm) / 2 / main.SAMPLE_RATE:.1f}s of audio)")
        try:
            r = main.run_pipeline(sentence_pcm, args.lang, context, vad_s, active)
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}  (skipping, like the server does)\n")
            continue
        tm = r["timing_ms"]
        ms = lambda v: "cached" if v == 0 else f"{v}ms"
        stage("vad", f"{tm['vad']}ms")
        stage("speech", f"{tm['stt']}ms  [{r['lang']}] {r['source']!r}")
        if not r["source"]:
            print("  (empty transcript, skipped)\n")
            continue
        probs = ", ".join(f"{d} {p:.0%}" for d, p in sorted(r["domain_probs"].items(), key=lambda x: -x[1]))
        stage("ml (local)", f"{tm['ml']}ms  domain={r['domain']} ({probs})  tone={r['tone']}")
        stage("", f"terms: {', '.join(t['match'] + ' -> ' + t['choice'] for t in r['terms']) or '-'}")
        stage("", f"context sent: {r['context_lines'] or '-'}")
        if r["larp"]:
            stage("larp (local)", f"{r['larp']['text']!r}  changes: {r['larp']['changes'] or '-'}")
        stage("llm", f"{ms(tm['llm'])}  {r['translation']!r}")
        out = f"out_{n}.wav"
        Path(out).write_bytes(main.pcm_to_wav(r["audio"]))
        stage("elevenlabs", f"{ms(tm['elevenlabs'])}  {len(r['audio']) / 2 / main.SAMPLE_RATE:.1f}s audio -> {out}")
        stage("total", f"{tm['total']}ms\n")


if __name__ == "__main__":
    main_cli()
