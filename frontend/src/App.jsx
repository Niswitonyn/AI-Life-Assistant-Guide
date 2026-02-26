import { useEffect, useState } from "react";
import { HashRouter as Router, Routes, Route } from "react-router-dom";

import JarvisAvatar from "./components/JarvisAvatar";
import ChatPanel from "./components/ChatPanel";
import Setup from "./components/Setup";

function App() {

  const [ready, setReady] = useState(false);

  useEffect(() => {

    async function checkSetup() {

      try {

        const res = await fetch(
          "http://127.0.0.1:8000/api/setup/status"
        );

        const data = await res.json();

        if (!data.configured) {
          window.location.href = "#/setup";
        } else {
          setReady(true);
        }

      } catch (err) {

        console.error("Setup check failed:", err);

        // allow app anyway if backend not reachable
        setReady(true);
      }
    }

    checkSetup();

  }, []);

  // Prevent render until check complete
  if (!ready) return null;

  return (
    <Router>
      <Routes>

        {/* Floating Jarvis */}
        <Route path="/" element={<JarvisAvatar />} />

        {/* Chat Window */}
        <Route path="/chat" element={<ChatPanel />} />

        {/* Setup Screen */}
        <Route path="/setup" element={<Setup />} />

      </Routes>
    </Router>
  );
}

export default App;