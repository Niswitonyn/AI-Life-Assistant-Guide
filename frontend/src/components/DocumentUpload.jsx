import { useEffect, useRef, useState } from "react";
import "./DocumentUpload.css";
import { listDocuments, uploadDocument } from "../utils/apiService";

export default function DocumentUpload({ onClose }) {
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [docs, setDocs] = useState([]);
  const inputRef = useRef(null);

  async function refresh() {
    try {
      const data = await listDocuments();
      setDocs(data.documents || []);
    } catch {
      setDocs([]);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function onFiles(files) {
    const f = files?.[0];
    if (!f) return;
    setBusy(true);
    setMessage("");
    try {
      const res = await uploadDocument(f);
      const name = res?.document?.filename || f.name;
      setMessage(`Uploaded: ${name}`);
      await refresh();
    } catch (err) {
      setMessage(err?.message || "Upload failed.");
    } finally {
      setBusy(false);
      setDragging(false);
    }
  }

  return (
    <div className="docu-wrap" onMouseDown={(e) => e.stopPropagation()}>
      <div className="docu-card">
        <div className="docu-head">
          <div>
            <div className="docu-title">Documents</div>
            <div className="docu-sub">Upload PDF / TXT / DOCX to build your knowledge base.</div>
          </div>
          <button className="docu-close" onClick={onClose} type="button">X</button>
        </div>

        <div
          className={`drop ${dragging ? "dragging" : ""}`}
          onDragEnter={(e) => { e.preventDefault(); setDragging(true); }}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={(e) => { e.preventDefault(); setDragging(false); }}
          onDrop={(e) => {
            e.preventDefault();
            onFiles(e.dataTransfer.files);
          }}
        >
          <div className="drop-title">{busy ? "Uploading…" : "Drag & drop a file here"}</div>
          <div className="drop-actions">
            <button type="button" onClick={() => inputRef.current?.click()} disabled={busy}>
              Choose file
            </button>
            <button type="button" className="ghost" onClick={refresh} disabled={busy}>
              Refresh
            </button>
          </div>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.txt,.docx,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            onChange={(e) => onFiles(e.target.files)}
            style={{ display: "none" }}
          />
        </div>

        {message ? <div className="docu-msg">{message}</div> : null}

        <div className="docu-list">
          {docs.length ? docs.map((d) => (
            <div key={d.id} className="docu-item">
              <div className="docu-name">{d.filename}</div>
              <div className="docu-meta">
                {d.chunk_count ?? 0} chunks • {d.upload_time ? new Date(d.upload_time).toLocaleString() : "—"}
              </div>
            </div>
          )) : (
            <div className="docu-empty">No documents yet.</div>
          )}
        </div>
      </div>
    </div>
  );
}

