import { useEffect, useState } from "react";
import Onboarding from "./components/onboarding/Onboarding";
import ChatWindow from "./components/ChatWindow";
import Login from "./components/Login";

function App() {

  const [configured, setConfigured] = useState(null);

  // ✅ Login token
  const token = localStorage.getItem("token");

  // -------------------------
  // CHECK FIRST RUN SETUP
  // -------------------------
  useEffect(() => {

    if (!token) return; // not logged in yet

    fetch("http://127.0.0.1:8000/api/setup/status")
      .then(res => res.json())
      .then(data => setConfigured(data.configured))
      .catch(() => setConfigured(false));

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
    return <div>Loading...</div>;
  }

  // -------------------------
  // FIRST RUN → ONBOARDING
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
  return <ChatWindow />;
}

export default App;