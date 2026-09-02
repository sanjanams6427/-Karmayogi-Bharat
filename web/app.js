/* ===== KB Dubbing Studio — Segment Editor ===== */
"use strict";

window.onerror = (msg, url, line) => { console.error("JS Error:", msg, url, line); };

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
    $("d-translate-btn")?.addEventListener("click", translateOne);
    $("d-tts-btn")?.addEventListener("click", ttsOne);
    $("d-approve-btn")?.addEventListener("click", () => setSegStatus("approved"));
    $("d-reject-btn")?.addEventListener("click", () => setSegStatus("rejected"));
    $("d-skip-btn")?.addEventListener("click", () => setSegStatus("skip"));
    $("stitch-btn")?.addEventListener("click", stitchVideo);
    
    console.log("[SegmentEditor] Ready!");
  } catch (e) {
    console.error("[SegmentEditor] Init error:", e);
  }
});

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
    console.log("[createSession] Session:", state.sessionId);
    
    const badge = $("session-badge");
    if (badge) { badge.textContent = "Session: " + state.sessionId; badge.className = "badge badge-active"; }
    
    if (lbl) lbl.textContent = "Loading segments...";
    await loadSegments();
    
    // Enable buttons
    ["translate-all-btn", "tts-all-btn", "auto-approve-btn", "stitch-btn"].forEach(id => {
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
    tbody.innerHTML = '<tr><td colspan="9">No segments yet</td></tr>';
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
      '<td>' + st.icon + " " + st.label + '</td></tr>';
  }).join("");
}

window.selectSeg = function(id) {
  state.selectedId = id;
  const s = state.segments.find(x => x.id === id);
  if (!s) return;
  
  renderTable();
  
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
  if (s.audio_url) { const a = $("d-audio"); if (a) a.src = s.audio_url; }
  
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

async function ttsOne() {
  const s = state.segments.find(x => x.id === state.selectedId);
  if (!s) return toast("Select a segment", "err");
  if (!s.translation) return toast("Translate first", "err");
  
  const btn = $("d-tts-btn");
  if (btn) { btn.disabled = true; btn.textContent = "..."; }
  
  try {
    const resp = await fetch(API + "sessions/" + state.sessionId + "/segments/" + s.id + "/tts", {
      method: "POST", headers: {"Content-Type": "application/json"}, body: "{}"
    });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    const data = await resp.json();
    s.tts_duration = data.tts_duration;
    s.audio_url = data.audio_url;
    if (s.audio_url) { const a = $("d-audio"); if (a) a.src = s.audio_url; }
    renderTable();
    updateDurationPreview();
    toast("TTS done!", "ok");
  } catch (e) {
    toast("Error: " + e.message, "err");
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "🔊 Generate TTS"; }
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
  if (!state.sessionId) return;
  
  const btnId = op === "translate" ? "translate-all-btn" : op === "tts" ? "tts-all-btn" : "auto-approve-btn";
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
      for (let i = 0; i < 300; i++) {
        await new Promise(r => setTimeout(r, 1000));
        const jr = await fetch(API + "jobs/" + data.job_id);
        const job = await jr.json();
        if (bar) bar.style.width = (job.progress||0) + "%";
        if (lbl) lbl.textContent = Math.round(job.progress||0) + "%";
        if (job.status === "done" || job.status === "complete") break;
        if (job.status === "failed") throw new Error(job.error || "Failed");
      }
    }
    
    await loadSegments();
    if (lbl) lbl.textContent = "Done!";
    toast(op + " complete!", "ok");
  } catch (e) {
    toast("Error: " + e.message, "err");
    if (lbl) lbl.textContent = "Error";
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function stitchVideo() {
  if (!state.sessionId) return;
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
      for (let i = 0; i < 300; i++) {
        await new Promise(r => setTimeout(r, 1000));
        const jr = await fetch(API + "jobs/" + data.job_id);
        const job = await jr.json();
        console.log("[stitch] Job poll:", job.status, job.progress);
        if (bar) bar.style.width = (job.progress||0) + "%";
        if (lbl) lbl.textContent = "Stitching... " + Math.round(job.progress||0) + "%";
        
        if (job.status === "done" || job.status === "complete") { 
          console.log("[stitch] Job complete, result:", job.result);
          if (job.result?.download_url) data.download_url = job.result.download_url;
          break; 
        }
        if (job.status === "failed") throw new Error(job.error || "Failed");
      }
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
  const origBar = $("timeline-original");
  const extBar = $("timeline-extended");
  
  if (origEl) origEl.textContent = fmtDur(origDur);
  if (finalEl) finalEl.textContent = fmtDur(finalDur);
  
  // Update bars width (original = 100%, extended = ratio%)
  if (origBar) origBar.style.width = "100%";
  if (extBar) extBar.style.width = Math.min(ratio, 150) + "%";
  
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
}

function toast(msg, type) {
  const t = $("toast");
  if (t) { t.textContent = msg; t.className = "toast " + (type||""); t.hidden = false; setTimeout(() => t.hidden = true, 4000); }
  console.log("[toast]", type, msg);
}
