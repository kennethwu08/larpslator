/* Larpslator backend client.
 *
 * The ONLY file that knows the wire format (docs/messages.md). UI code calls these methods and
 * listens for events; it never builds JSON or opens sockets itself. If the backend protocol
 * changes, this file (and mock.js) change, nothing else.
 *
 *   const larp = Larp.connect();            // real backend, or the mock with ?mock in the URL
 *   larp.on("utterance", u => ...);         // events = message types from docs/messages.md,
 *   larp.on("open" | "close", () => ...);   //   plus "open" / "close" for the connection
 *   larp.toggleContext("tennis", true);     // commands, see below
 *
 * Which backend: same host when the page is served by the backend (http://<laptop>:8000),
 * else localhost:8000, or ?server=192.168.1.20:8000 to choose.
 */
(function () {
  "use strict";

  class Emitter {
    constructor() { this.handlers = {}; }
    on(type, fn) { (this.handlers[type] ||= []).push(fn); return this; }
    emit(type, msg) {
      for (const fn of [...(this.handlers[type] || []), ...(this.handlers["*"] || [])]) {
        try { fn(msg, type); } catch (e) { console.error(`handler for "${type}" failed`, e); }
      }
    }
  }

  function serverAddress() {
    const fromUrl = new URLSearchParams(location.search).get("server");
    if (fromUrl) return fromUrl.replace(/^\w+:\/\//, "").replace(/\/$/, "");
    if (location.protocol.startsWith("http")) return location.host;
    return "localhost:8000";  // opened as a file
  }

  class LarpClient extends Emitter {
    constructor(address) {
      super();
      this.address = address;
      this.secure = location.protocol === "https:";
      this.connected = false;
      this._connect();
    }

    get httpBase() { return `${this.secure ? "https" : "http"}://${this.address}`; }

    _connect() {
      const ws = new WebSocket(`${this.secure ? "wss" : "ws"}://${this.address}/ws/dashboard`);
      ws.onopen = () => { this.connected = true; this.emit("open"); };
      ws.onclose = () => {
        if (this.connected) this.emit("close");
        this.connected = false;
        setTimeout(() => this._connect(), 1000);  // the backend restarts often during the hackathon
      };
      ws.onmessage = e => {
        let msg;
        try { msg = JSON.parse(e.data); } catch { return; }
        this.emit(msg.t, msg);
      };
      this.ws = ws;
    }

    _send(msg) {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(msg));
      else console.warn("not connected, dropped", msg);
    }

    // ------------------------------------------------------------ commands
    setListening(on) { this._send({ t: "mode", state: on ? "listen" : "stop" }); }
    setLanguage(language) { this._send({ t: "lang", value: language }); }
    /** Context checkbox: "pickleball" | "tennis" | "cs" | "math" | "larp" (ids come from status.contexts). */
    toggleContext(id, on) { this._send({ t: "toggle", id, on }); }
    /** Meeting notes pack (names, jargon, agenda). Saved on the backend and made active. */
    saveNotes(name, text) { this._send({ t: "context", name, text }); }
    /** 👍 (val 1) or 👎 (val -1). For 👎, pass the term the user clicked; else the backend picks one. */
    feedback(utteranceId, val, term) {
      const msg = { t: "fb", val, id: utteranceId };
      if (term) msg.term = term;
      this._send(msg);
    }
    resetLearning() { this._send({ t: "reset" }); }

    // voice setup from the badge mic
    voiceRecordOnBadge(name) { this._send({ t: "voice", action: "record", name }); }
    voiceStop() { this._send({ t: "voice", action: "stop" }); }
    voiceCancel() { this._send({ t: "voice", action: "cancel" }); }

    /** Voice setup from a browser recording (see Larp.recordMicrophone). Resolves to status.voice. */
    async voiceUpload(wavBlob, name) {
      const r = await fetch(`${this.httpBase}/api/voice?name=${encodeURIComponent(name || "My voice")}`,
        { method: "POST", body: wavBlob, headers: { "Content-Type": "audio/wav" } });
      const body = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(body.detail || `voice setup failed (${r.status})`);
      return body;
    }
    /** URL of a short WAV in the current voice, for an <audio> element. */
    voiceTestUrl() { return `${this.httpBase}/api/voice/test?t=${Date.now()}`; }
  }

  // ------------------------------------------------------------ browser microphone -> WAV
  /** Starts recording. Returns { stop(): Promise<Blob wav>, cancel(), seconds() }. Needs localhost or https. */
  async function recordMicrophone(onTick) {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    const ctx = new AudioContext();
    const source = ctx.createMediaStreamSource(stream);
    const proc = ctx.createScriptProcessor(4096, 1, 1);
    const chunks = [];
    const seconds = () => chunks.length * 4096 / ctx.sampleRate;
    proc.onaudioprocess = e => { chunks.push(new Float32Array(e.inputBuffer.getChannelData(0))); onTick && onTick(seconds()); };
    source.connect(proc);
    proc.connect(ctx.destination);
    const end = () => { proc.disconnect(); stream.getTracks().forEach(t => t.stop()); ctx.close(); };
    return {
      seconds,
      cancel: end,
      async stop() { end(); return encodeWav(chunks, ctx.sampleRate); },
    };
  }

  function encodeWav(chunks, rate) {
    const n = chunks.reduce((a, c) => a + c.length, 0);
    const view = new DataView(new ArrayBuffer(44 + n * 2));
    const str = (o, s) => [...s].forEach((ch, i) => view.setUint8(o + i, ch.charCodeAt(0)));
    str(0, "RIFF"); view.setUint32(4, 36 + n * 2, true); str(8, "WAVEfmt ");
    view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
    view.setUint32(24, rate, true); view.setUint32(28, rate * 2, true);
    view.setUint16(32, 2, true); view.setUint16(34, 16, true);
    str(36, "data"); view.setUint32(40, n * 2, true);
    let o = 44;
    for (const c of chunks) for (const x of c) { view.setInt16(o, Math.max(-1, Math.min(1, x)) * 32767, true); o += 2; }
    return new Blob([view], { type: "audio/wav" });
  }

  window.Larp = {
    Emitter,
    /** Real backend, or the fake one (mock.js) when the URL has ?mock. */
    connect() {
      if (new URLSearchParams(location.search).has("mock")) return new window.LarpMock();
      return new LarpClient(serverAddress());
    },
    recordMicrophone,
  };
})();
