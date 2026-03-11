import { useEffect, useMemo, useRef, useState } from "react";
import "./ChatPanel.css";
import { sendChatMessage } from "../utils/apiService";
import VoiceButton from "./VoiceButton";
import SystemStatus from "./SystemStatus";
import DocumentUpload from "./DocumentUpload";
import Notifications from "./Notifications";

function newId() {
  return `${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

export default function ChatPanel({ onClose }) {
  const [messages, setMessages] = useState([
    { id: "m0", role: "assistant", content: "Hello! How can I help you?", ts: Date.now() },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [showDocs, setShowDocs] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    try {
      endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    } catch {}
  }, [messages.length, loading]);

  const rendered = useMemo(() => messages, [messages]);

  async function sendMessage() {
    const cleaned = (input || "").trim();
    if (!cleaned) return;

    const userMsg = { id: newId(), role: "user", content: cleaned, ts: Date.now() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const data = await sendChatMessage(cleaned);
      const reply = data.response || "Okay.";
      setMessages((prev) => [...prev, { id: newId(), role: "assistant", content: reply, ts: Date.now() }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { id: newId(), role: "assistant", content: err?.message || "Request failed.", ts: Date.now() },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKey(e) {
    if (e.key === "Enter" && !e.shiftKey) sendMessage();
  }

  async function copy(text) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // ignore
    }
  }

  function openSettings() {
    if (window.electronAPI) {
      window.electronAPI.openSettings();
    } else {
      window.location.hash = "/settings";
    }
  }

  function closeChat() {
    if (onClose) {
      onClose();
    } else if (window.electronAPI) {
      window.electronAPI.closeChat();
    } else {
      window.close();
    }
  }

  return (
    <div className="chat-wrap">
      <Notifications />
      <div className="chat-container">
        <div className="chat-header">
          <span>JARVIS</span>
          <div className="chat-header-actions">
            <button onClick={() => setShowDocs(true)} className="chat-h-btn">Documents</button>
            <button onClick={openSettings} className="chat-h-btn">Settings</button>
            <button onClick={closeChat} className="chat-h-btn danger">X</button>
          </div>
        </div>

        <SystemStatus />

        <div className="chat-messages">
          {rendered.map((m) => (
            <div key={m.id} className={`msg ${m.role}`}>
              <div className="msg-content">{m.content}</div>
              <div className="msg-meta">
                <span className="msg-time">{new Date(m.ts || Date.now()).toLocaleTimeString()}</span>
                <button className="msg-copy" onClick={() => copy(m.content)} type="button">
                  Copy
                </button>
              </div>
            </div>
          ))}

          {loading ? (
            <div className="msg assistant">
              <div className="typing" aria-label="Assistant typing">
                <span className="dot" />
                <span className="dot" />
                <span className="dot" />
              </div>
            </div>
          ) : null}

          <div ref={endRef} />
        </div>

        <div className="chat-input">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Ask Jarvis..."
            disabled={loading}
          />

          <VoiceButton
            disabled={loading}
            onTranscript={(t) => setMessages((prev) => [...prev, { id: newId(), role: "user", content: t, ts: Date.now() }])}
            onResponse={(reply) => setMessages((prev) => [...prev, { id: newId(), role: "assistant", content: reply, ts: Date.now() }])}
          />

          <button onClick={sendMessage} disabled={loading}>
            Send
          </button>
        </div>
      </div>

      {showDocs ? (
        <div className="modal-backdrop" onMouseDown={() => setShowDocs(false)}>
          <div className="modal" onMouseDown={(e) => e.stopPropagation()}>
            <DocumentUpload onClose={() => setShowDocs(false)} />
          </div>
        </div>
      ) : null}
    </div>
  );
}

