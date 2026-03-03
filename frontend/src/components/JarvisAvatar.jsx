import { useEffect, useState, useRef } from "react";
import "./Jarvis.css";
import { apiUrl } from "../config/api";

export default function JarvisAvatar() {
  const HOLD_TO_TALK_DELAY_MS = 180;
  const CORE_HIT_RADIUS_PX = 42;

  const [state, setState] = useState("idle");
  const [hovered, setHovered] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  const recognitionRef = useRef(null);
  const isHoldingRef = useRef(false);
  const rootRef = useRef(null);

  const mediaStreamRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);

  const forceBackendSttRef = useRef(false);
  const isSendingAudioRef = useRef(false);
  const holdTimerRef = useRef(null);
  const didStartListeningRef = useRef(false);

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

        const clickThrough = state === "idle" && !hovered && !menuOpen;

        ipcRenderer.send("set-click-through", clickThrough);
      }
    } catch {
      // not electron
    }

  }, [state, hovered, menuOpen]);

  useEffect(() => {
    function handleDocClick(e) {
      if (!menuOpen) return;
      if (!rootRef.current?.contains(e.target)) {
        setMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", handleDocClick);
    return () => document.removeEventListener("mousedown", handleDocClick);
  }, [menuOpen]);

  // =========================
  // SMART PROXIMITY DETECTION
  // =========================
  useEffect(() => {
    function handleMouseMove(e) {
      const rect = document
        .querySelector(".jarvis-container")
        ?.getBoundingClientRect();

      if (!rect) return;

      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;

      const dist = Math.hypot(
        e.clientX - centerX,
        e.clientY - centerY
      );

      const near = dist < 150;
      setHovered(near);
    }

    window.addEventListener("mousemove", handleMouseMove);

    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);


  // =========================
  // CLEANUP
  // =========================
  function cleanupAudio() {
    if (holdTimerRef.current) {
      clearTimeout(holdTimerRef.current);
      holdTimerRef.current = null;
    }

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

    try { speechSynthesis.cancel(); } catch {}
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
        apiUrl("/api/voice"),
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

      const text = (data.text || "").trim();

      if (text.length > 1) {

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


  function handleMouseDown(e) {
    const target = e.currentTarget;
    const rect = target.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const dist = Math.hypot((e.clientX || 0) - cx, (e.clientY || 0) - cy);
    if (dist > CORE_HIT_RADIUS_PX) return;

    // Barge-in: stop TTS immediately when user starts speaking.
    try { speechSynthesis.cancel(); } catch {}
    if (state === "speaking") {
      setState("idle");
    }

    // Prevent duplicate starts while the user is already holding.
    if (isHoldingRef.current) return;

    // If a previous capture is still active, close it first.
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop();
    }

    isHoldingRef.current = true;
    didStartListeningRef.current = false;

    if (holdTimerRef.current) {
      clearTimeout(holdTimerRef.current);
    }
    holdTimerRef.current = setTimeout(() => {
      if (!isHoldingRef.current) return;
      didStartListeningRef.current = true;
      startListening();
    }, HOLD_TO_TALK_DELAY_MS);
  }


  function handleMouseUp() {

    if (!isHoldingRef.current) return;
    isHoldingRef.current = false;

    if (holdTimerRef.current) {
      clearTimeout(holdTimerRef.current);
      holdTimerRef.current = null;
    }

    // Ignore quick taps to reduce accidental activation.
    if (!didStartListeningRef.current) return;
    didStartListeningRef.current = false;

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
    const cleaned = (message || "").trim();
    if (!cleaned) {
      setState("idle");
      return;
    }
    const userId = localStorage.getItem("user_id") || "default";
    const token = localStorage.getItem("token");
    const headers = { "Content-Type": "application/json" };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    try {

      const res = await fetch(
        apiUrl("/api/ai/chat"),
        {
          method: "POST",
          headers,
          body: JSON.stringify({
            user_id: userId,
            messages: [
              {
                role: "user",
                content: cleaned,
              },
            ],
          }),
        }
      );

      if (!res.ok) {
        setState("idle");
        return;
      }

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
    const cleaned = (text || "").trim();
    if (!cleaned) {
      setState("idle");
      return;
    }

    setState("speaking");
    speechSynthesis.cancel();

    const utterance =
      new SpeechSynthesisUtterance(cleaned);

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
  function openChat(e) {
    // Require Shift + double click to avoid accidental popups.
    if (!e?.shiftKey) return;

    try {
      if (window.require) {
        const { ipcRenderer } = window.require("electron");
        ipcRenderer.send("open-chat");
      }
    } catch {}
  }

  function openSettings() {
    try {
      if (window.require) {
        const { ipcRenderer } = window.require("electron");
        ipcRenderer.send("open-settings");
      } else {
        window.location.hash = "/settings";
      }
    } catch {
      window.location.hash = "/settings";
    } finally {
      setMenuOpen(false);
    }
  }

  function openChatFromMenu() {
    try {
      if (window.require) {
        const { ipcRenderer } = window.require("electron");
        ipcRenderer.send("open-chat");
      } else {
        window.location.hash = "/chat";
      }
    } catch {
      window.location.hash = "/chat";
    } finally {
      setMenuOpen(false);
    }
  }

  function closeApp() {
    try {
      if (window.require) {
        const { ipcRenderer } = window.require("electron");
        ipcRenderer.send("close-app");
        return;
      }
    } catch {}
    window.close();
  }


  // =========================
  // UI
  // =========================
  return (
    <div
      ref={rootRef}
      className={`jarvis-container ${state}`}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
      onMouseLeave={() => {
        handleMouseUp();
        setHovered(false);
      }}
      onMouseEnter={() => setHovered(true)}
      onDoubleClick={openChat}
      title="Hold to talk. Shift + double-click to open chat."
    >
      <button
        className="jarvis-menu-btn"
        onMouseDown={(e) => e.stopPropagation()}
        onClick={(e) => {
          e.stopPropagation();
          setMenuOpen((v) => !v);
        }}
        title="Menu"
      >
        ⋮
      </button>

      {menuOpen && (
        <div className="jarvis-menu" onMouseDown={(e) => e.stopPropagation()}>
          <button onClick={openChatFromMenu}>Chat</button>
          <button onClick={openSettings}>Settings</button>
          <button onClick={closeApp} className="danger">Close App</button>
        </div>
      )}

      <div className="jarvis-ring"></div>
      <div className="jarvis-core"></div>
    </div>
  );
}
