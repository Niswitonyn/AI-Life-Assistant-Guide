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
    const TOTAL_STEPS = 3;
    const [step, setStep] = useState(0);
    const [fadeIn, setFadeIn] = useState(false);

    /* ── Step 1: AI Provider state ─────────────── */
    const [provider, setProvider] = useState("gemini");
    const [apiKey, setApiKey] = useState("");
    const [model, setModel] = useState("");
    const [aiSaving, setAiSaving] = useState(false);
    const [aiError, setAiError] = useState("");
    const [aiDone, setAiDone] = useState(false);

    /* ── Step 2: Google Gmail state ────────────── */
    const [credFile, setCredFile] = useState(null);
    const [gmailUploading, setGmailUploading] = useState(false);
    const [gmailMsg, setGmailMsg] = useState("");
    const [gmailDone, setGmailDone] = useState(false);

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
            window.dispatchEvent(new Event("jarvis:setup-updated"));
        } catch {
            setAiError("Could not connect to backend.");
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
                {[0, 1, 2].map((i) => (
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
                                    onClick={() => { setProvider(key); setAiError(""); }}
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
                                onChange={(e) => setApiKey(e.target.value)}
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
                            onClick={async () => { await saveAI(); }}
                            disabled={aiSaving}
                        >
                            {aiSaving ? "Saving…" : aiDone ? "✅ Saved! Click Next →" : "Save AI Provider"}
                        </button>

                        <div className="onboarding-nav">
                            <span />
                            <button
                                className="onboarding-nav-btn"
                                onClick={() => aiDone && setStep(1)}
                                disabled={!aiDone}
                            >
                                Next →
                            </button>
                        </div>
                    </>
                )}

                {/* ─── STEP 1 : Google Gmail Credentials ─────── */}
                {step === 1 && (
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

                        <div className="onboarding-nav">
                            <button className="onboarding-nav-btn" onClick={() => setStep(0)}>← Back</button>
                            <button
                                className="onboarding-nav-btn"
                                onClick={() => setStep(2)}
                            >
                                {gmailDone ? "Next →" : "Skip for now →"}
                            </button>
                        </div>
                    </>
                )}

                {/* ─── STEP 2 : All Done ─────────────────────── */}
                {step === 2 && (
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
                            <button className="onboarding-nav-btn" onClick={() => setStep(1)}>← Back</button>
                            <span />
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
