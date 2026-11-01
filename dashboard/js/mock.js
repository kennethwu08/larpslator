/* Fake backend for building the UI without the server, the badge or API keys: open index.html?mock
 *
 * Same methods as LarpClient in api.js and the same event shapes as docs/messages.md, so code that
 * works here works against the real backend. Keep it in sync if the protocol changes.
 */
(function () {
  "use strict";

  const SAMPLES = [
    { domain: "tennis", source: "She won the first set after a long deuce game.",
      larpSource: "Um, I think she won the first set after, like, a long deuce game.",
      larpText: "I'm confident that she won the first set after a long deuce game.",
      changes: [{ from: "like", to: "" }, { from: "Um", to: "" }, { from: "I think", to: "I'm confident that" }],
      translation: "그녀는 긴 듀스 끝에 첫 세트를 따냈다.",
      terms: [["set", ["세트", "집합"]], ["deuce", ["듀스"]]] },
    { domain: "math", source: "Let A be a set and f a function from A to the reals.",
      larpSource: "So, um, let A be a set and f a function from A to the reals.",
      larpText: "So, let A be a set and f a function from A to the reals.",
      changes: [{ from: "um", to: "" }],
      translation: "A를 집합이라 하고 f를 A에서 실수로 가는 함수라 하자.",
      terms: [["set", ["집합", "세트"]], ["function", ["함수", "기능"]]] },
    { domain: "pickleball", source: "Stay out of the kitchen and dink it cross-court.",
      larpSource: "You know, stay out of the kitchen and kind of dink it cross-court.",
      larpText: "Stay out of the kitchen and dink it cross-court.",
      changes: [{ from: "You know", to: "" }, { from: "kind of", to: "" }],
      translation: "키친에 들어가지 말고 크로스코트로 딩크하세요.",
      terms: [["kitchen", ["키친(논발리 존)", "부엌"]], ["dink", ["딩크", "살짝 치기"]]] },
    { domain: "cs", source: "Can you merge my branch before the kernel build?",
      larpSource: "I guess, can you merge my branch before the kernel build?",
      larpText: "My read is that, can you merge my branch before the kernel build?",
      changes: [{ from: "I guess", to: "my read is that" }],
      translation: "커널 빌드 전에 제 브랜치를 병합해 줄 수 있나요?",
      terms: [["merge", ["병합하다", "합병하다"]], ["branch", ["브랜치", "나뭇가지"]], ["kernel", ["커널", "알맹이"]]] },
    { domain: "general", source: "Where should we get dinner tonight?",
      larpSource: "Um, where should we get dinner tonight?", larpText: "Where should we get dinner tonight?",
      changes: [{ from: "Um", to: "" }], translation: "오늘 저녁 어디서 먹을까요?", terms: [] },
  ];
  const FIELDS = { pickleball: "Pickleball", tennis: "Tennis", cs: "Computer science", math: "Math" };
  const rand = (a, b) => Math.round(a + Math.random() * (b - a));

  class LarpMock extends window.Larp.Emitter {
    constructor() {
      super();
      this.mock = true;
      this.connected = false;
      this.s = {
        listening: false, target: "Korean", active: new Set(Object.keys(FIELDS)),
        notes: { name: "", text: "" }, packs: [], voice: { ready: false, name: "", voice_id: "JBFqnCBsd6RMkjVDRZzb" },
        recording: null,
        activeBadge: "LC-7F3A", configV: 1,
      };
      this.badges = {
        "LC-7F3A": { id: "LC-7F3A", name: "Bernard's badge", fw: "0.3", battery: 87, rssi: -54, volume: 70, ip: "172.20.10.4", playing: false, rtt_ms: 38, online_s: 0 },
        "LC-2B90": { id: "LC-2B90", name: "Spare badge", fw: "0.3", battery: 41, rssi: -71, volume: 70, ip: "172.20.10.6", playing: false, rtt_ms: 61, online_s: 0 },
      };
      this.next = 1; this.turn = 0; this.history = []; this.utts = {};
      setInterval(() => {  // heartbeat, like the backend: battery drains, latency wobbles
        for (const b of Object.values(this.badges)) {
          b.online_s += 5; b.rtt_ms = rand(25, 90);
          if (Math.random() < 0.3) b.battery = Math.max(0, b.battery - 1);
        }
        this.emit("badges", { t: "badges", badges: this._badges() });
      }, 5000);
      setTimeout(() => {
        this.connected = true; this.emit("open"); this._status(); this._metrics();
        if (new URLSearchParams(location.search).get("mock") === "play") this.setListening(true);  // ?mock=play
      }, 300);
    }

    _badgeConfig() {
      return { v: this.s.configV, listening: this.s.listening, target: this.s.target,
        fields: Object.keys(FIELDS).filter(d => this.s.active.has(d)), larp: this.s.active.has("larp"),
        domain: "auto", voice: this.s.voice.ready ? this.s.voice.name : "", voice_setup: this.s.recording !== null };
    }
    _badges() {
      return Object.values(this.badges).map(b => ({ ...b, active: b.id === this.s.activeBadge, seen_s_ago: 0.4, config_synced: true }));
    }

    _status() {
      this.s.configV++;
      const contexts = Object.entries(FIELDS).map(([id, label]) =>
        ({ id, label, kind: "field", on: this.s.active.has(id), source: "built-in" }));
      contexts.push({ id: "larp", label: "LARP mode", kind: "style", on: this.s.active.has("larp"), source: "built-in" });
      this.emit("status", {
        t: "status", listening: this.s.listening, target: this.s.target, contexts,
        context_name: this.s.notes.name, context: this.s.notes.text, packs: this.s.packs,
        languages: ["Korean", "Spanish", "French", "Mandarin Chinese", "Japanese", "German", "English"],
        voice: { ...this.s.voice }, voice_recording: this.s.recording,
        badge: !!this.s.activeBadge, badges: this._badges(), badge_config: this._badgeConfig(),
        badge_url: "ws://172.20.10.2:8000/ws/badge",
      });
    }

    _metrics() {
      const h = this.history, w = 5;
      const curve = h.map((_, i) => { const s = h.slice(Math.max(0, i - w + 1), i + 1); return +(s.reduce((a, b) => a + b, 0) / s.length).toFixed(2); });
      this.emit("metrics", { t: "metrics", n: h.length, accuracy: h.length ? +(h.reduce((a, b) => a + b, 0) / h.length).toFixed(2) : null, curve, window: w });
    }

    _speak() {
      if (!this.s.listening) return;
      const fields = [...this.s.active].filter(d => d in FIELDS);
      const pool = SAMPLES.filter(x => x.domain === "general" || fields.includes(x.domain));
      const x = pool[this.turn++ % pool.length];
      const larp = this.s.active.has("larp");
      const id = this.next++;
      const source = larp ? x.larpSource : x.source;
      this.emit("transcript", { t: "transcript", id, source, lang: "english" });
      setTimeout(() => {
        const probs = {};
        [...fields, "general"].forEach(d => probs[d] = d === x.domain ? 0.7 : +(0.3 / fields.length).toFixed(3));
        const terms = x.terms.map(([term, options]) => ({ term, match: term, pos: source.indexOf(term), domain: x.domain, options, choice: options[0] }));
        const timing = { vad: 0.4, whisper: rand(450, 750), ml: rand(3, 6), gemini: rand(300, 500), elevenlabs: rand(250, 400) };
        timing.total = Math.round(timing.vad + timing.whisper + timing.ml + timing.gemini + timing.elevenlabs);
        const u = { t: "utterance", id, retry: 0, source, lang: "english", target: this.s.target, translation: x.translation,
          tone: larp ? "confident" : "neutral", domain: x.domain, domain_probs: probs, terms,
          context_lines: this.s.notes.text ? this.s.notes.text.split("\n").filter(Boolean).slice(0, 5) : [],
          larp: larp ? { text: x.larpText, changes: x.changes } : null, timing_ms: timing };
        this.utts[id] = u;
        this.emit("utterance", u);
      }, 700);
    }

    // ------------------------------------------------------------ same commands as LarpClient
    setListening(on) {
      this.s.listening = on;
      clearInterval(this.timer);
      if (on) { this._speak(); this.timer = setInterval(() => this._speak(), 4500); }
      this._status();
    }
    setLanguage(language) { this.s.target = language; this._status(); }
    toggleContext(id, on) { on ? this.s.active.add(id) : this.s.active.delete(id); this._status(); }
    saveNotes(name, text) {
      this.s.notes = { name, text };
      this.s.packs = [{ name, text, saved_at: new Date().toISOString().slice(0, 19).replace("T", " ") },
        ...this.s.packs.filter(p => p.name !== name)];
      this._status();
    }
    feedback(id, val, term) {
      const u = this.utts[id];
      const blamed = u && val < 0 ? (u.terms.find(t => t.term === term) || u.terms.find(t => t.options.length > 1)) : null;
      if (u && (val > 0 || blamed)) { this.history.push(val > 0 ? 1 : 0); this._metrics(); }
      this.emit("feedback", { t: "feedback", id, val, term: blamed ? blamed.term : null });
      if (!blamed) return;
      const next = blamed.options[blamed.options.indexOf(blamed.choice) + 1];
      if (!next) { this.emit("error", { t: "error", id, msg: `no other translations left for '${blamed.term}'` }); return; }
      setTimeout(() => {
        const terms = u.terms.map(t => t === blamed ? { ...t, choice: next } : t);
        const r = { ...u, retry: u.retry + 1, terms, translation: u.translation.replace(blamed.choice, next),
          timing_ms: { gemini: rand(300, 500), elevenlabs: rand(250, 400), total: rand(600, 900) } };
        this.utts[id] = r;
        this.emit("utterance", r);
      }, 600);
    }
    resetLearning() { this.history = []; this._metrics(); }

    connectBadge(id) { if (this.badges[id]) { this.s.activeBadge = id; this._status(); } }
    disconnectBadge() { this.s.activeBadge = null; this._status(); }
    identifyBadge(id) { console.log(`[mock] ${id} blinks`); }
    setBadgeVolume(id, value) { if (this.badges[id]) { this.badges[id].volume = Math.max(0, Math.min(100, value)); this._status(); } }

    voiceRecordOnBadge(name) {
      this.s.recording = 0; this._status();
      let speech = 0, total = 0;
      this.recTimer = setInterval(() => {
        total += 3; speech += 2.6; this.s.recording = +speech.toFixed(1);
        this.emit("voice_progress", { t: "voice_progress", state: "recording", speech_s: +speech.toFixed(1), total_s: total });
      }, 1000);  // 3x speed so testing the UI doesn't take a minute
      this.recName = name || "My voice";
    }
    voiceStop() {
      clearInterval(this.recTimer);
      const speech = this.s.recording || 0;
      this.s.recording = null;
      if (speech < 20) {
        this.emit("error", { t: "error", id: null, msg: `voice setup: only ${Math.round(speech)} s of speech, need at least 20 s (about 60 s sounds best). Try again.` });
        this._status(); return;
      }
      this.emit("voice_progress", { t: "voice_progress", state: "creating" });
      setTimeout(() => { this.s.voice = { ready: true, name: this.recName, voice_id: "mockvoice123" }; this._status(); }, 1500);
    }
    voiceCancel() { clearInterval(this.recTimer); this.s.recording = null; this._status(); }
    async voiceUpload(wavBlob, name) {
      await new Promise(r => setTimeout(r, 1500));
      this.s.voice = { ready: true, name: name || "My voice", voice_id: "mockvoice123" };
      this._status();
      return { ...this.s.voice };
    }
    voiceTestUrl() { return null; }  // no audio in mock mode
  }

  window.LarpMock = LarpMock;
})();
