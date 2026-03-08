import { useEffect, useState } from "react";
import { HashRouter as Router, Routes, Route, Navigate } from "react-router-dom";

import JarvisAvatar from "./components/JarvisAvatar";
import ChatPanel from "./components/ChatPanel";
import Login from "./components/Login";
import Onboarding from "./components/Onboarding";
import SettingsPanel from "./components/SettingsPanel";
import AIProviderSetup from "./components/AIProviderSetup";
import Splash from "./components/Splash";
import { apiUrl } from "./config/api";

function App() {

  const isElectron =
    typeof navigator !== "undefined" &&
    navigator.userAgent.toLowerCase().includes("electron");
  const [ready, setReady] = useState(isElectron);
  const [aiReady, setAiReady] = useState(false);
  const [statusChecked, setStatusChecked] = useState(false);
  const [statusNonce, setStatusNonce] = useState(0);
  const [hasToken, setHasToken] = useState(
    typeof window !== "undefined" && !!window.localStorage.getItem("token")
  );

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
    const abortCtrl = new AbortController();
    const timeoutId = setTimeout(() => abortCtrl.abort(), 3000);

    fetch(apiUrl("/api/setup/status"), { signal: abortCtrl.signal })
      .then((res) => res.json())
      .then((data) => {
        if (cancelled) return;
        setAiReady(Boolean(data?.ai_ready));
      })
      .catch(() => {
        if (cancelled) return;
        // Backend unreachable or timed out — proceed with aiReady=false so
        // routes are never blocked indefinitely on a blank transparent window.
        setAiReady(false);
      })
      .finally(() => {
        clearTimeout(timeoutId);
        if (cancelled) return;
        setStatusChecked(true);
      });

    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
      abortCtrl.abort();
    };
  }, [hasToken, statusNonce]);

  useEffect(() => {
    function refreshStatus() {
      // Do NOT set statusChecked=false here — that would unmount all routes
      // (including Onboarding) for the duration of the fetch, resetting its
      // step state and making the window go blank.  Just increment the nonce
      // so the status effect re-runs in the background while routes stay up.
      setStatusNonce((n) => n + 1);
    }
    window.addEventListener("jarvis:setup-updated", refreshStatus);
    return () => window.removeEventListener("jarvis:setup-updated", refreshStatus);
  }, []);

  // Re-read the token from localStorage whenever Login (or any component)
  // dispatches "jarvis:auth-updated".  Without this, App's stale hasToken
  // closure would redirect the user back to /login immediately after login.
  useEffect(() => {
    function onAuthUpdate() {
      setHasToken(!!window.localStorage.getItem("token"));
    }
    window.addEventListener("jarvis:auth-updated", onAuthUpdate);
    return () => window.removeEventListener("jarvis:auth-updated", onAuthUpdate);
  }, []);

  // Prevent rendering app routes until setup check completes,
  // but always allow the splash route so it shows immediately.
  return (
    <Router>
      <Routes>
        {/* Splash is always renderable — no setup check required */}
        <Route path="/splash" element={<Splash />} />

        {/* All other routes wait for the setup/status check */}
        {ready && statusChecked ? (
          <>
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
          </>
        ) : null}
      </Routes>
    </Router>
  );
}

export default App;
