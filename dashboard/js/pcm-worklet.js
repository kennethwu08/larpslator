/* Web audio fallback: microphone -> 16 kHz mono 16-bit PCM, the badge's format. (WEB_AUDIO, see backend/web_audio.py)
 *
 * Loaded twice: as an AudioWorklet module (the normal path), and as a plain <script> so the ScriptProcessorNode
 * fallback can reuse the same encoder (globalThis.LarpPcmEncoder) on browsers without AudioWorklet.
 */
(function () {
  "use strict";

  /** Downsamples by averaging each output sample's span of input samples (a box filter that keeps aliasing
   *  down), converts to 16-bit, and emits fixed-size chunks. Works for any input rate (48 000, 44 100, ...). */
  class PcmEncoder {
    constructor(inRate, outRate = 16000, chunkSamples = 1600) {
      this.ratio = inRate / outRate;
      this.boundary = this.ratio;     // input-sample position where the current output sample ends
      this.pos = 0;
      this.sum = 0;
      this.n = 0;
      this.chunk = new Int16Array(chunkSamples);
      this.fill = 0;
      this.levelSum = 0;              // for the level meter: mean square of the input since the last chunk
      this.levelN = 0;
    }

    /** Feed mono float samples (-1..1). Returns finished chunks: [{pcm: ArrayBuffer, level: rms 0..1}]. */
    push(input) {
      const out = [];
      for (let i = 0; i < input.length; i++) {
        const x = input[i];
        this.sum += x; this.n++; this.pos++;
        this.levelSum += x * x; this.levelN++;
        if (this.pos >= this.boundary) {
          const v = Math.max(-1, Math.min(1, this.sum / this.n));
          this.chunk[this.fill++] = v < 0 ? v * 0x8000 : v * 0x7fff;
          this.sum = 0; this.n = 0; this.boundary += this.ratio;
          if (this.fill === this.chunk.length) {
            out.push({ pcm: this.chunk.slice().buffer, level: Math.sqrt(this.levelSum / Math.max(1, this.levelN)) });
            this.fill = 0; this.levelSum = 0; this.levelN = 0;
          }
        }
      }
      return out;
    }
  }

  /** Mixes all input channels to mono. */
  function mono(channels) {
    if (channels.length === 1) return channels[0];
    const m = new Float32Array(channels[0].length);
    for (const ch of channels) for (let i = 0; i < m.length; i++) m[i] += ch[i] / channels.length;
    return m;
  }

  globalThis.LarpPcmEncoder = PcmEncoder;
  globalThis.LarpMono = mono;

  if (typeof AudioWorkletProcessor !== "undefined") {
    class PcmCapture extends AudioWorkletProcessor {
      constructor(options) {
        super();
        const o = options.processorOptions || {};
        this.encoder = new PcmEncoder(sampleRate, o.outRate || 16000, o.chunkSamples || 1600);
      }
      process(inputs) {
        const input = inputs[0];
        if (input && input.length && input[0].length) {
          for (const c of this.encoder.push(mono(input))) this.port.postMessage(c, [c.pcm]);
        }
        return true;  // keep running until disconnected
      }
    }
    registerProcessor("larp-pcm-capture", PcmCapture);
  }
})();
