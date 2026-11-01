(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.EfCamera = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';
/**
 * Pixel → field ground point, using EXACTLY the camera-field-aligner / replay-system conventions
 * (frontend/src/lib/aligner/pose.ts, pose/pose.py):
 *   world: +X right, +Y downfield, +Z up (metres). Angles in DEGREES.
 *   R_body_to_world = Rz(-yaw) · Rx(pitch) · Ry(roll);  R_cv_to_world = R_body_to_world · R_BODY_FROM_CV
 *   OpenCV radial-tangential distortion (k1, k2, p1, p2, k3).
 * Unprojection inverts the distortion iteratively, casts the ray, and intersects z = groundZ.
 * An optional viewpoint.worldToField {dx, dy, rotDeg, flipX} maps the aligner frame into the
 * season's field frame if they differ.
 */
const d2r = (d) => (d * Math.PI) / 180;
const rotX = (a) => { const c = Math.cos(d2r(a)), s = Math.sin(d2r(a)); return [[1, 0, 0], [0, c, -s], [0, s, c]]; };
const rotY = (a) => { const c = Math.cos(d2r(a)), s = Math.sin(d2r(a)); return [[c, 0, s], [0, 1, 0], [-s, 0, c]]; };
const rotZ = (a) => { const c = Math.cos(d2r(a)), s = Math.sin(d2r(a)); return [[c, -s, 0], [s, c, 0], [0, 0, 1]]; };
const mm = (A, B) => A.map((r) => [0, 1, 2].map((j) => r[0] * B[0][j] + r[1] * B[1][j] + r[2] * B[2][j]));
const mv = (A, v) => A.map((r) => r[0] * v[0] + r[1] * v[1] + r[2] * v[2]);
const T = (A) => [0, 1, 2].map((j) => A.map((r) => r[j]));
const R_BODY_FROM_CV = [[1, 0, 0], [0, 0, 1], [0, -1, 0]];

function rotationCvToWorld(p) { return mm(mm(mm(rotZ(-p.yaw), rotX(p.pitch)), rotY(p.roll)), R_BODY_FROM_CV); }

function distCoeffs(cam) { return [...(cam.dist_coeffs || cam.distCoeffs || []), 0, 0, 0, 0, 0].slice(0, 5); }

/** Forward projection (for tests / round-trips). */
function project(world, cam, pose) {
  const R = T(rotationCvToWorld(pose));
  const c = mv(R, [world[0] - pose.x, world[1] - pose.y, world[2] - pose.z]);
  const [k1, k2, p1, p2, k3] = distCoeffs(cam);
  const xn = c[0] / c[2], yn = c[1] / c[2], r2 = xn * xn + yn * yn;
  const rad = 1 + k1 * r2 + k2 * r2 * r2 + k3 * r2 * r2 * r2;
  const xd = xn * rad + 2 * p1 * xn * yn + p2 * (r2 + 2 * xn * xn);
  const yd = yn * rad + p1 * (r2 + 2 * yn * yn) + 2 * p2 * xn * yn;
  return [cam.fx * xd + cam.cx, cam.fy * yd + cam.cy, c[2]];
}

/** Iteratively invert the distortion model → normalized undistorted coords. */
function undistort(u, v, cam) {
  const [k1, k2, p1, p2, k3] = distCoeffs(cam);
  const xd = (u - cam.cx) / cam.fx, yd = (v - cam.cy) / cam.fy;
  let x = xd, y = yd;
  for (let i = 0; i < 20; i++) {
    const r2 = x * x + y * y, rad = 1 + k1 * r2 + k2 * r2 * r2 + k3 * r2 * r2 * r2;
    const dx = 2 * p1 * x * y + p2 * (r2 + 2 * x * x), dy = p1 * (r2 + 2 * y * y) + 2 * p2 * x * y;
    x = (xd - dx) / rad; y = (yd - dy) / rad;
  }
  return [x, y];
}

function applyWorldToField(pt, w) {
  if (!w) return pt;
  let { x, y } = pt;
  if (w.flipX) x = -x;
  const c = Math.cos(d2r(w.rotDeg || 0)), s = Math.sin(d2r(w.rotDeg || 0));
  return { x: c * x - s * y + (w.dx || 0), y: s * x + c * y + (w.dy || 0) };
}

/**
 * @param {number} u,v  pixel in the CALIBRATED image (full resolution, before any crop/scale)
 * @param {{intrinsics, pose, worldToField?}} vp viewpoint from registry
 * @returns {{x,y}|null} null if the ray points above the horizon / behind the camera
 */
function pixelToGround(u, v, vp, groundZ = 0) {
  const cam = vp.intrinsics, pose = vp.pose;
  if (!cam || !pose) return null;
  const [xn, yn] = undistort(u, v, cam);
  const dir = mv(rotationCvToWorld(pose), [xn, yn, 1]);
  if (dir[2] >= -1e-6) return null; // ray doesn't come down to the ground
  const t = (groundZ - pose.z) / dir[2];
  if (t <= 0) return null;
  return applyWorldToField({ x: pose.x + t * dir[0], y: pose.y + t * dir[1] }, vp.worldToField);
}

return { pixelToGround, project, undistort, rotationCvToWorld };
});
