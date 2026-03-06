import { useState } from "react";
import { apiUrl } from "../../config/api";

export default function UserSetup({ next }) {

  const [name, setName] = useState("");

  const handleNext = async () => {

    await fetch(apiUrl("/api/setup/user"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ name })
    });

    next();
  };

  return (
    <div>
      <h2>Welcome 👋</h2>
      <p>Let's setup your assistant</p>

      <input
        placeholder="Your name"
        value={name}
        onChange={(e) => setName(e.target.value)}
      />

      <button onClick={handleNext}>
        Continue
      </button>
    </div>
  );
}
