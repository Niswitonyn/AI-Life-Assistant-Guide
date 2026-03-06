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
  const [googleStatus, setGoogleStatus] = useState({
    has_credentials: false,
    message: "",
    token_users: [],
  });
  const [uploadingCreds, setUploadingCreds] = useState(false);

  function loadStatus() {
    fetch(apiUrl("/api/setup/status"))
      .then((res) => res.json())
      .then((data) => setStatus(data))
      .catch(() => { });

    fetch(apiUrl("/api/setup/gmail/status"))
      .then((res) => res.json())
      .then((data) => setGoogleStatus(data))
      .catch(() => { });
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
    window.dispatchEvent(new Event("jarvis:setup-updated"));
    setMessage("AI settings saved.");
    loadStatus();
  }

  function closeSettings() {
    if (window.electronAPI) {
      window.electronAPI.openMain();
    } else {
      window.location.hash = "/";
    }
  }

  function connectGmail() {
    const userId = localStorage.getItem("user_id") || "default";
    if (!googleStatus.has_credentials) {
      setMessage("Upload Google Cloud credentials.json first.");
      return;
    }

    setConnecting(true);
    setMessage("");

    if (window.electronAPI) {
      // Electron path: use two-step OAuth flow
      fetch(`${apiUrl("/api/auth/gmail/login/init")}?user_id=${userId}`)
        .then((res) => {
          if (!res.ok) {
            return res.json().then((data) => {
              throw new Error(data.detail || "Failed to initialize OAuth");
            });
          }
          return res.json();
        })
        .then((data) => {
          // Step 1: Get auth URL, Step 2: Open popup
          return window.electronAPI.openOAuthPopup(data.auth_url);
        })
        .then(async () => {
          // Step 3: After popup closes, fetch profile and store tokens
          try {
            const profileRes = await fetch(`${apiUrl("/api/auth/gmail/profile")}?user_id=${userId}`);
            if (profileRes.ok) {
              const profile = await profileRes.json();
              if (profile.token) localStorage.setItem("token", profile.token);
              if (profile.user_id) localStorage.setItem("user_id", String(profile.user_id));
              await window.electronAPI.secureSet("gmail_profile", profile);
            }
          } catch { }
          setConnecting(false);
          setMessage("Gmail connected.");
          loadStatus();
        })
        .catch((err) => {
          setConnecting(false);
          setMessage(`Gmail OAuth failed: ${err.message || err}`);
        });
      return;
    }

    // Web path: use direct login endpoint (fallback)
    const oauthUrl = `${apiUrl("/api/auth/gmail/login")}?user_id=${userId}`;
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

  async function uploadGoogleCredentials(file) {
    if (!file) return;
    setUploadingCreds(true);
    setMessage("");

    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(apiUrl("/api/setup/gmail"), {
        method: "POST",
        body: form,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setMessage(data.detail || "Failed to save Google credentials.");
        return;
      }
      setMessage("Google credentials saved. You can now connect Gmail.");
      loadStatus();
    } catch {
      setMessage("Could not upload Google credentials.");
    } finally {
      setUploadingCreds(false);
    }
  }

  async function reconnectAI() {
    await fetch(apiUrl("/api/setup/reconnect-ai"), { method: "POST" });
    window.dispatchEvent(new Event("jarvis:setup-updated"));
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
          <label>Google Cloud OAuth</label>
          <input
            type="file"
            accept=".json,application/json"
            onChange={(e) => uploadGoogleCredentials(e.target.files?.[0])}
            disabled={uploadingCreds}
          />
          <p className="msg">
            {googleStatus.has_credentials
              ? "credentials.json configured"
              : (googleStatus.message || "credentials.json not configured")}
          </p>
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
