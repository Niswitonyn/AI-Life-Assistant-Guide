import { useEffect, useState } from "react";
import { HashRouter as Router, Routes, Route, Navigate } from "react-router-dom";

import JarvisAvatar from "./components/JarvisAvatar";
import ChatPanel from "./components/ChatPanel";
import Setup from "./components/Setup";
import Login from "./components/Login";
import { apiUrl } from "./config/api";

function App() {

  const isElectron =
    typeof navigator !== "undefined" &&
    navigator.userAgent.toLowerCase().includes("electron");
  const [ready, setReady] = useState(isElectron);
  const hasToken =
    typeof window !== "undefined" &&
    !!window.localStorage.getItem("token");

  useEffect(() => {
    if (isElectron) {
      return;
    }

    async function checkSetup() {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2000);

      try {

        const res = await fetch(
          apiUrl("/api/setup/status"),
          { signal: controller.signal }
        );

        const data = await res.json();

        if (!data.configured) {
          window.location.hash = "/setup";
        }
        setReady(true);

      } catch (err) {

        console.error("Setup check failed:", err);

        // allow app anyway if backend not reachable
        setReady(true);
      } finally {
        clearTimeout(timeoutId);
      }
    }

    checkSetup();

  }, [isElectron]);

  // Prevent render until check complete
  if (!ready) return null;

  return (
    <Router>
      <Routes>
        <Route
          path="/"
          element={hasToken ? <JarvisAvatar /> : <Navigate to="/login" replace />}
        />

        <Route
          path="/login"
          element={hasToken ? <Navigate to="/" replace /> : <Login />}
        />

        {/* Chat Window */}
        <Route path="/chat" element={<ChatPanel />} />

        {/* Setup Screen */}
        <Route path="/setup" element={<Setup />} />

        <Route path="*" element={<Navigate to="/" replace />} />

      </Routes>
    </Router>
  );
}

export default App;
