/**
 * Motion-blob detector + IoU tracker — the dependency-free CPU/browser fallback runner (and the one
 * the tests use). Real robot detection should use the ONNX segmentation runner; this exists so every
 * worker can contribute something, and so the pipeline is testable end-to-end without a GPU.
 * Shared by the Node worker and the browser compute page (UMD).
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.EfMotion = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  /** Running-average background subtraction on 8-bit grayscale frames. */
  function createMotionDetector({ width, height, alpha = 0.05, threshold = 28, minArea = 40, cell = 4, warmupFrames = 3 }) {
    let bg = null; let n = 0;
    const gw = Math.ceil(width / cell), gh = Math.ceil(height / cell);
    return function detect(gray) {
      n++;
      if (!bg) { bg = Float32Array.from(gray); return []; }
      const mask = new Uint8Array(gw * gh);
      for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
        const i = y * width + x; const d = Math.abs(gray[i] - bg[i]);
        if (d > threshold) mask[((y / cell) | 0) * gw + ((x / cell) | 0)]++;
        bg[i] += alpha * (gray[i] - bg[i]);
      }
      if (n <= warmupFrames) return [];
      // connected components on the coarse grid (cells with ≥ 1/4 of pixels moving)
      const on = (k) => mask[k] >= (cell * cell) / 4;
      const label = new Int32Array(gw * gh).fill(-1); const blobs = [];
      for (let k = 0; k < gw * gh; k++) {
        if (!on(k) || label[k] >= 0) continue;
        const b = { x0: 1e9, y0: 1e9, x1: -1, y1: -1, area: 0 }; const stack = [k]; label[k] = blobs.length;
        while (stack.length) {
          const c = stack.pop(); const cx = c % gw, cy = (c / gw) | 0;
          b.area++; b.x0 = Math.min(b.x0, cx); b.y0 = Math.min(b.y0, cy); b.x1 = Math.max(b.x1, cx); b.y1 = Math.max(b.y1, cy);
          for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
            const nx = cx + dx, ny = cy + dy; if (nx < 0 || ny < 0 || nx >= gw || ny >= gh) continue;
            const nk = ny * gw + nx; if (on(nk) && label[nk] < 0) { label[nk] = blobs.length; stack.push(nk); }
          }
        }
        blobs.push(b);
      }
      // A uniformly-coloured object moving over the background shows up as leading + trailing edge
      // blobs (its interior blends into the slow background model). Merge blobs separated by a gap
      // small relative to their size, so one robot = one detection.
      let merged = true;
      while (merged) {
        merged = false;
        for (let a = 0; a < blobs.length && !merged; a++) for (let c = a + 1; c < blobs.length && !merged; c++) {
          const A = blobs[a], C = blobs[c];
          const gapX = Math.max(0, Math.max(A.x0, C.x0) - Math.min(A.x1, C.x1) - 1), gapY = Math.max(0, Math.max(A.y0, C.y0) - Math.min(A.y1, C.y1) - 1);
          const size = Math.max(A.x1 - A.x0, A.y1 - A.y0, C.x1 - C.x0, C.y1 - C.y0) + 1;
          if (gapX <= size * 0.8 && gapY <= size * 0.8) {
            blobs[a] = { x0: Math.min(A.x0, C.x0), y0: Math.min(A.y0, C.y0), x1: Math.max(A.x1, C.x1), y1: Math.max(A.y1, C.y1), area: A.area + C.area };
            blobs.splice(c, 1); merged = true;
          }
        }
      }
      return blobs.filter((b) => b.area * cell * cell >= minArea).map((b) => ({
        bbox: [b.x0 * cell, b.y0 * cell, (b.x1 - b.x0 + 1) * cell, (b.y1 - b.y0 + 1) * cell],
        conf: Math.min(0.9, 0.3 + b.area / 400),
      }));
    };
  }

  function iou(a, b) {
    const x0 = Math.max(a[0], b[0]), y0 = Math.max(a[1], b[1]), x1 = Math.min(a[0] + a[2], b[0] + b[2]), y1 = Math.min(a[1] + a[3], b[1] + b[3]);
    const inter = Math.max(0, x1 - x0) * Math.max(0, y1 - y0);
    return inter / (a[2] * a[3] + b[2] * b[3] - inter || 1);
  }

  /** Greedy IoU tracker with centroid fallback; ids are local to one chunk (fusion links them). */
  function createTracker({ maxMissed = 10, minIou = 0.15 } = {}) {
    let tracks = []; let next = 1;
    return function step(dets) {
      const used = new Set();
      for (const t of tracks) {
        let best = -1, bestS = minIou;
        dets.forEach((d, i) => { if (used.has(i)) return; const s = iou(t.bbox, d.bbox); if (s > bestS) { bestS = s; best = i; } });
        if (best < 0) { // centroid fallback for fast motion
          const c = [t.bbox[0] + t.bbox[2] / 2, t.bbox[1] + t.bbox[3] / 2]; let bd = Math.max(t.bbox[2], t.bbox[3]);
          dets.forEach((d, i) => { if (used.has(i)) return; const dd = Math.hypot(d.bbox[0] + d.bbox[2] / 2 - c[0], d.bbox[1] + d.bbox[3] / 2 - c[1]); if (dd < bd) { bd = dd; best = i; } });
        }
        if (best >= 0) { used.add(best); t.bbox = dets[best].bbox; t.missed = 0; dets[best].trackId = t.id; } else t.missed++;
      }
      tracks = tracks.filter((t) => t.missed <= maxMissed);
      dets.forEach((d, i) => { if (!used.has(i)) { d.trackId = next++; tracks.push({ id: d.trackId, bbox: d.bbox, missed: 0 }); } });
      return dets;
    };
  }

  return { createMotionDetector, createTracker, iou };
});
