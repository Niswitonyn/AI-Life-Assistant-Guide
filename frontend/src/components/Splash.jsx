import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import "./Splash.css";

export default function Splash() {
  const navigate = useNavigate();
  const [error, setError] = useState(null);

  useEffect(() => {
    // Non-Electron environment: skip splash and go straight to login
    if (!window.electronAPI?.getBackendStatus) {
      navigate("/login", { replace: true });
      return;
    }

    function handleStatus(status) {
      if (status.ready) {
        navigate("/login", { replace: true });
      } else if (status.error) {
        setError(status.error);
      }
    }

    // Check status that may have already been resolved before this component mounted
    window.electronAPI.getBackendStatus().then(handleStatus);

    // Listen for future status updates pushed from the main process
    window.electronAPI.onBackendStatusUpdate(handleStatus);
  }, [navigate]);

  if (error) {
    return (
      <div className="splash">
        <div className="splash-error">
          <h2 className="splash-error-title">Failed to Start</h2>
          <p className="splash-error-message">{error}</p>
          <button
            className="splash-error-button"
            onClick={() => window.electronAPI?.closeApp()}
          >
            Close
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="splash">
      <div className="splash-loading">
        <h1 className="splash-title">Starting Jarvis...</h1>
        <div className="splash-spinner" />
      </div>
    </div>
  );
}
