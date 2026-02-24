import { useEffect, useRef, useState } from "react";

export default function JarvisAvatar() {

  const [mode, setMode] = useState("idle");

  const recognitionRef = useRef(null);

  // -------------------------
  // SPEAK
  // -------------------------
  const speak = (text) => {

    if (!("speechSynthesis" in window)) return;

    setMode("speaking");

    const msg = new SpeechSynthesisUtterance(text);

    msg.rate = 0.9;
    msg.pitch = 0.8;

    msg.onend = () => setMode("idle");

    speechSynthesis.speak(msg);
  };

  // -------------------------
  // FULL COMMAND LISTEN
  // -------------------------
  const startCommandListening = () => {

    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) return;

    const recognition = new SpeechRecognition();

    recognition.lang = "en-US";
    recognition.continuous = false;
    recognition.interimResults = false;

    setMode("listening");

    recognition.start();

    recognition.onresult = (event) => {

      const text = event.results[0][0].transcript;

      console.log("Command:", text);

      setMode("thinking");

      setTimeout(() => {
        speak("You said " + text);
      }, 600);
    };

    recognition.onend = () => {
      setMode("idle");
      startWakeWord(); // resume wake word
    };
  };

  // -------------------------
  // WAKE WORD LISTENER
  // -------------------------
  const startWakeWord = () => {

    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) return;

    const recognition = new SpeechRecognition();

    recognition.lang = "en-US";
    recognition.continuous = true;
    recognition.interimResults = false;

    recognitionRef.current = recognition;

    recognition.start();

    recognition.onresult = (event) => {

      const text =
        event.results[event.results.length - 1][0].transcript.toLowerCase();

      console.log("Heard:", text);

      if (text.includes("hey jarvis") || text.includes("ok jarvis")) {

        recognition.stop();

        setMode("listening");

        speak("Yes?");

        setTimeout(() => {
          startCommandListening();
        }, 500);
      }
    };

    recognition.onend = () => {
      // restart automatically
      setTimeout(() => startWakeWord(), 1000);
    };
  };

  // -------------------------
  // CLICK TO ACTIVATE
  // -------------------------
  const handleClick = () => {
    startCommandListening();
  };

  // -------------------------
  // START WAKE WORD ON LOAD
  // -------------------------
  useEffect(() => {

    startWakeWord();

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
    };

  }, []);

  return (
    <div
      className={`jarvis-container ${mode}`}
      onClick={handleClick}
    >
      <div className="jarvis-ring"></div>
      <div className="jarvis-core"></div>
    </div>
  );
}