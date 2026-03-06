import { useEffect, useState, useRef } from "react";
import "./Jarvis.css";
import { apiUrl } from "../config/api";

export default function JarvisAvatar() {
  const HOLD_TO_TALK_DELAY_MS = 180;
  const ORB_SIZE_PX = 108;
  const EDGE_PADDING_PX = 14;

  const [state, setState] = useState("idle");
  const [hovered, setHovered] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuPos, setMenuPos] = useState({ horizontal: "right", vertical: "down" });

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
  const draggingRef = useRef(false);
  const pointerStartRef = useRef({ x: 0, y: 0 });
  const positionStartRef = useRef({ x: 0, y: 0 });
  const [position, setPosition] = useState(() => {
    try {
      const raw = localStorage.getItem("jarvis_orb_position");
      if (raw) {
        const parsed = JSON.parse(raw);
        if (typeof parsed?.x === "number" && typeof parsed?.y === "number") {
          return parsed;
        }
      }
    } catch {}
    return { x: null, y: null };
  });

  function clampPosition(nextX, nextY) {
    const maxX = Math.max(EDGE_PADDING_PX, window.innerWidth - ORB_SIZE_PX - EDGE_PADDING_PX);
    const maxY = Math.max(EDGE_PADDING_PX, window.innerHeight - ORB_SIZE_PX - EDGE_PADDING_PX);
    return {
      x: Math.min(Math.max(nextX, EDGE_PADDING_PX), maxX),
      y: Math.min(Math.max(nextY, EDGE_PADDING_PX), maxY),
    };
  }

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
    if (position.x !== null && position.y !== null) {
      try {
        localStorage.setItem("jarvis_orb_position", JSON.stringify(position));
      } catch {}
    }
  }, [position]);

  useEffect(() => {
    const anchorX = position.x ?? (window.innerWidth - ORB_SIZE_PX - EDGE_PADDING_PX);
    const anchorY = position.y ?? (window.innerHeight - ORB_SIZE_PX - EDGE_PADDING_PX);
    const rightSpace = window.innerWidth - (anchorX + ORB_SIZE_PX);
    const bottomSpace = window.innerHeight - (anchorY + ORB_SIZE_PX);

    setMenuPos({
      horizontal: rightSpace < 170 ? "left" : "right",
      vertical: bottomSpace < 150 ? "up" : "down",
    });
  }, [position.x, position.y]);

  useEffect(() => {
    function ensureVisiblePosition() {
      if (position.x === null || position.y === null) return;
      const next = clampPosition(position.x, position.y);
      if (next.x !== position.x || next.y !== position.y) {
        setPosition(next);
      }
    }

    ensureVisiblePosition();
    window.addEventListener("resize", ensureVisiblePosition);
    return () => window.removeEventListener("resize", ensureVisiblePosition);
  }, [position.x, position.y]);

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

  useEffect(() => {
    function handlePointerMove(e) {
      if (!isHoldingRef.current) return;

      const deltaX = (e.clientX || 0) - pointerStartRef.current.x;
      const deltaY = (e.clientY || 0) - pointerStartRef.current.y;
      const movedEnough = Math.hypot(deltaX, deltaY) > 8;

      if (!draggingRef.current && movedEnough) {
        draggingRef.current = true;
        didStartListeningRef.current = false;
        if (holdTimerRef.current) {
          clearTimeout(holdTimerRef.current);
          holdTimerRef.current = null;
        }
        if (!forceBackendSttRef.current && recognitionRef.current) {
          try { recognitionRef.current.stop(); } catch {}
        }
        if (mediaRecorderRef.current?.state === "recording") {
          mediaRecorderRef.current.stop();
        }
        setState("idle");
      }

      if (!draggingRef.current) return;
      const next = clampPosition(positionStartRef.current.x + deltaX, positionStartRef.current.y + deltaY);
      setPosition(next);
    }

    function handlePointerUp() {
      if (!isHoldingRef.current) return;
      handleMouseUp();
    }

    window.addEventListener("mousemove", handlePointerMove);
    window.addEventListener("mouseup", handlePointerUp);
    return () => {
      window.removeEventListener("mousemove", handlePointerMove);
      window.removeEventListener("mouseup", handlePointerUp);
    };
  }, []);

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
    draggingRef.current = false;
    didStartListeningRef.current = false;
    pointerStartRef.current = { x: e.clientX || 0, y: e.clientY || 0 };
    const fallbackX = window.innerWidth - ORB_SIZE_PX - EDGE_PADDING_PX;
    const fallbackY = window.innerHeight - ORB_SIZE_PX - EDGE_PADDING_PX;
    positionStartRef.current = {
      x: position.x ?? fallbackX,
      y: position.y ?? fallbackY,
    };

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
    if (draggingRef.current) {
      draggingRef.current = false;
      return;
    }

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
      style={{
        left: position.x === null ? "auto" : `${position.x}px`,
        top: position.y === null ? "auto" : `${position.y}px`,
        right: position.x === null ? `${EDGE_PADDING_PX}px` : "auto",
        bottom: position.y === null ? `${EDGE_PADDING_PX}px` : "auto",
        cursor: draggingRef.current ? "grabbing" : "pointer",
      }}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
      onMouseLeave={() => {
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
        <div
          className={`jarvis-menu ${menuPos.horizontal} ${menuPos.vertical}`}
          onMouseDown={(e) => e.stopPropagation()}
        >
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
