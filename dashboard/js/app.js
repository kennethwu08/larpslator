/* Larpslator dashboard UI. Restyle and rearrange freely.
 *
 * Talks to the backend only through `larp` (js/api.js): call its methods, listen to its events.
 * Event and field names are documented in docs/messages.md.
 */
(function () {
  "use strict";
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const larp = Larp.connect();

  let status = null;          // latest "status" message
  let packs = [];
  let micRecording = null;    // browser voice recording in progress
  let uploading = false;

  // ------------------------------------------------------------ connection
  $("pill-mock").hidden = !larp.mock;
  larp.on("open", () => setPill("pill-server", "server: connected", "on"));
  larp.on("close", () => { setPill("pill-server", "server: reconnecting…", "bad"); $("listen").disabled = true; });

  function setPill(id, text, cls) { $(id).textContent = text; $(id).className = `pill ${cls || ""}`; }

  // ------------------------------------------------------------ status: everything that's on/off
  larp.on("status", m => {
    const first = !status;
    status = m;
    $("listen").disabled = false;
    $("listen").textContent = m.listening ? "Stop" : "Listen";
    $("listen").className = `listen ${m.listening ? "on" : "off"}`;
    setPill("pill-badge", m.badge ? "badge: connected" : "badge: offline", m.badge ? "on" : "");

    const lang = $("lang");
    if (lang.options.length !== m.languages.length) lang.innerHTML = m.languages.map(l => `<option>${esc(l)}</option>`).join("");
    lang.value = m.target;

    renderContexts(m.contexts);
    renderVoice(m.voice, m.voice_recording);
    renderPacks(m.packs, m.context_name);
    if (first) { $("notes").value = m.context; $("notes-name").value = m.context_name; }
  });

  $("listen").onclick = () => larp.setListening(!status.listening);
  $("lang").onchange = e => larp.setLanguage(e.target.value);

  // ------------------------------------------------------------ contexts (checkboxes)
  function renderContexts(contexts) {
    $("contexts").innerHTML = contexts.map(c => `
      <label class="ctx ${c.kind}">
        <input type="checkbox" data-id="${esc(c.id)}" ${c.on ? "checked" : ""}>
        ${esc(c.label)}
        <span class="source" title="Where this context's data comes from: data/ or the backend's built-in fallback">${esc(c.source)}</span>
      </label>`).join("");
    $("contexts").querySelectorAll("input").forEach(cb => cb.onchange = () => larp.toggleContext(cb.dataset.id, cb.checked));
  }

  // ------------------------------------------------------------ meeting notes
  function renderPacks(list, active) {
    packs = list;
    $("packs").innerHTML = `<option value="">Load saved notes…</option>` +
      list.map((p, i) => `<option value="${i}">${esc(p.name)} (${esc(p.saved_at)})</option>`).join("");
    $("notes-status").textContent = active ? `Active: ${active}` : "No notes active";
  }
  $("notes-save").onclick = () => larp.saveNotes($("notes-name").value.trim() || "default", $("notes").value);
  $("packs").onchange = e => {
    const p = packs[e.target.value];
    if (!p) return;
    $("notes-name").value = p.name; $("notes").value = p.text;
    larp.saveNotes(p.name, p.text);
  };

  // ------------------------------------------------------------ voice setup
  function renderVoice(v, badgeRecording) {
    setPill("pill-voice", v.ready ? `voice: ${v.name}` : "voice: stock (set up!)", v.ready ? "on" : "bad");
    $("voice-state").innerHTML = v.ready
      ? `Translations are spoken in <b>${esc(v.name)}</b>'s voice.<br><span class="small">voice id: ${esc(v.voice_id)}</span>`
      : `<span class="warn-text">⚠ Translations use a stock voice. Set up your voice so the badge sounds like you.</span>`;
    $("voice-summary").textContent = v.ready ? "Redo voice setup" : "Set up your voice";
    if (!v.ready && !$("voice-setup").dataset.touched) $("voice-setup").open = true;

    // A badge recording is tracked by the server; a browser recording only here.
    if (badgeRecording !== null) setRecording(true);
    else if (!micRecording && !uploading) {
      setRecording(false);
      if (v.ready && $("rec-progress").textContent.startsWith("Creating")) $("rec-progress").textContent = "Done. Press ▶ Play test.";
    }
  }
  function setRecording(on) {
    $("rec-badge").disabled = $("rec-browser").disabled = on;
    $("rec-stop").disabled = $("rec-cancel").disabled = !on;
  }
  const hint = s => s < 20 ? "Keep reading…" : s < 60 ? "Good. A bit more sounds better." : "Great, press Stop.";

  larp.on("voice_progress", m => {
    $("rec-progress").textContent = m.state === "creating" ? "Creating your voice with ElevenLabs…"
      : `${m.speech_s} s of speech (${m.total_s} s total). ${hint(m.speech_s)}`;
  });
  $("voice-setup").addEventListener("toggle", () => $("voice-setup").dataset.touched = "1");

  $("rec-badge").onclick = () => {
    larp.voiceRecordOnBadge($("voice-name").value);
    setRecording(true);
    $("rec-progress").textContent = "Recording on the badge… start reading.";
  };
  $("rec-browser").onclick = async () => {
    try {
      micRecording = await Larp.recordMicrophone(s => $("rec-progress").textContent = `${s.toFixed(0)} s recorded. ${hint(s)}`);
      setRecording(true);
    } catch (e) {
      // Browsers only allow the mic on localhost or https. Otherwise record on the badge.
      $("rec-progress").textContent = `Microphone not available: ${e.message}`;
    }
  };
  $("rec-stop").onclick = async () => {
    if (!micRecording) { larp.voiceStop(); $("rec-stop").disabled = true; return; }
    const rec = micRecording;
    micRecording = null;
    uploading = true;
    $("rec-stop").disabled = $("rec-cancel").disabled = true;
    $("rec-progress").textContent = "Creating your voice with ElevenLabs…";
    try {
      await larp.voiceUpload(await rec.stop(), $("voice-name").value);
      $("rec-progress").textContent = "Done. Press ▶ Play test.";
    } catch (e) {
      $("rec-progress").textContent = e.message;
    } finally {
      uploading = false;
      setRecording(false);
    }
  };
  $("rec-cancel").onclick = () => {
    if (micRecording) { micRecording.cancel(); micRecording = null; setRecording(false); }
    else larp.voiceCancel();
    $("rec-progress").textContent = "Cancelled.";
  };
  $("voice-test").onclick = () => {
    const url = larp.voiceTestUrl();
    if (!url) { $("rec-progress").textContent = "No audio in mock mode."; return; }
    $("voice-audio").src = url;
    $("voice-audio").play();
  };

  // ------------------------------------------------------------ conversation
  function card(id) {
    let el = document.querySelector(`.utt[data-id="${id}"]`);
    if (!el) {
      el = document.createElement("div");
      el.className = "utt";
      el.dataset.id = id;
      document.querySelector("#utterances .empty")?.remove();
      $("utterances").prepend(el);
    }
    return el;
  }

  larp.on("transcript", m => {
    card(m.id).innerHTML = `<div class="pair"><div class="said">${esc(m.source)}</div>
      <div class="heard muted">translating…</div></div>`;
  });

  larp.on("utterance", u => {
    const t = u.timing_ms || {};
    const ms = (label, v) => v === undefined ? "" : ` · ${label} ${v === 0 ? "cached" : v + " ms"}`;
    const larpTag = u.larp ? ` <span class="tag larp">LARP</span>` : "";
    const said = u.larp && u.larp.text !== u.source
      ? `<div class="original">${esc(u.source)}</div>${esc(u.larp.text)}${larpTag}`
      : `${esc(u.source)}${larpTag}`;
    const chips = u.terms.map(x => `<button class="chip" data-term="${esc(x.term)}" title="Wrong? Try the next translation">${esc(x.match)} → ${esc(x.choice)}</button>`).join("");
    const el = card(u.id);
    el.innerHTML = `
      <div class="pair"><div class="said">${said}</div><div class="heard">${esc(u.translation)}</div></div>
      <div class="actions">
        <button class="up" title="Good translation">👍</button><button class="down" title="Bad: try the next option">👎</button>
        ${chips}
      </div>
      <div class="meta">#${u.id} · ${esc(u.domain)} · ${esc(u.tone)} · ${esc(u.lang)} → ${esc(u.target)}${u.retry ? ` · retry ${u.retry}` : ""}
        ${ms("whisper", t.whisper)}${ms("ml", t.ml)}${ms("gemini", t.gemini)}${ms("voice", t.elevenlabs)} · total ${t.total} ms</div>`;
    el.querySelector(".up").onclick = () => larp.feedback(u.id, 1);
    el.querySelector(".down").onclick = () => larp.feedback(u.id, -1);
    el.querySelectorAll(".chip").forEach(c => c.onclick = () => larp.feedback(u.id, -1, c.dataset.term));

    if (el === $("utterances").firstElementChild) { renderFields(u.domain_probs, u.domain); renderTerms(u.terms); }
  });

  larp.on("feedback", m => {
    const el = document.querySelector(`.utt[data-id="${m.id}"]`);
    if (!el) return;
    el.querySelector(".up")?.classList.toggle("sel", m.val === 1);
    el.querySelector(".down")?.classList.toggle("sel", m.val === -1);
  });

  larp.on("error", m => {
    const div = document.createElement("div");
    div.className = "error";
    div.textContent = `${m.id ? `#${m.id} ` : ""}${m.msg}`;
    $("errors").prepend(div);
    setTimeout(() => div.remove(), 15000);
    if (m.msg.startsWith("voice setup")) { $("rec-progress").textContent = m.msg; setRecording(false); }
  });

  // ------------------------------------------------------------ detected field + special words
  const LABELS = { pickleball: "Pickleball", tennis: "Tennis", cs: "Computer sci.", math: "Math", general: "General" };
  function renderFields(probs, chosen) {
    $("fields").innerHTML = Object.entries(probs).sort((a, b) => b[1] - a[1]).map(([d, p]) => `
      <div class="field ${d === chosen ? "top" : ""}"><span>${esc(LABELS[d] || d)}</span>
        <div class="track"><div class="fill" style="width:${Math.round(p * 100)}%"></div></div>
        <span class="pct">${Math.round(p * 100)}%</span></div>`).join("");
  }
  function renderTerms(terms) {
    $("terms").innerHTML = terms.length ? terms.map(t => `
      <div class="term"><span class="word">${esc(t.match)}</span> <span class="muted small">(${esc(LABELS[t.domain] || t.domain)})</span><br>
        ${t.options.map(o => `<span class="opt ${o === t.choice ? "chosen" : ""}">${esc(o)}</span>`).join("")}</div>`).join("")
      : `<p class="muted">No jargon in the latest sentence.</p>`;
  }

  // ------------------------------------------------------------ learning curve
  const chart = new Chart($("curve"), {
    type: "line",
    data: { labels: [], datasets: [{ data: [], borderColor: "#2ecc71", backgroundColor: "rgba(46,204,113,.15)", fill: true, tension: .3, pointRadius: 2 }] },
    options: {
      animation: false, maintainAspectRatio: false, plugins: { legend: { display: false } },
      scales: { y: { min: 0, max: 1, ticks: { callback: v => `${v * 100}%` } }, x: { ticks: { display: false } } },
    },
  });
  larp.on("metrics", m => {
    $("accuracy").textContent = m.accuracy === null ? "–" : `${Math.round(m.accuracy * 100)}%`;
    $("accuracy-meta").textContent = m.n ? `${m.n} ratings · line = last ${m.window}` : "No feedback yet";
    chart.data.labels = m.curve.map((_, i) => i + 1);
    chart.data.datasets[0].data = m.curve;
    chart.update();
  });
  $("reset").onclick = () => { if (confirm("Forget everything learned from 👍/👎?")) larp.resetLearning(); };
})();
