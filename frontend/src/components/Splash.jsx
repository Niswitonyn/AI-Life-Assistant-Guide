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

    const controller = new AbortController();
    let navigated = false;

    // Fast-path: if the backend was already running before Jarvis launched,
    // skip IPC polling entirely and navigate to login immediately.
    fetch("http://127.0.0.1:8000/health", { signal: controller.signal })
      .then((res) => {
        if (!navigated && res.ok) {
          navigated = true;
          navigate("/login", { replace: true });
        }
      })
      .catch(() => {
        // Backend not yet ready — fall through to IPC polling below
      });

    function handleStatus(status) {
      if (navigated) return;
      if (status.ready) {
        navigated = true;
        navigate("/login", { replace: true });
      } else if (status.error) {
        setError(status.error);
      }
    }

    // Check status that may have already been resolved before this component mounted
    window.electronAPI.getBackendStatus().then(handleStatus);

    // Listen for future status updates pushed from the main process
    window.electronAPI.onBackendStatusUpdate(handleStatus);

    return () => {
      controller.abort();
      navigated = true; // prevent callbacks firing after unmount
    };
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
