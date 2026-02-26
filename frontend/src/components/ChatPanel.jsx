import { useState } from "react";
import "./ChatPanel.css";

export default function ChatPanel() {

  const [messages, setMessages] = useState([
    { role: "assistant", content: "Hello 👋 How can I help you?" }
  ]);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function sendMessage() {

    if (!input.trim()) return;

    const userMsg = {
      role: "user",
      content: input
    };

    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    const userId = localStorage.getItem("user_id") || "default";
    const token = localStorage.getItem("token");
    const headers = {
      "Content-Type": "application/json"
    };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    try {

      const res = await fetch(
        "http://127.0.0.1:8000/api/ai/chat",
        {
          method: "POST",
          headers,
          body: JSON.stringify({
            user_id: userId,
            messages: [
              {
                role: "user",
                content: userMsg.content
              }
            ]
          })
        }
      );

      const data = await res.json();

      const reply = data.response || "Okay";

      setMessages(prev => [
        ...prev,
        { role: "assistant", content: reply }
      ]);

    } catch (err) {
      console.error(err);
    }

    setLoading(false);
  }

  function handleKey(e) {
    if (e.key === "Enter") sendMessage();
  }

  return (
    <div className="chat-container">

      <div className="chat-header">
        JARVIS
      </div>

      <div className="chat-messages">

        {messages.map((m, i) => (
          <div
            key={i}
            className={`msg ${m.role}`}
          >
            {m.content}
          </div>
        ))}

        {loading && (
          <div className="msg assistant">
            Thinking...
          </div>
        )}

      </div>

      <div className="chat-input">

        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Ask Jarvis..."
        />

        <button onClick={sendMessage}>
          Send
        </button>

      </div>

    </div>
  );
}
