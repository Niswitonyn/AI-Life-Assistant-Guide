import { useEffect, useState } from "react";
import { apiUrl } from "../config/api";
import { getMachineCredentials } from "../utils/machineAuth";
import "./Login.css";

export default function Login() {
  const [backendReady, setBackendReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [fadeIn, setFadeIn] = useState(false);

  const [step, setStep] = useState("login");
  // "login" | "setup-info" | "upload-creds" | "connect-gmail"
  const [credFile, setCredFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const [uploadDone, setUploadDone] = useState(false);
  const [gmailConnecting, setGmailConnecting] = useState(false);
  const [gmailMsg, setGmailMsg] = useState("");
  const [gmailConnected, setGmailConnected] = useState(false);
  const [gmailHelpMsg, setGmailHelpMsg] = useState("");

  /* ── poll backend health ─────────────────────────────── */
  useEffect(() => {
    let cancelled = false;
    let timer = null;

    const ping = async () => {
      try {
        const res = await fetch(apiUrl("/health"), { cache: "no-store" });
        if (!cancelled && res.ok) {
          setBackendReady(true);
          return;
        }
      } catch {
        // backend may still be booting
      }
      if (!cancelled) timer = setTimeout(ping, 1000);
    };

    ping();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  /* ── trigger fade-in animation ───────────────────────── */
  useEffect(() => {
    const t = setTimeout(() => setFadeIn(true), 100);
    return () => clearTimeout(t);
  }, []);

  /* ── auto login / register ───────────────────────────── */
  const enter = async () => {
    setError("");
    setLoading(true);

    try {
      // Get unique machine-local credentials
      const { email, password } = await getMachineCredentials();

      // Try login first
      let res = await fetch(apiUrl("/api/user/login"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      // If user doesn't exist yet, register then login
      if (res.status === 401 || res.status === 404) {
        const regRes = await fetch(apiUrl("/api/user/register"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email,
            password,
            name: "User",
          }),
        });

        // 409 = already exists, that's fine — just means password mismatch
        if (!regRes.ok && regRes.status !== 409) {
          const regData = await regRes.json().catch(() => ({}));
          setError(regData.detail || "Could not create local account");
          setLoading(false);
          return;
        }

        // Retry login
        res = await fetch(apiUrl("/api/user/login"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
      }

      const data = await res.json();
      if (data.token && data.user_id) {
        localStorage.setItem("token", data.token);
        localStorage.setItem("user_id", String(data.user_id));
        window.dispatchEvent(new Event("jarvis:auth-updated"));
        setStep("setup-info");
        setLoading(false);
        return;
      }

      setError(data.detail || "Login failed");
    } catch (err) {
      setError(
        err.message || "Could not connect to backend"
      );
    } finally {
      setLoading(false);
    }
  };

  async function uploadCredentials() {
    if (!credFile) {
      setUploadMsg("Please choose your credentials.json file first.");
      return;
    }
    setUploading(true);
    setUploadMsg("");
    try {
      const form = new FormData();
      form.append("file", credFile);
      const res = await fetch(apiUrl("/api/setup/gmail"), {
        method: "POST",
        body: form,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setUploadMsg("❌ " + (data.detail || "Upload failed."));
        return;
      }
      setUploadMsg("✅ Credentials saved!");
      setUploadDone(true);
    } catch {
      setUploadMsg("❌ Could not upload file.");
    } finally {
      setUploading(false);
    }
  }

  async function connectGmail() {
    window.electronAPI?.setAlwaysOnTop?.(false);
    setGmailConnecting(true);
    setGmailMsg("Opening Google sign-in in your browser...");
    setGmailHelpMsg("");
    const userId = localStorage.getItem("user_id") || "default";
    let timeout;
    try {
      const controller = new AbortController();
      timeout = setTimeout(() => controller.abort(), 300000);
      const res = await fetch(
        apiUrl("/api/auth/gmail/login") + "?user_id=" + userId,
        { signal: controller.signal }
      );
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || "Gmail connect failed.");
      }
      const data = await res.json();
      if (data.token) localStorage.setItem("token", data.token);
      if (data.user_id) localStorage.setItem("user_id", String(data.user_id));
      if (data.email) {
        setGmailConnected(true);
        setGmailMsg("✅ Gmail connected as " + data.email);
        return;
      }
      setGmailConnected(true);
      setGmailMsg("✅ Gmail connected.");
    } catch (err) {
      const raw = String(err?.message || "Gmail connect failed.");
      const lower = raw.toLowerCase();
      setGmailMsg("❌ " + raw);
      if (lower.includes("credentials")) {
        setGmailHelpMsg("credentials.json not found — re-upload it");
      } else if (lower.includes("token") || lower.includes("authenticated")) {
        setGmailHelpMsg("Gmail token invalid — click Sign in again");
      } else if (lower.includes("scope")) {
        setGmailHelpMsg("Permission issue — disconnect and reconnect Gmail");
      } else {
        setGmailHelpMsg(raw);
      }
    } finally {
      setGmailConnecting(false);
      clearTimeout(timeout);
      window.electronAPI?.setAlwaysOnTop?.(true);
    }
  }

  function finishSetup() {
    window.electronAPI?.setAlwaysOnTop?.(true);
    window.dispatchEvent(new Event("jarvis:auth-updated"));
    window.location.hash = "/";
  }

  /* ── render ──────────────────────────────────────────── */
  return (
    <div className="login-wrap">
      {/* animated background orbs */}
      <div className="login-orb orb1" />
      <div className="login-orb orb2" />
      <div className="login-orb orb3" />

      <div className={`login-card ${fadeIn ? "" : "hidden"}`}>
        {step === "login" && (
          <>
            {/* logo / icon */}
            <div className="login-logo-wrap">
              <div className="login-logo-circle">
                <span className="login-logo-emoji">🤖</span>
              </div>
            </div>

            <h1 className="login-title">Jarvis Assistant</h1>
            <p className="login-subtitle">
              Your personal AI-powered life assistant —<br />
              ready to help you organise, automate, and thrive.
            </p>

            <button
              className="login-button"
              onClick={enter}
              disabled={!backendReady || loading}
            >
              {loading
                ? "Setting things up…"
                : !backendReady
                  ? "⏳  Connecting to backend…"
                  : "🚀  Get Started"}
            </button>

            {error && <p className="login-error">{error}</p>}

            <p className="login-footer">v0.1.9 · runs 100% locally</p>
          </>
        )}

        {step === "setup-info" && (
          <>
            <h2 className="login-title" style={{ fontSize: 20 }}>
              📧 Set Up Gmail Access
            </h2>
            <p className="login-subtitle">
              To use Gmail features, you need a free Google credentials file.
              Takes about 5 minutes — done once only.
            </p>

            <div style={{
              width: "100%",
              background: "rgba(0,0,0,0.25)",
              borderRadius: 12,
              padding: "14px 16px",
              fontSize: 13,
              color: "#94a3b8",
              lineHeight: 1.8,
              textAlign: "left",
              maxHeight: 280,
              overflowY: "auto",
            }}>
              <p style={{ margin: "0 0 6px", color: "#cbd5e1", fontWeight: 600 }}>
                How to get credentials.json from Google:
              </p>
              <p style={{ margin: "0 0 4px" }}>
                <strong style={{ color: "#00e5ff" }}>1.</strong>{" "}
                Go to{" "}
                <span
                  style={{ color: "#60a5fa", cursor: "pointer", textDecoration: "underline" }}
                  onClick={() => window.electronAPI
                    ? window.electronAPI.openExternal("https://console.cloud.google.com")
                    : window.open("https://console.cloud.google.com", "_blank")
                  }
                >
                  console.cloud.google.com ↗
                </span>
                {" "}and sign in.
              </p>
              <p style={{ margin: "0 0 4px" }}>
                <strong style={{ color: "#00e5ff" }}>2.</strong>{" "}
                Create a new project — name it{" "}
                <strong style={{ color: "#e2e8f0" }}>Jarvis</strong>.
              </p>
              <p style={{ margin: "0 0 4px" }}>
                <strong style={{ color: "#00e5ff" }}>3.</strong>{" "}
                Go to <strong style={{ color: "#e2e8f0" }}>
                APIs & Services → Library</strong>,
                search <strong style={{ color: "#e2e8f0" }}>Gmail API</strong>,
                click Enable.
              </p>
              <p style={{ margin: "0 0 4px" }}>
                <strong style={{ color: "#00e5ff" }}>4.</strong>{" "}
                Go to <strong style={{ color: "#e2e8f0" }}>
                OAuth Consent Screen</strong> → Get Started →
                fill in app name and email → click through all steps → Create.
              </p>
              <p style={{ margin: "0 0 4px" }}>
                <strong style={{ color: "#00e5ff" }}>5.</strong>{" "}
                Go to <strong style={{ color: "#e2e8f0" }}>Audience</strong> →
                click <strong style={{ color: "#e2e8f0" }}>Publish App</strong> → confirm.
              </p>
              <p style={{ margin: "0 0 4px" }}>
                <strong style={{ color: "#00e5ff" }}>6.</strong>{" "}
                Go to <strong style={{ color: "#e2e8f0" }}>
                Credentials → Create Credentials → OAuth Client ID</strong>.
                Choose <strong style={{ color: "#e2e8f0" }}>Desktop app</strong> → Create.
              </p>
              <p style={{ margin: "0 0 4px" }}>
                <strong style={{ color: "#00e5ff" }}>7.</strong>{" "}
                Click the <strong style={{ color: "#e2e8f0" }}>⬇️ download icon</strong>{" "}
                next to your new client → save the file as{" "}
                <strong style={{ color: "#e2e8f0" }}>credentials.json</strong>.
              </p>
              <p style={{ margin: "8px 0 0", fontSize: 11, color: "#475569" }}>
                🔒 Stored locally on your device only. Never uploaded to any server.
              </p>
            </div>

            <button
              className="login-button"
              onClick={() => setStep("upload-creds")}
            >
              I have my credentials.json →
            </button>
            <button
              style={{
                background: "none", border: "none",
                color: "#64748b", fontSize: 13, cursor: "pointer",
              }}
              onClick={finishSetup}
            >
              Skip — set up Gmail later in Settings
            </button>
          </>
        )}

        {step === "upload-creds" && (
          <>
            <h2 className="login-title" style={{ fontSize: 20 }}>
              📄 Upload credentials.json
            </h2>
            <p className="login-subtitle">
              Choose the credentials.json file you downloaded from Google Cloud.
            </p>

            <label style={{
              width: "100%",
              padding: "12px 16px",
              background: "rgba(0,0,0,0.25)",
              border: "1px dashed rgba(0,229,255,0.3)",
              borderRadius: 12,
              cursor: "pointer",
              textAlign: "center",
              color: credFile ? "#34d399" : "#64748b",
              fontSize: 13,
              boxSizing: "border-box",
            }}>
              <input
                type="file"
                accept=".json,application/json"
                style={{ display: "none" }}
                onChange={(e) => {
                  setCredFile(e.target.files?.[0] || null);
                  setUploadMsg("");
                  setUploadDone(false);
                }}
              />
              {credFile ? `📄 ${credFile.name}` : "Click to choose credentials.json"}
            </label>

            <button
              className="login-button"
              onClick={uploadCredentials}
              disabled={uploading || !credFile}
            >
              {uploading ? "Uploading…" : "Upload"}
            </button>

            {uploadMsg && (
              <p style={{
                fontSize: 13, margin: 0, textAlign: "center",
                color: uploadMsg.startsWith("✅") ? "#34d399" : "#f87171",
              }}>
                {uploadMsg}
              </p>
            )}

            {uploadDone && (
              <button
                className="login-button"
                onClick={() => setStep("connect-gmail")}
              >
                Continue → Sign in with Google
              </button>
            )}

            <button
              style={{
                background: "none", border: "none",
                color: "#64748b", fontSize: 13, cursor: "pointer",
              }}
              onClick={() => setStep("setup-info")}
            >
              ← Back
            </button>
          </>
        )}

        {step === "connect-gmail" && (
          <>
            <h2 className="login-title" style={{ fontSize: 20 }}>
              🔗 Sign in with Google
            </h2>
            <p className="login-subtitle">
              Click below — your browser will open Google sign-in.
              Sign in with the Gmail account you want Jarvis to use.
            </p>

            <div style={{
              width: "100%",
              background: "rgba(0,0,0,0.25)",
              borderRadius: 12,
              padding: "12px 16px",
              fontSize: 13,
              color: "#94a3b8",
              lineHeight: 1.7,
              textAlign: "left",
            }}>
              <p style={{ margin: "0 0 4px" }}>
                <strong style={{ color: "#00e5ff" }}>1.</strong>{" "}
                Click <strong style={{ color: "#e2e8f0" }}>
                Sign in with Google</strong> below.
              </p>
              <p style={{ margin: "0 0 4px" }}>
                <strong style={{ color: "#00e5ff" }}>2.</strong>{" "}
                Your browser opens — sign in with your Gmail.
              </p>
              <p style={{ margin: "0 0 4px" }}>
                <strong style={{ color: "#00e5ff" }}>3.</strong>{" "}
                If Google shows{" "}
                <strong style={{ color: "#e2e8f0" }}>"This app isn't verified"</strong>
                {" "}→ click <strong style={{ color: "#e2e8f0" }}>Advanced</strong>
                {" "}→ <strong style={{ color: "#e2e8f0" }}>
                Go to app (unsafe)</strong>.
              </p>
              <p style={{ margin: "0 0 4px" }}>
                <strong style={{ color: "#00e5ff" }}>4.</strong>{" "}
                Click <strong style={{ color: "#e2e8f0" }}>Allow</strong> on all screens.
              </p>
              <p style={{ margin: "0 0 4px" }}>
                <strong style={{ color: "#00e5ff" }}>5.</strong>{" "}
                Come back here — you will see a success message.
              </p>
            </div>

            {!gmailConnected && (
              <button
                className="login-button"
                onClick={connectGmail}
                disabled={gmailConnecting}
              >
                {gmailConnecting ? "Opening browser…" : "🔗 Sign in with Google"}
              </button>
            )}

            {gmailMsg && (
              <p style={{
                fontSize: 13, margin: 0, textAlign: "center",
                color: gmailMsg.startsWith("✅") ? "#34d399" : "#f87171",
              }}>
                {gmailMsg}
              </p>
            )}

            {gmailHelpMsg && (
              <div style={{
                width: "100%",
                background: "rgba(239, 68, 68, 0.12)",
                border: "1px solid rgba(239, 68, 68, 0.4)",
                borderRadius: 10,
                padding: "10px 12px",
                color: "#fca5a5",
                fontSize: 12,
                lineHeight: 1.5,
                textAlign: "left",
                boxSizing: "border-box",
              }}>
                {gmailHelpMsg}
              </div>
            )}

            {gmailConnected && (
              <button className="login-button" onClick={finishSetup}>
                🚀 Launch Jarvis
              </button>
            )}

            <button
              style={{
                background: "none", border: "none",
                color: "#64748b", fontSize: 13, cursor: "pointer",
              }}
              onClick={gmailConnected ? finishSetup : () => setStep("upload-creds")}
            >
              {gmailConnected ? "Skip → go to Jarvis" : "← Back"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
