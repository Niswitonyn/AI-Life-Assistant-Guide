import { useEffect, useState } from "react";
import "./Notifications.css";
import { subscribeEvents } from "../utils/eventService";

function toToast(evt) {
  const t = evt?.type;
  const d = evt?.data || {};
  if (t === "email.new") {
    return { title: "New Email", body: d.subject || "You received a new email." };
  }
  if (t === "document_uploaded") {
    return { title: "Upload", body: `Uploaded ${d.filename || "document"}` };
  }
  if (t === "document_ingested") {
    return { title: "Indexed", body: `Ready: ${d.filename || "document"}` };
  }
  if (t === "task_error") {
    return { title: "Task Error", body: d.error || "Something went wrong." };
  }
  if (t === "suggestion.new") {
    return { title: "Suggestion", body: d.text || "I have a suggestion." };
  }
  if (t === "alert.new") {
    const lvl = (d.level || "").toUpperCase();
    return { title: lvl ? `System ${lvl}` : "System Alert", body: d.message || "A system issue was detected." };
  }
  return null;
}

export default function Notifications() {
  const [toasts, setToasts] = useState([]);

  useEffect(() => {
    return subscribeEvents((evt) => {
      const toast = toToast(evt);
      if (!toast) return;
      const id = `${Date.now()}_${Math.random().toString(16).slice(2)}`;
      setToasts((prev) => [{ id, ...toast }, ...prev].slice(0, 4));
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 5500);
    });
  }, []);

  if (!toasts.length) return null;

  return (
    <div className="toast-wrap" aria-live="polite" aria-relevant="additions">
      {toasts.map((t) => (
        <div key={t.id} className="toast">
          <div className="toast-title">{t.title}</div>
          <div className="toast-body">{t.body}</div>
        </div>
      ))}
    </div>
  );
}
