import { useEffect } from "react";

export default function JarvisAvatar() {

  useEffect(() => {
    startListening();
  }, []);

  function startListening() {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      console.log("Speech recognition not supported");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.lang = "en-US";

    recognition.onresult = async (event) => {
      const text =
        event.results[event.results.length - 1][0].transcript;

      console.log("🎤 Heard:", text);

      await sendToBackend(text);
    };

    recognition.start();
  }

  async function sendToBackend(message) {
    try {
      const res = await fetch("http://127.0.0.1:8000/api/ai/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: message
        }),
      });

      const data = await res.json();

      speak(data.reply || data.response || "Okay");
    } catch (err) {
      console.error(err);
    }
  }

  function speak(text) {
    const utterance = new SpeechSynthesisUtterance(text);
    speechSynthesis.speak(utterance);
  }

  return (
    <div className="jarvis-container">
      <div className="jarvis-ring"></div>
      <div className="jarvis-core"></div>
    </div>
  );
}