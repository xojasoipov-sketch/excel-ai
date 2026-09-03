import { supabase } from './supabase';

// In production the API and the SPA share one origin (FastAPI serves the built
// frontend), so an empty base is correct. In dev, Vite runs on another port.
const RAW_BASE = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '');
export const API_BASE = RAW_BASE.replace(/\/$/, '');

async function accessToken() {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

/**
 * fetch() with the Supabase access token attached. Throws an Error carrying
 * `status` and the parsed `payload`, so callers can special-case the 402
 * quota response (`payload.detail.upgrade_required`).
 */
export async function apiFetch(path, options = {}) {
  const token = await accessToken();
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body && !(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });

  let payload = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = { detail: text };
    }
  }

  if (!response.ok) {
    const detail = payload?.detail ?? payload?.error;
    const message = typeof detail === 'string'
      ? detail
      : detail?.message || `So‘rov muvaffaqiyatsiz (${response.status})`;
    const error = new Error(message);
    error.status = response.status;
    error.payload = payload;
    error.upgradeRequired = Boolean(detail?.upgrade_required);
    throw error;
  }

  return payload;
}

/** WebSocket URL with the access token as a query param (browsers can't set WS headers). */
export async function websocketUrl(path) {
  const token = await accessToken();
  const base = API_BASE || window.location.origin;
  const url = new URL(`${base}${path}`);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  if (token) url.searchParams.set('token', token);
  return url.toString();
}
