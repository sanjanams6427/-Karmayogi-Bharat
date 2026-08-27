/* ===== KB Dubbing Studio — Frontend Logic ===== */
"use strict";

const API = "/api/";

/* 22 scheduled Indian languages (KB tender). */
const LANGUAGES = [
  { code: "eng", name: "English" },
  { code: "hin", name: "Hindi" },
  { code: "ben", name: "Bengali" },
  { code: "tam", name: "Tamil" },
  { code: "tel", name: "Telugu" },
  { code: "kan", name: "Kannada" },
  { code: "mal", name: "Malayalam" },
  { code: "mar", name: "Marathi" },
  { code: "guj", name: "Gujarati" },
  { code: "pan", name: "Punjabi" },
  { code: "ory", name: "Odia" },
  { code: "asm", name: "Assamese" },
  { code: "urd", name: "Urdu" },
  { code: "nep", name: "Nepali" },
  { code: "mai", name: "Maithili" },
  { code: "doi", name: "Dogri" },
  { code: "bod", name: "Bodo" },
  { code: "mni", name: "Manipuri" },
  { code: "sat", name: "Santali" },
  { code: "san", name: "Sanskrit" },
  { code: "kok", name: "Konkani" },
  { code: "snd", name: "Sindhi" },
  { code: "kas", name: "Kashmiri" },
];

const STATUS = {
  pending:  { icon: "⏳", label: "Pending",  cls: "st-pending" },
  approved: { icon: "✅", label: "Approved", cls: "st-approved" },
  overflow: { icon: "⚠️", label: "Overflow", cls: "st-overflow" },
  skip:     { icon: "⏭️", label: "Skipped",  cls: "st-skip" },
  rejected: { icon: "✖",  label: "Rejected", cls: "st-rejected" },
};

/* ---- App state ---- */
const state = {
  sessionId: null,
  file: null,
  segments: [],
  selectedId: null,
  origDuration: 0,
};

/* ---- Element cache ---- */
const $ = (id) => document.getElementById(id);
const el = {};

document.addEventListener("DOMContentLoaded", init);

function init() {
  [
    "dropzone", "video-input", "browse-btn", "file-name",
    "src-lang", "tgt-lang", "create-session-btn",
    "upload-progress-wrap", "upload-progress", "upload-progress-label",
    "translate-all-btn", "tts-all-btn", "auto-approve-btn",
    "batch-progress", "batch-progress-label",
    "seg-tbody", "segment-count", "session-badge",
    "detail-empty", "detail-content",
    "d-id", "d-status-badge", "d-thumb", "d-thumb-fallback",
    "d-time", "d-dur", "d-original", "d-translation", "d-audio", "d-fit",
    "d-translate-btn", "d-tts-btn", "d-skip-btn", "d-keep-btn", "d-approve-btn", "d-reject-btn",
    "stitch-btn", "orig-duration", "final-duration", "dur-ratio", "download-link",
    "toast",
  ].forEach((id) => { el[id] = $(id); });

  populateLanguages();
  bindUpload();
  bindBatch();
  bindDetail();
  el["stitch-btn"].addEventListener("click", stitchVideo);
}

/* ============ Language dropdowns ============ */
function populateLanguages() {
  LANGUAGES.forEach((l) => {
    el["src-lang"].add(new Option(`${l.name} (${l.code})`, l.code));
  });
  LANGUAGES.filter((l) => l.code !== "eng").forEach((l) => {
    el["tgt-lang"].add(new Option(`${l.name} (${l.code})`, l.code));
  });
  el["src-lang"].value = "eng";
  el["tgt-lang"].value = "hin";
}

/* ============ Upload / Create Session ============ */
function bindUpload() {
  const dz = el["dropzone"];
  el["browse-btn"].addEventListener("click", () => el["video-input"].click());
  dz.addEventListener("click", (e) => { if (e.target.tagName !== "BUTTON") el["video-input"].click(); });
  dz.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") el["video-input"].click(); });

  ["dragenter", "dragover"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("dragover"); }));
  ["dragleave", "drop"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("dragover"); }));
  dz.addEventListener("drop", (e) => {
    if (e.dataTransfer.files.length) setFile(e.dataTransfer.files[0]);
  });
  el["video-input"].addEventListener("change", (e) => {
    if (e.target.files.length) setFile(e.target.files[0]);
  });

  el["create-session-btn"].addEventListener("click", createSession);
}

function setFile(file) {
  state.file = file;
  el["file-name"].textContent = `📎 ${file.name} (${(file.size / 1048576).toFixed(1)} MB)`;
  el["create-session-btn"].disabled = false;
}

async function createSession() {
  if (!state.file) return toast("Select a file first", "err");
  const btn = el["create-session-btn"];
  btn.disabled = true;
  showUploadProgress(true, 0, "Uploading…");

  const form = new FormData();
  form.append("video", state.file);
  form.append("src_lang", el["src-lang"].value);
  form.append("tgt_lang", el["tgt-lang"].value);

  try {
    const xhr = new XMLHttpRequest();
    const data = await new Promise((resolve, reject) => {
      xhr.open("POST", API + "sessions");
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          const pct = Math.round((e.loaded / e.total) * 100);
          showUploadProgress(true, pct, `Uploading… ${pct}%`);
        }
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try { resolve(JSON.parse(xhr.responseText || "{}")); }
          catch { resolve({}); }
        } else reject(new Error(`HTTP ${xhr.status}`));
      };
      xhr.onerror = () => reject(new Error("Network error"));
      xhr.send(form);
    });

    state.sessionId = data.session_id || data.id || `sess-${Date.now()}`;
    showUploadProgress(true, 100, "Processing audio & running ASR…");
    el["session-badge"].textContent = `Session: ${state.sessionId}`;
    el["session-badge"].className = "badge badge-active";

    await loadSegments();
    enableBatch(true);
    toast("Session created — segments loaded", "ok");
  } catch (err) {
    toast(`Upload failed: ${err.message}`, "err");
    btn.disabled = false;
  } finally {
    setTimeout(() => showUploadProgress(false), 800);
  }
}

function showUploadProgress(show, pct = 0, label = "") {
  el["upload-progress-wrap"].hidden = !show;
  el["upload-progress"].style.width = `${pct}%`;
  if (label) el["upload-progress-label"].textContent = label;
}

/* ============ Load segments ============ */
async function loadSegments() {
  try {
    const res = await fetch(`${API}sessions/${state.sessionId}/segments`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.segments = normalizeSegments(data.segments || data || []);
  } catch (err) {
    toast(`Could not load segments: ${err.message}`, "err");
    state.segments = [];
  }
  state.origDuration = state.segments.reduce((m, s) => Math.max(m, s.end || 0), 0);
  el["orig-duration"].textContent = fmtTime(state.origDuration);
  renderTable();
  el["stitch-btn"].disabled = state.segments.length === 0;
}

function normalizeSegments(arr) {
  return arr.map((s, i) => ({
    id: s.id != null ? s.id : i + 1,
    start: s.start ?? 0,
    end: s.end ?? 0,
    duration: s.duration ?? ((s.end ?? 0) - (s.start ?? 0)),
    original: s.original ?? s.text ?? "",
    translation: s.translation ?? "",
    action: s.action ?? "translate",
    tts_duration: s.tts_duration ?? null,
    fit: s.fit ?? "auto",
    status: s.status ?? "pending",
    audio_url: s.audio_url ?? null,
    thumb_url: s.thumb_url ?? null,
  }));
}

/* ============ Render segment table ============ */
function renderTable() {
  const tb = el["seg-tbody"];
  tb.innerHTML = "";
  el["segment-count"].textContent = `${state.segments.length} segments`;

  if (!state.segments.length) {
    tb.innerHTML = `<tr class="empty-row"><td colspan="9">No segments yet — create a session to begin.</td></tr>`;
    return;
  }

  state.segments.forEach((s) => {
    const st = STATUS[s.status] || STATUS.pending;
    const tr = document.createElement("tr");
    tr.className = st.cls + (s.id === state.selectedId ? " selected" : "");
    tr.dataset.id = s.id;
    tr.innerHTML = `
      <td>${s.id}</td>
      <td>${fmtTime(s.start)}</td>
      <td>${(s.duration || 0).toFixed(1)}s</td>
      <td class="col-text"><span class="cell-clip" title="${esc(s.original)}">${esc(s.original) || "—"}</span></td>
      <td>${s.action}</td>
      <td class="col-text"><span class="cell-clip" title="${esc(s.translation)}">${esc(s.translation) || "—"}</span></td>
      <td>${s.tts_duration != null ? s.tts_duration.toFixed(1) + "s" : "—"}</td>
      <td>${s.fit}</td>
      <td class="status-cell">${st.icon} ${st.label}</td>`;
    tr.addEventListener("click", () => selectSegment(s.id));
    tb.appendChild(tr);
  });
}

/* ============ Segment detail panel ============ */
function selectSegment(id) {
  state.selectedId = id;
  const s = state.segments.find((x) => x.id === id);
  if (!s) return;
  renderTable();

  el["detail-empty"].hidden = true;
  el["detail-content"].hidden = false;

  el["d-id"].textContent = s.id;
  const st = STATUS[s.status] || STATUS.pending;
  el["d-status-badge"].textContent = `${st.icon} ${st.label}`;
  el["d-time"].textContent = `${fmtTime(s.start)} → ${fmtTime(s.end)}`;
  el["d-dur"].textContent = `${(s.duration || 0).toFixed(1)}s`;
  el["d-original"].value = s.original || "";
  el["d-translation"].value = s.translation || "";
  el["d-fit"].value = s.fit || "auto";

  // thumbnail
  if (s.thumb_url) {
    el["d-thumb"].src = s.thumb_url;
    el["d-thumb"].style.display = "block";
    el["d-thumb-fallback"].style.display = "none";
  } else {
    el["d-thumb"].style.display = "none";
    el["d-thumb-fallback"].style.display = "flex";
  }

  // audio
  if (s.audio_url) { 
    el["d-audio"].src = s.audio_url; 
    el["d-audio"].load();  // Force reload
  }
  else { el["d-audio"].removeAttribute("src"); el["d-audio"].load(); }
}

function currentSeg() {
  return state.segments.find((x) => x.id === state.selectedId);
}

function bindDetail() {
  el["d-translation"].addEventListener("input", (e) => {
    const s = currentSeg(); if (s) s.translation = e.target.value;
  });
  el["d-fit"].addEventListener("change", (e) => {
    const s = currentSeg(); if (s) { s.fit = e.target.value; renderTable(); }
  });

  el["d-translate-btn"].addEventListener("click", translateSegment);
  el["d-tts-btn"].addEventListener("click", ttsSegment);
  el["d-skip-btn"].addEventListener("click", () => setStatus("skip", "translate"));
  el["d-keep-btn"].addEventListener("click", () => {
    const s = currentSeg();
    if (s) { s.translation = s.original; s.action = "keep"; el["d-translation"].value = s.original; }
    updateSegment();
  });
  el["d-approve-btn"].addEventListener("click", () => setStatus("approved"));
  el["d-reject-btn"].addEventListener("click", () => setStatus("rejected"));
}

async function translateSegment() {
  const s = currentSeg(); if (!s) return;
  el["d-translate-btn"].disabled = true;
  try {
    const res = await fetch(`${API}sessions/${state.sessionId}/segments/${s.id}/translate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tgt_lang: el["tgt-lang"].value }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    s.translation = data.translation ?? s.translation;
    s.tts_duration = data.tts_duration ?? s.tts_duration;
    s.status = data.status ?? "pending";
    el["d-translation"].value = s.translation;
    selectSegment(s.id);
    renderTable();
    toast("Segment translated", "ok");
  } catch (err) {
    toast(`Translate failed: ${err.message}`, "err");
  } finally {
    el["d-translate-btn"].disabled = false;
  }
}

async function ttsSegment() {
  const s = currentSeg(); if (!s) return;
  if (!s.translation) {
    toast("Translate the segment first", "err");
    return;
  }
  el["d-tts-btn"].disabled = true;
  try {
    const res = await fetch(`${API}sessions/${state.sessionId}/segments/${s.id}/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    s.tts_duration = data.tts_duration ?? s.tts_duration;
    s.audio_url = data.audio_url ?? s.audio_url;
    s.status = data.status ?? s.status;
    selectSegment(s.id);
    renderTable();
    toast("TTS generated", "ok");
  } catch (err) {
    toast(`TTS failed: ${err.message}`, "err");
  } finally {
    el["d-tts-btn"].disabled = false;
  }
}

function setStatus(status, action) {
  const s = currentSeg(); if (!s) return;
  s.status = status;
  if (action) s.action = action;
  updateSegment();
}

async function updateSegment() {
  const s = currentSeg(); if (!s) return;
  selectSegment(s.id);
  renderTable();
  try {
    await fetch(`${API}sessions/${state.sessionId}/segments/${s.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        translation: s.translation, action: s.action,
        fit: s.fit, status: s.status,
      }),
    });
  } catch (err) {
    toast(`Save failed: ${err.message}`, "err");
  }
}

/* ============ Batch operations ============ */
function bindBatch() {
  el["translate-all-btn"].addEventListener("click", () => batchOp("translate", "🌐 Translating all…"));
  el["tts-all-btn"].addEventListener("click", () => batchOp("tts", "🔊 Generating TTS…"));
  el["auto-approve-btn"].addEventListener("click", () => batchOp("auto-approve", "✅ Auto-approving…"));
}

function enableBatch(on) {
  ["translate-all-btn", "tts-all-btn", "auto-approve-btn"].forEach((id) => { el[id].disabled = !on; });
}

async function batchOp(op, label) {
  if (!state.sessionId) return;
  setBatchProgress(5, label);
  enableBatch(false);
  try {
    const res = await fetch(`${API}sessions/${state.sessionId}/batch/${op}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tgt_lang: el["tgt-lang"].value }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    // Poll job progress if the API returns a job id, else reload directly.
    const data = await res.json();
    if (data.job_id) await pollJob(data.job_id, label);
    else setBatchProgress(100, "Done");

    await loadSegments();
    setBatchProgress(100, "Complete");
    toast(`Batch ${op} complete`, "ok");
  } catch (err) {
    toast(`Batch ${op} failed: ${err.message}`, "err");
    setBatchProgress(0, "Failed");
  } finally {
    enableBatch(true);
    setTimeout(() => setBatchProgress(0, "Idle"), 1500);
  }
}

async function pollJob(jobId, label) {
  for (let i = 0; i < 600; i++) {
    await sleep(1000);
    try {
      const res = await fetch(`${API}jobs/${jobId}`);
      if (!res.ok) continue;
      const j = await res.json();
      const pct = Math.round(j.progress ?? 0);
      setBatchProgress(pct, `${label} ${pct}%`);
      if (j.status === "done" || j.status === "complete") return j;
      if (j.status === "failed" || j.status === "error") throw new Error(j.error || "job failed");
    } catch (err) {
      throw err;
    }
  }
  throw new Error("job timed out");
}

function setBatchProgress(pct, label) {
  el["batch-progress"].style.width = `${pct}%`;
  el["batch-progress-label"].textContent = label;
}

/* ============ Stitch / final output ============ */
async function stitchVideo() {
  if (!state.sessionId) return;
  el["stitch-btn"].disabled = true;
  el["stitch-btn"].textContent = "🎞️ Stitching…";
  try {
    const res = await fetch(`${API}sessions/${state.sessionId}/stitch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fit_default: "auto" }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    let data = await res.json();

    if (data.job_id) {
      const job = await pollJob(data.job_id, "🎞️ Stitching…");
      // stitch result lives on the completed job object
      data = (job && job.result) ? job.result : data;
    }

    const finalDur = data.final_duration ?? state.origDuration;
    el["final-duration"].textContent = fmtTime(finalDur);
    const ratio = state.origDuration ? finalDur / state.origDuration : 1;
    el["dur-ratio"].textContent = `${(ratio * 100).toFixed(0)}%`;
    el["dur-ratio"].style.color = ratio > 1.2 ? "var(--warn)" : "var(--success)";

    const url = data.download_url || data.output_url;
    if (url) {
      el["download-link"].href = url;
      el["download-link"].hidden = false;
    }
    toast("Video stitched successfully", "ok");
  } catch (err) {
    toast(`Stitch failed: ${err.message}`, "err");
  } finally {
    el["stitch-btn"].disabled = false;
    el["stitch-btn"].textContent = "🎞️ Stitch Video";
  }
}

/* ============ Helpers ============ */
function fmtTime(sec) {
  sec = Math.max(0, Math.round(sec || 0));
  const m = Math.floor(sec / 60), s = sec % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}
function esc(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

let toastTimer;
function toast(msg, type = "") {
  clearTimeout(toastTimer);
  el["toast"].textContent = msg;
  el["toast"].className = "toast" + (type ? " " + type : "");
  el["toast"].hidden = false;
  toastTimer = setTimeout(() => { el["toast"].hidden = true; }, 3200);
}
