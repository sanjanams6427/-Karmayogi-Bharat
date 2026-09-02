/* ===== KB Dubbing Studio — Admin Pages JavaScript ===== */
"use strict";

const KB_11 = ["asm", "ben", "guj", "hin", "kan", "mal", "mar", "ory", "pan", "tam", "tel"];

/* ===== STATE ===== */
const adminState = {
  batchFile: null,
  batchMeta: null,
  batchQuiz: null,
  batchLangs: [...KB_11],
  batchJobId: null,
  docFile: null,
  docLangs: [...KB_11],
  reviewSegments: [],
  reviewPath: "",
  corrTickets: [],
  monthlyEntries: [],
  glossaryEntries: [],
};

/* ===== INITIALIZATION ===== */
document.addEventListener("DOMContentLoaded", () => {
  console.log("[admin.js] Initializing admin pages...");
  
  // Only initialize if we're not on a page that doesn't have these elements
  try {
    initTabs();
    
    // Only init batch dubbing if elements exist
    if (document.getElementById('batch-tgt-langs')) {
      initBatchDubbing();
    }
    if (document.getElementById('doc-tgt-langs')) {
      initTranslateDoc();
    }
    if (document.getElementById('qa-src-lang')) {
      initQACert();
    }
    if (document.getElementById('review-input')) {
      initHumanReview();
    }
    if (document.getElementById('corr-lang')) {
      initCorrections();
    }
    if (document.getElementById('monthly-langs')) {
      initMonthly();
    }
    if (document.getElementById('gl-term')) {
      initGlossary();
    }
    if (document.getElementById('settings-hf-token')) {
      initSettings();
    }
    
    checkPipelineStatus();
    console.log("[admin.js] Initialization complete");
  } catch (e) {
    console.error("[admin.js] Init error:", e);
  }
});

/* ===== TAB NAVIGATION ===== */
function initTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tabId = btn.dataset.tab;
      document.querySelectorAll('.tab-page').forEach(page => page.classList.remove('active'));
      document.getElementById('page-' + tabId)?.classList.add('active');
    });
  });
}

/* ===== UTILITY FUNCTIONS ===== */
function showToast(msg, type = "info") {
  const toast = document.getElementById("toast");
  if (toast) {
    toast.textContent = msg;
    toast.className = `toast toast-${type}`;
    toast.hidden = false;
    setTimeout(() => { toast.hidden = true; }, 4000);
  }
}

function getLangName(code) {
  const lang = LANGUAGES?.find(l => l.code === code);
  return lang ? lang.name : code;
}

function populateLangSelect(selectId, includeEng = true) {
  const select = document.getElementById(selectId);
  if (!select || !LANGUAGES) return;
  select.innerHTML = '';
  LANGUAGES.forEach(l => {
    if (!includeEng && l.code === 'eng') return;
    const opt = document.createElement('option');
    opt.value = l.code;
    opt.textContent = l.name;
    select.appendChild(opt);
  });
}

function populateLangGrid(gridId, selectedLangs, onChange) {
  const grid = document.getElementById(gridId);
  if (!grid || !LANGUAGES) return;
  grid.innerHTML = '';
  LANGUAGES.filter(l => l.code !== 'eng').forEach(l => {
    const label = document.createElement('label');
    label.className = 'lang-check';
    label.innerHTML = `<input type="checkbox" value="${l.code}" ${selectedLangs.includes(l.code) ? 'checked' : ''}><span>${l.name}</span>`;
    label.querySelector('input').addEventListener('change', onChange);
    grid.appendChild(label);
  });
}

function getSelectedLangs(gridId) {
  return Array.from(document.querySelectorAll(`#${gridId} input:checked`)).map(cb => cb.value);
}

function setSelectedLangs(gridId, codes) {
  document.querySelectorAll(`#${gridId} input`).forEach(cb => {
    cb.checked = codes.includes(cb.value);
  });
}

function setupDropzone(dropzoneId, inputId, fileNameId, onFile) {
  const dropzone = document.getElementById(dropzoneId);
  const input = document.getElementById(inputId);
  if (!dropzone || !input) return;
  
  dropzone.addEventListener('click', () => input.click());
  dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('dragover'); });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
  dropzone.addEventListener('drop', e => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    if (e.dataTransfer.files.length) onFile(e.dataTransfer.files[0]);
  });
  input.addEventListener('change', () => { if (input.files.length) onFile(input.files[0]); });
}

async function checkPipelineStatus() {
  try {
    const resp = await fetch('/api/pipeline/status');
    const data = await resp.json();
    const badge = document.getElementById('pipeline-status');
    if (badge) {
      badge.textContent = data.ready ? '✅ Pipeline Ready' : '⏳ Loading...';
      badge.className = `badge ${data.ready ? 'badge-active' : 'badge-muted'}`;
    }
  } catch (e) {
    console.log('Pipeline status check failed');
  }
}

/* ===== PAGE 2: BATCH DUBBING ===== */
function initBatchDubbing() {
  populateLangSelect('batch-src-lang', true);
  document.getElementById('batch-src-lang').value = 'eng';
  
  populateLangGrid('batch-tgt-langs', adminState.batchLangs, () => {
    adminState.batchLangs = getSelectedLangs('batch-tgt-langs');
    updateBatchBtn();
  });
  
  setupDropzone('batch-dropzone', 'batch-video-input', 'batch-file-name', file => {
    adminState.batchFile = file;
    document.getElementById('batch-file-name').textContent = file.name;
    document.getElementById('batch-dropzone').classList.add('has-file');
    updateBatchBtn();
  });
  
  setupDropzone('batch-meta-dropzone', 'batch-meta-input', 'batch-meta-name', file => {
    adminState.batchMeta = file;
    document.getElementById('batch-meta-name').textContent = file.name;
  });
  
  setupDropzone('batch-quiz-dropzone', 'batch-quiz-input', 'batch-quiz-name', file => {
    adminState.batchQuiz = file;
    document.getElementById('batch-quiz-name').textContent = file.name;
  });
  
  document.getElementById('btn-kb11')?.addEventListener('click', () => {
    setSelectedLangs('batch-tgt-langs', KB_11);
    adminState.batchLangs = KB_11;
    updateBatchBtn();
  });
  document.getElementById('btn-all22')?.addEventListener('click', () => {
    const all = LANGUAGES.filter(l => l.code !== 'eng').map(l => l.code);
    setSelectedLangs('batch-tgt-langs', all);
    adminState.batchLangs = all;
    updateBatchBtn();
  });
  document.getElementById('btn-clear-langs')?.addEventListener('click', () => {
    setSelectedLangs('batch-tgt-langs', []);
    adminState.batchLangs = [];
    updateBatchBtn();
  });
  
  document.getElementById('batch-start-btn')?.addEventListener('click', startBatchDubbing);
}

function updateBatchBtn() {
  const btn = document.getElementById('batch-start-btn');
  if (btn) btn.disabled = !adminState.batchFile || adminState.batchLangs.length === 0;
}

async function startBatchDubbing() {
  const courseId = document.getElementById('batch-course-id').value.trim() || 'KB_COURSE_001';
  const srcLang = document.getElementById('batch-src-lang').value;
  const force = document.getElementById('batch-force').checked;
  
  document.getElementById('batch-progress-card').hidden = false;
  document.getElementById('batch-start-btn').disabled = true;
  document.getElementById('batch-log').textContent = '';
  document.getElementById('batch-results-tbody').innerHTML = '<tr class="empty-row"><td colspan="9">Processing...</td></tr>';
  adminState.seenLogLines = new Set();  // Reset log tracking
  
  const formData = new FormData();
  formData.append('file', adminState.batchFile);
  formData.append('course_id', courseId);
  formData.append('src_lang', srcLang);
  formData.append('tgt_langs', JSON.stringify(adminState.batchLangs));
  formData.append('force', force ? '1' : '0');
  if (adminState.batchMeta) formData.append('metadata', adminState.batchMeta);
  if (adminState.batchQuiz) formData.append('quiz', adminState.batchQuiz);
  
  appendBatchLog(`Uploading ${adminState.batchFile.name}...`);
  
  try {
    const resp = await fetch('/api/batch/start', { method: 'POST', body: formData });
    if (!resp.ok) throw new Error((await resp.json()).detail || 'Upload failed');
    const data = await resp.json();
    adminState.batchJobId = data.job_id;
    appendBatchLog(`Job started: ${data.job_id}`);
    pollBatchJob();
  } catch (e) {
    appendBatchLog(`ERROR: ${e.message}`);
    document.getElementById('batch-start-btn').disabled = false;
    showToast(e.message, 'error');
  }
}

async function pollBatchJob() {
  if (!adminState.batchJobId) return;
  try {
    const resp = await fetch(`/api/batch/status/${adminState.batchJobId}`);
    const data = await resp.json();
    
    document.getElementById('batch-job-progress').style.width = `${data.progress}%`;
    document.getElementById('batch-job-label').textContent = data.status_message || `${data.progress}%`;
    
    // Track seen log lines to avoid duplicates
    if (data.log_lines) {
      if (!adminState.seenLogLines) adminState.seenLogLines = new Set();
      data.log_lines.forEach(line => {
        if (!adminState.seenLogLines.has(line)) {
          adminState.seenLogLines.add(line);
          appendBatchLog(line);
        }
      });
    }
    if (data.results) updateBatchResults(data.results);
    if (data.summary) document.getElementById('batch-summary').textContent = data.summary;
    
    if (data.status === 'completed') {
      appendBatchLog('✅ Job completed!');
      document.getElementById('batch-start-btn').disabled = false;
      showToast('Batch dubbing completed!', 'success');
      // Show downloads section
      const downloads = document.getElementById('batch-downloads');
      if (downloads) downloads.hidden = false;
      return;
    }
    if (data.status === 'failed') {
      appendBatchLog(`❌ Failed: ${data.error}`);
      document.getElementById('batch-start-btn').disabled = false;
      showToast('Job failed', 'error');
      return;
    }
    setTimeout(pollBatchJob, 2000);
  } catch (e) {
    setTimeout(pollBatchJob, 5000);
  }
}

function appendBatchLog(line) {
  const log = document.getElementById('batch-log');
  if (log) {
    log.textContent += `[${new Date().toLocaleTimeString()}] ${line}\n`;
    log.scrollTop = log.scrollHeight;
  }
}

function updateBatchResults(results) {
  const tbody = document.getElementById('batch-results-tbody');
  if (!tbody) return;
  
  console.log('[Batch] Updating results:', results);
  
  tbody.innerHTML = results.map(r => {
    const downloadBtns = r.output_path ? `
      <div class="download-btns">
        <a href="/api/batch/download/${adminState.batchJobId}/${r.lang}/mp4" class="btn btn-xs btn-success" download title="Video">🎬 MP4</a>
        <a href="/api/batch/download/${adminState.batchJobId}/${r.lang}/mp3" class="btn btn-xs btn-ghost" download title="Audio">🔊 MP3</a>
        <a href="/api/batch/download/${adminState.batchJobId}/${r.lang}/srt" class="btn btn-xs btn-ghost" download title="Subtitles">📝 SRT</a>
        <a href="/api/batch/download/${adminState.batchJobId}/${r.lang}/vtt" class="btn btn-xs btn-ghost" download title="Web Subtitles">📝 VTT</a>
        <a href="/api/batch/download/${adminState.batchJobId}/${r.lang}/json" class="btn btn-xs btn-ghost" download title="Metadata">📋 JSON</a>
      </div>
    ` : (r.error ? `<span class="text-error" title="${r.error}">❌ ${r.error.substring(0, 30)}...</span>` : '—');
    
    const scoreClass = r.score >= 0.55 ? 'score-pass' : r.score >= 0.30 ? 'score-review' : r.score != null ? 'score-fail' : '';
    const scoreDisplay = r.score != null ? `<span class="${scoreClass}">${r.score.toFixed(2)}</span>` : '—';
    
    return `
    <tr class="${r.status === 'completed' ? 'row-success' : r.status === 'failed' ? 'row-error' : ''}">
      <td><strong>${getLangName(r.lang)}</strong></td>
      <td>${scoreDisplay}</td>
      <td><span class="status-badge status-${r.status}">${r.status}</span></td>
      <td>${r.pass_rate != null ? (r.pass_rate * 100).toFixed(0) + '%' : '—'}</td>
      <td>${r.total_segments || '—'}</td>
      <td>${r.failed_segments || '0'}</td>
      <td>${r.review_segments || '0'}</td>
      <td>${r.duration_ratio != null ? (r.duration_ratio * 100).toFixed(0) + '%' : '—'}</td>
      <td>${downloadBtns}</td>
    </tr>`;
  }).join('');
}

/* ===== PAGE 3: TRANSLATE DOCUMENT ===== */
function initTranslateDoc() {
  populateLangSelect('doc-src-lang', true);
  document.getElementById('doc-src-lang').value = 'eng';
  
  populateLangGrid('doc-tgt-langs', adminState.docLangs, () => {
    adminState.docLangs = getSelectedLangs('doc-tgt-langs');
    updateDocBtn();
  });
  
  setupDropzone('doc-dropzone', 'doc-input', 'doc-file-name', file => {
    adminState.docFile = file;
    document.getElementById('doc-file-name').textContent = file.name;
    document.getElementById('doc-dropzone').classList.add('has-file');
    updateDocBtn();
  });
  
  document.getElementById('doc-translate-btn')?.addEventListener('click', translateDocument);
}

window.selectDocLangs = function(type) {
  let codes = [];
  if (type === 'kb11') codes = KB_11;
  else if (type === 'all') codes = LANGUAGES.filter(l => l.code !== 'eng').map(l => l.code);
  setSelectedLangs('doc-tgt-langs', codes);
  adminState.docLangs = codes;
  updateDocBtn();
};

function updateDocBtn() {
  const btn = document.getElementById('doc-translate-btn');
  if (btn) btn.disabled = !adminState.docFile || adminState.docLangs.length === 0;
}

async function translateDocument() {
  const log = document.getElementById('doc-log');
  log.textContent = 'Starting translation...\n';
  
  const formData = new FormData();
  formData.append('file', adminState.docFile);
  formData.append('src_lang', document.getElementById('doc-src-lang').value);
  formData.append('tgt_langs', JSON.stringify(adminState.docLangs));
  formData.append('doc_type', document.getElementById('doc-type').value);
  formData.append('title', document.getElementById('doc-title').value);
  
  try {
    const resp = await fetch('/api/docs/translate', { method: 'POST', body: formData });
    const data = await resp.json();
    
    if (data.error) {
      log.textContent += `❌ Error: ${data.error}\n`;
      showToast(data.error, 'error');
    } else {
      log.textContent += `✅ Translation complete!\n`;
      log.textContent += `Processed ${data.languages?.length || 0} languages\n`;
      if (data.outputs) {
        const links = document.getElementById('doc-download-links');
        links.innerHTML = data.outputs.map(o => 
          `<a href="${o.url}" class="btn btn-sm btn-ghost" download>${o.name}</a>`
        ).join(' ');
        document.getElementById('doc-downloads').hidden = false;
      }
      showToast('Document translated!', 'success');
    }
  } catch (e) {
    log.textContent += `❌ Error: ${e.message}\n`;
    showToast(e.message, 'error');
  }
}

/* ===== PAGE 4: QA CERTIFICATE ===== */
function initQACert() {
  populateLangSelect('qa-src-lang', true);
  populateLangSelect('qa-tgt-lang', false);
  document.getElementById('qa-src-lang').value = 'eng';
  document.getElementById('qa-tgt-lang').value = 'hin';
  
  setupDropzone('qa-src-dropzone', 'qa-src-input', 'qa-src-name', file => {
    document.getElementById('qa-src-name').textContent = file.name;
  });
  setupDropzone('qa-out-dropzone', 'qa-out-input', 'qa-out-name', file => {
    document.getElementById('qa-out-name').textContent = file.name;
  });
  
  document.getElementById('qa-generate-btn')?.addEventListener('click', generateQACert);
}

async function generateQACert() {
  const log = document.getElementById('qa-log');
  log.textContent = 'Generating certificate...\n';
  
  const formData = new FormData();
  formData.append('course_id', document.getElementById('qa-course-id').value);
  formData.append('src_lang', document.getElementById('qa-src-lang').value);
  formData.append('tgt_lang', document.getElementById('qa-tgt-lang').value);
  formData.append('reviewer', document.getElementById('qa-reviewer').value);
  
  const srcInput = document.getElementById('qa-src-input');
  const outInput = document.getElementById('qa-out-input');
  if (srcInput.files[0]) formData.append('source_file', srcInput.files[0]);
  if (outInput.files[0]) formData.append('output_file', outInput.files[0]);
  
  try {
    const resp = await fetch('/api/qa/generate', { method: 'POST', body: formData });
    const data = await resp.json();
    
    if (data.error) {
      log.textContent += `❌ ${data.error}\n`;
    } else {
      log.textContent += `✅ Certificate generated!\n`;
      const dl = document.getElementById('qa-download');
      dl.href = data.download_url;
      dl.hidden = false;
      showToast('QA Certificate generated!', 'success');
    }
  } catch (e) {
    log.textContent += `❌ ${e.message}\n`;
  }
}

/* ===== PAGE 5: HUMAN REVIEW ===== */
function initHumanReview() {
  setupDropzone('review-dropzone', 'review-input', 'review-file-name', file => {
    document.getElementById('review-file-name').textContent = file.name;
  });
  
  document.getElementById('review-load-btn')?.addEventListener('click', loadReviewSegments);
  document.getElementById('review-approve-all')?.addEventListener('click', approveAllUnflagged);
  document.getElementById('review-save')?.addEventListener('click', saveReview);
  document.getElementById('review-cert')?.addEventListener('click', exportReviewCert);
}

async function loadReviewSegments() {
  const input = document.getElementById('review-input');
  if (!input.files[0]) { showToast('Select a metadata JSON file', 'error'); return; }
  
  const formData = new FormData();
  formData.append('file', input.files[0]);
  
  try {
    const resp = await fetch('/api/review/load', { method: 'POST', body: formData });
    const data = await resp.json();
    
    if (data.error) {
      document.getElementById('review-log').textContent = `❌ ${data.error}`;
    } else {
      adminState.reviewSegments = data.segments;
      adminState.reviewPath = data.path;
      renderReviewTable();
      updateReviewStats();
      document.getElementById('review-log').textContent = `✅ Loaded ${data.segments.length} segments`;
    }
  } catch (e) {
    document.getElementById('review-log').textContent = `❌ ${e.message}`;
  }
}

function renderReviewTable() {
  const tbody = document.getElementById('review-tbody');
  tbody.innerHTML = adminState.reviewSegments.map((seg, i) => `
    <tr>
      <td>${seg.id}</td>
      <td>${seg.time || '—'}</td>
      <td>${(seg.source_text || '').substring(0, 50)}...</td>
      <td>${(seg.translated_text || '').substring(0, 50)}...</td>
      <td><input type="text" class="input input-sm" data-idx="${i}" data-field="corrected" value="${seg.corrected_text || seg.translated_text || ''}" /></td>
      <td>${seg.score?.toFixed(2) || '—'}</td>
      <td>${seg.flags || '—'}</td>
      <td><select class="select select-sm" data-idx="${i}" data-field="decision">
        <option value="" ${!seg.decision ? 'selected' : ''}>—</option>
        <option value="approved" ${seg.decision === 'approved' ? 'selected' : ''}>approved</option>
        <option value="corrected" ${seg.decision === 'corrected' ? 'selected' : ''}>corrected</option>
        <option value="rejected" ${seg.decision === 'rejected' ? 'selected' : ''}>rejected</option>
      </select></td>
    </tr>
  `).join('');
  
  tbody.querySelectorAll('input, select').forEach(el => {
    el.addEventListener('change', () => {
      const idx = parseInt(el.dataset.idx);
      const field = el.dataset.field;
      if (field === 'corrected') adminState.reviewSegments[idx].corrected_text = el.value;
      if (field === 'decision') adminState.reviewSegments[idx].decision = el.value;
    });
  });
}

function updateReviewStats() {
  const segs = adminState.reviewSegments;
  const total = segs.length;
  const approved = segs.filter(s => s.decision === 'approved').length;
  const corrected = segs.filter(s => s.decision === 'corrected').length;
  const rejected = segs.filter(s => s.decision === 'rejected').length;
  document.getElementById('review-stats').textContent = 
    `Total: ${total} | Approved: ${approved} | Corrected: ${corrected} | Rejected: ${rejected} | Pending: ${total - approved - corrected - rejected}`;
}

function approveAllUnflagged() {
  adminState.reviewSegments.forEach(seg => {
    if (!seg.flags && !seg.decision) seg.decision = 'approved';
  });
  renderReviewTable();
  updateReviewStats();
}

async function saveReview() {
  const reviewer = document.getElementById('review-name').value || 'Reviewer';
  try {
    const resp = await fetch('/api/review/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: adminState.reviewPath, segments: adminState.reviewSegments, reviewer })
    });
    const data = await resp.json();
    document.getElementById('review-log').textContent = data.error ? `❌ ${data.error}` : `✅ Saved!`;
    updateReviewStats();
  } catch (e) {
    document.getElementById('review-log').textContent = `❌ ${e.message}`;
  }
}

async function exportReviewCert() {
  const reviewer = document.getElementById('review-name').value || 'Reviewer';
  try {
    const resp = await fetch('/api/review/certificate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: adminState.reviewPath, segments: adminState.reviewSegments, reviewer })
    });
    const data = await resp.json();
    if (data.download_url) {
      const dl = document.getElementById('review-download');
      dl.href = data.download_url;
      dl.hidden = false;
      document.getElementById('review-log').textContent = '✅ Certificate generated!';
    } else {
      document.getElementById('review-log').textContent = `❌ ${data.error}`;
    }
  } catch (e) {
    document.getElementById('review-log').textContent = `❌ ${e.message}`;
  }
}

/* ===== PAGE 6: CORRECTIONS ===== */
function initCorrections() {
  populateLangSelect('corr-lang', false);
  populateLangSelect('corr-rep-lang', false);
  
  // Add "All languages" option
  const repLang = document.getElementById('corr-rep-lang');
  if (repLang) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = 'All languages';
    repLang.insertBefore(opt, repLang.firstChild);
    repLang.value = '';
  }
  
  document.getElementById('corr-raise-btn')?.addEventListener('click', raiseTicket);
  document.getElementById('corr-refresh')?.addEventListener('click', refreshTickets);
  document.getElementById('corr-inprog-btn')?.addEventListener('click', () => updateTicketStatus('in_progress'));
  document.getElementById('corr-close-btn')?.addEventListener('click', closeTicket);
  document.getElementById('corr-export-btn')?.addEventListener('click', exportClosureReport);
  
  refreshTickets();
}

async function raiseTicket() {
  const log = document.getElementById('corr-raise-log');
  try {
    const resp = await fetch('/api/corrections/raise', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        course_id: document.getElementById('corr-course').value,
        lang: document.getElementById('corr-lang').value,
        feedback: document.getElementById('corr-feedback').value,
        raised_by: document.getElementById('corr-raised-by').value,
        date: document.getElementById('corr-date').value
      })
    });
    const data = await resp.json();
    log.textContent = data.error ? `❌ ${data.error}` : `✅ ${data.ticket_id} raised. Deadline: ${data.deadline}`;
    refreshTickets();
  } catch (e) { log.textContent = `❌ ${e.message}`; }
}

async function refreshTickets() {
  try {
    const resp = await fetch('/api/corrections/list');
    const data = await resp.json();
    adminState.corrTickets = data.tickets || [];
    renderTicketsTable();
  } catch (e) { console.error(e); }
}

function renderTicketsTable() {
  const tbody = document.getElementById('corr-tbody');
  if (adminState.corrTickets.length === 0) {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="7">No tickets</td></tr>';
    return;
  }
  tbody.innerHTML = adminState.corrTickets.map(t => `
    <tr>
      <td>${t.ticket_id}</td>
      <td>${t.course_id}</td>
      <td>${t.lang}</td>
      <td><span class="status-badge status-${t.status}">${t.status}</span></td>
      <td>${(t.feedback || '').substring(0, 40)}...</td>
      <td>${t.deadline?.split('T')[0] || '—'}</td>
      <td>${t.penalty_pct ? t.penalty_pct.toFixed(1) + '%' : '—'}</td>
    </tr>
  `).join('');
}

async function updateTicketStatus(status) {
  const log = document.getElementById('corr-close-log');
  const ticketId = document.getElementById('corr-ticket-id').value;
  if (!ticketId) { log.textContent = '❌ Enter ticket ID'; return; }
  
  try {
    const resp = await fetch('/api/corrections/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticket_id: ticketId, status })
    });
    const data = await resp.json();
    log.textContent = data.error ? `❌ ${data.error}` : `✅ ${ticketId} marked ${status}`;
    refreshTickets();
  } catch (e) { log.textContent = `❌ ${e.message}`; }
}

async function closeTicket() {
  const log = document.getElementById('corr-close-log');
  const ticketId = document.getElementById('corr-ticket-id').value;
  const resolution = document.getElementById('corr-resolution').value;
  const closedBy = document.getElementById('corr-closed-by').value;
  
  if (!ticketId || !resolution) { log.textContent = '❌ Enter ticket ID and resolution'; return; }
  
  try {
    const resp = await fetch('/api/corrections/close', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticket_id: ticketId, resolution, closed_by: closedBy })
    });
    const data = await resp.json();
    log.textContent = data.error ? `❌ ${data.error}` : `✅ ${ticketId} closed. Penalty: ${data.penalty_pct?.toFixed(1) || 0}%`;
    refreshTickets();
  } catch (e) { log.textContent = `❌ ${e.message}`; }
}

async function exportClosureReport() {
  try {
    const resp = await fetch('/api/corrections/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        course_id: document.getElementById('corr-rep-course').value,
        lang: document.getElementById('corr-rep-lang').value,
        agency: document.getElementById('corr-rep-agency').value
      })
    });
    const data = await resp.json();
    if (data.download_url) {
      const dl = document.getElementById('corr-download');
      dl.href = data.download_url;
      dl.hidden = false;
    }
  } catch (e) { console.error(e); }
}

/* ===== PAGE 7: MONTHLY DELIVERY ===== */
function initMonthly() {
  populateLangGrid('monthly-langs', KB_11, () => {});
  
  document.getElementById('monthly-add-btn')?.addEventListener('click', addMonthlyEntry);
  document.getElementById('monthly-report-btn')?.addEventListener('click', exportMonthlyReport);
  document.getElementById('monthly-complete-btn')?.addEventListener('click', exportCompletionReport);
  document.getElementById('ir-generate-btn')?.addEventListener('click', generateInceptionReport);
}

function addMonthlyEntry() {
  const month = parseInt(document.getElementById('monthly-month').value);
  const course = document.getElementById('monthly-course').value;
  const hours = parseFloat(document.getElementById('monthly-hours').value) || 0;
  const langs = getSelectedLangs('monthly-langs');
  
  if (!month || !course) { showToast('Month and Course ID required', 'error'); return; }
  
  adminState.monthlyEntries.push({ month, course, langs: langs.join(', '), hours });
  renderMonthlyTable();
  updateMonthlySummary();
}

function renderMonthlyTable() {
  const tbody = document.getElementById('monthly-tbody');
  tbody.innerHTML = adminState.monthlyEntries.map(e => `
    <tr><td>${e.month}</td><td>${e.course}</td><td>${e.langs}</td><td>${e.hours}</td><td>—</td></tr>
  `).join('');
}

function updateMonthlySummary() {
  const SCHEDULE = { 1: 50, 2: 55, 3: 100, 4: 125, 5: 100, 6: 125, 7: 100, 8: 125, 9: 100, 10: 125, 11: 100 };
  const byMonth = {};
  adminState.monthlyEntries.forEach(e => { byMonth[e.month] = (byMonth[e.month] || 0) + e.hours; });
  
  let summary = 'KB Tender §5.1B — SLA per Month\n' + '='.repeat(50) + '\n';
  Object.keys(byMonth).sort((a, b) => a - b).forEach(m => {
    const target = SCHEDULE[m] || 0;
    const actual = byMonth[m];
    const shortfall = target > 0 ? Math.max(0, (target - actual) / target * 100) : 0;
    let penalty = 0;
    if (shortfall > 20) penalty = 5;
    else if (shortfall > 10) penalty = 4;
    else if (shortfall > 5) penalty = 2;
    summary += `Month ${m}: ${actual.toFixed(1)}/${target}h | shortfall ${shortfall.toFixed(1)}% | penalty ${penalty}%\n`;
  });
  document.getElementById('monthly-summary').textContent = summary;
}

async function exportMonthlyReport() {
  try {
    const resp = await fetch('/api/monthly/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ entries: adminState.monthlyEntries })
    });
    const data = await resp.json();
    if (data.download_url) {
      const dl = document.getElementById('monthly-download');
      dl.href = data.download_url;
      dl.hidden = false;
    }
  } catch (e) { console.error(e); }
}

async function exportCompletionReport() {
  try {
    const resp = await fetch('/api/monthly/completion');
    const data = await resp.json();
    if (data.download_url) {
      const dl = document.getElementById('monthly-download');
      dl.href = data.download_url;
      dl.hidden = false;
    }
  } catch (e) { console.error(e); }
}

async function generateInceptionReport() {
  try {
    const resp = await fetch('/api/inception/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        agency: document.getElementById('ir-agency').value,
        address: document.getElementById('ir-address').value,
        contact: document.getElementById('ir-contact').value,
        email: document.getElementById('ir-email').value,
        t0: document.getElementById('ir-t0').value,
        courses: document.getElementById('ir-courses').value
      })
    });
    const data = await resp.json();
    if (data.download_url) {
      const dl = document.getElementById('ir-download');
      dl.href = data.download_url;
      dl.hidden = false;
      showToast('Inception Report generated!', 'success');
    }
  } catch (e) { console.error(e); }
}

/* ===== PAGE 8: GLOSSARY ===== */
function initGlossary() {
  document.getElementById('gl-add-btn')?.addEventListener('click', addGlossaryTerm);
  document.getElementById('gl-export-btn')?.addEventListener('click', exportGlossary);
  
  const importInput = document.getElementById('gl-import-input');
  importInput?.parentElement?.addEventListener('click', () => importInput.click());
  importInput?.addEventListener('change', importGlossary);
}

function addGlossaryTerm() {
  const term = document.getElementById('gl-term').value.trim();
  const domain = document.getElementById('gl-domain').value.trim();
  const transText = document.getElementById('gl-translations').value;
  
  if (!term) { showToast('Term is required', 'error'); return; }
  
  const transMap = {};
  transText.split('\n').forEach(line => {
    if (line.includes(':')) {
      const [k, v] = line.split(':').map(s => s.trim());
      if (k && v) transMap[k] = v;
    }
  });
  
  adminState.glossaryEntries.push({
    term, domain,
    langs: Object.keys(transMap).join(', '),
    trans: Object.entries(transMap).map(([k, v]) => `${k}: ${v}`).join(' | '),
    transMap
  });
  
  renderGlossaryTable();
  document.getElementById('gl-log').textContent = `✅ Added "${term}" (${adminState.glossaryEntries.length} terms)`;
  
  // Clear inputs
  document.getElementById('gl-term').value = '';
  document.getElementById('gl-translations').value = '';
}

function renderGlossaryTable() {
  const tbody = document.getElementById('gl-tbody');
  tbody.innerHTML = adminState.glossaryEntries.map(e => `
    <tr><td>${e.term}</td><td>${e.domain}</td><td>${e.langs}</td><td>${e.trans.substring(0, 60)}...</td></tr>
  `).join('');
}

async function exportGlossary() {
  if (adminState.glossaryEntries.length === 0) { showToast('No entries to export', 'error'); return; }
  
  try {
    const resp = await fetch('/api/glossary/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ entries: adminState.glossaryEntries })
    });
    const data = await resp.json();
    if (data.download_url) {
      const dl = document.getElementById('gl-download');
      dl.href = data.download_url;
      dl.hidden = false;
      document.getElementById('gl-log').textContent = `✅ Exported ${adminState.glossaryEntries.length} terms`;
    }
  } catch (e) {
    document.getElementById('gl-log').textContent = `❌ ${e.message}`;
  }
}

async function importGlossary() {
  const input = document.getElementById('gl-import-input');
  if (!input.files[0]) return;
  
  const formData = new FormData();
  formData.append('file', input.files[0]);
  
  try {
    const resp = await fetch('/api/glossary/import', { method: 'POST', body: formData });
    const data = await resp.json();
    if (data.entries) {
      adminState.glossaryEntries = [...adminState.glossaryEntries, ...data.entries];
      renderGlossaryTable();
      document.getElementById('gl-log').textContent = `✅ Imported ${data.entries.length} terms`;
    }
  } catch (e) {
    document.getElementById('gl-log').textContent = `❌ ${e.message}`;
  }
}

/* ===== PAGE 9: SETTINGS ===== */
function initSettings() {
  document.getElementById('settings-save-btn')?.addEventListener('click', saveSettings);
  document.getElementById('settings-open-btn')?.addEventListener('click', openOutputFolder);
  loadSettings();
}

async function loadSettings() {
  try {
    const resp = await fetch('/api/settings');
    const data = await resp.json();
    if (data.output_dir) document.getElementById('settings-output-dir').value = data.output_dir;
    if (data.sovereign_mode) {
      document.getElementById('sovereign-status').textContent = 
        data.sovereign_mode ? '🔒 ENABLED — Foreign LLM APIs blocked' : '⚠️ DISABLED';
    }
  } catch (e) { console.error(e); }
}

async function saveSettings() {
  const log = document.getElementById('settings-log');
  try {
    const resp = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        hf_token: document.getElementById('settings-hf-token').value,
        output_dir: document.getElementById('settings-output-dir').value
      })
    });
    const data = await resp.json();
    log.textContent = data.error ? `❌ ${data.error}` : '✅ Settings saved!';
  } catch (e) {
    log.textContent = `❌ ${e.message}`;
  }
}

async function openOutputFolder() {
  try {
    await fetch('/api/settings/open-folder', { method: 'POST' });
    document.getElementById('settings-log').textContent = '✅ Folder opened';
  } catch (e) { console.error(e); }
}
