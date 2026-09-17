/* ===== KB Dubbing Studio — Segment Editor ===== */
"use strict";

window.onerror = (msg, url, line) => {
  // Benign, spec-defined notification (often triggered by extensions or
  // scrollbar/layout interplay) — logging it hundreds of times is itself a
  // performance problem. Every major site filters it.
  if (String(msg).includes("ResizeObserver loop")) return true;
  console.error("JS Error:", msg, url, line);
};

const API = "/api/";

const LANGUAGES = [
  { code: "eng", name: "English" }, { code: "hin", name: "Hindi" },
  { code: "ben", name: "Bengali" }, { code: "tam", name: "Tamil" },
  { code: "tel", name: "Telugu" }, { code: "kan", name: "Kannada" },
  { code: "mal", name: "Malayalam" }, { code: "mar", name: "Marathi" },
  { code: "guj", name: "Gujarati" }, { code: "pan", name: "Punjabi" },
  { code: "ory", name: "Odia" }, { code: "asm", name: "Assamese" },
  { code: "urd", name: "Urdu" }, { code: "nep", name: "Nepali" },
  { code: "mai", name: "Maithili" }, { code: "doi", name: "Dogri" },
  { code: "bod", name: "Bodo" }, { code: "mni", name: "Manipuri" },
  { code: "sat", name: "Santali" }, { code: "san", name: "Sanskrit" },
  { code: "kok", name: "Konkani" }, { code: "snd", name: "Sindhi" },
  { code: "kas", name: "Kashmiri" },
];

const STATUS = {
  pending:  { icon: "⏳", label: "Pending", cls: "st-pending" },
  approved: { icon: "✅", label: "Approved", cls: "st-approved" },
  overflow: { icon: "⚠️", label: "Overflow", cls: "st-overflow" },
  skip:     { icon: "⏭️", label: "Skipped", cls: "st-skip" },
  rejected: { icon: "✖", label: "Rejected", cls: "st-rejected" },
};

const state = { sessionId: null, file: null, segments: [], selectedId: null };

const $ = id => document.getElementById(id);

document.addEventListener("DOMContentLoaded", () => {
  console.log("[SegmentEditor] Initializing...");
  
  try {
    // Language dropdowns
    const srcLang = $("src-lang");
    const tgtLang = $("tgt-lang");
    if (srcLang) LANGUAGES.forEach(l => srcLang.add(new Option(l.name, l.code)));
    if (tgtLang) LANGUAGES.filter(l => l.code !== "eng").forEach(l => tgtLang.add(new Option(l.name, l.code)));
    if (srcLang) srcLang.value = "eng";
    if (tgtLang) tgtLang.value = "hin";
    
    // File upload handlers
    $("browse-btn")?.addEventListener("click", () => $("video-input")?.click());
    $("dropzone")?.addEventListener("click", e => { if (e.target.tagName !== "BUTTON") $("video-input")?.click(); });
    $("video-input")?.addEventListener("change", e => {
      if (e.target.files.length) {
        state.file = e.target.files[0];
        const fn = $("file-name");
        if (fn) fn.textContent = "📎 " + state.file.name;
        const btn = $("create-session-btn");
        if (btn) btn.disabled = false;
      }
    });
    
    // Button handlers
    $("create-session-btn")?.addEventListener("click", createSession);
    $("translate-all-btn")?.addEventListener("click", () => batchOp("translate"));
    $("tts-all-btn")?.addEventListener("click", () => batchOp("tts"));
    $("auto-approve-btn")?.addEventListener("click", () => batchOp("auto-approve"));
    $("fit-all-btn")?.addEventListener("click", fitAll);
    $("qa-verify-btn")?.addEventListener("click", () => batchOp("qa-verify"));
    $("play-all-btn")?.addEventListener("click", playAll);
    $("gl-apply-btn")?.addEventListener("click", glossaryApply);
    $("d-shorten-btn")?.addEventListener("click", () => llmAssist("shorten"));
    $("d-enhance-btn")?.addEventListener("click", () => llmAssist("enhance"));
    // Auto-save translation edits when the user leaves the textarea —
    // without this, an edited translation was NEVER sent to the server, so
    // regenerate/stitch silently kept using the old text.
    $("d-translation")?.addEventListener("change", saveTranslation);
    // Fit dropdown in the detail panel — previously had NO handler at all
    // (selecting a fit did nothing).
    $("d-fit")?.addEventListener("change", async () => {
      const s = state.segments.find(x => x.id === state.selectedId);
      if (!s || !state.sessionId) return;
      try {
        const resp = await fetch(API + "sessions/" + state.sessionId + "/segments/" + s.id, {
          method: "PATCH", headers: {"Content-Type": "application/json"},
          body: JSON.stringify({ fit: $("d-fit").value })
        });
        if (!resp.ok) throw new Error("HTTP " + resp.status);
        const data = await resp.json();
        Object.assign(s, data);
        renderTable(); updateDurationPreview();
        toast("Fit set to " + data.fit, "ok");
      } catch (e) { toast("Error: " + e.message, "err"); }
    });
    $("d-translate-btn")?.addEventListener("click", translateOne);
    $("d-tts-btn")?.addEventListener("click", ttsOne);
    $("d-approve-btn")?.addEventListener("click", () => setSegStatus("approved"));
    $("d-reject-btn")?.addEventListener("click", () => setSegStatus("rejected"));
    $("d-skip-btn")?.addEventListener("click", () => setSegStatus("skip"));
    $("stitch-btn")?.addEventListener("click", stitchVideo);

    // Reattach to the last session after a refresh — the session lives on
    // the server; only the page's memory of its id was being lost.
    resumeSession();

    console.log("[SegmentEditor] Ready!");
  } catch (e) {
    console.error("[SegmentEditor] Init error:", e);
  }
});

async function resumeSession() {
  let saved = null;
  try { saved = localStorage.getItem("kb_session_id"); } catch (e) {}
  if (!saved) return;
  try {
    const resp = await fetch(API + "sessions/" + saved + "/segments");
    if (!resp.ok) {  // session gone server-side — forget it
      try { localStorage.removeItem("kb_session_id"); } catch (e) {}
      return;
    }
    state.sessionId = saved;
    const badge = $("session-badge");
    if (badge) { badge.textContent = "Session: " + saved + " (resumed)"; badge.className = "badge badge-active"; }
    await loadSegments();
    ["translate-all-btn", "tts-all-btn", "auto-approve-btn", "stitch-btn", "fit-all-btn",
     "qa-verify-btn", "play-all-btn", "gl-apply-btn"].forEach(id => {
      const b = $(id); if (b) b.disabled = false;
    });
    toast("Resumed session " + saved + " — " + state.segments.length + " segments.", "ok");
  } catch (e) {
    console.warn("[resumeSession]", e);
  }
}

async function createSession() {
  if (!state.file) return toast("Select a file first", "err");
  
  const btn = $("create-session-btn");
  const prog = $("upload-progress-wrap");
  const lbl = $("upload-progress-label");
  
  if (btn) btn.disabled = true;
  if (prog) prog.hidden = false;
  if (lbl) lbl.textContent = "Uploading & running ASR...";
  
  const form = new FormData();
  form.append("video", state.file);
  form.append("src_lang", $("src-lang")?.value || "eng");
  form.append("tgt_lang", $("tgt-lang")?.value || "hin");
  
  try {
    const resp = await fetch(API + "sessions", { method: "POST", body: form });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    const data = await resp.json();
    
    state.sessionId = data.session_id;
    try { localStorage.setItem("kb_session_id", state.sessionId); } catch (e) {}
    console.log("[createSession] Session:", state.sessionId);
    
    const badge = $("session-badge");
    if (badge) { badge.textContent = "Session: " + state.sessionId; badge.className = "badge badge-active"; }
    
    if (lbl) lbl.textContent = "Loading segments...";
    await loadSegments();
    
    // Enable buttons
    ["translate-all-btn", "tts-all-btn", "auto-approve-btn", "stitch-btn", "fit-all-btn",
     "qa-verify-btn", "play-all-btn", "gl-apply-btn"].forEach(id => {
      const b = $(id); if (b) b.disabled = false;
    });
    
    toast("Session created! " + state.segments.length + " segments. Click a row to edit.", "ok");
  } catch (e) {
    console.error("[createSession]", e);
    toast("Error: " + e.message, "err");
  } finally {
    if (btn) btn.disabled = false;
    if (prog) prog.hidden = true;
  }
}

async function loadSegments() {
  if (!state.sessionId) return;
  try {
    const resp = await fetch(API + "sessions/" + state.sessionId + "/segments");
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    const data = await resp.json();
    state.segments = data.segments || [];
    state.videoDuration = data.video_duration || state.videoDuration || 0;
    if (data.target_lang && data.target_lang !== state.targetLang) {
      state.targetLang = data.target_lang;
      loadGlossary();
    }
    console.log("[loadSegments]", state.segments.length, "segments");
    renderTable();
    updateDurationPreview();
  } catch (e) {
    console.error("[loadSegments]", e);
  }
}

function renderTable() {
  const tbody = $("seg-tbody");
  if (!tbody) return console.error("seg-tbody not found");
  
  const cnt = $("segment-count");
  if (cnt) cnt.textContent = state.segments.length + " segments";
  
  if (!state.segments.length) {
    tbody.innerHTML = '<tr><td colspan="10">No segments yet</td></tr>';
    return;
  }
  
  tbody.innerHTML = state.segments.map(s => {
    const st = STATUS[s.status] || STATUS.pending;
    const sel = s.id === state.selectedId ? "selected" : "";
    return '<tr class="' + st.cls + ' ' + sel + '" onclick="selectSeg(' + s.id + ')">' +
      '<td>' + s.id + '</td>' +
      '<td>' + fmtTime(s.start) + '</td>' +
      '<td>' + (s.duration||0).toFixed(1) + 's</td>' +
      '<td class="col-text">' + esc(s.original||"").substring(0,50) + '</td>' +
      '<td>' + (s.action||"pending") + '</td>' +
      '<td class="col-text">' + esc(s.translation||"—").substring(0,50) + '</td>' +
      '<td>' + (s.tts_duration ? "✓"+s.tts_duration.toFixed(1)+"s" : "—") + '</td>' +
      '<td>' + (s.fit||"auto") + '</td>' +
      '<td>' + qaCell(s) + '</td>' +
      '<td>' + st.icon + " " + st.label + '</td></tr>';
  }).join("");
}

function qaCell(s) {
  const q = (s.qa === undefined || s.qa === null) ? -1 : s.qa;
  if (q < 0) return '<span class="muted">—</span>';
  const pct = Math.round(q * 100);
  return q >= 0.6 ? '<span title="round-trip ASR match">✓ ' + pct + '%</span>'
                  : '<span class="qa-low" title="TTS audio may be garbled or truncated — listen!">⚠ ' + pct + '%</span>';
}

window.selectSeg = function(id) {
  state.selectedId = id;
  const s = state.segments.find(x => x.id === id);
  if (!s) return;

  renderTable();
  renderTimeline();
  
  const empty = $("detail-empty");
  const content = $("detail-content");
  if (empty) empty.hidden = true;
  if (content) content.hidden = false;
  
  const setVal = (id, val) => { const e = $(id); if (e) e.value = val; };
  const setTxt = (id, val) => { const e = $(id); if (e) e.textContent = val; };
  
  setTxt("d-id", s.id);
  setTxt("d-time", fmtTime(s.start) + " → " + fmtTime(s.end));
  setTxt("d-dur", (s.duration||0).toFixed(1) + "s");
  setVal("d-original", s.original || "");
  setVal("d-translation", s.translation || "");
  setVal("d-fit", s.fit || "auto");
  
  if (s.thumb_url) { const t = $("d-thumb"); if (t) { t.src = s.thumb_url; t.hidden = false; } }
  const a = $("d-audio");
  if (a) {
    if (s.audio_url && s.tts_duration) {
      a.src = s.audio_url;
      a.play().catch(() => {});  // click-to-play; browsers allow after a user gesture
    } else {
      a.removeAttribute("src");  // no stale audio from the previous segment
    }
  }

  console.log("[selectSeg]", id, s);
};

async function translateOne() {
  const s = state.segments.find(x => x.id === state.selectedId);
  if (!s) return toast("Select a segment", "err");
  
  const btn = $("d-translate-btn");
  if (btn) { btn.disabled = true; btn.textContent = "..."; }
  
  try {
    const resp = await fetch(API + "sessions/" + state.sessionId + "/segments/" + s.id + "/translate", {
      method: "POST", headers: {"Content-Type": "application/json"}, body: "{}"
    });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    const data = await resp.json();
    s.translation = data.translation;
    const tf = $("d-translation"); if (tf) tf.value = s.translation || "";
    renderTable();
    toast("Translated!", "ok");
  } catch (e) {
    toast("Error: " + e.message, "err");
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "🌐 Translate"; }
  }
}

async function saveTranslation() {
  const s = state.segments.find(x => x.id === state.selectedId);
  const tf = $("d-translation");
  if (!s || !tf || !state.sessionId) return false;
  const edited = tf.value.trim();
  if (!edited || edited === (s.translation || "").trim()) return false;  // nothing to save
  try {
    const resp = await fetch(API + "sessions/" + state.sessionId + "/segments/" + s.id, {
      method: "PATCH", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ translation: edited })
    });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    const data = await resp.json();
    // Server cleared the now-stale TTS + approval — mirror all of it locally
    // so the table doesn't show audio that no longer exists.
    Object.assign(s, data);
    renderTable(); updateDurationPreview();
    toast("Translation saved — regenerate TTS for this segment.", "ok");
    return true;
  } catch (e) {
    toast("Could not save translation: " + e.message, "err");
    return false;
  }
}

async function ttsOne() {
  const s = state.segments.find(x => x.id === state.selectedId);
  if (!s) return toast("Select a segment", "err");

  const btn = $("d-tts-btn");
  if (btn) { btn.disabled = true; btn.textContent = "..."; }

  try {
    // Safety net: if the textarea holds an unsaved edit, save it FIRST so
    // the regeneration speaks the edited text, not the stale server copy.
    await saveTranslation();
    if (!(s.translation || $("d-translation")?.value || "").trim())
      return toast("Translate first", "err");

    const resp = await fetch(API + "sessions/" + state.sessionId + "/segments/" + s.id + "/tts", {
      method: "POST", headers: {"Content-Type": "application/json"}, body: "{}"
    });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    const data = await resp.json();
    Object.assign(s, data);
    // Cache-bust: the browser may cache the audio URL briefly; a regenerated
    // clip must be re-fetched or the player replays the OLD audio.
    if (s.audio_url) s.audio_url = s.audio_url.split("?")[0] + "?v=" + Date.now();
    const a = $("d-audio");
    if (a && s.audio_url) { a.src = s.audio_url; a.play().catch(() => {}); }
    renderTable();
    updateDurationPreview();
    toast("TTS regenerated (" + (s.tts_duration || 0).toFixed(1) + "s)", "ok");
  } catch (e) {
    toast("Error: " + e.message, "err");
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "🔊 Generate TTS"; }
  }
}

async function llmAssist(kind) {
  const s = state.segments.find(x => x.id === state.selectedId);
  if (!s) return toast("Select a segment", "err");
  const btn = $(kind === "shorten" ? "d-shorten-btn" : "d-enhance-btn");
  if (btn) { btn.disabled = true; btn.textContent = "..."; }
  try {
    await saveTranslation();  // operate on what the user sees
    const resp = await fetch(API + "sessions/" + state.sessionId + "/segments/" + s.id + "/" + kind, {
      method: "POST", headers: {"Content-Type": "application/json"}, body: "{}"
    });
    if (!resp.ok) {
      const detail = (await resp.json().catch(() => ({}))).detail || ("HTTP " + resp.status);
      throw new Error(detail);
    }
    const data = await resp.json();
    Object.assign(s, data);
    const tf = $("d-translation"); if (tf) tf.value = s.translation || "";
    renderTable(); updateDurationPreview();
    toast((kind === "shorten" ? "Shortened — " : "Polished — ") +
          "review the text, then regenerate TTS.", "ok");
  } catch (e) {
    toast(e.message, "err");
  } finally {
    if (btn) { btn.disabled = false;
      btn.textContent = kind === "shorten" ? "✂️ Shorten to Fit" : "✨ LLM Polish"; }
  }
}

let playAllActive = false;
async function playAll() {
  const btn = $("play-all-btn");
  const a = $("d-audio");
  if (playAllActive) {  // acts as Stop
    playAllActive = false;
    if (a) a.pause();
    if (btn) btn.textContent = "▶️ Play All";
    return;
  }
  const withAudio = state.segments.filter(s => s.audio_url && s.tts_duration);
  if (!withAudio.length) return toast("No TTS audio to play yet", "err");
  if (!a) return;
  playAllActive = true;
  if (btn) btn.textContent = "⏹ Stop";
  for (const s of withAudio) {
    if (!playAllActive) break;
    selectSeg(s.id);  // highlights row + timeline, loads + plays the audio
    await new Promise(res => {
      a.onended = res;
      a.onerror = res;
      // If a segment can't autoplay for any reason, don't hang forever.
      setTimeout(res, ((s.tts_duration || 5) + 3) * 1000);
    });
  }
  playAllActive = false;
  if (btn) btn.textContent = "▶️ Play All";
}

async function loadGlossary() {
  const lang = state.targetLang || $("tgt-lang")?.value || "hin";
  try {
    const resp = await fetch(API + "glossary/" + lang);
    if (!resp.ok) return;
    const data = await resp.json();
    const terms = data.terms || {};
    const el = $("gl-list");
    const cnt = $("gl-count");
    if (cnt) cnt.textContent = Object.keys(terms).length + " terms (" + lang + ")";
    if (el) {
      el.innerHTML = Object.entries(terms).sort()
        .map(([src, tgt]) => '<span class="gl-term" title="glossary term">' +
             esc(src) + ' → ' + esc(tgt) + '</span>').join("") ||
        '<span class="muted">No terms yet — fix a term below to start the library.</span>';
    }
  } catch (e) { console.warn("[glossary]", e); }
}

async function glossaryApply() {
  if (!state.sessionId) return toast("No session attached.", "err");
  const find = $("gl-find")?.value.trim();
  const replace = $("gl-replace")?.value.trim();
  const src = $("gl-src")?.value.trim();
  if (!find || !replace) return toast("Enter both a term to find and its replacement.", "err");
  const btn = $("gl-apply-btn");
  if (btn) btn.disabled = true;
  try {
    const resp = await fetch(API + "sessions/" + state.sessionId + "/glossary", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ find: find, replace: replace, register_src: src || null })
    });
    if (!resp.ok) throw new Error("HTTP " + resp.status + ": " + await resp.text());
    const data = await resp.json();
    state.segments = data.segments || state.segments;
    renderTable(); updateDurationPreview();
    const n = (data.applied_to || []).length;
    toast("Replaced in " + n + " segment(s)" +
          (src ? ", term saved to glossary" : "") +
          (n ? " — those segments need TTS regeneration." : "."), n ? "ok" : "");
    ["gl-find", "gl-replace", "gl-src"].forEach(id => { const e = $(id); if (e) e.value = ""; });
    loadGlossary();
  } catch (e) {
    toast("Error: " + e.message, "err");
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function setSegStatus(status) {
  const s = state.segments.find(x => x.id === state.selectedId);
  if (!s) return;
  try {
    await fetch(API + "sessions/" + state.sessionId + "/segments/" + s.id, {
      method: "PATCH", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ status: status })
    });
    s.status = status;
    renderTable();
  } catch (e) {
    toast("Error", "err");
  }
}

async function batchOp(op) {
  // Never fail silently — a click that does nothing is indistinguishable
  // from a broken button.
  if (!state.sessionId) return toast("No session attached — upload a video or wait for session resume.", "err");
  
  const btnId = op === "translate" ? "translate-all-btn"
              : op === "tts" ? "tts-all-btn"
              : op === "qa-verify" ? "qa-verify-btn"
              : "auto-approve-btn";
  const btn = $(btnId);
  const lbl = $("batch-progress-label");
  const bar = $("batch-progress");
  
  if (btn) btn.disabled = true;
  if (lbl) lbl.textContent = "Running " + op + "...";
  
  try {
    const resp = await fetch(API + "sessions/" + state.sessionId + "/batch/" + op, {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ tgt_lang: $("tgt-lang")?.value || "hin" })
    });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    const data = await resp.json();
    
    if (data.job_id) {
      // Poll until the job actually ends — a full-session TTS run takes
      // 10-15 minutes, so no fixed iteration cap (the old 300×1s cap made
      // the UI silently give up at 5 minutes and report "Done!" on a job
      // that was still running). Sanity ceiling: 2 hours.
      const deadline = Date.now() + 2 * 3600 * 1000;
      let lastTableRefresh = 0;
      while (Date.now() < deadline) {
        await new Promise(r => setTimeout(r, 2000));
        let job;
        try {
          const jr = await fetch(API + "jobs/" + data.job_id);
          if (jr.status === 404) throw new Error("Job vanished (server restarted?)");
          job = await jr.json();
        } catch (pollErr) {
          // Transient poll failure (network blip, server busy) — keep polling;
          // the job runs server-side regardless of this connection.
          console.warn("[batchOp] poll failed, retrying:", pollErr);
          continue;
        }
        if (bar) bar.style.width = (job.progress||0) + "%";
        if (lbl) lbl.textContent = "Running " + op + "... " + Math.round(job.progress||0) + "%";
        if (job.status === "done" || job.status === "complete") break;
        if (job.status === "failed") throw new Error(job.error || "Failed");
        // Refresh the table every ~15s mid-run so finished segments show up
        // live instead of only after the whole batch ends.
        if (Date.now() - lastTableRefresh > 15000) {
          lastTableRefresh = Date.now();
          loadSegments();
        }
      }
    }

    await loadSegments();
    if (lbl) lbl.textContent = "Done!";
    toast(op + " complete!", "ok");
  } catch (e) {
    toast("Error: " + e.message, "err");
    if (lbl) lbl.textContent = "Error";
    // The job may well have finished server-side even though this page lost
    // track of it — pull whatever state the server has rather than
    // leaving a stale table.
    loadSegments();
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function fitAll() {
  if (!state.sessionId) return toast("No session attached — upload a video or wait for session resume.", "err");
  const fit = $("fit-all-select")?.value || "auto";
  const btn = $("fit-all-btn");
  if (btn) btn.disabled = true;
  try {
    const resp = await fetch(API + "sessions/" + state.sessionId + "/fit-all", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ fit: fit })
    });
    if (!resp.ok) throw new Error("HTTP " + resp.status + ": " + await resp.text());
    const data = await resp.json();
    state.segments = data.segments || state.segments;
    renderTable();
    updateDurationPreview();
    let note = "Fit '" + fit + "' applied to " + (data.updated ?? "all") + " segments.";
    if (fit === "extend") {
      // Extend only reaches the final video via the extensions stitch path —
      // make sure that checkbox is on so the choice isn't silently ignored.
      const ue = $("use-extensions");
      if (ue && !ue.checked) { ue.checked = true; note += " 'Apply video extensions' enabled."; }
    }
    toast(note, "ok");
  } catch (e) {
    toast("Error: " + e.message, "err");
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function stitchVideo() {
  if (!state.sessionId) return toast("No session attached — upload a video or wait for session resume.", "err");
  const btn = $("stitch-btn");
  const lbl = $("batch-progress-label");
  const bar = $("batch-progress");
  
  if (btn) { btn.disabled = true; btn.textContent = "⏳ Stitching..."; }
  if (lbl) lbl.textContent = "Stitching video...";
  
  try {
    const resp = await fetch(API + "sessions/" + state.sessionId + "/stitch", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ use_extensions: $("use-extensions")?.checked, mix_original_bgm: $("mix-bgm")?.checked })
    });
    if (!resp.ok) {
      const errText = await resp.text();
      throw new Error("HTTP " + resp.status + ": " + errText);
    }
    const data = await resp.json();
    console.log("[stitch] Job started:", data);
    
    if (data.job_id) {
      // Poll until the job actually ends (1h ceiling) — the old 300×1s cap
      // abandoned any stitch longer than 5 minutes and then reported
      // "complete" with no download link.
      const deadline = Date.now() + 3600 * 1000;
      let finished = false;
      while (Date.now() < deadline) {
        await new Promise(r => setTimeout(r, 2000));
        let job;
        try {
          const jr = await fetch(API + "jobs/" + data.job_id);
          if (jr.status === 404) throw new Error("Job vanished (server restarted?)");
          job = await jr.json();
        } catch (pollErr) {
          console.warn("[stitch] poll failed, retrying:", pollErr);
          continue;
        }
        if (bar) bar.style.width = (job.progress||0) + "%";
        if (lbl) lbl.textContent = "Stitching... " + Math.round(job.progress||0) + "%";

        if (job.status === "done" || job.status === "complete") {
          console.log("[stitch] Job complete, result:", job.result);
          if (job.result?.download_url) data.download_url = job.result.download_url;
          finished = true;
          break;
        }
        if (job.status === "failed") throw new Error(job.error || "Failed");
      }
      if (!finished) throw new Error("Stitch did not finish within 1 hour");
    }
    
    const dl = $("download-link");
    console.log("[stitch] Download URL:", data.download_url, "Element:", dl);
    if (dl && data.download_url) { 
      dl.href = data.download_url; 
      dl.hidden = false;
      dl.style.display = "block";  // Force display
      console.log("[stitch] Download link shown");
    }
    if (lbl) lbl.textContent = "✅ Stitch complete!";
    toast("✅ Video stitched! Click Download below.", "ok");
  } catch (e) {
    console.error("[stitch] Error:", e);
    toast("Error: " + e.message, "err");
    if (lbl) lbl.textContent = "Error";
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "🎞️ Stitch Video"; }
  }
}

function fmtTime(s) { s = Math.round(s||0); return Math.floor(s/60) + ":" + String(s%60).padStart(2,"0"); }
function fmtDur(s) { return (s||0).toFixed(1) + "s"; }
function esc(s) { return String(s||"").replace(/[<>&]/g, c => ({"<":"&lt;",">":"&gt;","&":"&amp;"})[c]); }

function updateDurationPreview() {
  if (!state.segments.length) return;
  
  // Calculate original duration (from segments)
  const origDur = state.segments.reduce((max, s) => Math.max(max, s.end || 0), 0);
  
  // Calculate extended duration based on TTS durations and fit strategies
  let totalExtension = 0;
  let extendCount = 0;
  
  state.segments.forEach(s => {
    if (s.tts_duration && s.duration) {
      const overflow = s.tts_duration - s.duration;
      if (overflow > 0) {
        // If fit is 'extend' or auto with overflow, count as extension
        if (s.fit === 'extend' || (s.fit === 'auto' && overflow > s.duration * 0.35)) {
          totalExtension += overflow;
          extendCount++;
        }
      }
    }
  });
  
  const finalDur = origDur + totalExtension;
  const ratio = origDur > 0 ? (finalDur / origDur * 100) : 100;
  
  // Update UI elements
  const origEl = $("orig-duration");
  const finalEl = $("final-duration");
  const infoEl = $("timeline-info");
  const summaryEl = $("extension-summary");
  const ratioEl = $("dur-ratio");
  if (origEl) origEl.textContent = fmtDur(origDur);
  if (finalEl) finalEl.textContent = fmtDur(finalDur);

  // Update info text
  if (infoEl) {
    const segsWithTts = state.segments.filter(s => s.tts_duration).length;
    infoEl.textContent = `${segsWithTts}/${state.segments.length} segments have TTS`;
  }
  
  // Update extension summary
  if (summaryEl) {
    if (totalExtension > 0.1) {
      summaryEl.innerHTML = `<span class="ext-warn">⚠️ ${extendCount} segment(s) will extend video by +${fmtDur(totalExtension)}</span>`;
    } else {
      summaryEl.innerHTML = `<span class="ext-ok">✅ No video extensions needed</span>`;
    }
  }
  
  // Update duration ratio badge
  if (ratioEl) {
    ratioEl.textContent = ratio.toFixed(0) + "%";
    ratioEl.className = "dur-ratio-badge " + (ratio > 120 ? "ratio-warn" : "ratio-ok");
  }

  renderTimeline();
}

// Per-segment timeline: every segment drawn as a clickable block at its real
// position/width on the video's time axis, colored by status. Row 1 shows the
// original timeline; row 2 shows the dubbed timeline where EXTEND segments
// widen (green dashed extension part) and shift everything after them.
function renderTimeline() {
  const origBar = $("timeline-original");
  const extBar = $("timeline-extended");
  if (!origBar || !extBar) return;
  if (!state.segments.length) { origBar.innerHTML = ""; extBar.innerHTML = ""; return; }

  const vidDur = state.videoDuration ||
    state.segments.reduce((m, s) => Math.max(m, s.end || 0), 0);
  if (vidDur <= 0) return;

  const isExtend = (s, slot, over) =>
    over > 0.05 && (s.fit === "extend" || (s.fit === "auto" && over > slot));

  let totalExt = 0;
  state.segments.forEach(s => {
    const slot = (s.end || 0) - (s.start || 0);
    const over = (s.tts_duration || 0) - slot;
    if (isExtend(s, slot, over)) totalExt += over;
  });
  const scale = vidDur + totalExt;  // one shared scale keeps the rows aligned

  const statusColor = {
    approved: "var(--success)", overflow: "var(--warn)",
    rejected: "var(--danger)", skip: "#556", pending: "var(--accent)",
  };

  const mkRow = (extendedRow) => {
    let html = "", cursor = 0, shift = 0;
    for (const s of state.segments) {
      const slot = Math.max((s.end || 0) - (s.start || 0), 0.05);
      const over = (s.tts_duration || 0) - slot;
      const ext = isExtend(s, slot, over);
      const start = (s.start || 0) + (extendedRow ? shift : 0);
      const gap = start - cursor;
      if (gap > 0.01) html += '<span class="seg-gap" style="width:' + (gap / scale * 100).toFixed(3) + '%"></span>';
      const sel = s.id === state.selectedId ? " selected" : "";
      const color = statusColor[s.status] || statusColor.pending;
      const wPct = slot / scale * 100;
      const label = wPct > 2.2 ? s.id : "";  // no label on slivers — unreadable
      const title = "#" + s.id + "  " + fmtTime(s.start) + "-" + fmtTime(s.end) +
        "  slot " + slot.toFixed(1) + "s" +
        (s.tts_duration ? ", tts " + s.tts_duration.toFixed(1) + "s (" + (s.tts_duration / slot).toFixed(2) + "x)" : ", no TTS") +
        "  [" + s.status + "]";
      html += '<span class="seg-block' + sel + '" data-id="' + label + '" title="' + title +
        '" onclick="selectSeg(' + s.id + ')" style="width:' + wPct.toFixed(3) + '%;background:' + color + '"></span>';
      if (extendedRow && ext) {
        html += '<span class="seg-block extension' + sel + '" data-id="" title="' + title +
          ' — video extended +' + over.toFixed(1) + 's" onclick="selectSeg(' + s.id + ')" style="width:' +
          (over / scale * 100).toFixed(3) + '%"></span>';
        shift += over;
        cursor = start + slot + over;
      } else {
        cursor = start + slot;
      }
    }
    return html;
  };

  origBar.innerHTML = mkRow(false);
  extBar.innerHTML = mkRow(true);
}

function toast(msg, type) {
  const t = $("toast");
  if (t) { t.textContent = msg; t.className = "toast " + (type||""); t.hidden = false; setTimeout(() => t.hidden = true, 4000); }
  console.log("[toast]", type, msg);
}
