import { useEffect, useState } from "react";
import { apiUrl } from "../config/api";
import "./Login.css";

const DEFAULT_EMAIL = "jarvis@local";
const DEFAULT_PASS = "jarvis-auto-local";

export default function Login() {
  const [backendReady, setBackendReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [fadeIn, setFadeIn] = useState(false);

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
      // Try login first
      let res = await fetch(apiUrl("/api/user/login"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: DEFAULT_EMAIL, password: DEFAULT_PASS }),
      });

      // If user doesn't exist yet, register then login
      if (res.status === 401 || res.status === 404) {
        const regRes = await fetch(apiUrl("/api/user/register"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: DEFAULT_EMAIL,
            password: DEFAULT_PASS,
            name: "User",
          }),
        });

        // 409 = already exists, that's fine — just means password mismatch
        if (!regRes.ok && regRes.status !== 409) {
          const regData = await regRes.json().catch(() => ({}));
          setError(regData.detail || "Could not create default account");
          setLoading(false);
          return;
        }

        // Retry login
        res = await fetch(apiUrl("/api/user/login"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: DEFAULT_EMAIL, password: DEFAULT_PASS }),
        });
      }

      const data = await res.json();
      if (data.token && data.user_id) {
        localStorage.setItem("token", data.token);
        localStorage.setItem("user_id", String(data.user_id));
        window.location.hash = "/";
        return;
      }

      setError(data.detail || "Login failed");
    } catch {
      setError("Could not connect to backend");
    } finally {
      setLoading(false);
    }
  };

  /* ── render ──────────────────────────────────────────── */
  return (
    <div className="login-wrap">
      {/* animated background orbs */}
      <div className="login-orb orb1" />
      <div className="login-orb orb2" />
      <div className="login-orb orb3" />

      <div className={`login-card ${fadeIn ? "" : "hidden"}`}>
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
      </div>
    </div>
  );
}
