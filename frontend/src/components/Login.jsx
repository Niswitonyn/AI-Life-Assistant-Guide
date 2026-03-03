import { useState } from "react";
import { apiUrl } from "../config/api";

export default function Login() {

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const login = async () => {
    setError("");

    const res = await fetch(apiUrl("/api/user/login"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ email, password })
    });

    const data = await res.json();

    if (data.token && data.user_id) {
      localStorage.setItem("token", data.token);
      localStorage.setItem("user_id", String(data.user_id));
      window.location.reload();
      return;
    }
    setError(data.detail || data.error || "Login failed");
  };

  return (
    <div style={styles.wrap}>
      <div style={styles.card}>
        <h2 style={styles.title}>Jarvis Login</h2>

        <input
          style={styles.input}
          placeholder="Email"
          value={email}
          onChange={e => setEmail(e.target.value)}
        />

        <input
          style={styles.input}
          placeholder="Password"
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
        />

        <button style={styles.button} onClick={login}>Login</button>
        {error && <p style={styles.error}>{error}</p>}
      </div>
    </div>
  );
}

const styles = {
  wrap: {
    width: "100vw",
    height: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "#0b1220",
    color: "#e5e7eb",
    fontFamily: "Segoe UI, Arial, sans-serif",
  },
  card: {
    width: "min(380px, 92vw)",
    padding: "24px",
    borderRadius: "12px",
    background: "#111827",
    border: "1px solid #1f2937",
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  },
  title: {
    margin: 0,
    fontSize: "22px",
    color: "#f9fafb",
  },
  input: {
    padding: "10px 12px",
    borderRadius: "8px",
    border: "1px solid #374151",
    background: "#0f172a",
    color: "#f9fafb",
    outline: "none",
  },
  button: {
    padding: "10px 12px",
    borderRadius: "8px",
    border: "none",
    background: "#2563eb",
    color: "#fff",
    cursor: "pointer",
    fontWeight: 600,
  },
  error: {
    margin: 0,
    color: "#f87171",
    fontSize: "13px",
  },
};
