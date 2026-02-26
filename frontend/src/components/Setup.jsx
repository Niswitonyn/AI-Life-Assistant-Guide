import { useState } from "react";
import "./Setup.css";

export default function Setup() {

  const [apiKey, setApiKey] = useState("");
  const [provider, setProvider] = useState("openai");

  async function saveSetup() {

    try {

      const res = await fetch(
        "http://127.0.0.1:8000/api/setup/ai",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            provider,
            api_key: apiKey
          })
        }
      );

      if (res.ok) {
        alert("Setup saved ✅");
        window.location.href = "/";
      }

    } catch (err) {
      console.error(err);
    }
  }

  return (
    <div className="setup-container">

      <h2>Jarvis Setup</h2>

      <select
        value={provider}
        onChange={e => setProvider(e.target.value)}
      >
        <option value="openai">OpenAI</option>
        <option value="gemini">Gemini</option>
      </select>

      <input
        type="password"
        placeholder="API Key"
        value={apiKey}
        onChange={e => setApiKey(e.target.value)}
      />

      <button onClick={saveSetup}>
        Save & Continue
      </button>

    </div>
  );
}