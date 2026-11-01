/* Presentation layer only. All commands and events go through the unchanged Larp API. */
(function () {
  "use strict";
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const LABELS = { pickleball: "Pickleball", tennis: "Tennis", cs: "Computer science", math: "Math", general: "Everyday conversation" };
  const SYMBOLS = { pickleball: "◒", tennis: "◉", cs: "⌘", math: "∑", larp: "✧", general: "○" };
  const TARGET_CODES = { Korean: "ko", Spanish: "es", French: "fr", "Mandarin Chinese": "zh", Japanese: "ja", German: "de", English: "en", Tamil: "ta" };
  const larp = Larp.connect();
  const cards = new Map();
  const utterances = new Map();
  let status = null, packs = [], micRecording = null, uploading = false, acquiringMic = false;
  let latestId = null, contextSignature = "", toastTimer, recording = false;

  function toast(message) {
    clearTimeout(toastTimer);
    $("toast").textContent = message;
    $("toast").hidden = false;
    toastTimer = setTimeout(() => { $("toast").hidden = true; }, 4500);
  }
  function setPill(id, text, kind = "") {
    $(id).textContent = text;
    $(id).className = "pill " + kind;
  }
  function activeConnection(connected) {
    $("listen").disabled = $("lang").disabled = $("notes-save").disabled = $("voice-open").disabled = $("reset").disabled = !connected;
    $("voice-test").disabled = !connected;
    $("badge-open").disabled = !connected;
    $("contexts").querySelectorAll("input").forEach(input => { input.disabled = !connected; });
  }
  $("pill-mock").hidden = !larp.mock;
  if (larp.mock) $("rec-browser").textContent = "Simulate recording";
  larp.on("open", () => setPill("pill-server", larp.mock ? "Demo connected" : "Session connected", "on"));
  larp.on("close", () => {
    setPill("pill-server", "Reconnecting…", "bad");
    activeConnection(false);
    document.body.classList.remove("is-listening");
    $("session-state").textContent = "Connection interrupted";
    $("session-hint").textContent = "Reconnecting to your session…";
    $("feed-label").textContent = "Connection interrupted";
  });

  larp.on("status", m => {
    const first = !status;
    status = m;
    activeConnection(true);
    document.body.classList.toggle("is-listening", !!m.listening);
    $("listen").className = "listen " + (m.listening ? "on" : "off");
    $("listen-label").textContent = m.listening ? "Stop listening" : "Start listening";
    $("listen").querySelector(".listen-symbol").textContent = m.listening ? "■" : "●";
    $("listen").setAttribute("aria-pressed", String(!!m.listening));
    $("session-state").textContent = m.listening ? (larp.mock ? "A conversation, in motion" : "Listening to your conversation") : "A moment of quiet";
    $("session-hint").textContent = m.listening ? (larp.mock ? "Simulated conversation · no microphone or API calls" : "Speak naturally. Your badge is listening.") : "Press Start listening when you're ready.";
    $("feed-label").textContent = m.listening ? "Live updates" : "Session paused";
    const languages = Array.isArray(m.languages) ? m.languages : [];
    if (JSON.stringify([...$("lang").options].map(o => o.value)) !== JSON.stringify(languages)) {
      $("lang").innerHTML = languages.map(l => '<option value="' + esc(l) + '">' + esc(l) + "</option>").join("");
    }
    $("lang").value = m.target;
    $("target-caption").textContent = m.target;
    renderBadges(m.badges || []);
    renderContexts(m.contexts || []);
    renderVoice(m.voice || {}, m.voice_recording);
    const signature = JSON.stringify(m.packs || []);
    if (signature !== $("packs").dataset.signature) {
      packs = m.packs || [];
      $("packs").innerHTML = '<option value="">Load saved notes…</option>' + packs.map((p, i) => '<option value="' + i + '">' + esc(p.name) + "</option>").join("");
      $("packs").dataset.signature = signature;
    }
    $("notes-status").textContent = m.context_name ? "Active: " + m.context_name : "No notes active";
    if (first) {
      $("notes").value = m.context || "";
      $("notes-name").value = m.context_name || "";
    }
  });
  $("listen").onclick = () => { if (status) larp.setListening(!status.listening); };
  $("lang").onchange = event => {
    larp.setLanguage(event.target.value);
    if (larp.mock) toast("Demo text stays in Korean. Live sessions use the language you select.");
  };
  $("present").onclick = () => {
    const on = document.body.classList.toggle("presentation");
    $("present").setAttribute("aria-pressed", String(on));
    $("present").textContent = on ? "↙" : "↗";
    $("present").title = on ? "Exit presentation view" : "Enter presentation view";
  };

  function renderContexts(contexts) {
    const signature = JSON.stringify(contexts);
    if (signature === contextSignature) return;
    contextSignature = signature;
    $("contexts").innerHTML = contexts.map(c =>
      '<label class="ctx ' + esc(c.kind) + '"><input type="checkbox" data-id="' + esc(c.id) + '" ' + (c.on ? "checked" : "") + '><span class="context-icon" aria-hidden="true">' + esc(SYMBOLS[c.id] || "○") + "</span><span>" + esc(c.label) + "</span>" +
      (c.kind === "style" ? '<span class="style-tag">EXPERT STYLE</span>' :
        '<span class="source" title="' + (c.source === "data" ? "Using your custom context glossary" : "Using the starter context glossary") + '">' + (c.source === "data" ? "Custom" : "Starter") + "</span>") + "</label>"
    ).join("");
    $("contexts").querySelectorAll("input").forEach(input => {
      input.onchange = () => larp.toggleContext(input.dataset.id, input.checked);
    });
  }
  $("notes-save").onclick = () => {
    larp.saveNotes($("notes-name").value.trim() || "My session", $("notes").value);
    toast("Session context saved.");
  };
  $("packs").onchange = event => {
    if (event.target.value === "") return;
    const p = packs[Number(event.target.value)];
    if (!p) return;
    $("notes-name").value = p.name;
    $("notes").value = p.text;
    larp.saveNotes(p.name, p.text);
    toast("Loaded " + p.name + ".");
  };

  // Voice setup keeps the badge and browser flows provided by api.js.
  $("voice-open").onclick = () => $("voice-dialog").showModal();
  $("voice-close").onclick = () => $("voice-dialog").close();
  function setRecording(on) {
    recording = on;
    $("rec-badge").disabled = on || acquiringMic || !status?.badge;
    $("rec-browser").disabled = on || acquiringMic || !status;
    $("rec-stop").disabled = $("rec-cancel").disabled = !on || uploading;
  }
  function renderVoice(voice, badgeRecording) {
    const badgeIsRecording = badgeRecording !== null && badgeRecording !== undefined;
    setPill("pill-voice", voice.ready ? (larp.mock ? "Demo voice: " : "Voice: ") + (voice.name || "My voice") : "Stock voice · set up yours", voice.ready ? "on" : "bad");
    $("voice-state").textContent = voice.ready ? "Your translations, in " + (voice.name || "your") + "'s voice." : "A stock voice is active. Add yours for a more personal conversation.";
    $("voice-open").innerHTML = (voice.ready ? "Manage voice" : "Set up voice") + "<span>↗</span>";
    setRecording(badgeIsRecording || !!micRecording || uploading || acquiringMic);
    if (voice.ready && !badgeIsRecording && !micRecording && !uploading) {
      if ($("rec-progress").textContent.startsWith("Creating")) $("rec-progress").textContent = "Your voice is ready. Play a sample from the sidebar.";
    }
  }
  const hint = seconds => seconds < 20 ? "Keep reading…" : seconds < 60 ? "Good. A little more makes it more natural." : "Ready. You can stop recording.";
  larp.on("voice_progress", m => {
    $("rec-progress").textContent = m.state === "creating" ? "Creating your voice…" : m.speech_s + " seconds of speech · " + hint(m.speech_s);
    if (m.state === "creating") {
      $("rec-stop").disabled = $("rec-cancel").disabled = true;
    }
  });
  $("rec-badge").onclick = () => {
    if (!status?.badge || recording) return;
    larp.voiceRecordOnBadge($("voice-name").value);
    setRecording(true);
    $("rec-progress").textContent = larp.mock ? "Simulated recording. Read along, then stop after 20 seconds of speech." : "Recording on your badge. Start reading.";
  };
  $("rec-browser").onclick = async () => {
    if (recording || acquiringMic) return;
    if (larp.mock) {
      larp.voiceRecordOnBadge($("voice-name").value);
      setRecording(true);
      $("rec-progress").textContent = "Simulated recording · no microphone is in use.";
      return;
    }
    acquiringMic = true;
    setRecording(false);
    $("rec-progress").textContent = "Waiting for microphone permission…";
    try {
      micRecording = await Larp.recordMicrophone(s => { $("rec-progress").textContent = s.toFixed(0) + " seconds recorded · " + hint(s); });
    } catch (e) {
      $("rec-progress").textContent = "Microphone unavailable: " + e.message;
    } finally {
      acquiringMic = false;
      setRecording(!!micRecording);
    }
  };
  $("rec-stop").onclick = async () => {
    if (!micRecording) {
      larp.voiceStop();
      $("rec-stop").disabled = true;
      return;
    }
    const rec = micRecording;
    micRecording = null;
    uploading = true;
    setRecording(true);
    $("rec-progress").textContent = "Creating your voice…";
    try {
      await larp.voiceUpload(await rec.stop(), $("voice-name").value);
      $("rec-progress").textContent = "Your voice is ready. Play a sample from the sidebar.";
    } catch (e) {
      $("rec-progress").textContent = "Voice setup: " + e.message;
    } finally {
      uploading = false;
      setRecording(false);
    }
  };
  $("rec-cancel").onclick = () => {
    if (micRecording) { micRecording.cancel(); micRecording = null; }
    else larp.voiceCancel();
    setRecording(false);
    $("rec-progress").textContent = "Recording cancelled.";
  };
  $("voice-test").onclick = async () => {
    const url = larp.voiceTestUrl();
    if (!url) { toast("Voice playback is available in a live session. This is a visual demo."); return; }
    $("voice-audio").src = url;
    try { await $("voice-audio").play(); } catch (_) { toast("Couldn't play the voice sample. Check your connection and voice setup."); }
  };

  // Badge: the backend tracks every badge online; the user picks one, and the backend keeps it in sync.
  const wifi = rssi => rssi == null ? "unknown" : rssi > -60 ? "strong" : rssi > -72 ? "good" : "weak";
  larp.on("badges", m => { if (status) { status.badges = m.badges; renderBadges(m.badges || []); } });  // 5 s heartbeat
  $("badge-open").onclick = () => $("badge-dialog").showModal();
  $("badge-close").onclick = () => $("badge-dialog").close();
  $("badge-disconnect").onclick = () => { larp.disconnectBadge(); toast("Badge disconnected. It stays online until you connect it again."); };
  const identify = () => {
    const active = (status?.badges || []).find(b => b.active);
    if (active) { larp.identifyBadge(active.id); toast("Your badge is blinking."); }
  };
  $("badge-identify").onclick = $("badge-identify-dialog").onclick = identify;

  function renderBadges(badges) {
    const active = badges.find(b => b.active);
    const name = b => b.name || b.id;
    setPill("pill-badge", active ? (larp.mock ? "Demo badge · " : "Badge · ") + name(active) : badges.length ? "Badge not connected" : "Badge offline", active ? "on" : "bad");
    $("badge-summary").textContent = active
      ? name(active) + (active.battery != null ? " · " + active.battery + "% battery" : "") + (active.config_synced ? " · in sync" : "")
      : badges.length ? badges.length + " badge" + (badges.length > 1 ? "s" : "") + " online. Choose one to connect." : "No badge online yet.";
    $("badge-open").innerHTML = (active ? "Manage badge" : "Connect badge") + "<span>↗</span>";
    $("badge-identify").disabled = !active;
    $("badge-url").textContent = status?.badge_url || "…";
    if (!badges.length && !$("badge-help").dataset.touched) $("badge-help").open = true;

    $("badge-list").innerHTML = badges.length ? badges.map(b =>
      '<div class="badge-row"><div><div class="badge-name">' + esc(name(b)) + '</div><div class="badge-stats">' +
      (b.battery != null ? esc(b.battery) + "% battery · " : "") + "Wi-Fi " + wifi(b.rssi) + '</div></div>' +
      '<button class="secondary-button ' + (b.active ? "connected" : "") + '" data-id="' + esc(b.id) + '" ' + (b.active ? "disabled" : "") + ">" + (b.active ? "Connected" : "Connect") + "</button></div>"
    ).join("") : '<p class="muted small" style="margin-top:12px">No badge online. See "How to connect a new badge" below.</p>';
    $("badge-list").querySelectorAll("button[data-id]").forEach(button => {
      button.onclick = () => { larp.connectBadge(button.dataset.id); toast("Connecting your badge…"); };
    });

    $("badge-detail").hidden = !active;
    if (!active || !status) return;
    const cfg = status.badge_config || {};
    const fields = (status.contexts || []).filter(c => (cfg.fields || []).includes(c.id)).map(c => c.label);
    const rows = [
      ["Language", esc(cfg.target)],
      ["Contexts", esc(fields.join(", ") || "None (everyday words)")],
      ["Expert style", cfg.larp ? "On" : "Off"],
      ["Listening", cfg.voice_setup ? "Recording your voice" : cfg.listening ? "Yes" : "Paused"],
      ["Voice", esc(cfg.voice || "Stock voice")],
      ["Battery", active.battery != null ? esc(active.battery) + "%" : "Not reported"],
      ["Wi-Fi", active.rssi != null ? wifi(active.rssi) + " (" + esc(active.rssi) + " dBm)" : "Not reported"],
      ["Latency", active.rtt_ms != null ? esc(active.rtt_ms) + " ms" : "Measuring…"],
      ["Firmware", esc(active.fw || "Not reported")],
      ["Settings", active.config_synced ? '<span class="synced">In sync ✓</span>' : "Sent · waiting for the badge"],
    ];
    $("badge-info").innerHTML = rows.map(([k, v]) => "<dt>" + k + "</dt><dd>" + v + "</dd>").join("");
    if (document.activeElement !== $("badge-volume")) $("badge-volume").value = active.volume ?? 70;
    $("badge-volume").onchange = event => larp.setBadgeVolume(active.id, Number(event.target.value));
  }
  $("badge-help").addEventListener("toggle", () => { $("badge-help").dataset.touched = "1"; });

  function card(id) {
    const key = String(id);
    if (cards.has(key)) return cards.get(key);
    const el = document.createElement("article");
    el.className = "utt";
    el.dataset.id = key;
    $("utterances").querySelector(".empty")?.remove();
    $("utterances").prepend(el);
    cards.set(key, el);
    latestId = key;
    // A bounded feed stays responsive during a long rehearsal.
    if (cards.size > 40) {
      const oldest = cards.keys().next().value;
      cards.get(oldest).remove();
      cards.delete(oldest);
      utterances.delete(oldest);
    }
    $("utterance-count").textContent = cards.size;
    return el;
  }
  function highlightedSource(source, terms) {
    const ranges = (terms || []).filter(t => Number.isInteger(t.pos) && t.pos >= 0 && t.match && source.slice(t.pos, t.pos + t.match.length).toLowerCase() === t.match.toLowerCase())
      .map(t => ({ start: t.pos, end: t.pos + t.match.length })).sort((a, b) => a.start - b.start);
    let cursor = 0, output = "";
    for (const range of ranges) {
      if (range.start < cursor) continue;
      output += esc(source.slice(cursor, range.start)) + "<mark>" + esc(source.slice(range.start, range.end)) + "</mark>";
      cursor = range.end;
    }
    return output + esc(source.slice(cursor));
  }
  larp.on("transcript", m => {
    card(m.id).innerHTML = '<div class="utt-heading"><span class="utterance-id">#' + esc(m.id) + '</span><span class="domain-tag">Finding the meaning</span></div><div class="pair"><div class="text-label">You said</div><div class="said">' + esc(m.source) + '</div><div class="translation-block"><div class="text-label">Making the connection</div><div class="heard">Translating<span class="typing" aria-hidden="true"><i></i><i></i><i></i></span></div></div></div>';
    cards.get(String(m.id)).classList.add("pending");
  });
  larp.on("utterance", u => {
    utterances.set(String(u.id), u);
    const el = card(u.id), terms = u.terms || [], timing = u.timing_ms || {};
    el.classList.remove("pending");
    const total = Number.isFinite(timing.total) ? (timing.total === 0 ? "Cached" : (timing.total / 1000).toFixed(2) + "s") : "—";
    const breakdown = Object.entries(timing).map(([key, value]) => key + ": " + (value === 0 ? "cached" : value + " ms")).join(" · ");
    el.innerHTML =
      '<div class="utt-heading"><span class="utterance-id">#' + esc(u.id) + '</span><span class="domain-tag"><span aria-hidden="true">' + esc(SYMBOLS[u.domain] || "○") + "</span>" + esc(LABELS[u.domain] || u.domain) + '</span>' +
      (u.larp ? '<span class="tag">LARP STYLE</span>' : "") + '<span class="utt-time">' + (u.retry ? "Updated · take " + (u.retry + 1) : "Translation") + "</span></div>" +
      '<div class="pair"><div class="text-label">You said <span>· ' + esc(u.lang || "Auto-detected") + '</span></div><div class="said source-text">' + highlightedSource(u.source || "", terms) + "</div>" +
      (u.larp?.text && u.larp.text !== u.source ? '<div class="larp-edit"><div class="text-label">Expert phrasing</div>' + esc(u.larp.text) + "</div>" : "") +
      '<div class="translation-block"><div class="text-label"><span class="translation-marker"></span>In ' + esc(larp.mock ? "Korean · demo fixture" : u.target) + '</div><div class="heard" lang="' + esc(larp.mock ? "ko" : TARGET_CODES[u.target] || "") + '">' + esc(u.translation) + "</div></div>" +
      (terms.length ? '<div class="chips">' + terms.map(t => '<button class="chip" data-term="' + esc(t.term) + '" aria-label="Try next translation for ' + esc(t.term) + '">' + esc(t.match) + " → " + esc(t.choice) + "</button>").join("") + "</div>" : "") + "</div>" +
      '<div class="utt-bottom"><span class="latency" title="' + esc(breakdown) + '"><strong>' + esc(total) + '</strong> · ' + (larp.mock ? "simulated timing" : "end to end") + '</span><div class="actions"><span class="feedback-prompt">Did we get it?</span><button class="feedback-button up" aria-label="Good translation for sentence ' + esc(u.id) + '" title="Good translation">↑</button><button class="feedback-button down" aria-label="Try another translation for sentence ' + esc(u.id) + '" title="Try another translation">↓</button></div></div>';
    el.querySelector(".up").onclick = () => larp.feedback(u.id, 1);
    el.querySelector(".down").onclick = () => larp.feedback(u.id, -1);
    el.querySelectorAll(".chip").forEach(button => { button.onclick = () => larp.feedback(u.id, -1, button.dataset.term); });
    if (String(u.id) === latestId) {
      renderFields(u.domain_probs || {}, u.domain);
      renderTerms(terms, u.id);
    }
  });
  larp.on("feedback", m => {
    const el = cards.get(String(m.id));
    if (!el) return;
    for (const [kind, value] of [["up", 1], ["down", -1]]) {
      const button = el.querySelector("." + kind);
      button?.classList.toggle("sel", m.val === value);
      button?.setAttribute("aria-pressed", String(m.val === value));
    }
    toast(m.val > 0 ? "Noted. Your feedback makes the next conversation better." : m.term ? 'Trying the next meaning for "' + m.term + '".' : "Feedback noted.");
  });
  larp.on("error", m => {
    const div = document.createElement("div");
    div.className = "error";
    div.textContent = (m.id != null ? "Sentence " + m.id + ": " : "") + m.msg;
    $("errors").prepend(div);
    while ($("errors").children.length > 3) $("errors").lastElementChild.remove();
    setTimeout(() => div.remove(), 15000);
    const el = cards.get(String(m.id));
    if (el?.classList.contains("pending")) {
      el.classList.remove("pending");
      const heard = el.querySelector(".heard");
      if (heard) heard.textContent = "Translation unavailable. Listening continues.";
    }
    if (String(m.msg).toLowerCase().startsWith("voice setup")) {
      $("rec-progress").textContent = m.msg;
      setRecording(false);
    }
  });
  function renderFields(probs, chosen) {
    $("fields").innerHTML = Object.entries(probs).sort((a, b) => b[1] - a[1]).map(([domain, probability]) => {
      const pct = Math.round(Math.max(0, Math.min(1, Number(probability) || 0)) * 100);
      return '<div class="field ' + (domain === chosen ? "top" : "") + '"><div class="field-label"><span>' + esc(LABELS[domain] || domain) + '</span><span>' + pct + '%</span></div><div class="track" role="meter" aria-label="' + esc(LABELS[domain] || domain) + '" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + pct + '"><div class="fill" style="width:' + pct + '%"></div></div></div>';
    }).join("");
  }
  function renderTerms(terms, id) {
    $("terms").innerHTML = terms.length ? terms.map(t =>
      '<div class="term"><div class="term-heading"><span class="word">' + esc(t.match) + '</span><span class="term-domain">' + esc(LABELS[t.domain] || t.domain) + '</span></div><div class="term-options">' +
      (t.options || []).map(o => '<span class="opt ' + (o === t.choice ? "chosen" : "") + '">' + esc(o) + "</span>").join("") + '</div><button class="term-retry" data-term="' + esc(t.term) + '" aria-label="Try next meaning for ' + esc(t.term) + '">Try next meaning ↗</button></div>'
    ).join("") : '<p class="muted small" style="margin-top:15px">Everyday words. No special terms needed.</p>';
    $("terms").querySelectorAll(".term-retry").forEach(button => { button.onclick = () => larp.feedback(id, -1, button.dataset.term); });
  }
  const chart = typeof Chart !== "undefined" ? new Chart($("curve"), {
    type: "line",
    data: { labels: [], datasets: [{ data: [], borderColor: "#729b60", backgroundColor: "rgba(100,150,70,.12)", fill: true, tension: .35, pointRadius: 3, pointBackgroundColor: "#8daf70", pointBorderWidth: 0, borderWidth: 2 }] },
    options: {
      animation: false, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => Math.round(ctx.parsed.y * 100) + "% positive feedback" } } },
      scales: {
        y: { min: 0, max: 1, ticks: { stepSize: .5, color: "#8b9c7e", font: { size: 8 }, callback: value => Math.round(value * 100) + "%" }, border: { display: false }, grid: { color: "#d3dfc8" } },
        x: { ticks: { display: false }, border: { display: false }, grid: { display: false } }
      }
    }
  }) : null;
  larp.on("metrics", m => {
    $("accuracy").textContent = m.accuracy == null ? "—" : Math.round(m.accuracy * 100) + "%";
    $("accuracy-meta").textContent = m.n ? m.n + " ratings · last " + m.window + " shown" : "Your feedback starts the curve.";
    if (chart) {
      chart.data.labels = (m.curve || []).map((_, i) => i + 1);
      chart.data.datasets[0].data = m.curve || [];
      chart.update();
    }
  });
  $("reset").onclick = () => {
    if (confirm("Reset the learned term choices? This clears your feedback history.")) {
      larp.resetLearning();
      toast("Learning reset. A fresh start.");
    }
  };
  // ------------------------------------------------------------ signal studio interactions
  const emptyFeed = $("utterances").innerHTML;
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let ambientPaused = reducedMotion.matches;
  const machine = $("signal-machine");
  const canvas = $("signal-canvas");
  const context2d = canvas.getContext("2d");
  let canvasWidth = 1, canvasHeight = 1, frame = 0, visible = true, lastDraw = 0;
  let pointer = { x: 0, y: 0 };
  const dots = Array.from({ length: 130 }, (_, i) => ({
    phase: i * 2.399963, radius: .22 + ((i * 37) % 100) / 220,
    size: i % 11 === 0 ? 2 : .7
  }));
  function sizeCanvas() {
    const rect = machine.getBoundingClientRect();
    canvasWidth = rect.width; canvasHeight = rect.height;
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(canvasWidth * ratio);
    canvas.height = Math.round(canvasHeight * ratio);
    context2d?.setTransform(ratio, 0, 0, ratio, 0, 0);
  }
  function drawSignal(now) {
    if (!context2d) return;
    context2d.clearRect(0, 0, canvasWidth, canvasHeight);
    const t = ambientPaused || reducedMotion.matches ? 0 : now / 6500;
    const cx = canvasWidth / 2 + pointer.x * 8;
    const cy = canvasHeight / 2 + pointer.y * 8;
    const radius = Math.min(canvasWidth, canvasHeight) * .43;
    const pulse = document.body.classList.contains("is-listening") ? 1.08 : 1;
    for (const dot of dots) {
      const angle = dot.phase + t * (dot.size > 1 ? -.4 : .3);
      const x = cx + Math.cos(angle) * radius * dot.radius * 1.9 * pulse;
      const y = cy + Math.sin(angle) * radius * dot.radius * 1.4 * pulse;
      context2d.beginPath();
      context2d.arc(x, y, dot.size, 0, Math.PI * 2);
      context2d.fillStyle = dot.size > 1 ? "#c5fa66" : "#739e5966";
      context2d.fill();
      if (dot.size > 1) {
        context2d.strokeStyle = "#c5fa6614";
        context2d.beginPath(); context2d.moveTo(cx, cy); context2d.lineTo(x, y); context2d.stroke();
      }
    }
    for (let ring = 0; ring < 3; ring++) {
      const distance = ((t * .13 + ring / 3) % 1) * radius;
      context2d.strokeStyle = "rgba(184,234,114," + (.16 * (1 - distance / radius)) + ")";
      context2d.lineWidth = .7; context2d.beginPath();
      context2d.ellipse(cx, cy, distance, distance * .72, -.4, 0, Math.PI * 2);
      context2d.stroke();
    }
  }
  function animateSignal(now) {
    frame = 0;
    if (!visible || document.hidden) return;
    if (now - lastDraw >= 45) { drawSignal(now); lastDraw = now; }
    if (!ambientPaused) frame = requestAnimationFrame(animateSignal);
  }
  function refreshMotion() {
    document.body.classList.toggle("motion-paused", ambientPaused);
    $("motion-toggle").textContent = ambientPaused ? "Play motion ▷" : "Pause motion Ⅱ";
    $("motion-toggle").setAttribute("aria-pressed", String(!ambientPaused));
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
    drawSignal(performance.now());
    if (!ambientPaused && visible && !document.hidden) frame = requestAnimationFrame(animateSignal);
  }
  new ResizeObserver(() => { sizeCanvas(); drawSignal(performance.now()); }).observe(machine);
  new IntersectionObserver(entries => { visible = entries[0].isIntersecting; refreshMotion(); }).observe(machine);
  document.addEventListener("visibilitychange", refreshMotion);
  window.addEventListener("pagehide", () => { if (frame) cancelAnimationFrame(frame); });
  $("motion-toggle").onclick = () => { ambientPaused = !ambientPaused; refreshMotion(); };
  reducedMotion.addEventListener("change", e => { ambientPaused = e.matches; refreshMotion(); });
  machine.addEventListener("pointermove", event => {
    if (ambientPaused || reducedMotion.matches || event.pointerType === "touch") return;
    const box = machine.getBoundingClientRect();
    pointer = { x: (event.clientX - box.left) / box.width - .5, y: (event.clientY - box.top) / box.height - .5 };
    machine.style.setProperty("--tilt-x", -pointer.y * 8 + "deg");
    machine.style.setProperty("--tilt-y", pointer.x * 8 + "deg");
  });
  machine.addEventListener("pointerleave", () => {
    pointer = { x: 0, y: 0 };
    machine.style.setProperty("--tilt-x", "0deg"); machine.style.setProperty("--tilt-y", "0deg");
  });
  sizeCanvas(); refreshMotion();

  const wordWorlds = {
    tennis: { word: "set", meaning: "A chapter of the match.", example: "“She won the first set.”", orbit: "a round of tennis" },
    math: { word: "set", meaning: "A collection of things.", example: "“Let A be a set of integers.”", orbit: "a mathematical collection" },
    cs: { word: "kernel", meaning: "The core of your operating system.", example: "“The kernel schedules the thread.”", orbit: "the operating system core" },
    pickleball: { word: "kitchen", meaning: "The non-volley zone.", example: "“Wait for the bounce in the kitchen.”", orbit: "the non-volley zone" }
  };
  document.querySelectorAll(".lab-context").forEach(button => {
    button.onclick = () => {
      const world = wordWorlds[button.dataset.demo];
      document.querySelectorAll(".lab-context").forEach(other => {
        const active = other === button; other.classList.toggle("active", active); other.setAttribute("aria-pressed", String(active));
      });
      $("lab-word").textContent = world.word;
      $("lab-meaning").textContent = world.meaning;
      $("lab-example").textContent = world.example;
      $("orbit-source").textContent = "“" + world.word + "”";
      $("orbit-meaning").textContent = world.orbit;
      const result = document.querySelector(".lab-result");
      result.classList.remove("switching");
      void result.offsetWidth;
      result.classList.add("switching");
    };
  });
  $("explore-meaning").onclick = () => {
    $("meaning-lab").scrollIntoView({ behavior: reducedMotion.matches ? "instant" : "smooth", block: "center" });
    document.querySelector(".lab-context.active").focus({ preventScroll: true });
  };
  $("hero-start").onclick = () => {
    if (status && !status.listening) larp.setListening(true);
    document.querySelector(".studio-heading").scrollIntoView({ behavior: reducedMotion.matches ? "instant" : "smooth", block: "start" });
  };
  larp.on("status", m => {
    $("hero-start").disabled = false;
    $("hero-start").innerHTML = (m.listening ? "Step into the live studio" : "Enter the conversation") + "<span>↗</span>";
    $("machine-status").textContent = m.listening ? (larp.mock ? "DEMO SIGNAL ACTIVE" : "SESSION LISTENING") : "READY TO CONNECT";
  });
  larp.on("close", () => {
    $("hero-start").disabled = true;
    $("machine-status").textContent = "SIGNAL INTERRUPTED";
  });
  function syncViewButtons() {
    const on = document.body.classList.contains("presentation");
    $("view-stage").classList.toggle("active", on); $("view-stage").setAttribute("aria-pressed", String(on));
    $("view-studio").classList.toggle("active", !on); $("view-studio").setAttribute("aria-pressed", String(!on));
  }
  $("present").addEventListener("click", syncViewButtons);
  $("view-stage").onclick = () => { if (!document.body.classList.contains("presentation")) $("present").click(); };
  $("view-studio").onclick = () => { if (document.body.classList.contains("presentation")) $("present").click(); };
  $("toggle-settings").onclick = () => {
    const on = document.body.classList.toggle("settings-open");
    $("toggle-settings").setAttribute("aria-expanded", String(on));
    $("toggle-settings").setAttribute("aria-label", on ? "Close session settings" : "Open session settings");
  };
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && document.body.classList.contains("settings-open")) {
      document.body.classList.remove("settings-open");
      $("toggle-settings").setAttribute("aria-expanded", "false");
      $("toggle-settings").setAttribute("aria-label", "Open session settings");
      $("toggle-settings").focus();
    }
  });
  $("copy-latest").onclick = async () => {
    const current = utterances.get(latestId);
    if (!current) return;
    try { await navigator.clipboard.writeText(current.translation); toast("Latest translation copied."); }
    catch (_) { toast("Select the translation text to copy it."); }
  };
  larp.on("utterance", () => { $("copy-latest").disabled = !utterances.has(latestId); });
  $("clear-view").onclick = () => {
    if (!cards.size) { toast("A fresh canvas. Your next sentence will appear here."); return; }
    cards.clear(); utterances.clear(); latestId = null;
    $("utterances").innerHTML = emptyFeed;
    $("utterance-count").textContent = "0";
    $("copy-latest").disabled = true;
    $("fields").innerHTML = '<div class="waiting-state">Waiting for the next sentence.<span>⌁</span></div>';
    $("terms").innerHTML = '<p class="muted small">Your next special words will appear here.</p>';
    toast("View cleared. Your learned choices are kept.");
  };

  $("focus-session").onclick = () => {
    const focused = document.body.classList.toggle("session-focused");
    $("focus-session").setAttribute("aria-pressed", String(focused));
    $("focus-session").textContent = focused ? "Show the whole studio ↙" : "Focus on conversation ↗";
    document.querySelector(".studio-heading").scrollIntoView({behavior: "instant", block: "start"});
  };
})();
