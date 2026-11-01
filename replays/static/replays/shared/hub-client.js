/**
 * Browser client for the hub (pits, admin, compute pages).
 *  - login with an access code (pits/workers) or the admin token; remembered on this device
 *  - short-lived JWT refreshed automatically
 *  - live bus WebSocket that RECONNECTS by itself (backoff + jitter), re-reads the snapshot on every
 *    reconnect so nothing that happened while offline is missed, and reports connection state
 */
(function () {
  'use strict';
  const LS = 'ef-hub-cred';

  class Hub {
    constructor() { this.cred = JSON.parse(localStorage.getItem(LS) || 'null'); this.token = null; this.exp = 0; this.principal = null; this.listeners = new Map(); this.liveState = 'offline'; }
    loggedIn() { return !!this.cred; }
    async login(kind, value) {
      this.cred = kind === 'admin' ? { admin: value } : { code: value };
      try { await this.tokenNow(true); } catch (e) { this.cred = null; throw e; }
      localStorage.setItem(LS, JSON.stringify(this.cred));
    }
    logout() { localStorage.removeItem(LS); this.cred = null; this.token = null; location.reload(); }

    async tokenNow(force) {
      if (!this.cred) throw new Error('not logged in');
      if (this.cred.admin) { this.token = null; this.principal = { sub: 'admin', kind: 'user', scopes: ['*'] }; return null; }
      if (!force && this.token && Date.now() < this.exp - 60000) return this.token;
      const r = await fetch('/auth/v1/auth/token', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code: this.cred.code }) });
      if (!r.ok) throw new Error(r.status === 401 ? 'That access code is not valid (or was revoked).' : `Login failed (HTTP ${r.status})`);
      const b = await r.json(); this.token = b.access_token; this.exp = Date.now() + b.expires_in * 1000; this.principal = b.principal;
      return this.token;
    }
    async authHeader() { const t = await this.tokenNow(); return this.cred.admin ? { Authorization: `Token ${this.cred.admin}` } : { Authorization: `Bearer ${t}` }; }

    async api(method, path, body) {
      for (let attempt = 0; ; attempt++) {
        try {
          const r = await fetch(path, { method, headers: { ...(await this.authHeader()), ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}) }, body: body !== undefined ? JSON.stringify(body) : undefined });
          if (r.status === 401 && attempt === 0 && !this.cred.admin) { this.token = null; continue; }
          const data = r.status === 204 ? null : await r.json().catch(() => null);
          if (!r.ok) { const e = new Error((data && data.error) || `HTTP ${r.status}`); e.status = r.status; throw e; }
          return data;
        } catch (e) { if (e.status || attempt >= 2) throw e; await new Promise((res) => setTimeout(res, 800 * (attempt + 1))); }
      }
    }
    async blob(path) { const r = await fetch(path, { headers: await this.authHeader() }); if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.blob(); }

    on(type, fn) { if (!this.listeners.has(type)) this.listeners.set(type, new Set()); this.listeners.get(type).add(fn); }
    emit(type, payload) { for (const fn of this.listeners.get(type) || []) try { fn(payload); } catch (e) { console.error(e); } for (const fn of this.listeners.get('*') || []) try { fn(type, payload); } catch (e) { console.error(e); } }

    /** Live bus with self-healing reconnect. Emits 'live-state' ('connecting'|'live'|'reconnecting'). */
    connectLive() {
      let backoff = 1000; let lastMsg = Date.now(); let ws = null;
      const open = async () => {
        this.liveState = 'connecting'; this.emit('live-state', this.liveState);
        let q = '';
        try { const t = await this.tokenNow(); q = this.cred.admin ? '' : `?access_token=${encodeURIComponent(t)}`; } catch { return retry(); }
        const proto = location.protocol === 'https:' ? 'wss' : 'ws';
        // Admin token can't go in a WS header from a browser: the admin page uses a pit/worker code for live, or polls.
        ws = new WebSocket(`${proto}://${location.host}/session/v1/live${q || (this.cred.admin ? `?access_token=${encodeURIComponent(this.cred.admin)}` : '')}`);
        ws.onopen = () => { backoff = 1000; lastMsg = Date.now(); this.liveState = 'live'; this.emit('live-state', 'live'); };
        ws.onmessage = (e) => { lastMsg = Date.now(); const m = JSON.parse(e.data); this.emit(m.type, m.payload); };
        ws.onclose = () => retry();
        ws.onerror = () => { try { ws.close(); } catch { /* */ } };
      };
      const retry = () => { this.liveState = 'reconnecting'; this.emit('live-state', 'reconnecting'); setTimeout(open, backoff + Math.random() * 400); backoff = Math.min(30000, backoff * 2); };
      setInterval(() => { if (ws && ws.readyState === 1 && Date.now() - lastMsg > 45000) ws.close(); }, 10000); // half-open socket guard
      window.addEventListener('online', () => { if (!ws || ws.readyState > 1) open(); });
      open();
    }
  }

  window.EfHub = new Hub();
  window.efFmt = {
    ago: (t) => (!t ? 'never' : `${Math.max(0, Math.round((Date.now() - t) / 1000))}s ago`),
    bytes: (n) => (n == null ? '—' : n > 1e9 ? `${(n / 1e9).toFixed(2)} GB` : n > 1e6 ? `${(n / 1e6).toFixed(1)} MB` : `${Math.round(n / 1e3)} kB`),
    esc: (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])),
  };
})();
