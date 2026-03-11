import { apiUrl } from "../config/api";

let ws = null;
let stopped = false;
let reconnectTimer = null;
let reconnectDelayMs = 400;
const listeners = new Set();

function toWsUrl(httpUrl) {
  if (httpUrl.startsWith("https://")) return httpUrl.replace(/^https:\/\//, "wss://");
  if (httpUrl.startsWith("http://")) return httpUrl.replace(/^http:\/\//, "ws://");
  return httpUrl;
}

function notify(evt) {
  for (const fn of listeners) {
    try {
      fn(evt);
    } catch {
      // ignore
    }
  }
}

function clearReconnect() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
}

function scheduleReconnect() {
  if (stopped) return;
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, reconnectDelayMs);
  reconnectDelayMs = Math.min(8000, Math.round(reconnectDelayMs * 1.6));
}

function connect() {
  if (stopped) return;
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;

  clearReconnect();
  const url = toWsUrl(apiUrl("/api/events/ws"));
  try {
    ws = new WebSocket(url);
  } catch {
    scheduleReconnect();
    return;
  }

  ws.onopen = () => {
    reconnectDelayMs = 400;
    notify({ type: "events_connected", data: {} });
  };

  ws.onmessage = (msg) => {
    const raw = msg?.data;
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw);
      if (parsed && parsed.type) {
        notify(parsed);
      }
    } catch {
      // ignore
    }
  };

  ws.onerror = () => {
    // Let close handler reconnect.
  };

  ws.onclose = () => {
    notify({ type: "events_disconnected", data: {} });
    scheduleReconnect();
  };
}

export function startEvents() {
  stopped = false;
  if (listeners.size > 0) connect();
}

export function stopEvents() {
  stopped = true;
  clearReconnect();
  try {
    ws?.close();
  } catch {
    // ignore
  }
  ws = null;
}

export function subscribeEvents(fn) {
  listeners.add(fn);
  connect();
  return () => {
    listeners.delete(fn);
    if (listeners.size === 0) {
      // Keep connection for orb UX, but close after short idle window.
      setTimeout(() => {
        if (listeners.size === 0) stopEvents();
      }, 30000);
    }
  };
}

