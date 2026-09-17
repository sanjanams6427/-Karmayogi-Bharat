/* ============================================================
 * GPU Monitor — live nvidia-smi stats + model load/evict timeline
 *
 * Polls /api/gpu/stats and /api/gpu/events (see api/web_routes.py and
 * pipeline/gpu_monitor.py) and renders:
 *   - per-GPU utilization + VRAM meters
 *   - a rolling VRAM-over-time line chart (plain canvas, no libraries)
 *   - which engines (ASR/translator/TTS) are currently resident
 *   - a scrolling timeline of load/swap/evict events
 *
 * Uses the global `API` constant already defined in app.js ("/api/").
 * Only fetches while its tab is the active one, on a 1.5s interval.
 * ============================================================ */

(function () {
  const POLL_MS = 1500;
  const HISTORY_LIMIT = 180; // ~4.5 min of samples at 1.5s/tick

  // gpuIndex -> [{ts, mem_used_mb}, ...]
  const history = {};
  let lastEventTs = 0;
  let pollTimer = null;

  function isTabActive() {
    const page = document.getElementById("page-gpu-monitor");
    return !!page && page.classList.contains("active");
  }

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888";
  }

  // Fixed line colors, one per GPU index — same categorical set the rest
  // of the app already uses, so a 4-GPU box (this system's documented
  // target) reads consistently with the rest of the UI.
  function gpuColor(idx) {
    const palette = [cssVar("--accent"), cssVar("--success"), cssVar("--warn"), cssVar("--accent-2")];
    return palette[idx % palette.length];
  }

  function fmtGB(mb) {
    return (mb / 1024).toFixed(1) + " GB";
  }

  function fmtAge(ts) {
    const s = Math.max(0, Math.round(Date.now() / 1000 - ts));
    if (s < 60) return s + "s ago";
    if (s < 3600) return Math.round(s / 60) + "m ago";
    return Math.round(s / 3600) + "h ago";
  }

  function fmtClock(ts) {
    const d = new Date(ts * 1000);
    return d.toLocaleTimeString([], { hour12: false });
  }

  /* ---------- GPU status meters ---------- */
  function renderGpuStatus(data) {
    const el = document.getElementById("gpu-status-list");
    if (!el) return;

    if (!data.available) {
      el.innerHTML = `<div class="gpu-unavailable">No GPU telemetry available` +
        (data.error ? `: ${escapeHtml(data.error)}` : "") +
        `. (Are you running on a machine without an NVIDIA GPU, or is <code>nvidia-smi</code> not on PATH?)</div>`;
      return;
    }
    if (!data.gpus.length) {
      el.innerHTML = `<div class="muted">nvidia-smi reported no GPUs.</div>`;
      return;
    }

    el.innerHTML = data.gpus.map((g) => {
      const memPct = Math.min(100, (g.mem_used_mb / g.mem_total_mb) * 100);
      const hot = memPct > 85;
      return `
        <div class="gpu-card-row">
          <div class="gpu-row-head">
            <span class="gpu-name">GPU ${g.index} — ${escapeHtml(g.name)}</span>
            <span class="gpu-temp">${g.temp_c.toFixed(0)}°C</span>
          </div>
          <div class="gpu-meter-label"><span>Utilization</span><span>${g.util_pct.toFixed(0)}%</span></div>
          <div class="gpu-meter"><div class="gpu-meter-fill util" style="width:${g.util_pct}%"></div></div>
          <div class="gpu-meter-label"><span>VRAM</span><span>${fmtGB(g.mem_used_mb)} / ${fmtGB(g.mem_total_mb)}</span></div>
          <div class="gpu-meter"><div class="gpu-meter-fill mem${hot ? " mem-hot" : ""}" style="width:${memPct}%"></div></div>
        </div>`;
    }).join("");
  }

  /* ---------- Loaded-model chips ---------- */
  function renderLoaded(loaded) {
    const el = document.getElementById("gpu-loaded-chips");
    if (!el) return;
    const keys = Object.keys(loaded || {});
    if (!keys.length) {
      el.innerHTML = `<span class="gpu-chip-empty">Nothing loaded yet</span>`;
      return;
    }
    el.innerHTML = keys.map((k) => {
      const info = loaded[k];
      return `<span class="gpu-chip"><span class="gpu-chip-dot"></span>${escapeHtml(info.label || k)}
              <span class="gpu-chip-age">${fmtAge(info.since)}</span></span>`;
    }).join("");
  }

  /* ---------- VRAM-over-time chart ---------- */
  function pushHistory(gpus) {
    const now = Date.now() / 1000;
    gpus.forEach((g) => {
      if (!history[g.index]) history[g.index] = [];
      const h = history[g.index];
      h.push({ ts: now, mem_used_mb: g.mem_used_mb, mem_total_mb: g.mem_total_mb });
      if (h.length > HISTORY_LIMIT) h.shift();
    });
  }

  function renderChart(gpus) {
    const canvas = document.getElementById("gpu-vram-canvas");
    const legendEl = document.getElementById("gpu-chart-legend");
    if (!canvas) return;

    const dpr = window.devicePixelRatio || 1;
    const cssW = canvas.clientWidth || 600;
    const cssH = 220;
    // Only touch the backing-store size when it actually changed. Assigning
    // canvas.width unconditionally resets the canvas AND forces a layout pass
    // every poll — and when a scrollbar appears/disappears it oscillates
    // clientWidth by the scrollbar width, feeding a resize→layout→resize loop
    // (the "ResizeObserver loop" console spam + visible stutter).
    if (canvas.width !== cssW * dpr || canvas.height !== cssH * dpr) {
      canvas.width = cssW * dpr;
      canvas.height = cssH * dpr;
    }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);

    const padL = 46, padR = 12, padT = 10, padB = 22;
    const plotW = cssW - padL - padR;
    const plotH = cssH - padT - padB;

    const border = cssVar("--border");
    const textDim = cssVar("--text-dim");

    if (!gpus.length) {
      ctx.fillStyle = textDim;
      ctx.font = "12px sans-serif";
      ctx.fillText("No GPU data yet.", padL, padT + 16);
      if (legendEl) legendEl.innerHTML = "";
      return;
    }

    const maxTotal = Math.max(...gpus.map((g) => g.mem_total_mb), 1024);
    // Nice round GB ceiling for the y-axis (8/12/16/24/32/48 GB steps)
    const steps = [8192, 12288, 16384, 24576, 32768, 49152, 65536];
    const yMax = steps.find((s) => s >= maxTotal) || maxTotal * 1.1;

    // gridlines
    ctx.strokeStyle = border;
    ctx.lineWidth = 1;
    ctx.fillStyle = textDim;
    ctx.font = "10px monospace";
    const ySteps = 4;
    for (let i = 0; i <= ySteps; i++) {
      const gb = (yMax / ySteps) * i;
      const y = padT + plotH - (gb / yMax) * plotH;
      ctx.beginPath();
      ctx.moveTo(padL, y);
      ctx.lineTo(padL + plotW, y);
      ctx.stroke();
      ctx.fillText((gb / 1024).toFixed(0) + "G", 4, y + 3);
    }

    // one line per GPU
    const now = Date.now() / 1000;
    const windowS = 270; // matches HISTORY_LIMIT * POLL_MS, gives headroom
    let legendHtml = "";
    gpus.forEach((g) => {
      const h = history[g.index] || [];
      const color = gpuColor(g.index);
      legendHtml += `<span><span class="gpu-legend-swatch" style="background:${color}"></span>GPU ${g.index}</span>`;
      if (h.length < 2) return;

      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.lineJoin = "round";
      ctx.beginPath();
      h.forEach((pt, i) => {
        const xFrac = 1 - (now - pt.ts) / windowS;
        const x = padL + Math.max(0, Math.min(1, xFrac)) * plotW;
        const y = padT + plotH - Math.min(pt.mem_used_mb / yMax, 1) * plotH;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.stroke();

      // current-value dot at the right edge
      const last = h[h.length - 1];
      const y = padT + plotH - Math.min(last.mem_used_mb / yMax, 1) * plotH;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(padL + plotW, y, 3, 0, Math.PI * 2);
      ctx.fill();
    });

    if (legendEl) legendEl.innerHTML = legendHtml;
  }

  /* ---------- Event timeline ---------- */
  function renderNewEvents(events) {
    const el = document.getElementById("gpu-event-log");
    if (!el || !events.length) return;
    const frag = document.createDocumentFragment();
    events.forEach((e) => {
      const row = document.createElement("div");
      row.className = "gpu-event-row";
      row.innerHTML = `
        <span class="gpu-event-time">${fmtClock(e.ts)}</span>
        <span class="gpu-event-dot ${e.kind}"></span>
        <span class="gpu-event-label">${escapeHtml(e.label)}</span>
        <span class="gpu-event-detail">${escapeHtml(e.detail || "")}</span>`;
      frag.appendChild(row);
    });
    // column-reverse layout: append = visually goes to top (newest first)
    el.appendChild(frag);
    // keep the log bounded so a long session doesn't grow the DOM forever
    while (el.children.length > 300) el.removeChild(el.firstChild);
  }

  function escapeHtml(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  /* ---------- Poll loop ---------- */
  async function pollOnce() {
    if (!isTabActive()) return;
    try {
      const statsResp = await fetch(API + "gpu/stats");
      const stats = await statsResp.json();
      if (stats.available) pushHistory(stats.gpus);
      renderGpuStatus(stats);
      renderChart(stats.available ? stats.gpus : []);
      renderLoaded(stats.loaded);
    } catch (e) {
      console.error("[gpu-monitor] stats poll failed:", e);
    }
    try {
      const evResp = await fetch(API + "gpu/events?since=" + lastEventTs);
      const evData = await evResp.json();
      if (evData.events && evData.events.length) {
        renderNewEvents(evData.events);
        lastEventTs = evData.events[evData.events.length - 1].ts;
      }
    } catch (e) {
      console.error("[gpu-monitor] events poll failed:", e);
    }
  }

  function start() {
    if (pollTimer) return;
    pollOnce();
    pollTimer = setInterval(pollOnce, POLL_MS);
  }

  document.addEventListener("DOMContentLoaded", () => {
    start();
    // Also re-poll immediately whenever the user switches into this tab,
    // so it doesn't sit on stale data from before they clicked it.
    document.querySelectorAll(".tab-btn").forEach((btn) => {
      if (btn.dataset.tab === "gpu-monitor") {
        btn.addEventListener("click", pollOnce);
      }
    });
    window.addEventListener("resize", () => { if (isTabActive()) pollOnce(); });
  });
})();
