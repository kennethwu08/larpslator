/* Web audio: this browser is the translator's mic and speaker, so the dashboard works without the badge.
 * (WEB_AUDIO: on unless the backend has WEB_AUDIO_FALLBACK=0; see backend/web_audio.py and docs/messages.md.)
 * With no badge connected, the header's Start Listening uses this too (app.js, via available/toggle/onChange).
 *
 * Self-contained so it can be removed in one go. It talks to /ws/web, a second audio client on the same
 * pipeline as the badge: mic audio goes up as 16 kHz 16-bit mono PCM binary frames (the badge's format), the
 * translation comes back the same way and plays through Web Audio. While it plays, the mic is muted until
 * resume_after_ms (300 ms) after playback ends, the same rule as the badge, so the translation isn't re-heard.
 * Transcripts and translations arrive on the dashboard socket like the badge's, tagged client: "web".
 */
(function () {
  "use strict";
  const $ = id => document.getElementById(id);
  const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const RECONNECT_TRIES = 3;
  const STEP_TIMEOUT_MS = 10000;  // no start-up step (mic permission, socket, worklet) may hang the button

  function withTimeout(promise, what) {
    let timer;
    return Promise.race([promise, new Promise((_, reject) => {
      timer = setTimeout(() => reject(Object.assign(new Error(`${what} didn't respond`), { name: "TimeoutError" })), STEP_TIMEOUT_MS);
    })]).finally(() => clearTimeout(timer));
  }

  let larp, info = null, ws = null, ctx = null, gain = null;
  let stream = null, node = null, source = null;
  let listening = false, muted = false, resumeTimer = null, nextTime = 0;
  const changeHandlers = [];
  const stats = { chunksSent: 0, bytesSent: 0, droppedWhileMuted: 0, chunksPlayed: 0, secondsPlayed: 0, level: 0 };
  window.__larpWebAudio = stats;  // read by tests and handy in the console

  function report(text, level, extra) {
    window.LarpMonitor?.message(text, level || "warning", extra, { client: "web" });
  }
  function setStatus(text, kind) {
    $("wa-status").textContent = text;
    $("wa-status").className = "secondary small" + (kind ? " " + kind : "");
  }
  function showError(text) {
    $("wa-error").textContent = text;
    $("wa-error").hidden = !text;
  }

  // ---------------------------------------------------------------- setup
  async function init(client) {
    larp = client;
    if (larp.mock) return;  // nothing to stream to
    larp.on("open", probe);  // the backend may come up (or be restarted) after the page loaded
    await probe();
    $("wa-listen").onclick = () => (listening ? stop() : start());
    $("wa-volume").oninput = e => {
      e.target.style.setProperty("--pct", e.target.value + "%");
      if (gain) gain.gain.value = e.target.value / 100;
    };
    $("wa-volume").style.setProperty("--pct", $("wa-volume").value + "%");
    larp.on("transcript", m => { if (m.client === "web") row(m.id, m.source, "Translating…"); });
    larp.on("utterance", u => { if (u.client === "web") row(u.id, u.source, u.translation); });
    larp.on("error", m => {
      if (m.client !== "web") return;
      showError(`That sentence couldn't be translated (${m.msg}). Listening continues.`);
    });
  }

  async function probe() {
    if (info) return;
    try {
      const r = await fetch(`${larp.httpBase}/api/web-audio`);
      if (!r.ok) return;    // 404: web audio is off, the section stays hidden
      info = await r.json();
    } catch { return; }
    $("web-audio").hidden = false;
    changeHandlers.forEach(fn => fn());
  }

  // ---------------------------------------------------------------- the socket
  function connect() {
    return new Promise((resolve, reject) => {
      const q = larp.token ? `?token=${encodeURIComponent(larp.token)}` : "";
      const sock = new WebSocket(`${larp.secure ? "wss" : "ws"}://${larp.address}${info.websocket}${q}`);
      sock.binaryType = "arraybuffer";
      sock.onopen = () => { ws = sock; resolve(); };
      sock.onmessage = e => {
        if (typeof e.data === "string") return;  // hello / acks: nothing needed
        play(e.data);
      };
      sock.onerror = () => {};
      sock.onclose = e => {
        if (ws !== sock) { reject(new Error(e.code === 4401 ? "pairing code required" : "couldn't connect")); return; }
        ws = null;
        if (!listening) return;
        if (e.code === 4401) { stop(); showError("This device isn't paired. Enter the pairing code, then press Listen."); return; }
        report("Web audio connection dropped", "warning", { code: e.code });
        reconnect();
      };
    });
  }

  /** After a drop while listening: a few tries with growing waits, then stop with a clear message. */
  async function reconnect() {
    for (let attempt = 1; attempt <= RECONNECT_TRIES && listening; attempt++) {
      setStatus(`Connection dropped. Reconnecting (${attempt}/${RECONNECT_TRIES})…`, "warn");
      await new Promise(r => setTimeout(r, 1000 * attempt));
      if (!listening) return;
      try {
        await withTimeout(connect(), "The backend");
        send({ t: "mode", state: "listen" });
        setStatus("Listening", "ok");
        return;
      } catch { /* next attempt */ }
    }
    if (!listening) return;
    stop();
    showError("Lost the connection to the backend. Check the Wi-Fi and that the laptop is running Larpslator, then press Listen again.");
    report("Web audio gave up reconnecting", "error");
  }
  function send(msg) { if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg)); }

  // ---------------------------------------------------------------- mic capture
  async function start() {
    showError("");
    if (!navigator.mediaDevices?.getUserMedia) {
      showError("This browser blocks the microphone here. Open the dashboard on localhost or https.");
      report("Web audio: no getUserMedia (insecure context?)", "warning");
      return;
    }
    $("wa-listen").disabled = true;
    setStatus("Starting…");
    try {
      // Created on this click: browsers only allow audio to start from a user gesture.
      stats.phase = "audio context";
      ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
      await withTimeout(ctx.resume(), "Audio output");
      if (!gain) { gain = ctx.createGain(); gain.gain.value = $("wa-volume").value / 100; gain.connect(ctx.destination); }
      stats.phase = "microphone";
      stream = await withTimeout(navigator.mediaDevices.getUserMedia({ audio: true }), "The microphone");
      stats.phase = "connecting";
      if (!ws) await withTimeout(connect(), "The backend");
      stats.phase = "capture";
      source = ctx.createMediaStreamSource(stream);
      node = await withTimeout(captureNode(), "Audio capture");
      stats.phase = "running";
      source.connect(node);
      send({ t: "mode", state: "listen" });
      listening = true;
      setListenButton();
      setStatus("Listening", "ok");
    } catch (e) {
      cleanupMic();
      const denied = e.name === "NotAllowedError" || e.name === "SecurityError";
      const missing = e.name === "NotFoundError" || e.name === "OverconstrainedError";
      showError(denied ? "Microphone access was denied. Allow it in the browser's site settings, then press Listen."
        : missing ? "No microphone found. Plug one in or pick one in the system settings."
        : e.name === "TimeoutError" ? `${e.message}. Check the microphone permission prompt and the connection, then press Listen again.`
        : `Couldn't start web audio: ${e.message}`);
      setStatus("Stopped");
      report(denied ? "Web audio: microphone permission denied" : missing ? "Web audio: no microphone"
        : `Web audio failed to start: ${e.message}`, denied ? "info" : "warning");
    } finally {
      $("wa-listen").disabled = false;
    }
  }

  /** AudioWorklet when available; ScriptProcessorNode otherwise. Both use LarpPcmEncoder (pcm-worklet.js). */
  async function captureNode() {
    const opts = { outRate: info.sample_rate, chunkSamples: Math.round(info.sample_rate * info.chunk_ms / 1000) };
    if (ctx.audioWorklet && window.AudioWorkletNode) {
      await ctx.audioWorklet.addModule("js/pcm-worklet.js");
      const n = new AudioWorkletNode(ctx, "larp-pcm-capture", { processorOptions: opts, channelCountMode: "explicit", channelCount: 1 });
      n.port.onmessage = e => onChunk(e.data);
      stats.capture = "audioworklet";
      return n;
    }
    const enc = new window.LarpPcmEncoder(ctx.sampleRate, opts.outRate, opts.chunkSamples);
    const n = ctx.createScriptProcessor(4096, 1, 1);
    n.onaudioprocess = e => {
      const chans = [...Array(e.inputBuffer.numberOfChannels)].map((_, i) => e.inputBuffer.getChannelData(i));
      for (const c of enc.push(window.LarpMono(chans))) onChunk(c);
    };
    n.connect(ctx.destination);  // ScriptProcessor only runs when connected; its output is silent
    stats.capture = "scriptprocessor";
    return n;
  }

  function onChunk({ pcm, level }) {
    stats.level = level;
    meter(level);
    if (!listening) return;
    if (muted) { stats.droppedWhileMuted++; return; }  // translation playing: don't send it back
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(pcm);
      stats.chunksSent++; stats.bytesSent += pcm.byteLength;
    }
  }

  function meter(level) {
    const db = level > 0 ? 20 * Math.log10(level) : -100;
    const pct = Math.max(0, Math.min(100, (db + 60) / 60 * 100));  // -60 dB .. 0 dB
    $("wa-meter").style.width = pct + "%";
    $("wa-meter-wrap").setAttribute("aria-valuenow", String(Math.round(pct)));
  }

  function stop() {
    if (listening) send({ t: "mode", state: "stop" });  // the backend finishes the sentence being spoken
    listening = false;
    cleanupMic();
    setListenButton();
    meter(0);
    setStatus("Stopped");
  }
  function cleanupMic() {
    try { source?.disconnect(); node?.disconnect(); } catch { /* already gone */ }
    if (node?.port) node.port.onmessage = null;
    stream?.getTracks().forEach(t => t.stop());
    stream = null; node = null; source = null;
  }
  function setListenButton() {
    $("wa-listen").classList.toggle("on", listening);
    $("wa-listen").setAttribute("aria-pressed", String(listening));
    $("wa-listen-label").textContent = listening ? "Stop" : "Listen";
    changeHandlers.forEach(fn => fn());
  }

  // ---------------------------------------------------------------- playback
  /** One binary frame of the translation: 16 kHz 16-bit mono, queued right after the previous one. */
  function play(buffer) {
    if (!ctx || !buffer.byteLength) return;
    const pcm = new Int16Array(buffer, 0, buffer.byteLength >> 1);
    const audio = ctx.createBuffer(1, pcm.length, info.sample_rate);  // same rate as sent: no pitch shift
    const ch = audio.getChannelData(0);
    for (let i = 0; i < pcm.length; i++) ch[i] = pcm[i] / 0x8000;
    const src = ctx.createBufferSource();
    src.buffer = audio;
    src.connect(gain);
    // Small lead on the first frame of a clip so network jitter doesn't cause gaps.
    if (nextTime < ctx.currentTime + 0.02) nextTime = ctx.currentTime + 0.12;
    src.start(nextTime);
    nextTime += audio.duration;
    stats.chunksPlayed++; stats.secondsPlayed += audio.duration;

    // Mic muted until resume_after_ms after the last frame ends (reset on every new frame).
    muted = true;
    stats.muted = true;
    clearTimeout(resumeTimer);
    resumeTimer = setTimeout(() => {
      muted = false; stats.muted = false;
      if (!listening) setStatus("Stopped");
      else if (ws) setStatus("Listening", "ok");  // not while reconnecting
    },
      (nextTime - ctx.currentTime) * 1000 + info.resume_after_ms);
    setStatus("Speaking the translation…", "ok");
  }

  // ---------------------------------------------------------------- transcript panel (web sentences only)
  function row(id, said, heard) {
    let el = $("wa-list").querySelector(`[data-id="${CSS.escape(String(id))}"]`);
    if (!el) {
      el = document.createElement("div");
      el.className = "wa-row";
      el.dataset.id = id;
      $("wa-list").prepend(el);
      const rows = $("wa-list").querySelectorAll(".wa-row");  // keep the 5 newest (not the placeholder)
      for (let i = 5; i < rows.length; i++) rows[i].remove();
      const empty = $("wa-empty");
      if (empty) empty.hidden = true;
    }
    el.innerHTML = `<div class="secondary small">${esc(said)}</div><div class="wa-heard">${esc(heard)}</div>`;
  }

  window.LarpWebAudio = {
    init,
    available: () => !!info,
    listening: () => listening,
    toggle: () => { if (!$("wa-listen").disabled) listening ? stop() : start(); },  // disabled while starting
    onChange: fn => changeHandlers.push(fn),
  };
})();
