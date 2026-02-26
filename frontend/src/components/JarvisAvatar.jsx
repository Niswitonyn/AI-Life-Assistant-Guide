import { useEffect, useState, useRef } from "react";
import "./Jarvis.css";

export default function JarvisAvatar() {

  const [state, setState] = useState("idle");
  const [hovered, setHovered] = useState(false);

  const recognitionRef = useRef(null);
  const isHoldingRef = useRef(false);

  const mediaStreamRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);

  const forceBackendSttRef = useRef(false);
  const isSendingAudioRef = useRef(false);

  // =========================
  // INIT
  // =========================
  useEffect(() => {

    console.log("Jarvis ready — hold circle to talk");

    const isElectron =
      typeof navigator !== "undefined" &&
      navigator.userAgent.toLowerCase().includes("electron");

    forceBackendSttRef.current = isElectron;

    if (!forceBackendSttRef.current) {
      initializeRecognition();
    } else {
      console.log("Using backend speech mode (Electron)");
    }

    return () => cleanupAudio();

  }, []);


  // =========================
  // ELECTRON CLICK‑THROUGH HOOK
  // =========================
  useEffect(() => {

    try {
      if (window.require) {
        const { ipcRenderer } = window.require("electron");

        const clickThrough = state === "idle" && !hovered;

        ipcRenderer.send("set-click-through", clickThrough);
      }
    } catch {
      // not electron
    }

  }, [state, hovered]);


  // =========================
  // CLEANUP
  // =========================
  function cleanupAudio() {

    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch {}
    }

    if (mediaRecorderRef.current &&
        mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current
        .getTracks()
        .forEach(track => track.stop());
    }
  }


  // =========================
  // WEB SPEECH INIT
  // =========================
  function initializeRecognition() {

    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      forceBackendSttRef.current = true;
      return;
    }

    const recognition = new SpeechRecognition();

    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    recognitionRef.current = recognition;

    recognition.onstart = () => {
      setState("listening");
    };

    recognition.onresult = async (event) => {

      const text =
        event.results[event.results.length - 1][0].transcript;

      setState("thinking");

      await sendToBackend(text);
    };

    recognition.onerror = (e) => {

      if (e.error === "network") {
        forceBackendSttRef.current = true;
        startAudioCapture();
      }

      setState("idle");
    };
  }


  // =========================
  // AUDIO CAPTURE
  // =========================
  async function startAudioCapture() {

    try {

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000,
        },
      });

      mediaStreamRef.current = stream;

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: "audio/webm;codecs=opus",
      });

      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = async () => {

        const audioBlob =
          new Blob(chunksRef.current, { type: "audio/webm" });

        if (audioBlob.size < 2000) {
          setState("idle");
          return;
        }

        await sendAudioToBackend(audioBlob);

        stream.getTracks().forEach(t => t.stop());
      };

      mediaRecorder.start();

      setState("listening");

    } catch (err) {

      console.error(err);
      setState("idle");

    }
  }


  // =========================
  // SEND AUDIO → BACKEND
  // =========================
  async function sendAudioToBackend(audioBlob) {

    if (isSendingAudioRef.current) return;

    isSendingAudioRef.current = true;

    try {

      const formData = new FormData();
      formData.append("audio", audioBlob, "recording.webm");

      const res = await fetch(
        "http://127.0.0.1:8000/api/voice",
        {
          method: "POST",
          body: formData,
        }
      );

      if (!res.ok) {
        setState("idle");
        return;
      }

      const data = await res.json();

      const text = data.text || "";

      if (text.length > 0) {

        setState("thinking");

        await sendToBackend(text);

      } else {

        setState("idle");

      }

    } catch (err) {

      console.error(err);
      setState("idle");

    } finally {

      isSendingAudioRef.current = false;

    }
  }


  // =========================
  // START LISTEN
  // =========================
  function startListening() {

    if (forceBackendSttRef.current) {
      startAudioCapture();
      return;
    }

    if (recognitionRef.current) {
      try {
        recognitionRef.current.start();
      } catch {
        startAudioCapture();
      }
    } else {
      startAudioCapture();
    }
  }


  function handleMouseDown() {
    isHoldingRef.current = true;
    startListening();
  }


  function handleMouseUp() {

    isHoldingRef.current = false;

    if (!forceBackendSttRef.current && recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch {}
    }

    if (mediaRecorderRef.current &&
        mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
    }
  }


  // =========================
  // CHAT BACKEND
  // =========================
  async function sendToBackend(message) {

    try {

      const res = await fetch(
        "http://127.0.0.1:8000/api/ai/chat",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            messages: [
              {
                role: "user",
                content: message,
              },
            ],
          }),
        }
      );

      const data = await res.json();

      const reply = data.response || "Okay";

      speak(reply);

    } catch (err) {

      console.error(err);
      setState("idle");

    }
  }


  // =========================
  // SPEAK
  // =========================
  function speak(text) {

    setState("speaking");

    const utterance =
      new SpeechSynthesisUtterance(text);

    utterance.onend = () => {

      setState("idle");

      if (isHoldingRef.current) {
        startListening();
      }
    };

    speechSynthesis.speak(utterance);
  }


  // =========================
  // OPEN CHAT WINDOW
  // =========================
  function openChat() {

    try {
      if (window.require) {
        const { ipcRenderer } = window.require("electron");
        ipcRenderer.send("open-chat");
      }
    } catch {}
  }


  // =========================
  // UI
  // =========================
  return (
    <div
      className={`jarvis-container ${state}`}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
      onMouseLeave={(e) => {
        handleMouseUp();
        setHovered(false);
      }}
      onMouseEnter={() => setHovered(true)}
      onDoubleClick={openChat}
    >
      <div className="jarvis-ring"></div>
      <div className="jarvis-core"></div>
    </div>
  );
}
