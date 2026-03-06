import { useEffect, useState } from "react";
import { HashRouter as Router, Routes, Route, Navigate } from "react-router-dom";

import JarvisAvatar from "./components/JarvisAvatar";
import ChatPanel from "./components/ChatPanel";
import Login from "./components/Login";
import Onboarding from "./components/Onboarding";
import SettingsPanel from "./components/SettingsPanel";
import AIProviderSetup from "./components/AIProviderSetup";
import { apiUrl } from "./config/api";

function App() {

  const isElectron =
    typeof navigator !== "undefined" &&
    navigator.userAgent.toLowerCase().includes("electron");
  const [ready, setReady] = useState(isElectron);
  const [aiReady, setAiReady] = useState(false);
  const [statusChecked, setStatusChecked] = useState(false);
  const [statusNonce, setStatusNonce] = useState(0);
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

  useEffect(() => {
    if (!hasToken) {
      setAiReady(false);
      setStatusChecked(true);
      return;
    }

    let cancelled = false;
    fetch(apiUrl("/api/setup/status"))
      .then((res) => res.json())
      .then((data) => {
        if (cancelled) return;
        setAiReady(Boolean(data?.ai_ready));
      })
      .catch(() => {
        if (cancelled) return;
        setAiReady(false);
      })
      .finally(() => {
        if (cancelled) return;
        setStatusChecked(true);
      });

    return () => {
      cancelled = true;
    };
  }, [hasToken, statusNonce]);

  useEffect(() => {
    function refreshStatus() {
      setStatusChecked(false);
      setStatusNonce((n) => n + 1);
    }
    window.addEventListener("jarvis:setup-updated", refreshStatus);
    return () => window.removeEventListener("jarvis:setup-updated", refreshStatus);
  }, []);

  // Prevent render until check complete
  if (!ready || !statusChecked) return null;

  return (
    <Router>
      <Routes>
        <Route
          path="/"
          element={hasToken
            ? (aiReady ? <JarvisAvatar /> : <Navigate to="/onboarding" replace />)
            : <Navigate to="/login" replace />
          }
        />

        <Route
          path="/login"
          element={<Login />}
        />

        <Route
          path="/onboarding"
          element={hasToken ? <Onboarding /> : <Navigate to="/login" replace />}
        />

        {/* Chat Window */}
        <Route path="/chat" element={<ChatPanel />} />

        {/* Setup Routes */}
        <Route
          path="/provider-setup"
          element={hasToken ? <AIProviderSetup /> : <Navigate to="/login" replace />}
        />
        <Route
          path="/settings"
          element={hasToken ? <SettingsPanel /> : <Navigate to="/login" replace />}
        />

        <Route path="*" element={<Navigate to="/" replace />} />

      </Routes>
    </Router>
  );
}

export default App;
