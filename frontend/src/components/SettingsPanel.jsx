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
  const [connectingGmail, setConnectingGmail] = useState(false);
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

  async function connectGmail() {
    const userId = localStorage.getItem("user_id") || "default";

    if (!googleStatus.has_credentials) {
      setMessage(
        "Upload credentials.json first. " +
        "Download it from Google Cloud Console → APIs & Services → Credentials."
      );
      return;
    }

    setConnectingGmail(true);
    setMessage("");

    try {
      const initRes = await fetch(
        apiUrl("/api/auth/gmail/login/init") + "?user_id=" + userId
      );

      if (!initRes.ok) {
        const d = await initRes.json().catch(() => ({}));
        const detail = d.detail || "Failed to start OAuth.";
        if (detail.includes("Redirect URI") || detail.includes("redirect")) {
          setMessage(
            "Redirect URI missing. In Google Cloud Console add: " +
            "http://localhost:8000/api/auth/gmail/callback " +
            "as an Authorized Redirect URI, re-download credentials.json and re-upload here."
          );
        } else {
          setMessage("❌ " + detail);
        }
        return;
      }

      const data = await initRes.json();

      if (window.electronAPI?.openOAuthPopup) {
        await window.electronAPI.openOAuthPopup(data.auth_url);
      } else {
        const popup = window.open(
          data.auth_url,
          "_blank",
          "width=560,height=760"
        );
        if (!popup) {
          setMessage("Popup blocked. Please allow popups and try again.");
          return;
        }
        await new Promise(resolve => {
          const timer = setInterval(() => {
            if (popup.closed) {
              clearInterval(timer);
              resolve();
            }
          }, 500);
        });
      }

      // Confirm token was saved by fetching profile
      const profileRes = await fetch(
        apiUrl("/api/auth/gmail/profile") + "?user_id=" + userId
      );
      if (profileRes.ok) {
        const profile = await profileRes.json();
        if (profile.token) localStorage.setItem("token", profile.token);
        if (profile.user_id) {
          localStorage.setItem("user_id", String(profile.user_id));
        }
        if (window.electronAPI?.secureSet) {
          await window.electronAPI.secureSet("gmail_profile", profile);
        }
        setMessage("✅ Gmail connected as " + (profile.email || "unknown"));
        loadStatus();
      } else {
        setMessage(
          "⚠️ Sign-in window closed but token not confirmed. " +
          "Please try Connect Gmail again."
        );
      }
    } catch (err) {
      setMessage("❌ Gmail connect failed: " + (err.message || err));
    } finally {
      setConnectingGmail(false);
    }
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
          <label>Gmail Connection</label>

          <div style={{
            padding: "10px 14px",
            borderRadius: 10,
            background: "rgba(0,0,0,0.2)",
            fontSize: 13,
            color: "#94a3b8",
            lineHeight: 1.7,
          }}>
            <p style={{ margin: "0 0 6px", color: "#cbd5e1", fontWeight: 600 }}>
              How to connect your Gmail:
            </p>
            <p style={{ margin: "0 0 4px" }}>
              1. Click <strong style={{ color: "#e2e8f0" }}>Connect Gmail</strong> below.
            </p>
            <p style={{ margin: "0 0 4px" }}>
              2. A Google sign-in window will open — sign in with your Gmail account.
            </p>
            <p style={{ margin: "0 0 4px" }}>
              3. If Google shows <strong style={{ color: "#e2e8f0" }}>"This app isn't verified"</strong>,
              click <strong style={{ color: "#e2e8f0" }}>Advanced</strong> then
              <strong style={{ color: "#e2e8f0" }}> Go to Jarvis Assistant (unsafe)</strong>.
            </p>
            <p style={{ margin: "0 0 4px" }}>
              4. Click <strong style={{ color: "#e2e8f0" }}>Allow</strong> on all permission screens.
            </p>
            <p style={{ margin: "0 0 4px" }}>
              5. The window closes automatically when done.
            </p>
            <p style={{ margin: "10px 0 0", fontSize: 11, color: "#64748b" }}>
              🔒 Your Gmail token is stored locally on your device only.
              You can disconnect anytime.
            </p>
          </div>

          <div className="row">
            <button onClick={connectGmail} disabled={connectingGmail}>
              {connectingGmail ? "Opening Google sign-in…" : "🔗 Connect Gmail"}
            </button>
            <button onClick={disconnectGmail}>Disconnect Gmail</button>
          </div>

          <div className="status-row" style={{ justifyContent: "flex-start" }}>
            <span className={status.gmail_ready ? "ok" : "bad"}>
              {status.gmail_ready ? "Gmail connected" : "Gmail not connected"}
            </span>
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
