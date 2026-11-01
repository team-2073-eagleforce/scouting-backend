/* Replay viewer: top-down field replay, YouTube-synced overlay, events, caveats. Uses the hub's shared
   evaluator (replays/static/replays/shared/replay-eval.js, vendored from replay-web-service). */
(function () {
  'use strict';
  const cfg = window.EF_REPLAY; const $ = (id) => document.getElementById(id);
  let replay = null, digest = null, t = 0, playing = false, mode = 'field', yt = null, ytOffset = null;

  fetch(cfg.dataUrl, { credentials: 'same-origin' }).then((r) => r.json()).then((d) => {
    replay = d.replay; digest = d.digest; ytOffset = d.youtube_offset_s; t = replay.timebase.t0_ms;
    $('caveats').innerHTML = (digest.caveats.length ? digest.caveats : ['No known data gaps.']).map((c) => `<li>${esc(c)}</li>`).join('');
    $('robots').innerHTML = replay.robots.map((r) => {
      const obs = Math.round((r.observed_ms || 0) / 1000), dur = Math.round((replay.timebase.t1_ms - replay.timebase.t0_ms) / 1000);
      return `<div><b style="color:${color(r)}">${r.team ?? 'unknown'}</b> ${r.alliance || ''} · observed ${obs}/${dur}s${r.stitched_fragments ? ` · ${r.stitched_fragments} re-acquisition(s)` : ''}</div>`;
    }).join('');
    $('events').innerHTML = (digest.events || []).map((e) => `<div>${(e.t / 1000).toFixed(1)}s ${esc(e.type)} ${e.value != null ? '= ' + esc(e.value) : ''}</div>`).join('') || '<span class="text-muted">none</span>';
    if (d.youtube_key) $('ytKey').value = d.youtube_key;
    draw();
  });

  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const color = (r) => (r.alliance === 'red' ? '#ff6b6b' : r.alliance === 'blue' ? '#4dabf7' : '#bbb');

  function drawField(canvas, tm, { labels = true } = {}) {
    const g = canvas.getContext('2d'); const W = canvas.width, H = canvas.height; g.clearRect(0, 0, W, H);
    const L = replay.match.field.length || 16.54, FW = replay.match.field.width || 8.07, sx = W / L, sy = H / FW;
    g.strokeStyle = '#ffffff66'; g.lineWidth = 2; g.strokeRect(1, 1, W - 2, H - 2); g.beginPath(); g.moveTo(W / 2, 0); g.lineTo(W / 2, H); g.stroke();
    for (const r of window.ReplayEval.evalReplay(replay, tm)) {
      if (r.kind === 'none') continue;
      const x = r.x * sx, y = H - r.y * sy;
      g.save(); g.translate(x, y); g.rotate(-r.theta); g.globalAlpha = r.kind === 'observed' ? 1 : 0.35;
      g.fillStyle = color(r); g.fillRect(-0.43 * sx, -0.43 * sy, 0.86 * sx, 0.86 * sy);
      g.fillStyle = '#fff'; g.fillRect(0.2 * sx, -0.08 * sy, 0.25 * sx, 0.16 * sy); g.restore();
      if (labels) { g.fillStyle = '#fff'; g.font = `${Math.max(12, H / 30)}px system-ui`; g.fillText(`${r.team ?? '?'}`, x - 18, y - 0.55 * sy); }
    }
  }

  function draw() {
    if (!replay) return;
    const span = replay.timebase.t1_ms - replay.timebase.t0_ms;
    if (mode === 'field') drawField($('field'), t);
    if (mode === 'overlay') drawField($('mini'), t, { labels: true });
    if (mode === 'video') $('mini').getContext('2d').clearRect(0, 0, 660, 322);
    $('scrub').value = String(Math.round(1000 * (t - replay.timebase.t0_ms) / Math.max(1, span)));
    $('tlabel').textContent = `${((t - replay.timebase.t0_ms) / 1000).toFixed(1)}s`;
  }

  // Field-only playback clock; in video modes the YouTube player is the clock.
  let last = 0;
  function tick(now) {
    if (mode !== 'field' && yt && yt.getCurrentTime && ytOffset != null) {
      t = replay.timebase.t0_ms + (yt.getCurrentTime() - ytOffset) * 1000;
      draw();
    } else if (playing && replay) {
      t += (now - last) * Number($('speed').value);
      if (t > replay.timebase.t1_ms) t = replay.timebase.t0_ms;
      draw();
    }
    last = now; requestAnimationFrame(tick);
  }
  requestAnimationFrame((n) => { last = n; tick(n); });

  $('play').onclick = () => { playing = !playing; $('play').textContent = playing ? '❚❚' : '▶'; if (yt && mode !== 'field') { playing ? yt.playVideo() : yt.pauseVideo(); } };
  $('scrub').oninput = (e) => {
    if (!replay) return;
    t = replay.timebase.t0_ms + (e.target.value / 1000) * (replay.timebase.t1_ms - replay.timebase.t0_ms);
    if (yt && mode !== 'field' && ytOffset != null) yt.seekTo(ytOffset + (t - replay.timebase.t0_ms) / 1000, true);
    draw();
  };

  document.querySelectorAll('[data-mode]').forEach((b) => b.addEventListener('click', () => {
    mode = b.dataset.mode;
    document.querySelectorAll('[data-mode]').forEach((x) => x.classList.toggle('active', x === b));
    $('field').classList.toggle('d-none', mode !== 'field');
    $('yt-wrap').classList.toggle('d-none', mode === 'field');
    $('videoSetup').classList.toggle('d-none', mode === 'field');
    $('mini').classList.toggle('d-none', mode !== 'overlay');
    if (mode !== 'field' && !yt && $('ytKey').value) loadVideo();
    draw();
  }));

  function videoId(v) { const m = String(v).match(/(?:v=|youtu\.be\/|embed\/)([A-Za-z0-9_-]{11})/); return m ? m[1] : v.trim(); }
  function loadVideo() {
    const id = videoId($('ytKey').value);
    if (!/^[A-Za-z0-9_-]{11}$/.test(id)) { alert('Paste a YouTube link or 11-character id'); return; }
    const make = () => { if (yt) yt.loadVideoById(id); else yt = new window.YT.Player('yt', { videoId: id, playerVars: { playsinline: 1, rel: 0 } }); save({ youtube_key: id }); };
    if (window.YT && window.YT.Player) return make();
    window.onYouTubeIframeAPIReady = make;
    const s = document.createElement('script'); s.src = 'https://www.youtube.com/iframe_api'; document.head.appendChild(s);
  }
  $('ytLoad').onclick = loadVideo;
  $('ytSync').onclick = () => {
    if (!yt || !yt.getCurrentTime) return;
    ytOffset = yt.getCurrentTime();
    $('ytOffset').textContent = `match starts at ${ytOffset.toFixed(2)}s`;
    save({ youtube_key: videoId($('ytKey').value), youtube_offset_s: ytOffset });
  };
  function save(patch) {
    fetch(cfg.videoUrl, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': cfg.csrf, 'X-Requested-With': 'XMLHttpRequest' },
      body: JSON.stringify({ youtube_key: videoId($('ytKey').value), youtube_offset_s: ytOffset, ...patch }) });
  }
})();
