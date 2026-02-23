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

    setConnecting(true);
    setMessage("");

    const popup = window.open(
      `http://127.0.0.1:8000/api/auth/connect-gmail?user_id=${userId}`,
      "_blank"
    );

    const timer = setInterval(() => {
      if (popup.closed) {
        clearInterval(timer);

        loadStatus();
        setConnecting(false);
        setMessage("✅ Gmail connected successfully");
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