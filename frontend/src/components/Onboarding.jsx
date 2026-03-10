import { useEffect, useMemo, useState } from "react";
import { apiUrl } from "../config/api";
import "./Onboarding.css";

/* ═══════════════════════════════════════════════════════
   STEP DEFINITIONS
   ═══════════════════════════════════════════════════════ */

const providerInfo = {
    openai: {
        label: "OpenAI",
        icon: "🟢",
        keyPlaceholder: "sk-xxxxxxxxxxxxxxx",
        modelPlaceholder: "gpt-4o (leave blank for default)",
        steps: [
            { text: "Go to", link: "https://platform.openai.com/api-keys", linkLabel: "platform.openai.com → API Keys" },
            { text: "Sign in or create an account." },
            { text: 'Click "Create new secret key", give it a name, then copy the key.' },
            { text: "Paste the key below." },
        ],
    },
    gemini: {
        label: "Google Gemini",
        icon: "🔵",
        keyPlaceholder: "AIzaSy...",
        modelPlaceholder: "gemini-2.0-flash (leave blank for default)",
        steps: [
            { text: "Go to", link: "https://aistudio.google.com/app/apikey", linkLabel: "Google AI Studio → API Keys" },
            { text: "Sign in with your Google account." },
            { text: 'Click "Create API Key", select a project, then copy the key.' },
            { text: "Paste the key below." },
        ],
    },
    ollama: {
        label: "Ollama (Local / Free)",
        icon: "🟠",
        keyPlaceholder: "",
        modelPlaceholder: "llama3.1",
        steps: [
            { text: "Download & install from", link: "https://ollama.com/download", linkLabel: "ollama.com/download" },
            { text: "Open a terminal and run:  ollama pull llama3.1" },
            { text: "Keep Ollama running in the background." },
            { text: "No API key needed — it runs 100% on your machine." },
        ],
    },
};

const gmailSteps = [
    { text: "Go to", link: "https://console.cloud.google.com/", linkLabel: "Google Cloud Console" },
    { text: 'Create a new project (or select an existing one).' },
    { text: 'Navigate to "APIs & Services → Credentials".' },
    { text: 'Click "Create Credentials → OAuth client ID".' },
    { text: 'Set application type to "Desktop app" and click Create.' },
    { text: 'Download the JSON file (it starts with "client_secret_…").' },
    { text: 'Enable the Gmail API: go to "APIs & Services → Library", search "Gmail API", and click Enable.' },
    { text: "Upload the downloaded JSON file below." },
];

/* ═══════════════════════════════════════════════════════
   COMPONENT
   ═══════════════════════════════════════════════════════ */

export default function Onboarding() {
    const TOTAL_STEPS = 4;
    const [step, setStep] = useState(0);
    const [fadeIn, setFadeIn] = useState(false);

    /* ── Step 1: AI Provider state ─────────────── */
    const [provider, setProvider] = useState("gemini");
    const [apiKey, setApiKey] = useState("");
    const [model, setModel] = useState("");
    const [, setAiSaving] = useState(false);
    const [aiError, setAiError] = useState("");
    const [aiDone, setAiDone] = useState(false);
    const [testStatus, setTestStatus] = useState(null); // null | "testing" | "ok" | "error"
    const [testMsg, setTestMsg] = useState("");

    /* ── Step 2: Google Gmail state ────────────── */
    const [credFile, setCredFile] = useState(null);
    const [gmailUploading, setGmailUploading] = useState(false);
    const [gmailMsg, setGmailMsg] = useState("");
    const [gmailDone, setGmailDone] = useState(false);
    const [gmailConnecting, setGmailConnecting] = useState(false);
    const [gmailConnected, setGmailConnected] = useState(false);
    const [gmailConnectMsg, setGmailConnectMsg] = useState("");

    const help = useMemo(() => providerInfo[provider], [provider]);

    /* ── fade-in when step changes ─────────────── */
    useEffect(() => {
        setFadeIn(false);
        const t = setTimeout(() => setFadeIn(true), 60);
        return () => clearTimeout(t);
    }, [step]);

    /* ── save AI provider ──────────────────────── */
    async function saveAI() {
        setAiError("");
        if (provider !== "ollama" && !apiKey.trim()) {
            setAiError("Please paste your API key first.");
            return;
        }
        setAiSaving(true);
        try {
            const res = await fetch(apiUrl("/api/setup/ai"), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    provider: provider === "local" ? "ollama" : provider,
                    api_key: provider === "ollama" ? "" : apiKey.trim(),
                    model: model.trim(),
                }),
            });
            if (!res.ok) {
                const d = await res.json().catch(() => ({}));
                setAiError(d.detail || "Failed to save.");
                return;
            }
            setAiDone(true);
            setStep(2);
            window.dispatchEvent(new Event("jarvis:setup-updated"));
            window.dispatchEvent(new Event("jarvis:auth-updated"));
        } catch {
            setAiError("Could not connect to backend.");
        } finally {
            setAiSaving(false);
        }
    }

    /* ── test + save AI provider ───────────────── */
    async function testConnection() {
        setAiError("");
        setTestMsg("");
        if (provider !== "ollama" && !apiKey.trim()) {
            setAiError("Please paste your API key first.");
            return;
        }
        setTestStatus("testing");
        setAiSaving(true);
        try {
            const saveRes = await fetch(apiUrl("/api/setup/ai"), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    provider: provider === "local" ? "ollama" : provider,
                    api_key: provider === "ollama" ? "" : apiKey.trim(),
                    model: model.trim(),
                }),
            });
            if (!saveRes.ok) {
                const d = await saveRes.json().catch(() => ({}));
                setTestStatus("error");
                setTestMsg(d.detail || "Failed to save settings.");
                return;
            }
            setAiDone(true);
            window.dispatchEvent(new Event("jarvis:setup-updated"));
            window.dispatchEvent(new Event("jarvis:auth-updated"));

            const healthRes = await fetch(apiUrl("/api/ai/health"));
            if (healthRes.ok) {
                setTestStatus("ok");
                setTestMsg("Connection successful! You can continue to the next step.");
            } else {
                const d = await healthRes.json().catch(() => ({}));
                setTestStatus("error");
                setTestMsg(d.detail || "AI provider returned an error. Check your API key and try again.");
            }
        } catch {
            setTestStatus("error");
            setTestMsg("Could not reach the backend. Make sure Jarvis is running.");
        } finally {
            setAiSaving(false);
        }
    }

    /* ── upload Gmail credentials ──────────────── */
    async function uploadGmail() {
        if (!credFile) {
            setGmailMsg("Please choose the credentials JSON file first.");
            return;
        }
        setGmailMsg("");
        setGmailUploading(true);
        try {
            const form = new FormData();
            form.append("file", credFile);
            const res = await fetch(apiUrl("/api/setup/gmail"), {
                method: "POST",
                body: form,
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                setGmailMsg(data.detail || "Upload failed.");
                return;
            }
            setGmailMsg("✅ Google credentials saved!");
            setGmailDone(true);
        } catch {
            setGmailMsg("Could not upload file.");
        } finally {
            setGmailUploading(false);
        }
    }

    /* ── connect Gmail via OAuth ───────────────── */
    async function connectGmail() {
        setGmailConnecting(true);
        setGmailConnectMsg("");
        const userId = localStorage.getItem("user_id") || "default";
        try {
            const res = await fetch(
                apiUrl("/api/auth/gmail/login/init") + "?user_id=" + userId
            );
            if (!res.ok) {
                const d = await res.json().catch(() => ({}));
                throw new Error(
                    d.detail ||
                    "OAuth init failed. Make sure http://localhost:8000/api/auth/gmail/callback " +
                    "is added as an Authorized Redirect URI in Google Cloud Console."
                );
            }
            const data = await res.json();

            if (window.electronAPI?.openOAuthPopup) {
                await window.electronAPI.openOAuthPopup(data.auth_url);
            } else {
                window.open(data.auth_url, "_blank", "width=560,height=760");
                await new Promise(resolve => setTimeout(resolve, 8000));
            }

            const profileRes = await fetch(
                apiUrl("/api/auth/gmail/profile") + "?user_id=" + userId
            );
            if (profileRes.ok) {
                const profile = await profileRes.json();
                if (profile.token) localStorage.setItem("token", profile.token);
                if (profile.user_id) localStorage.setItem("user_id", String(profile.user_id));
                if (window.electronAPI?.secureSet) {
                    await window.electronAPI.secureSet("gmail_profile", profile);
                }
                setGmailConnected(true);
                setGmailConnectMsg("✅ Gmail connected! You can now send and read emails.");
            } else {
                setGmailConnectMsg(
                    "⚠️ Sign-in window closed. If you completed sign-in, click Sign in again to confirm."
                );
            }
        } catch (err) {
            const msg = err.message || "Gmail connect failed.";
            if (msg.includes("Redirect URI") || msg.includes("redirect")) {
                setGmailConnectMsg(
                    "❌ Redirect URI not set. In Google Cloud Console add " +
                    "http://localhost:8000/api/auth/gmail/callback " +
                    "as Authorized Redirect URI, re-download and re-upload credentials.json."
                );
            } else {
                setGmailConnectMsg("❌ " + msg);
            }
        } finally {
            setGmailConnecting(false);
        }
    }

    /* ── finish onboarding ─────────────────────── */
    function finish() {
        window.dispatchEvent(new Event("jarvis:setup-updated"));
        window.location.hash = "/";
    }

    /* ═══════════════════════════════════════════════
       RENDER
       ═══════════════════════════════════════════════ */
    return (
        <div className="onboarding-wrap">
            <div className="onboarding-orb orb1" />
            <div className="onboarding-orb orb2" />

            {/* progress bar */}
            <div className="onboarding-progress-row">
                {[0, 1, 2, 3].map((i) => (
                    <div
                        key={i}
                        className={`onboarding-dot ${i <= step ? "active" : ""}`}
                    />
                ))}
                <span className="onboarding-step-label">Step {step + 1} of {TOTAL_STEPS}</span>
            </div>

            <div className={`onboarding-card ${fadeIn ? "" : "hidden"}`}>
                {/* ─── STEP 0 : AI Provider ──────────────────── */}
                {step === 0 && (
                    <>
                        <div className="onboarding-header">
                            <span className="onboarding-header-icon">🧠</span>
                            <div>
                                <h2 className="onboarding-title">Choose your AI Provider</h2>
                                <p className="onboarding-subtitle">Jarvis needs an AI backend to think. Pick one below.</p>
                            </div>
                        </div>

                        {/* provider selector cards */}
                        <div className="onboarding-provider-grid">
                            {Object.entries(providerInfo).map(([key, info]) => (
                                <button
                                    key={key}
                                    className={`onboarding-provider-card ${provider === key ? "active" : ""}`}
                                    onClick={() => { setProvider(key); setAiError(""); setTestStatus(null); setTestMsg(""); }}
                                >
                                    <span className="onboarding-icon-large">{info.icon}</span>
                                    <span className="onboarding-provider-label">{info.label}</span>
                                </button>
                            ))}
                        </div>

                        {/* instructions box */}
                        <div className="onboarding-help-box">
                            <p className="onboarding-help-title">How to get your key:</p>
                            {help.steps.map((s, i) => (
                                <p key={i} className="onboarding-help-step">
                                    <span className="onboarding-step-num">{i + 1}</span>
                                    {s.text}{" "}
                                    {s.link && (
                                        <a
                                            href={s.link}
                                            target="_blank"
                                            rel="noreferrer"
                                            className="onboarding-link"
                                            onClick={(e) => {
                                                e.preventDefault();
                                                // use Electron shell if available, else window.open
                                                if (window.electronAPI) {
                                                    window.electronAPI.openExternal(s.link);
                                                } else {
                                                    window.open(s.link, "_blank");
                                                }
                                            }}
                                        >
                                            {s.linkLabel}  ↗
                                        </a>
                                    )}
                                </p>
                            ))}
                        </div>

                        {provider !== "ollama" && (
                            <input
                                className="onboarding-input"
                                type="password"
                                placeholder={help.keyPlaceholder}
                                value={apiKey}
                                onChange={(e) => { setApiKey(e.target.value); setTestStatus(null); setTestMsg(""); }}
                            />
                        )}

                        <input
                            className="onboarding-input"
                            placeholder={help.modelPlaceholder}
                            value={model}
                            onChange={(e) => setModel(e.target.value)}
                        />

                        {aiError && <p className="onboarding-error">{aiError}</p>}

                        <button
                            className="onboarding-btn"
                            onClick={testConnection}
                            disabled={testStatus === "testing"}
                        >
                            {testStatus === "testing" ? "Testing…" : testStatus === "ok" ? "✅ Connected — Test Again" : "Test Connection"}
                        </button>

                        {aiDone && testStatus !== "error" && (
                            <p className="onboarding-success">
                                ✅ Provider saved! Moving to next step...
                            </p>
                        )}

                        {testMsg && (
                            <p className={testStatus === "ok" ? "onboarding-success" : "onboarding-error"}>
                                {testStatus === "ok" ? "✅ " : "❌ "}{testMsg}
                            </p>
                        )}

                        <div className="onboarding-nav">
                            <span />
                            <button
                                className="onboarding-nav-btn"
                                onClick={() => testStatus === "ok" && setStep(2)}
                                disabled={testStatus !== "ok"}
                            >
                                Next →
                            </button>
                        </div>
                    </>
                )}

                {/* ─── STEP 1 : Gmail Instructions ──────────── */}
                {step === 1 && (
                    <>
                        <div className="onboarding-header">
                            <span className="onboarding-header-icon">📧</span>
                            <div>
                                <h2 className="onboarding-title">Set Up Gmail Access</h2>
                                <p className="onboarding-subtitle">
                                    Create your own free Google credentials so Jarvis can
                                    read and send emails on your behalf. Takes about 5 minutes.
                                </p>
                            </div>
                        </div>

                        <div className="onboarding-help-box" style={{ maxHeight: 340, overflowY: "auto" }}>
                            <p className="onboarding-help-title">Step-by-step setup:</p>

                            <p className="onboarding-help-step">
                                <span className="onboarding-step-num">1</span>
                                Go to{" "}
                                <a className="onboarding-link" href="#" onClick={(e) => {
                                    e.preventDefault();
                                    window.electronAPI
                                        ? window.electronAPI.openExternal("https://console.cloud.google.com")
                                        : window.open("https://console.cloud.google.com", "_blank");
                                }}>
                                    console.cloud.google.com ↗
                                </a>
                                {" "}and sign in with your Google account.
                            </p>

                            <p className="onboarding-help-step">
                                <span className="onboarding-step-num">2</span>
                                Click the project dropdown at the top →
                                <strong style={{ color: "#e2e8f0" }}> New Project</strong> →
                                name it anything (e.g. "Jarvis") → click
                                <strong style={{ color: "#e2e8f0" }}> Create</strong>.
                            </p>

                            <p className="onboarding-help-step">
                                <span className="onboarding-step-num">3</span>
                                In the left menu go to
                                <strong style={{ color: "#e2e8f0" }}> APIs & Services → Library</strong>.
                                Search for <strong style={{ color: "#e2e8f0" }}>Gmail API</strong> → click it → click
                                <strong style={{ color: "#e2e8f0" }}> Enable</strong>.
                            </p>

                            <p className="onboarding-help-step">
                                <span className="onboarding-step-num">4</span>
                                Go to
                                <strong style={{ color: "#e2e8f0" }}> APIs & Services → OAuth Consent Screen</strong>.
                                Click <strong style={{ color: "#e2e8f0" }}>Get Started</strong>.
                                Fill in App name: <strong style={{ color: "#e2e8f0" }}>Jarvis Assistant</strong>,
                                your email, then click through all steps and hit
                                <strong style={{ color: "#e2e8f0" }}> Create</strong>.
                            </p>

                            <p className="onboarding-help-step">
                                <span className="onboarding-step-num">5</span>
                                Go to <strong style={{ color: "#e2e8f0" }}>Audience</strong> in the left menu.
                                Under Publishing status click
                                <strong style={{ color: "#e2e8f0" }}> Publish App</strong> → confirm.
                                This lets anyone sign in without being added as a test user.
                            </p>

                            <p className="onboarding-help-step">
                                <span className="onboarding-step-num">6</span>
                                Go to
                                <strong style={{ color: "#e2e8f0" }}> APIs & Services → Credentials</strong>.
                                Click <strong style={{ color: "#e2e8f0" }}>+ Create Credentials → OAuth Client ID</strong>.
                                Application type: <strong style={{ color: "#e2e8f0" }}>Desktop app</strong>.
                                Name it anything → click <strong style={{ color: "#e2e8f0" }}>Create</strong>.
                            </p>

                            <p className="onboarding-help-step">
                                <span className="onboarding-step-num">7</span>
                                Click the <strong style={{ color: "#e2e8f0" }}>edit (pencil) icon</strong> on
                                the credential you just created.
                                Under <strong style={{ color: "#e2e8f0" }}>Authorized Redirect URIs</strong>
                                click <strong style={{ color: "#e2e8f0" }}>+ Add URI</strong> and enter exactly:
                                <br />
                                <code style={{
                                    display: "inline-block",
                                    marginTop: 4,
                                    padding: "2px 8px",
                                    background: "rgba(0,229,255,0.08)",
                                    borderRadius: 6,
                                    color: "#00e5ff",
                                    fontSize: 12,
                                    userSelect: "all",
                                }}>
                                    http://localhost:8000/api/auth/gmail/callback
                                </code>
                                <br />
                                Then click <strong style={{ color: "#e2e8f0" }}>Save</strong>.
                            </p>

                            <p className="onboarding-help-step">
                                <span className="onboarding-step-num">8</span>
                                Click the <strong style={{ color: "#e2e8f0" }}>⬇️ download icon</strong> next
                                to your OAuth client to download
                                <strong style={{ color: "#e2e8f0" }}> credentials.json</strong>.
                            </p>

                            <p className="onboarding-help-step">
                                <span className="onboarding-step-num">9</span>
                                Upload the downloaded credentials.json file using the button below,
                                then click <strong style={{ color: "#e2e8f0" }}>Sign in with Google</strong>.
                            </p>

                            <div style={{
                                marginTop: 12,
                                padding: "10px 14px",
                                borderRadius: 10,
                                background: "rgba(0, 229, 255, 0.06)",
                                border: "1px solid rgba(0, 229, 255, 0.15)",
                            }}>
                                <p style={{ margin: 0, fontSize: 12, color: "#94a3b8", lineHeight: 1.6 }}>
                                    🔒 <strong style={{ color: "#cbd5e1" }}>Your privacy is protected.</strong>
                                    {" "}Your credentials and Gmail token are stored locally on your
                                    device only. Your emails are never uploaded to any server.
                                    You can disconnect Gmail at any time from Settings.
                                </p>
                            </div>
                        </div>

                        <div className="onboarding-file-row" style={{ marginTop: 12 }}>
                            <label className="onboarding-file-label">
                                <input
                                    type="file"
                                    accept=".json,application/json"
                                    style={{ display: "none" }}
                                    onChange={(e) => {
                                        setCredFile(e.target.files?.[0] || null);
                                        setGmailMsg("");
                                    }}
                                />
                                <span className="onboarding-file-inner">
                                    {credFile ? `📄 ${credFile.name}` : "Choose credentials.json"}
                                </span>
                            </label>
                            <button
                                className="onboarding-btn onboarding-file-btn"
                                onClick={uploadGmail}
                                disabled={gmailUploading}
                            >
                                {gmailUploading ? "Uploading…" : "Upload"}
                            </button>
                        </div>

                        {gmailMsg && (
                            <p className={gmailMsg.startsWith("✅") ? "onboarding-success" : "onboarding-error"}>
                                {gmailMsg}
                            </p>
                        )}

                        {gmailDone && (
                            <button
                                className="onboarding-btn"
                                onClick={connectGmail}
                                disabled={gmailConnecting}
                                style={{ marginTop: 8 }}
                            >
                                {gmailConnecting
                                    ? "Opening Google sign-in…"
                                    : gmailConnected
                                        ? "✅ Signed in — Sign in again"
                                        : "🔗 Sign in with Google"}
                            </button>
                        )}

                        {gmailConnected && (
                            <div style={{
                                padding: "12px 16px",
                                borderRadius: 12,
                                background: "rgba(52, 211, 153, 0.08)",
                                border: "1px solid rgba(52, 211, 153, 0.2)",
                                textAlign: "center",
                            }}>
                                <p style={{ margin: 0, color: "#34d399", fontWeight: 600 }}>
                                    ✅ Gmail connected successfully!
                                </p>
                                <p style={{ margin: "4px 0 0", fontSize: 12, color: "#6ee7b7" }}>
                                    Jarvis can now read and send your emails.
                                </p>
                            </div>
                        )}

                        {gmailConnectMsg && !gmailConnected && (
                            <p className={
                                gmailConnectMsg.startsWith("✅")
                                    ? "onboarding-success"
                                    : "onboarding-error"
                            }>
                                {gmailConnectMsg}
                            </p>
                        )}

                        <div className="onboarding-nav">
                            <button className="onboarding-nav-btn" onClick={() => setStep(0)}>
                                ← Back
                            </button>
                            <button className="onboarding-nav-btn" onClick={() => setStep(2)}>
                                {gmailConnected ? "Next →" : "Skip for now →"}
                            </button>
                        </div>
                    </>
                )}

                {/* ─── STEP 2 : Google Gmail Credentials ─────── */}
                {step === 2 && (
                    <>
                        <div className="onboarding-header">
                            <span className="onboarding-header-icon">📧</span>
                            <div>
                                <h2 className="onboarding-title">Connect Gmail <span className="onboarding-optional">(Optional)</span></h2>
                                <p className="onboarding-subtitle">
                                    Upload your Google Cloud OAuth credentials so Jarvis can read and send emails for you.
                                </p>
                            </div>
                        </div>

                        <div className="onboarding-help-box">
                            <p className="onboarding-help-title">How to get your credentials.json:</p>
                            {gmailSteps.map((s, i) => (
                                <p key={i} className="onboarding-help-step">
                                    <span className="onboarding-step-num">{i + 1}</span>
                                    {s.text}{" "}
                                    {s.link && (
                                        <a
                                            href={s.link}
                                            target="_blank"
                                            rel="noreferrer"
                                            className="onboarding-link"
                                            onClick={(e) => {
                                                e.preventDefault();
                                                if (window.electronAPI) {
                                                    window.electronAPI.openExternal(s.link);
                                                } else {
                                                    window.open(s.link, "_blank");
                                                }
                                            }}
                                        >
                                            {s.linkLabel}  ↗
                                        </a>
                                    )}
                                </p>
                            ))}
                        </div>

                        <div className="onboarding-file-row">
                            <label className="onboarding-file-label">
                                <input
                                    type="file"
                                    accept=".json,application/json"
                                    style={{ display: "none" }}
                                    onChange={(e) => {
                                        setCredFile(e.target.files?.[0] || null);
                                        setGmailMsg("");
                                    }}
                                />
                                <span className="onboarding-file-inner">
                                    {credFile ? `📄 ${credFile.name}` : "Choose credentials.json"}
                                </span>
                            </label>
                            <button
                                className="onboarding-btn onboarding-file-btn"
                                onClick={uploadGmail}
                                disabled={gmailUploading}
                            >
                                {gmailUploading ? "Uploading…" : "Upload"}
                            </button>
                        </div>

                        {gmailMsg && (
                            <p className={gmailMsg.startsWith("✅") ? "onboarding-success" : "onboarding-error"}>{gmailMsg}</p>
                        )}

                        {gmailDone && (
                            <button
                                className="onboarding-btn"
                                onClick={connectGmail}
                                disabled={gmailConnecting}
                                style={{ marginTop: 8 }}
                            >
                                {gmailConnecting
                                    ? "Opening Google sign-in…"
                                    : gmailConnected
                                        ? "✅ Signed in — Sign in again"
                                        : "🔗 Sign in with Google"}
                            </button>
                        )}

                        {gmailConnectMsg && (
                            <p className={
                                gmailConnectMsg.startsWith("✅")
                                    ? "onboarding-success"
                                    : "onboarding-error"
                            }>
                                {gmailConnectMsg}
                            </p>
                        )}

                        <div className="onboarding-nav">
                            <button className="onboarding-nav-btn" onClick={() => setStep(1)}>← Back</button>
                            <button
                                className="onboarding-nav-btn"
                                onClick={() => setStep(3)}
                            >
                                {gmailConnected ? "Next →" : "Skip for now →"}
                            </button>
                        </div>
                    </>
                )}

                {/* ─── STEP 3 : All Done ─────────────────────── */}
                {step === 3 && (
                    <>
                        <div className="onboarding-done-wrapper">
                            <div className="onboarding-done-emoji">🎉</div>
                            <h2 className="onboarding-title" style={{ fontSize: 26 }}>You're all set!</h2>
                            <p className="onboarding-subtitle" style={{ maxWidth: 320, margin: "0 auto" }}>
                                Jarvis is ready to assist you. You can change these settings
                                anytime from the Settings panel.
                            </p>

                            <div className="onboarding-summary-box">
                                <div className="onboarding-summary-row">
                                    <span className="onboarding-summary-label">AI Provider</span>
                                    <span className="onboarding-summary-value">
                                        {providerInfo[provider].icon} {providerInfo[provider].label}
                                    </span>
                                </div>
                                <div className="onboarding-summary-row">
                                    <span className="onboarding-summary-label">Gmail</span>
                                    <span className="onboarding-summary-value">
                                        {gmailDone ? "✅ Connected" : "⏭️ Skipped"}
                                    </span>
                                </div>
                            </div>
                        </div>

                        <button className="onboarding-btn" style={{ fontSize: 17, padding: "14px 24px" }} onClick={finish}>
                            🚀  Launch Jarvis
                        </button>

                        <div className="onboarding-nav">
                            <button className="onboarding-nav-btn" onClick={() => setStep(2)}>← Back</button>
                            <span />
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
