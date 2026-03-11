import { apiUrl } from "../config/api";

function getAuthHeaders({ json = true } = {}) {
  const token = localStorage.getItem("token");
  const headers = {};
  if (json) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function readJsonSafe(res) {
  const text = await res.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

export async function sendChatMessage(text) {
  const cleaned = (text || "").trim();
  if (!cleaned) throw new Error("Empty message");
  const userId = localStorage.getItem("user_id") || "default";

  const res = await fetch(apiUrl("/api/ai/chat"), {
    method: "POST",
    headers: getAuthHeaders({ json: true }),
    body: JSON.stringify({
      user_id: userId,
      messages: [{ role: "user", content: cleaned }],
    }),
  });

  const data = await readJsonSafe(res);
  if (!res.ok) throw new Error(data?.detail || "Chat request failed");
  return { response: (data.response || "").trim() };
}

export async function sendVoiceInput({ audioBlob = null, text = null } = {}) {
  const userId = localStorage.getItem("user_id") || "default";

  let res;
  if (audioBlob) {
    const formData = new FormData();
    formData.append("audio", audioBlob, "recording.webm");
    formData.append("user_id", userId);
    res = await fetch(apiUrl("/api/voice/input"), {
      method: "POST",
      headers: getAuthHeaders({ json: false }),
      body: formData,
    });
  } else {
    const cleaned = (text || "").trim();
    if (!cleaned) throw new Error("Empty transcript");
    res = await fetch(apiUrl("/api/voice/input"), {
      method: "POST",
      headers: getAuthHeaders({ json: true }),
      body: JSON.stringify({ user_id: userId, text: cleaned }),
    });
  }

  const data = await readJsonSafe(res);
  if (!res.ok) throw new Error(data?.detail?.message || data?.detail || "Voice request failed");
  return data;
}

export async function uploadDocument(file) {
  const userId = localStorage.getItem("user_id") || "default";
  const formData = new FormData();
  formData.append("file", file);
  formData.append("user_id", userId);

  const res = await fetch(apiUrl("/api/documents/upload"), {
    method: "POST",
    headers: getAuthHeaders({ json: false }),
    body: formData,
  });

  const data = await readJsonSafe(res);
  if (!res.ok) throw new Error(data?.detail?.message || data?.detail || "Upload failed");
  return data;
}

export async function listDocuments() {
  const userId = localStorage.getItem("user_id") || "default";
  const res = await fetch(apiUrl(`/api/documents/list?user_id=${encodeURIComponent(userId)}`), {
    method: "GET",
    headers: getAuthHeaders({ json: false }),
  });
  const data = await readJsonSafe(res);
  if (!res.ok) throw new Error(data?.detail || "List documents failed");
  return data;
}

export async function getMemoryHistory({ limit = 50 } = {}) {
  const userId = localStorage.getItem("user_id") || "default";
  const res = await fetch(
    apiUrl(`/memory/history?user_id=${encodeURIComponent(userId)}&limit=${encodeURIComponent(String(limit))}`),
    { method: "GET", headers: getAuthHeaders({ json: false }) }
  );
  const data = await readJsonSafe(res);
  if (!res.ok) throw new Error(data?.detail || "Memory history failed");
  return data;
}

export async function getSystemStatus() {
  const res = await fetch(apiUrl("/api/setup/status"), {
    method: "GET",
    headers: getAuthHeaders({ json: false }),
  });
  const data = await readJsonSafe(res);
  if (!res.ok) throw new Error(data?.detail || "Status request failed");
  return data;
}

export async function getSystemHealth() {
  const res = await fetch(apiUrl("/api/system/health"), {
    method: "GET",
    headers: getAuthHeaders({ json: false }),
  });
  const data = await readJsonSafe(res);
  if (!res.ok) throw new Error(data?.detail || "Health request failed");
  return data;
}

export async function getLearningPreferences() {
  const userId = localStorage.getItem("user_id") || "default";
  const res = await fetch(apiUrl(`/api/learning/preferences?user_id=${encodeURIComponent(userId)}`), {
    method: "GET",
    headers: getAuthHeaders({ json: false }),
  });
  const data = await readJsonSafe(res);
  if (!res.ok) throw new Error(data?.detail || "Failed to load preferences");
  return data;
}

export async function setBehaviorTracking(enabled) {
  const userId = localStorage.getItem("user_id") || "default";
  const res = await fetch(apiUrl("/api/learning/tracking"), {
    method: "POST",
    headers: getAuthHeaders({ json: true }),
    body: JSON.stringify({ user_id: userId, enabled: !!enabled }),
  });
  const data = await readJsonSafe(res);
  if (!res.ok) throw new Error(data?.detail || "Failed to update tracking");
  return data;
}

export async function resetLearning() {
  const userId = localStorage.getItem("user_id") || "default";
  const res = await fetch(apiUrl("/api/learning/reset"), {
    method: "POST",
    headers: getAuthHeaders({ json: true }),
    body: JSON.stringify({ user_id: userId, reset_preferences: true, reset_behavior: true }),
  });
  const data = await readJsonSafe(res);
  if (!res.ok) throw new Error(data?.detail || "Failed to reset learning");
  return data;
}

export async function getSuggestions() {
  const userId = localStorage.getItem("user_id") || "default";
  const res = await fetch(apiUrl(`/api/learning/suggestions?user_id=${encodeURIComponent(userId)}`), {
    method: "GET",
    headers: getAuthHeaders({ json: false }),
  });
  const data = await readJsonSafe(res);
  if (!res.ok) throw new Error(data?.detail || "Failed to load suggestions");
  return data;
}
