import { useEffect, useState } from "react";
import { apiUrl } from "../config/api";
import "./SettingsPanel.css";

export default function SettingsPanel() {
  const [status, setStatus] = useState({
    gmail_ready: false,
    ai_ready: false,
    user_ready: false,
  });
  const [name, setName] = useState("");
  const [provider, setProvider] = useState("openai");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [message, setMessage] = useState("");

  function loadStatus() {
    fetch(apiUrl("/api/setup/status"))
      .then((res) => res.json())
      .then((data) => setStatus(data))
      .catch(() => {});
  }

  useEffect(() => {
    loadStatus();
  }, []);

  async function saveUser() {
    await fetch(apiUrl("/api/setup/user"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    setMessage("Profile saved.");
    loadStatus();
  }

  async function saveAiConfig() {
    const payload = {
      provider: provider === "local" ? "ollama" : provider,
      api_key: apiKey,
      model,
    };

    await fetch(apiUrl("/api/setup/ai"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    setMessage("AI settings saved.");
    loadStatus();
  }

  function closeSettings() {
    try {
      if (window.require) {
        const { ipcRenderer } = window.require("electron");
        ipcRenderer.send("open-main");
        return;
      }
    } catch {}
    window.location.hash = "/";
  }

  function connectGmail() {
    const userId = localStorage.getItem("user_id") || "default";
    const oauthUrl = `${apiUrl("/api/auth/gmail/login")}?user_id=${userId}`;

    setConnecting(true);
    setMessage("");

    let ipcRenderer = null;
    try {
      if (window.require) {
        ipcRenderer = window.require("electron").ipcRenderer;
      }
    } catch {}

    if (ipcRenderer) {
      ipcRenderer.invoke("open-oauth-popup", oauthUrl)
        .then(async () => {
          try {
            const profileRes = await fetch(`${apiUrl("/api/auth/gmail/profile")}?user_id=${userId}`);
            if (profileRes.ok) {
              const profile = await profileRes.json();
              if (profile.token) localStorage.setItem("token", profile.token);
              if (profile.user_id) localStorage.setItem("user_id", String(profile.user_id));
              await ipcRenderer.invoke("secure-set", "gmail_profile", profile);
            }
          } catch {}
          setConnecting(false);
          setMessage("Gmail connected.");
          loadStatus();
        })
        .catch(() => {
          setConnecting(false);
          setMessage("Gmail OAuth failed.");
        });
      return;
    }

    const popup = window.open(oauthUrl, "_blank");
    if (!popup) {
      setConnecting(false);
      setMessage("Popup blocked.");
      return;
    }

    const timer = setInterval(() => {
      if (!popup.closed) return;
      clearInterval(timer);
      setConnecting(false);
      setMessage("Gmail connected.");
      loadStatus();
    }, 1000);
  }

  async function disconnectGmail() {
    await fetch(apiUrl("/api/setup/disconnect-gmail"), { method: "POST" });
    setMessage("Gmail disconnected.");
    loadStatus();
  }

  async function reconnectAI() {
    await fetch(apiUrl("/api/setup/reconnect-ai"), { method: "POST" });
    setMessage("AI config reset.");
    loadStatus();
  }

  function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("user_id");
    window.location.hash = "/login";
  }

  return (
    <div className="settings-wrap">
      <div className="settings-card">
        <div className="settings-head">
          <h2>Settings</h2>
          <button className="settings-close" onClick={closeSettings}>X</button>
        </div>

        <section>
          <label>Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Your name"
          />
          <button onClick={saveUser}>Save Profile</button>
        </section>

        <section>
          <label>AI Provider</label>
          <select value={provider} onChange={(e) => setProvider(e.target.value)}>
            <option value="openai">OpenAI</option>
            <option value="gemini">Gemini</option>
            <option value="local">Local (Ollama)</option>
          </select>
          <input
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="API key (for OpenAI / Gemini)"
          />
          <input
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="Model (optional)"
          />
          <div className="row">
            <button onClick={saveAiConfig}>Save AI</button>
            <button onClick={reconnectAI}>Reset AI</button>
          </div>
        </section>

        <section>
          <div className="row">
            <button onClick={connectGmail} disabled={connecting}>
              {connecting ? "Connecting..." : "Connect Gmail"}
            </button>
            <button onClick={disconnectGmail}>Disconnect Gmail</button>
          </div>
        </section>

        <div className="status-row">
          <span className={status.user_ready ? "ok" : "bad"}>User</span>
          <span className={status.ai_ready ? "ok" : "bad"}>AI</span>
          <span className={status.gmail_ready ? "ok" : "bad"}>Gmail</span>
        </div>

        {message && <p className="msg">{message}</p>}

        <button className="logout" onClick={logout}>Logout</button>
      </div>
    </div>
  );
}
