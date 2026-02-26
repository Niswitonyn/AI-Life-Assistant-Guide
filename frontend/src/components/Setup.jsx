import { useState } from "react";
import "./Setup.css";

export default function Setup() {

  const [apiKey, setApiKey] = useState("");
  const [provider, setProvider] = useState("openai");
  const [gmailMessage, setGmailMessage] = useState("");

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

  function loginGmail() {
    const userId = localStorage.getItem("user_id") || "default";
    const popup = window.open(
      `http://127.0.0.1:8000/api/auth/gmail/login?user_id=${userId}`,
      "_blank"
    );

    if (!popup) {
      setGmailMessage("Popup blocked. Allow popups and try again.");
      return;
    }

    const timer = setInterval(() => {
      if (popup.closed) {
        clearInterval(timer);
        fetch(`http://127.0.0.1:8000/api/auth/gmail/profile?user_id=${userId}`)
          .then((res) => res.ok ? res.json() : null)
          .then((profile) => {
            if (profile?.token) {
              localStorage.setItem("token", profile.token);
            }
            if (profile?.user_id) {
              localStorage.setItem("user_id", String(profile.user_id));
            }
            setGmailMessage("Gmail OAuth completed.");
          })
          .catch(() => setGmailMessage("Gmail OAuth completed."));
      }
    }, 1000);
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

      <button onClick={loginGmail}>
        Login with Gmail
      </button>

      {gmailMessage && <p>{gmailMessage}</p>}

    </div>
  );
}
