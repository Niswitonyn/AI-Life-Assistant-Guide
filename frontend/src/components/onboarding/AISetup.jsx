import { useState } from "react";

export default function AISetup({ next }) {

  const [provider, setProvider] = useState("ollama");
  const [value, setValue] = useState("");

  const handleNext = async () => {

    if (!value) {
      alert("AI setup required");
      return;
    }

    await fetch("http://127.0.0.1:8000/api/setup/ai", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        provider,
        value
      })
    });

    next();
  };

  return (
    <div>
      <h2>AI Setup (Required)</h2>

      <select value={provider} onChange={(e) => setProvider(e.target.value)}>
        <option value="ollama">Ollama</option>
        <option value="openai">OpenAI</option>
      </select>

      <input
        placeholder="API Key or URL"
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />

      <button onClick={handleNext}>
        Continue
      </button>
    </div>
  );
}