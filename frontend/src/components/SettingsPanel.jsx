import { useEffect, useState } from "react";

export default function SettingsPanel() {

  const [status, setStatus] = useState({
    gmail_ready: false,
    ai_ready: false,
    user_ready: false
  });

  const [name, setName] = useState("");

  // ✅ NEW STATES
  const [connecting, setConnecting] = useState(false);
  const [message, setMessage] = useState("");

  // -------------------------
  // LOAD STATUS
  // -------------------------
  const loadStatus = () => {
    fetch("http://127.0.0.1:8000/api/setup/status")
      .then(res => res.json())
      .then(data => setStatus(data))
      .catch(() => {});
  };

  useEffect(() => {
    loadStatus();
  }, []);

  // -------------------------
  // SAVE USER
  // -------------------------
  const saveUser = async () => {
    await fetch("http://127.0.0.1:8000/api/setup/user", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name })
    });

    loadStatus();
  };

  // -------------------------
  // CONNECT GMAIL (OAuth + AUTO REFRESH + LOADING)
  // -------------------------
  const connectGmail = () => {

    const userId = localStorage.getItem("user_id") || "default";
    const oauthUrl = `http://127.0.0.1:8000/api/auth/gmail/login?user_id=${userId}`;

    setConnecting(true);
    setMessage("");

    let ipcRenderer = null;
    try {
      if (window.require) {
        ipcRenderer = window.require("electron").ipcRenderer;
      }
    } catch {}

    if (ipcRenderer) {
      ipcRenderer.invoke("open-oauth-popup", oauthUrl)
        .then(async () => {
          try {
            const profileRes = await fetch(
              `http://127.0.0.1:8000/api/auth/gmail/profile?user_id=${userId}`
            );
            if (profileRes.ok) {
              const profile = await profileRes.json();
              if (profile.token) {
                localStorage.setItem("token", profile.token);
              }
              if (profile.user_id) {
                localStorage.setItem("user_id", String(profile.user_id));
              }
              await ipcRenderer.invoke("secure-set", "gmail_profile", profile);
            }
          } catch {}

          loadStatus();
          setConnecting(false);
          setMessage("Gmail connected successfully");
        })
        .catch(() => {
          setConnecting(false);
          setMessage("OAuth popup failed");
        });
      return;
    }

    const popup = window.open(oauthUrl, "_blank");

    if (!popup) {
      setConnecting(false);
      setMessage("Popup blocked. Allow popups and try again.");
      return;
    }

    const timer = setInterval(() => {
      if (popup.closed) {
        clearInterval(timer);
        fetch(`http://127.0.0.1:8000/api/auth/gmail/profile?user_id=${userId}`)
          .then((res) => res.ok ? res.json() : null)
          .then((profile) => {
            if (!profile) return;
            if (profile.token) {
              localStorage.setItem("token", profile.token);
            }
            if (profile.user_id) {
              localStorage.setItem("user_id", String(profile.user_id));
            }
          })
          .catch(() => {});

        loadStatus();
        setConnecting(false);
        setMessage("Gmail connected successfully");
      }
    }, 1000);
  };

  // -------------------------
  // DISCONNECT GMAIL
  // -------------------------
  const disconnectGmail = async () => {

    await fetch("http://127.0.0.1:8000/api/setup/disconnect-gmail", {
      method: "POST"
    });

    loadStatus();
  };

  // -------------------------
  // RECONNECT AI
  // -------------------------
  const reconnectAI = async () => {

    await fetch("http://127.0.0.1:8000/api/setup/reconnect-ai", {
      method: "POST"
    });

    loadStatus();
  };

  // -------------------------
  // LOGOUT
  // -------------------------
  const logout = () => {

    localStorage.removeItem("token");
    localStorage.removeItem("user_id");

    window.location.reload();
  };

  const badge = (ok) =>
    ok
      ? "bg-green-500 text-white px-2 py-1 rounded text-xs"
      : "bg-red-500 text-white px-2 py-1 rounded text-xs";

  return (
    <div className="max-w-xl mx-auto p-6 space-y-6">

      <h2 className="text-2xl font-bold">⚙ Settings</h2>

      {/* USER PROFILE */}
      <div className="bg-gray-900 text-white p-4 rounded-xl shadow">
        <div className="flex justify-between mb-3">
          <span>User Profile</span>
          <span className={badge(status.user_ready)}>
            {status.user_ready ? "Connected" : "Not Connected"}
          </span>
        </div>

        <input
          className="w-full p-2 rounded text-black"
          placeholder="Your name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />

        <button
          onClick={saveUser}
          className="mt-3 bg-blue-500 px-4 py-2 rounded"
        >
          Save Profile
        </button>
      </div>

      {/* GMAIL */}
      <div className="bg-gray-900 text-white p-4 rounded-xl shadow">
        <div className="flex justify-between mb-3">
          <span>Gmail</span>
          <span className={badge(status.gmail_ready)}>
            {status.gmail_ready ? "Connected" : "Not Connected"}
          </span>
        </div>

        <div className="flex gap-2">

          <button
            onClick={connectGmail}
            disabled={connecting}
            className="bg-green-500 px-4 py-2 rounded"
          >
            {connecting ? "Connecting..." : "Connect"}
          </button>

          <button
            onClick={disconnectGmail}
            className="bg-red-500 px-4 py-2 rounded"
          >
            Disconnect
          </button>

        </div>

        {/* SUCCESS MESSAGE */}
        {message && (
          <div className="text-green-400 text-sm mt-2">
            {message}
          </div>
        )}

      </div>

      {/* AI PROVIDER */}
      <div className="bg-gray-900 text-white p-4 rounded-xl shadow">
        <div className="flex justify-between mb-3">
          <span>AI Provider</span>
          <span className={badge(status.ai_ready)}>
            {status.ai_ready ? "Configured" : "Not Configured"}
          </span>
        </div>

        <button
          onClick={reconnectAI}
          className="bg-purple-500 px-4 py-2 rounded"
        >
          Reconnect AI
        </button>
      </div>

      {/* LOGOUT */}
      <div className="text-center">
        <button
          onClick={logout}
          className="bg-gray-700 text-white px-6 py-2 rounded"
        >
          Logout
        </button>
      </div>

    </div>
  );
} 

