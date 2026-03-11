import { useEffect, useMemo, useState } from "react";
import "./SystemStatus.css";
import { subscribeEvents } from "../utils/eventService";
import { getSystemHealth } from "../utils/apiService";

function friendlyStatus(evt) {
  const t = evt?.type;
  const d = evt?.data || {};
  if (t === "task_started") return `Working: ${d.task || d.action || "task"}`;
  if (t === "task_completed") return `Done: ${d.task || d.action || "task"}`;
  if (t === "task_error") return `Error: ${d.task || d.action || "task"}`;
  if (t === "document_uploaded") return `Uploading: ${d.filename || "document"}`;
  if (t === "document_ingested") return `Indexed: ${d.filename || "document"}`;
  if (t === "email.new") return `New email: ${d.subject || "message"}`;
  if (t === "suggestion.new") return `Suggestion: ${d.text || ""}`.trim();
  if (t === "alert.new") return `Alert: ${d.message || d.component || "issue"}`;
  return null;
}

export default function SystemStatus({ maxItems = 5 }) {
  const [items, setItems] = useState([]);
  const [health, setHealth] = useState(null);

  useEffect(() => {
    return subscribeEvents((evt) => {
      if (evt?.type === "health.update" && evt?.data) {
        setHealth(evt.data);
        return;
      }
      const msg = friendlyStatus(evt);
      if (!msg) return;
      setItems((prev) => {
        const next = [{ ts: Date.now(), msg, type: evt.type }, ...prev].slice(0, Math.max(1, maxItems));
        return next;
      });
    });
  }, [maxItems]);

  useEffect(() => {
    let alive = true;
    async function poll() {
      try {
        const data = await getSystemHealth();
        if (!alive) return;
        setHealth(data);
      } catch {
        // ignore
      }
    }
    poll();
    const id = setInterval(poll, 15000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const latest = useMemo(() => items[0]?.msg || "Idle", [items]);

  const healthStatus = (health?.status || "unknown").toLowerCase();
  const cpu = health?.metrics?.process?.cpu_percent;
  const rss = health?.metrics?.process?.rss_mb;

  return (
    <div className="sys-status" aria-label="System status">
      <div className="sys-status-title">Status</div>
      <div className="sys-health">
        <span className={`sys-health-badge ${healthStatus}`}>{healthStatus}</span>
        <span className="sys-health-metrics">
          {typeof cpu === "number" ? `CPU ${cpu.toFixed(0)}%` : "CPU —"} ·{" "}
          {typeof rss === "number" ? `RAM ${rss.toFixed(0)} MB` : "RAM —"}
        </span>
      </div>
      <div className="sys-status-latest">{latest}</div>
      {items.length > 1 ? (
        <div className="sys-status-list">
          {items.slice(1).map((it) => (
            <div key={it.ts} className="sys-status-item">
              {it.msg}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
