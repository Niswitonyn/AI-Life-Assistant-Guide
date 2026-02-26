import { useState } from "react";

export default function Login() {

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const login = async () => {
    setError("");

    const res = await fetch("http://127.0.0.1:8000/api/user/login", {
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
    <div>
      <input
        placeholder="Email"
        value={email}
        onChange={e => setEmail(e.target.value)}
      />

      <input
        placeholder="Password"
        type="password"
        value={password}
        onChange={e => setPassword(e.target.value)}
      />

      <button onClick={login}>Login</button>
      {error && <p>{error}</p>}
    </div>
  );
}
