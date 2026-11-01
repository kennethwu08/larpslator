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
    setPill("pill-badge", m.badge ? (larp.mock ? "Demo badge online" : "Badge connected") : "Badge offline", m.badge ? "on" : "bad");
    const languages = Array.isArray(m.languages) ? m.languages : [];
    if (JSON.stringify([...$("lang").options].map(o => o.value)) !== JSON.stringify(languages)) {
      $("lang").innerHTML = languages.map(l => '<option value="' + esc(l) + '">' + esc(l) + "</option>").join("");
    }
    $("lang").value = m.target;
    $("target-caption").textContent = m.target;
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
    data: { labels: [], datasets: [{ data: [], borderColor: "#a58bb9", backgroundColor: "rgba(165,139,185,.10)", fill: true, tension: .35, pointRadius: 3, pointBackgroundColor: "#bca5cd", pointBorderWidth: 0, borderWidth: 2 }] },
    options: {
      animation: false, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => Math.round(ctx.parsed.y * 100) + "% positive feedback" } } },
      scales: {
        y: { min: 0, max: 1, ticks: { stepSize: .5, color: "#b3a3bf", font: { size: 8 }, callback: value => Math.round(value * 100) + "%" }, border: { display: false }, grid: { color: "#dfd6e7" } },
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
})();
