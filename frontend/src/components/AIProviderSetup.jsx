import { useMemo, useState } from "react";
import { apiUrl } from "../config/api";
import "./AIProviderSetup.css";

const providerHelp = {
  openai: {
    title: "OpenAI API key",
    steps: [
      "Open https://platform.openai.com/ and sign in.",
      "Go to API Keys and create a new secret key.",
      "Copy it once and paste it here.",
    ],
  },
  gemini: {
    title: "Google Gemini API key",
    steps: [
      "Open https://aistudio.google.com/app/apikey and sign in.",
      "Create a new API key in Google AI Studio.",
      "Copy it and paste it here.",
    ],
  },
  ollama: {
    title: "Local Ollama (no cloud key needed)",
    steps: [
      "Install Ollama from https://ollama.com/download.",
      "Run `ollama pull llama3.1` (or another model).",
      "Keep Ollama running on your machine.",
    ],
  },
};

export default function AIProviderSetup() {
  const [provider, setProvider] = useState("openai");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const help = useMemo(() => providerHelp[provider], [provider]);

  async function saveProvider() {
    setError("");
    if (provider !== "ollama" && !apiKey.trim()) {
      setError("API key is required for this provider.");
      return;
    }

    setSaving(true);
    try {
      const payload = {
        provider: provider === "local" ? "ollama" : provider,
        api_key: provider === "ollama" ? "" : apiKey.trim(),
        model: model.trim(),
      };

      const res = await fetch(apiUrl("/api/setup/ai"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || "Failed to save AI provider.");
        return;
      }
      window.dispatchEvent(new Event("jarvis:setup-updated"));
      window.location.hash = "/";
    } catch {
      setError("Could not connect to backend.");
    } finally {
      setSaving(false);
    }
  }

  function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("user_id");
    window.location.hash = "/login";
  }

  return (
    <div className="ai-setup-wrap">
      <div className="ai-setup-card">
        <h2>AI Provider Setup (Required)</h2>
        <p className="sub">Choose provider and complete this once before using Jarvis.</p>

        <label>Provider</label>
        <select value={provider} onChange={(e) => setProvider(e.target.value)}>
          <option value="openai">OpenAI</option>
          <option value="gemini">Gemini</option>
          <option value="ollama">Local (Ollama)</option>
        </select>

        {provider !== "ollama" && (
          <>
            <label>API Key</label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Paste your API key"
            />
          </>
        )}

        <label>Model (optional)</label>
        <input
          value={model}
          onChange={(e) => setModel(e.target.value)}
          placeholder={provider === "ollama" ? "e.g., llama3.1" : "Leave empty for default"}
        />

        <div className="help-box">
          <h3>{help.title}</h3>
          {help.steps.map((step, idx) => (
            <p key={idx}>{idx + 1}. {step}</p>
          ))}
        </div>

        {error && <p className="err">{error}</p>}

        <div className="row">
          <button onClick={saveProvider} disabled={saving}>
            {saving ? "Saving..." : "Save and Continue"}
          </button>
          <button className="alt" onClick={logout}>Logout</button>
        </div>
      </div>
    </div>
  );
}
