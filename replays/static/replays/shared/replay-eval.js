/**
 * match-replay.v1 evaluator — ONE implementation shared by the hub (Node), the pits page and
 * scouting-backend's viewer (browser). A robot's track is stored as knots (time ms, x mm, y mm,
 * θ centi-degrees, unwrapped) and evaluated with PCHIP (monotone cubic Hermite): passes exactly
 * through every knot, never overshoots between them, so a stationary robot stays put.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.ReplayEval = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  /** PCHIP slopes (Fritsch–Carlson). */
  function pchipSlopes(t, v) {
    const n = t.length, d = new Array(n).fill(0);
    if (n < 2) return d;
    const h = [], del = [];
    for (let i = 0; i < n - 1; i++) { h.push(t[i + 1] - t[i]); del.push((v[i + 1] - v[i]) / (t[i + 1] - t[i])); }
    if (n === 2) { d[0] = d[1] = del[0]; return d; }
    for (let i = 1; i < n - 1; i++) {
      if (del[i - 1] === 0 || del[i] === 0 || Math.sign(del[i - 1]) !== Math.sign(del[i])) d[i] = 0;
      else { const w1 = 2 * h[i] + h[i - 1], w2 = h[i] + 2 * h[i - 1]; d[i] = (w1 + w2) / (w1 / del[i - 1] + w2 / del[i]); }
    }
    const end = (h0, h1, d0, d1) => { let s = ((2 * h0 + h1) * d0 - h0 * d1) / (h0 + h1); if (Math.sign(s) !== Math.sign(d0)) s = 0; else if (Math.sign(d0) !== Math.sign(d1) && Math.abs(s) > Math.abs(3 * d0)) s = 3 * d0; return s; };
    d[0] = end(h[0], h[1], del[0], del[1]);
    d[n - 1] = end(h[n - 2], h[n - 3], del[n - 2], del[n - 3]);
    return d;
  }

  /** Prepared channel → fast repeated evaluation. */
  function prepare(t, v) { return { t, v, d: pchipSlopes(t, v) }; }

  function evalPrepared(c, x) {
    const { t, v, d } = c; const n = t.length;
    if (!n) return NaN;
    if (x <= t[0]) return v[0];
    if (x >= t[n - 1]) return v[n - 1];
    let lo = 0, hi = n - 1;
    while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (t[mid] <= x) lo = mid; else hi = mid; }
    const h = t[hi] - t[lo], s = (x - t[lo]) / h, s2 = s * s, s3 = s2 * s;
    return (2 * s3 - 3 * s2 + 1) * v[lo] + (s3 - 2 * s2 + s) * h * d[lo] + (-2 * s3 + 3 * s2) * v[hi] + (s3 - s2) * h * d[hi];
  }

  const cache = new WeakMap();
  function prepared(robot) {
    let p = cache.get(robot);
    if (!p) {
      const k = robot.track;
      p = { x: prepare(k.t_ms, k.x_mm), y: prepare(k.t_ms, k.y_mm), th: prepare(k.t_ms, k.theta_cdeg) };
      cache.set(robot, p);
    }
    return p;
  }

  /** Robot state at match time tMs → {x, y (metres), theta (radians, wrapped to ±π), confidence}. */
  function evalRobot(robot, tMs) {
    const p = prepared(robot);
    const th = (evalPrepared(p.th, tMs) / 100) * Math.PI / 180;
    let conf = 0, kind = 'none';
    for (const c of robot.confidence || []) if (tMs >= c.t0 && tMs <= c.t1) { conf = c.c; kind = c.kind || 'observed'; break; }
    const k = robot.track.t_ms;
    const inRange = k.length && tMs >= k[0] && tMs <= k[k.length - 1];
    return { x: evalPrepared(p.x, tMs) / 1000, y: evalPrepared(p.y, tMs) / 1000, theta: Math.atan2(Math.sin(th), Math.cos(th)), confidence: inRange ? conf : 0, kind: inRange ? kind : 'none' };
  }

  /** All robots at tMs. */
  function evalReplay(replay, tMs) {
    return replay.robots.map((r) => ({ team: r.team, alliance: r.alliance, id: r.id, ...evalRobot(r, tMs) }));
  }

  function unwrapAngles(rad) {
    const out = []; let off = 0;
    for (let i = 0; i < rad.length; i++) {
      if (i) { const d = rad[i] + off - out[i - 1]; if (d > Math.PI) off -= 2 * Math.PI; else if (d < -Math.PI) off += 2 * Math.PI; }
      out.push(rad[i] + off);
    }
    return out;
  }

  return { pchipSlopes, prepare, evalPrepared, evalRobot, evalReplay, unwrapAngles };
});
