/* Larpslator dashboard UI. Talks to the backend only through `larp` (js/api.js); see docs/messages.md. */
(function () {
  "use strict";
  const $ = id => document.getElementById(id);
  const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const icon = name => `<svg class="icon"><use href="#i-${name}"/></svg>`;
  const LABELS = { pickleball: "Pickleball", tennis: "Tennis", cs: "Computer Science", math: "Math", general: "Everyday" };
  const larp = Larp.connect();

  let status = null, packs = [], micRecording = null, uploading = false, toastTimer;
  const cards = new Map();

  function toast(text) {
    clearTimeout(toastTimer);
    $("toast").textContent = text;
    $("toast").hidden = false;
    toastTimer = setTimeout(() => { $("toast").hidden = true; }, 3500);
  }
  function setConn(text, kind) { $("conn-text").textContent = text; $("conn-dot").className = "dot " + kind; }
  function enable(on) {
    for (const id of ["listen", "lang", "voice-open", "voice-test", "notes-open", "reset"]) $(id).disabled = !on;
  }

  // ---------------------------------------------------------------- connection + status
  $("pill-mock").hidden = !larp.mock;
  larp.on("open", () => setConn("Connected", "on"));
  larp.on("close", () => { setConn("Reconnecting…", "bad"); enable(false); });

  larp.on("status", m => {
    const first = !status;
    status = m;
    enable(true);
    $("listen").classList.toggle("on", !!m.listening);
    $("listen").setAttribute("aria-pressed", String(!!m.listening));
    $("listen").innerHTML = m.listening ? icon("stop") + "<span>Stop</span>" : icon("mic") + "<span>Start Listening</span>";
    $("feed-state").textContent = m.voice_recording != null ? "Recording voice" : m.listening ? "Listening" : "Paused";

    const langs = m.languages || [];
    if ([...$("lang").options].map(o => o.value).join() !== langs.join()) {
      $("lang").innerHTML = langs.map(l => `<option>${esc(l)}</option>`).join("");
    }
    $("lang").value = m.target;

    renderContexts(m.contexts || []);
    renderVoice(m.voice || {}, m.voice_recording);
    renderBadges(m.badges || []);
    renderNotes(m, first);
  });

  $("listen").onclick = () => { if (status) larp.setListening(!status.listening); };
  $("lang").onchange = e => larp.setLanguage(e.target.value);

  // ---------------------------------------------------------------- contexts (switches)
  function switchRow(c) {
    return `<label class="row"><span>${esc(c.label)}${c.source === "data" ? "" : '<span class="row-sub">Starter glossary</span>'}</span>
      <input type="checkbox" class="switch" data-id="${esc(c.id)}" ${c.on ? "checked" : ""} aria-label="${esc(c.label)}"></label>`;
  }
  function renderContexts(contexts) {
    const fields = contexts.filter(c => c.kind === "field"), styles = contexts.filter(c => c.kind === "style");
    const sig = JSON.stringify(contexts);
    if ($("contexts").dataset.sig === sig) return;
    $("contexts").dataset.sig = sig;
    $("contexts").innerHTML = fields.map(switchRow).join("");
    $("styles").innerHTML = styles.map(c => switchRow({ ...c, source: "data" })).join("");
    document.querySelectorAll("#contexts .switch, #styles .switch").forEach(sw => {
      sw.onchange = () => larp.toggleContext(sw.dataset.id, sw.checked);
    });
  }

  // ---------------------------------------------------------------- badge (AirPods-style page)
  const wifi = rssi => rssi == null ? "—" : rssi > -60 ? "Excellent" : rssi > -72 ? "Good" : "Weak";
  larp.on("badges", m => { if (status) { status.badges = m.badges; renderBadges(m.badges || []); } });

  function renderBadges(badges) {
    const active = badges.find(b => b.active);
    const name = b => b.name || b.id;
    $("badge-url").textContent = status?.badge_url || "…";

    // Header: device art with the battery ring
    const device = document.querySelector(".device");
    device.classList.toggle("connected", !!active);
    $("device-name").textContent = active ? name(active) : badges.length ? "Choose a Badge" : "No Badge";
    const bits = [];
    if (active) {
      bits.push(active.battery != null ? `${active.battery}%` : "Connected");
      if (active.battery != null) bits.push("Connected");
    } else bits.push(badges.length ? `${badges.length} available` : "Not connected");
    $("device-sub").textContent = bits.join(" · ");
    const pct = active?.battery ?? 0;
    $("ring-fill").setAttribute("stroke-dasharray", `${active ? pct : 0} 100`);
    $("ring-fill").style.opacity = active && pct > 0 ? 1 : 0;  // a zero-length round stroke still draws a dot
    $("ring-fill").classList.toggle("low", pct > 0 && pct < 20);

    // Badges online but not connected
    const others = badges.filter(b => !b.active);
    $("available-wrap").hidden = !others.length;
    $("available").innerHTML = others.map(b => `
      <div class="row badge-pick"><span>${esc(name(b))}<span class="row-sub">${b.battery != null ? esc(b.battery) + "% · " : ""}Wi-Fi ${wifi(b.rssi)}</span></span>
        <button class="pill-button" data-id="${esc(b.id)}">Connect</button></div>`).join("");
    $("available").querySelectorAll("button").forEach(btn => {
      btn.onclick = () => { larp.connectBadge(btn.dataset.id); toast("Connecting…"); };
    });
    $("badge-help").hidden = !!active;

    // Controls + About, only with a connected badge
    $("badge-section").hidden = !active;
    if (!active) return;
    if (document.activeElement !== $("badge-name")) $("badge-name").value = name(active);
    if (document.activeElement !== $("badge-volume")) setVolume(active.volume ?? 70);
    const cfg = status?.badge_config || {};
    const about = [
      ["Firmware", active.fw || "—"],
      ["Wi-Fi", active.rssi != null ? `${wifi(active.rssi)} (${active.rssi} dBm)` : "—"],
      ["Latency", active.rtt_ms != null ? `${active.rtt_ms} ms` : "—"],
      ["Address", active.ip || "—"],
      ["Settings", active.config_synced ? '<span class="ok">Up to Date</span>' : "Updating…"],
      ["Language on Badge", esc(cfg.target || "—")],
    ];
    $("badge-about").innerHTML = about.map(([k, v]) =>
      `<div class="row"><span>${k}</span><span class="about-value">${k === "Settings" || k === "Language on Badge" ? v : esc(v)}</span></div>`).join("");
  }

  function setVolume(v) { $("badge-volume").value = v; $("badge-volume").style.setProperty("--pct", v + "%"); }
  const activeBadge = () => (status?.badges || []).find(b => b.active);
  $("badge-volume").oninput = e => setVolume(e.target.value);
  $("badge-volume").onchange = e => { const b = activeBadge(); if (b) larp.setBadgeVolume(b.id, Number(e.target.value)); };
  $("badge-name").onchange = e => {
    const b = activeBadge(), v = e.target.value.trim();
    if (b && v) larp.renameBadge(b.id, v);
  };
  $("badge-name").onkeydown = e => { if (e.key === "Enter") e.target.blur(); };
  $("badge-identify").onclick = () => { const b = activeBadge(); if (b) { larp.identifyBadge(b.id); toast("Badge light is blinking"); } };
  $("badge-disconnect").onclick = () => {
    if (confirm("Disconnect this badge? It stays on and can be connected again.")) larp.disconnectBadge();
  };

  // ---------------------------------------------------------------- voice
  function setRecording(on) {
    $("rec-badge").disabled = on || !status?.badge;
    $("rec-browser").disabled = on;
    $("rec-stop").disabled = $("rec-cancel").disabled = !on || uploading;
  }
  function renderVoice(v, badgeRecording) {
    $("voice-value").textContent = v.ready ? v.name || "Your voice" : "Not set up";
    $("voice-value").style.color = v.ready ? "" : "var(--orange)";
    const recordingOnBadge = badgeRecording !== null && badgeRecording !== undefined;
    if (!micRecording && !uploading) setRecording(recordingOnBadge);
    if (v.ready && $("rec-progress").textContent.startsWith("Creating")) $("rec-progress").textContent = "Done. Play Sample to hear it.";
  }
  const hint = s => s < 20 ? "Keep reading." : s < 60 ? "Good. A bit more sounds better." : "That's enough. Tap Stop.";
  larp.on("voice_progress", m => {
    $("rec-progress").textContent = m.state === "creating" ? "Creating your voice…" : `${m.speech_s} s of speech. ${hint(m.speech_s)}`;
  });
  $("voice-open").onclick = () => { setRecording(false); $("voice-sheet").showModal(); };
  $("voice-close").onclick = () => $("voice-sheet").close();
  $("rec-badge").onclick = () => {
    larp.voiceRecordOnBadge($("voice-name").value);
    setRecording(true);
    $("rec-progress").textContent = "Recording on the badge. Start reading.";
  };
  $("rec-browser").onclick = async () => {
    if (larp.mock) {  // no microphone in demo mode: simulate it
      larp.voiceRecordOnBadge($("voice-name").value);
      setRecording(true);
      $("rec-progress").textContent = "Simulated recording.";
      return;
    }
    try {
      micRecording = await Larp.recordMicrophone(s => { $("rec-progress").textContent = `${s.toFixed(0)} s recorded. ${hint(s)}`; });
      setRecording(true);
    } catch (e) {
      $("rec-progress").textContent = "Microphone unavailable: " + e.message + " (use localhost, https, or Record on Badge).";
    }
  };
  $("rec-stop").onclick = async () => {
    if (!micRecording) { larp.voiceStop(); $("rec-stop").disabled = true; return; }
    const rec = micRecording;
    micRecording = null;
    uploading = true;
    setRecording(true);
    $("rec-progress").textContent = "Creating your voice…";
    try {
      await larp.voiceUpload(await rec.stop(), $("voice-name").value);
      $("rec-progress").textContent = "Done. Play Sample to hear it.";
    } catch (e) {
      $("rec-progress").textContent = e.message;
    } finally {
      uploading = false;
      setRecording(false);
    }
  };
  $("rec-cancel").onclick = () => {
    if (micRecording) { micRecording.cancel(); micRecording = null; } else larp.voiceCancel();
    setRecording(false);
    $("rec-progress").textContent = "Cancelled.";
  };
  $("voice-test").onclick = async () => {
    const url = larp.voiceTestUrl();
    if (!url) { toast("No audio in demo mode"); return; }
    const audio = new Audio(url);
    try { await audio.play(); } catch { toast("Couldn't play the sample"); }
  };

  // ---------------------------------------------------------------- notes
  function renderNotes(m, first) {
    $("notes-value").textContent = m.context_name || "None";
    const sig = JSON.stringify(m.packs || []);
    if ($("packs").dataset.sig !== sig) {
      packs = m.packs || [];
      $("packs").innerHTML = `<option value="">None</option>` + packs.map((p, i) => `<option value="${i}">${esc(p.name)}</option>`).join("");
      $("packs").dataset.sig = sig;
    }
    if (first) { $("notes").value = m.context || ""; $("notes-name").value = m.context_name || ""; }
  }
  $("notes-open").onclick = () => $("notes-sheet").showModal();
  $("notes-close").onclick = () => $("notes-sheet").close();
  $("notes-save").onclick = () => {
    larp.saveNotes($("notes-name").value.trim() || "Notes", $("notes").value);
    $("notes-sheet").close();
    toast("Notes saved");
  };
  $("packs").onchange = e => {
    const p = packs[Number(e.target.value)];
    if (!p) return;
    $("notes-name").value = p.name;
    $("notes").value = p.text;
  };

  // ---------------------------------------------------------------- conversation
  function card(id) {
    const key = String(id);
    if (cards.has(key)) return cards.get(key);
    const el = document.createElement("article");
    el.className = "utt";
    $("empty")?.remove();
    $("utterances").prepend(el);
    cards.set(key, el);
    if (cards.size > 50) {  // keep long rehearsals fast
      const oldest = cards.keys().next().value;
      cards.get(oldest).remove();
      cards.delete(oldest);
    }
    return el;
  }
  function highlight(source, terms) {
    const spans = (terms || []).filter(t => Number.isInteger(t.pos) && t.pos >= 0 && t.match &&
      source.slice(t.pos, t.pos + t.match.length).toLowerCase() === t.match.toLowerCase()).sort((a, b) => a.pos - b.pos);
    let out = "", at = 0;
    for (const t of spans) {
      if (t.pos < at) continue;
      out += esc(source.slice(at, t.pos)) + "<mark>" + esc(source.slice(t.pos, t.pos + t.match.length)) + "</mark>";
      at = t.pos + t.match.length;
    }
    return out + esc(source.slice(at));
  }
  const cap = s => s ? s[0].toUpperCase() + s.slice(1) : "";

  larp.on("transcript", m => {
    const el = card(m.id);
    el.classList.add("pending");
    el.innerHTML = `<div class="lang">${esc(cap(m.lang))}</div><div class="said">${esc(m.source)}</div><div class="heard">Translating…</div>`;
  });

  larp.on("utterance", u => {
    const el = card(u.id), terms = u.terms || [], t = u.timing_ms || {};
    el.classList.remove("pending");
    const total = t.total ? (t.total / 1000).toFixed(1) + " s" : "cached";
    const larpLine = u.larp && u.larp.text !== u.source ? `<div class="larp"><b>LARP</b> ${esc(u.larp.text)}</div>` : "";
    el.innerHTML = `
      <div class="lang">${esc(cap(u.lang))} → ${esc(u.target)}</div>
      <div class="said">${highlight(u.source || "", terms)}</div>
      ${larpLine}
      <div class="heard" lang="${esc(u.target === "Korean" ? "ko" : "")}">${esc(u.translation)}</div>
      ${terms.length ? `<div class="chips">${terms.map(x =>
        `<button class="chip" data-term="${esc(x.term)}" title="Wrong? Try the next translation">${esc(x.match)}<span class="to">→</span>${esc(x.choice)}</button>`).join("")}</div>` : ""}
      <div class="utt-foot">
        <span class="meta">${esc(LABELS[u.domain] || u.domain)} · ${total}${u.retry ? " · updated" : ""}</span>
        <button class="fb up" aria-label="Good translation">${icon("up")}</button>
        <button class="fb down" aria-label="Wrong translation, try another">${icon("down")}</button>
      </div>`;
    el.querySelector(".up").onclick = () => larp.feedback(u.id, 1);
    el.querySelector(".down").onclick = () => larp.feedback(u.id, -1);
    el.querySelectorAll(".chip").forEach(c => { c.onclick = () => larp.feedback(u.id, -1, c.dataset.term); });
    if (el === $("utterances").firstElementChild) { renderFields(u.domain_probs || {}, u.domain); renderTerms(terms, u.id); }
  });

  larp.on("feedback", m => {
    const el = cards.get(String(m.id));
    el?.querySelector(".up")?.classList.toggle("sel", m.val === 1);
    el?.querySelector(".down")?.classList.toggle("sel", m.val === -1);
    if (m.val < 0 && m.term) toast(`Trying another translation for “${m.term}”`);
  });

  larp.on("error", m => {
    const div = document.createElement("div");
    div.className = "error";
    div.textContent = m.msg;
    $("errors").prepend(div);
    while ($("errors").children.length > 2) $("errors").lastElementChild.remove();
    setTimeout(() => div.remove(), 12000);
    const el = cards.get(String(m.id));
    if (el?.classList.contains("pending")) el.querySelector(".heard").textContent = "Couldn't translate this one.";
    if (String(m.msg).startsWith("voice setup")) { $("rec-progress").textContent = m.msg; setRecording(false); }
  });

  // ---------------------------------------------------------------- insights
  function renderFields(probs, chosen) {
    $("fields").innerHTML = Object.entries(probs).sort((a, b) => b[1] - a[1]).map(([d, p]) => {
      const pct = Math.round(p * 100);
      return `<div class="field ${d === chosen ? "top" : ""}"><div class="field-label"><span>${esc(LABELS[d] || d)}</span><span>${pct}%</span></div>
        <div class="track" role="meter" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100" aria-label="${esc(LABELS[d] || d)}"><div class="fill" style="width:${pct}%"></div></div></div>`;
    }).join("");
  }
  function renderTerms(terms, id) {
    $("terms").innerHTML = terms.length ? terms.map(t => `
      <div class="term"><div class="term-word">${esc(t.match)}<span>${esc(LABELS[t.domain] || t.domain)}</span></div>
        <div class="options">${(t.options || []).map(o => o === t.choice
          ? `<span class="opt chosen">${esc(o)}</span>`
          : `<button class="opt" data-term="${esc(t.term)}">${esc(o)}</button>`).join("")}</div></div>`).join("")
      : `<p class="secondary small">No jargon in the latest sentence.</p>`;
    $("terms").querySelectorAll("button.opt").forEach(b => { b.onclick = () => larp.feedback(id, -1, b.dataset.term); });
  }

  const css = getComputedStyle(document.documentElement);
  const chart = typeof Chart === "undefined" ? null : new Chart($("curve"), {
    type: "line",
    data: { labels: [], datasets: [{ data: [], borderColor: css.getPropertyValue("--blue").trim(), borderWidth: 2, pointRadius: 0, tension: .35, fill: false }] },
    options: {
      animation: false, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: { x: { display: false }, y: { min: 0, max: 1, display: false } },
    },
  });
  larp.on("metrics", m => {
    $("accuracy").textContent = m.accuracy == null ? "No ratings" : Math.round(m.accuracy * 100) + "%";
    $("accuracy").classList.toggle("secondary", m.accuracy == null);
    $("accuracy-meta").textContent = m.n ? `${m.n} rating${m.n === 1 ? "" : "s"}. Line shows the last ${m.window}.` : "From your thumbs up and down.";
    if (chart) { chart.data.labels = (m.curve || []).map((_, i) => i); chart.data.datasets[0].data = m.curve || []; chart.update(); }
  });
  $("reset").onclick = () => { if (confirm("Forget what was learned from your feedback?")) { larp.resetLearning(); toast("Learning reset"); } };
})();
