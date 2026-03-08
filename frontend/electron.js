const path = require("path");
const fs = require("fs");
const http = require("http");
const { spawn } = require("child_process");
const {
  app,
  BrowserWindow,
  screen,
  session,
  ipcMain,
  powerMonitor,
  safeStorage,
} = require("electron");

const BACKEND_HEALTH_URL = "http://127.0.0.1:8000/health";
const BACKEND_POLL_INTERVAL_MS = 1000;
const BACKEND_TIMEOUT_MS = 120000;

const isDev = !app.isPackaged;
const DEV_SERVER_URL = process.env.ELECTRON_RENDERER_URL || "http://localhost:5173";
const DIST_INDEX = path.join(__dirname, "dist", "index.html");
const PRELOAD_PATH = path.join(__dirname, "preload.js");

let win = null;
let chatWin = null;
let fullscreenWatchTimer = null;
let secureStore = null;
let backendProcess = null;
let backendStatus = { ready: false, error: null };

const gotLock = isDev ? true : app.requestSingleInstanceLock();
if (!gotLock) {
  // Another instance is already running — write a quick log before quitting
  try {
    const tmpLog = path.join(require("os").tmpdir(), "jarvis-second-instance.log");
    fs.appendFileSync(tmpLog, `[${new Date().toISOString()}] Second instance detected — quitting.\n`);
  } catch { /* best-effort */ }
  app.quit();
}

app.commandLine.appendSwitch("use-fake-ui-for-media-stream");
app.commandLine.appendSwitch("enable-speech-dispatcher");
app.commandLine.appendSwitch("enable-features", "AudioServiceOutOfProcess");
app.commandLine.appendSwitch("disable-features", "IsolateOrigins,site-per-process");

function setClickThrough(enabled) {
  if (!win) return;
  win.setIgnoreMouseEvents(enabled, { forward: true });
}

ipcMain.on("set-click-through", (_, enabled) => {
  setClickThrough(enabled);
});

function revealMainWindow() {
  if (!win || win.isDestroyed()) return;
  if (win.isMinimized()) win.restore();
  if (!win.isVisible()) win.show();
  win.focus();
}

function loadRenderer(windowRef, hashPath = "/") {
  if (isDev) {
    windowRef.loadURL(`${DEV_SERVER_URL}/#${hashPath}`);
    return;
  }
  windowRef.loadFile(DIST_INDEX, { hash: hashPath });
}

function createChatWindow() {
  if (chatWin) {
    chatWin.focus();
    return;
  }

  chatWin = new BrowserWindow({
    width: 380,
    height: 500,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: true,
    webPreferences: {
      // FIX: secure webPreferences - no Node.js access in renderer
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      preload: PRELOAD_PATH,
    },
  });

  chatWin.setBackgroundColor("#00000000");
  loadRenderer(chatWin, "/chat");

  chatWin.on("closed", () => {
    chatWin = null;
  });
}

ipcMain.on("open-chat", () => {
  createChatWindow();
});

ipcMain.on("open-settings", () => {
  revealMainWindow();
  if (!win || win.isDestroyed()) return;
  loadRenderer(win, "/settings");
});

ipcMain.on("open-main", () => {
  revealMainWindow();
  if (!win || win.isDestroyed()) return;
  loadRenderer(win, "/");
});

ipcMain.on("close-chat", () => {
  if (!chatWin || chatWin.isDestroyed()) return;
  chatWin.close();
});

ipcMain.on("close-app", () => {
  app.quit();
});

ipcMain.handle("open-oauth-popup", async (_, url) => {
  if (!url || typeof url !== "string") {
    return { status: "error", message: "Invalid OAuth URL" };
  }

  const popup = new BrowserWindow({
    width: 560,
    height: 760,
    parent: win || undefined,
    modal: false,
    autoHideMenuBar: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
  });

  await popup.loadURL(url);
  return await new Promise((resolve) => {
    popup.on("closed", () => resolve({ status: "closed" }));
  });
});

function encryptValue(plain) {
  if (!safeStorage.isEncryptionAvailable()) return plain;
  return safeStorage.encryptString(plain).toString("base64");
}

function decryptValue(encrypted) {
  if (!safeStorage.isEncryptionAvailable()) return encrypted;
  const buffer = Buffer.from(encrypted, "base64");
  return safeStorage.decryptString(buffer);
}

ipcMain.handle("secure-set", (_, key, value) => {
  if (!secureStore) return { status: "error", message: "Secure store unavailable" };
  if (!key) return { status: "error", message: "Missing key" };
  const serialized = typeof value === "string" ? value : JSON.stringify(value);
  secureStore.set(key, encryptValue(serialized));
  return { status: "ok" };
});

ipcMain.handle("secure-get", (_, key) => {
  if (!secureStore) return { status: "error", message: "Secure store unavailable" };
  if (!key) return { status: "error", message: "Missing key" };
  const stored = secureStore.get(key);
  if (!stored) return { status: "not_found" };

  try {
    const decrypted = decryptValue(stored);
    try {
      return { status: "ok", value: JSON.parse(decrypted) };
    } catch {
      return { status: "ok", value: decrypted };
    }
  } catch {
    return { status: "error", message: "Could not decrypt value" };
  }
});

ipcMain.handle("secure-delete", (_, key) => {
  if (!secureStore) return { status: "error", message: "Secure store unavailable" };
  if (!key) return { status: "error", message: "Missing key" };
  secureStore.delete(key);
  return { status: "ok" };
});

ipcMain.handle("get-backend-status", () => backendStatus);

function pollBackendHealth() {
  return new Promise((resolve) => {
    try {
      const req = http.get(BACKEND_HEALTH_URL, (res) => {
        resolve(res.statusCode >= 200 && res.statusCode < 400);
        res.resume();
      });
      req.on("error", () => resolve(false));
      req.setTimeout(3000, () => {
        req.destroy();
        resolve(false);
      });
    } catch {
      resolve(false);
    }
  });
}

async function waitForBackend(timeoutMs = BACKEND_TIMEOUT_MS) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    console.log(`[backend] Health check attempt at +${Date.now() - start}ms — ${BACKEND_HEALTH_URL}`);
    const ok = await pollBackendHealth();
    if (ok) {
      backendStatus = { ready: true, error: null };
      if (win && !win.isDestroyed()) {
        win.webContents.send("backend-status-update", backendStatus);
      }
      return;
    }
    await new Promise((res) => setTimeout(res, BACKEND_POLL_INTERVAL_MS));
  }
  backendStatus = {
    ready: false,
    error: "Backend failed to start after 120 seconds. Please restart the application.",
  };
  if (win && !win.isDestroyed()) {
    win.webContents.send("backend-status-update", backendStatus);
  }
}

function watchFullscreen() {
  // fullscreen hiding disabled
}

function setupAutoUpdater() {
  if (isDev) return;

  // Portable builds (PORTABLE_EXECUTABLE_DIR is set by electron-builder for portable targets).
  // electron-updater does NOT support portable EXE self-update reliably and, with
  // autoDownload:true, would download the update and immediately call quitAndInstall()
  // — which causes the app to silently close ~2 s after launch.
  if (process.env.PORTABLE_EXECUTABLE_DIR) {
    console.log("Auto-updater disabled for portable build.");
    return;
  }

  try {
    const { autoUpdater } = require("electron-updater");

    autoUpdater.autoDownload = false; // Never download automatically; user must consent.
    autoUpdater.on("error", (err) => console.error("Auto-update error:", err?.message || err));
    autoUpdater.on("update-available", () => console.log("Update available"));
    autoUpdater.on("update-not-available", () => console.log("No update available"));
    autoUpdater.on("update-downloaded", () => {
      console.log("Update downloaded; will install on next restart.");
      // Do NOT call quitAndInstall() automatically — let the user decide.
    });

    autoUpdater.checkForUpdatesAndNotify().catch((err) => {
      console.error("Update check failed:", err?.message || err);
    });
  } catch (err) {
    console.error("setupAutoUpdater threw:", err?.message || err);
  }
}

function startBundledBackend() {
  if (isDev || backendProcess) return;

  const candidatePaths = [
    path.join(process.resourcesPath, 'backend', 'jarvis-backend.exe'),
    path.join(path.dirname(process.execPath), 'resources', 'backend', 'jarvis-backend.exe'),
    path.join(app.getPath('exe'), '..', 'resources', 'backend', 'jarvis-backend.exe'),
    path.join(app.getAppPath(), '..', 'backend', 'jarvis-backend.exe'),
  ].filter(Boolean);

  candidatePaths.forEach(p => console.log('Checking backend path:', p, '→ exists:', fs.existsSync(p)));

  const backendExe = candidatePaths.find((p) => fs.existsSync(p));
  if (!backendExe) {
    console.error("Bundled backend executable not found. Checked:", candidatePaths);
    return;
  }

  const backendDataDir = path.join(app.getPath("userData"), "backend-data");
  fs.mkdirSync(backendDataDir, { recursive: true });
  const backendLogDir = path.join(app.getPath("userData"), "logs");
  fs.mkdirSync(backendLogDir, { recursive: true });
  const backendOutLog = path.join(backendLogDir, "backend-stdout.log");
  const backendErrLog = path.join(backendLogDir, "backend-stderr.log");

  try {
    const { execSync } = require('child_process');
    const result = execSync('netstat -ano | findstr :8000').toString();
    const lines = result.trim().split('\n');
    for (const line of lines) {
      if (line.includes('LISTENING')) {
        const pid = line.trim().split(/\s+/).pop();
        execSync(`taskkill /F /PID ${pid}`);
        console.log(`Killed process on port 8000: PID ${pid}`);
      }
    }
  } catch(e) {
    // port was free, no action needed
  }

  backendProcess = spawn(backendExe, [], {
    cwd: path.dirname(backendExe),
    env: {
      ...process.env,
      AI_LIFE_DATA_DIR: backendDataDir,
      DEBUG: "false",
    },
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
  });

  if (backendProcess.stdout) {
    backendProcess.stdout.on("data", (chunk) => {
      try {
        fs.appendFileSync(backendOutLog, chunk);
      } catch {
        // no-op
      }
    });
  }
  if (backendProcess.stderr) {
    backendProcess.stderr.on("data", (chunk) => {
      try {
        fs.appendFileSync(backendErrLog, chunk);
      } catch {
        // no-op
      }
    });
  }

  backendProcess.on("error", (err) => {
    console.error("Failed to start bundled backend:", err?.message || err);
  });

  backendProcess.on("exit", (code, signal) => {
    console.log("Bundled backend exited:", { code, signal });
    backendProcess = null;
  });
}

function stopBundledBackend() {
  if (!backendProcess || backendProcess.killed) return;
  backendProcess.kill();
}

function createWindow() {
  app.setLoginItemSettings({
    openAtLogin: true,
    path: app.getPath("exe"),
  });

  session.defaultSession.setPermissionRequestHandler((_, permission, callback) => {
    if (permission === "media" || permission === "audio-capture" || permission === "video-capture") {
      callback(true);
      return;
    }
    callback(false);
  });
  session.defaultSession.setDevicePermissionHandler(() => true);

  const { width, height, x, y } = screen.getPrimaryDisplay().workArea;

  win = new BrowserWindow({
    width,
    height,
    x,
    y,
    frame: false,
    transparent: true,
    resizable: false,
    hasShadow: true,
    skipTaskbar: false,
    autoHideMenuBar: true,
    webPreferences: {
      // FIX: secure webPreferences - no Node.js access in renderer
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      preload: PRELOAD_PATH,
      // NOTE: removed deprecated enableRemoteModule: true
      // audio is not a valid webPreference key - handled by media permissions above
    },
  });

  win.setBackgroundColor("#00000000");
  revealMainWindow();

  if (isDev) {
    const tryLoad = () => {
      win.loadURL(`${DEV_SERVER_URL}/#/splash`).catch(() => setTimeout(tryLoad, 1000));
    };
    tryLoad();
  } else {
    loadRenderer(win, "/splash");
  }

  if (isDev) {
    win.webContents.openDevTools({ mode: "detach" });
  }
}

app.whenReady().then(async () => {
  // ── Logging setup ─────────────────────────────────────────────────────────
  // Wrapped in its own try-catch: if the userData dir is somehow
  // unavailable we still want the rest of the app to start.
  try {
    const logFile = path.join(app.getPath('userData'), 'logs', 'electron-main.log');
    fs.mkdirSync(path.dirname(logFile), { recursive: true });
    const logStream = fs.createWriteStream(logFile, { flags: 'a' });
    console.log = (...args) => { logStream.write(args.join(' ') + '\n'); process.stdout.write(args.join(' ') + '\n'); };
    console.error = (...args) => { logStream.write('[ERR] ' + args.join(' ') + '\n'); process.stderr.write(args.join(' ') + '\n'); };
    console.log(`[startup] Jarvis starting — packaged=${app.isPackaged} portable=${!!process.env.PORTABLE_EXECUTABLE_DIR} isDev=${isDev}`);
  } catch (logErr) {
    process.stderr.write('[ERR] Could not initialise log file: ' + (logErr?.message || logErr) + '\n');
  }

  app.setAppUserModelId("com.jarvis.assistant");

  // ── Secure store ──────────────────────────────────────────────────────────
  try {
    const { default: Store } = await import("electron-store");
    secureStore = new Store({ name: "jarvis-secure-store" });
  } catch (err) {
    console.error("Failed to initialize electron-store:", err?.message || err);
  }

  // ── Core startup — must not throw past here ────────────────────────────────
  try {
    startBundledBackend();
  } catch (err) {
    console.error("startBundledBackend threw:", err?.message || err);
  }

  createWindow();
  waitForBackend(BACKEND_TIMEOUT_MS); // fire-and-forget; sends IPC updates to the splash screen
  setupAutoUpdater();
});

app.on("second-instance", () => {
  revealMainWindow();
});

app.on("window-all-closed", () => {
  stopBundledBackend();
  if (fullscreenWatchTimer) {
    clearInterval(fullscreenWatchTimer);
    fullscreenWatchTimer = null;
  }
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  stopBundledBackend();
});