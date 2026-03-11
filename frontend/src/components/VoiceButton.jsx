import { useEffect, useRef, useState } from "react";
import "./VoiceButton.css";
import { sendVoiceInput } from "../utils/apiService";

export default function VoiceButton({ onTranscript, onResponse, disabled }) {
  const [state, setState] = useState("idle"); // idle | listening | processing
  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);

  useEffect(() => {
    return () => {
      try {
        if (recorderRef.current && recorderRef.current.state === "recording") {
          recorderRef.current.stop();
        }
      } catch {}
      try {
        streamRef.current?.getTracks()?.forEach((t) => t.stop());
      } catch {}
    };
  }, []);

  async function start() {
    if (disabled) return;
    if (state !== "idle") return;

    setState("listening");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000,
        },
      });

      streamRef.current = stream;
      chunksRef.current = [];

      const mr = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" });
      recorderRef.current = mr;

      mr.ondataavailable = (e) => {
        if (e.data?.size > 0) chunksRef.current.push(e.data);
      };

      mr.onstop = async () => {
        setState("processing");
        try {
          const blob = new Blob(chunksRef.current, { type: "audio/webm" });
          if (blob.size < 2000) {
            setState("idle");
            return;
          }

          const data = await sendVoiceInput({ audioBlob: blob });
          const transcript = (data.transcript || "").trim();
          const responseText = (data.response_text || "").trim();

          if (transcript) onTranscript?.(transcript);
          if (responseText) onResponse?.(responseText);
        } catch (err) {
          onResponse?.(err?.message || "Voice failed. Please try again.");
        } finally {
          setState("idle");
          try {
            streamRef.current?.getTracks()?.forEach((t) => t.stop());
          } catch {}
          streamRef.current = null;
        }
      };

      mr.start();
    } catch (err) {
      setState("idle");
      onResponse?.(err?.message || "Microphone not available.");
    }
  }

  function stop() {
    if (state !== "listening") return;
    try {
      recorderRef.current?.stop();
    } catch {
      setState("idle");
    }
  }

  const label =
    state === "idle" ? "Mic" : state === "listening" ? "Listening" : "Processing";

  return (
    <button
      className={`voice-btn ${state}`}
      onClick={() => (state === "listening" ? stop() : start())}
      disabled={!!disabled || state === "processing"}
      title="Voice input"
      type="button"
    >
      <span className="voice-icon">🎙️</span>
      <span className="voice-label">{label}</span>
      {state === "listening" ? <span className="pulse" /> : null}
    </button>
  );
}

