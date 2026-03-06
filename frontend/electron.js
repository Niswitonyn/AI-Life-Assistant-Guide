const path = require("path");
const fs = require("fs");
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

const isDev = !app.isPackaged;
const DEV_SERVER_URL = process.env.ELECTRON_RENDERER_URL || "http://localhost:5173";
const DIST_INDEX = path.join(__dirname, "dist", "index.html");

let win = null;
let chatWin = null;
let fullscreenWatchTimer = null;
let secureStore = null;
let backendProcess = null;

const gotLock = isDev ? true : app.requestSingleInstanceLock();
if (!gotLock) {
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
  win.setAlwaysOnTop(true, "screen-saver");
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
    width: 420,
    height: 600,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: true,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      sandbox: false,
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

function watchFullscreen() {
  if (fullscreenWatchTimer) clearInterval(fullscreenWatchTimer);

  fullscreenWatchTimer = setInterval(() => {
    if (!win || win.isDestroyed()) return;

    // Only hide when the window itself is fullscreen.
    // Relying on isAlwaysOnTop() can incorrectly hide Jarvis on some systems.
    const isFull = win.isFullScreen();
    if (isFull) {
      if (win.isVisible()) win.hide();
    } else if (!win.isVisible()) {
      win.showInactive();
    }
  }, 2000);
}

function setupAutoUpdater() {
  if (isDev) return;
  const { autoUpdater } = require("electron-updater");

  autoUpdater.autoDownload = true;
  autoUpdater.on("error", (err) => console.error("Auto-update error:", err?.message || err));
  autoUpdater.on("update-available", () => console.log("Update available"));
  autoUpdater.on("update-not-available", () => console.log("No update available"));
  autoUpdater.on("update-downloaded", () => {
    console.log("Update downloaded; installing...");
    autoUpdater.quitAndInstall();
  });

  autoUpdater.checkForUpdatesAndNotify().catch((err) => {
    console.error("Update check failed:", err?.message || err);
  });
}

function startBundledBackend() {
  if (isDev || backendProcess) return;

  const candidatePaths = [
    path.join(process.resourcesPath, "backend", "jarvis-backend.exe"),
    path.join(path.dirname(process.execPath), "resources", "backend", "jarvis-backend.exe"),
    process.env.PORTABLE_EXECUTABLE_DIR
      ? path.join(process.env.PORTABLE_EXECUTABLE_DIR, "resources", "backend", "jarvis-backend.exe")
      : null,
  ].filter(Boolean);

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
  const windowWidth = width;
  const windowHeight = height;
  const initialX = x;
  const initialY = y;

  win = new BrowserWindow({
    width: windowWidth,
    height: windowHeight,
    x: initialX,
    y: initialY,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    hasShadow: true,
    skipTaskbar: false,
    autoHideMenuBar: true,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      sandbox: false,
      enableRemoteModule: true,
      audio: true,
    },
  });

  win.setBackgroundColor("#00000000");
  revealMainWindow();

  if (isDev) {
    const tryLoad = () => {
      win.loadURL(`${DEV_SERVER_URL}/#/login`).catch(() => setTimeout(tryLoad, 1000));
    };
    tryLoad();
  } else {
    loadRenderer(win, "/login");
  }

  watchFullscreen();

  if (isDev) {
    win.webContents.openDevTools({ mode: "detach" });
  }
}

app.whenReady().then(() => {
  import("electron-store")
    .then(({ default: Store }) => {
      secureStore = new Store({ name: "jarvis-secure-store" });
    })
    .catch((err) => {
      console.error("Failed to initialize electron-store:", err?.message || err);
    });

  app.setAppUserModelId("com.jarvis.assistant");
  startBundledBackend();
  createWindow();
  setupAutoUpdater();
  powerMonitor.on("resume", watchFullscreen);
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
