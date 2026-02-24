import { useEffect, useState } from "react";
import Onboarding from "./components/onboarding/Onboarding";
import ChatWindow from "./components/ChatWindow";
import Login from "./components/Login";
import JarvisAvatar from "./components/JarvisAvatar";

function App() {

  const [configured, setConfigured] = useState(null);

  // Login token
  const token = localStorage.getItem("token");

  // -------------------------
  // VOICE WELCOME
  // -------------------------
  const speakWelcome = () => {

    if (!("speechSynthesis" in window)) return;

    const msg = new SpeechSynthesisUtterance(
      "Welcome back. All systems are online."
    );

    msg.rate = 0.9;
    msg.pitch = 0.8;

    speechSynthesis.speak(msg);
  };

  // -------------------------
  // CHECK SETUP STATUS
  // -------------------------
  useEffect(() => {

    if (!token) return;

    fetch("http://127.0.0.1:8000/api/setup/status")
      .then(res => res.json())
      .then(data => setConfigured(data.configured))
      .catch(() => setConfigured(false));

    speakWelcome();

  }, [token]);

  // -------------------------
  // NOT LOGGED IN
  // -------------------------
  if (!token) {
    return <Login />;
  }

  // -------------------------
  // LOADING
  // -------------------------
  if (configured === null) {
    return <div style={{ color: "white", padding: 20 }}>Loading...</div>;
  }

  // -------------------------
  // FIRST RUN
  // -------------------------
  if (!configured) {
    return (
      <Onboarding
        onComplete={() => setConfigured(true)}
      />
    );
  }

  // -------------------------
  // NORMAL APP
  // -------------------------
  return (
    <>
      <ChatWindow />

      {/* Floating Jarvis */}
      <JarvisAvatar />
    </>
  );
}

export default App;