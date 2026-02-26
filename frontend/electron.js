const {
  app,
  BrowserWindow,
  screen,
  session,
  ipcMain,
  powerMonitor,
  safeStorage
} = require("electron");
const Store = require("electron-store");

console.log("🚀 Electron starting...");

let win = null;
let chatWin = null;
let fullscreenWatchTimer = null;
const secureStore = new Store({ name: "jarvis-secure-store" });

// =========================
// SINGLE INSTANCE LOCK
// =========================

const gotLock = app.requestSingleInstanceLock();

if (!gotLock) {
  app.quit();
}

// =========================
// CHROMIUM FLAGS (Audio / Mic Stability)
// =========================

app.commandLine.appendSwitch("use-fake-ui-for-media-stream");
app.commandLine.appendSwitch("enable-speech-dispatcher");
app.commandLine.appendSwitch("enable-features", "AudioServiceOutOfProcess");
app.commandLine.appendSwitch(
  "disable-features",
  "IsolateOrigins,site-per-process"
);

// =========================
// CLICK THROUGH CONTROL
// =========================

function setClickThrough(enabled) {
  if (!win) return;

  win.setIgnoreMouseEvents(enabled, {
    forward: true,
  });

  console.log("🖱 Click-through:", enabled);
}

ipcMain.on("set-click-through", (_, enabled) => {
  setClickThrough(enabled);
});

// =========================
// CHAT WINDOW
// =========================

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

  chatWin.loadURL("http://localhost:5173/#/chat");

  chatWin.on("closed", () => {
    chatWin = null;
  });
}

ipcMain.on("open-chat", () => {
  createChatWindow();
});

// =========================
// OAUTH POPUP (ELECTRON NATIVE)
// =========================

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

// =========================
// SECURE TOKEN STORAGE (ELECTRON)
// =========================

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
  if (!key) return { status: "error", message: "Missing key" };
  const serialized = typeof value === "string" ? value : JSON.stringify(value);
  secureStore.set(key, encryptValue(serialized));
  return { status: "ok" };
});

ipcMain.handle("secure-get", (_, key) => {
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
  if (!key) return { status: "error", message: "Missing key" };
  secureStore.delete(key);
  return { status: "ok" };
});

// =========================
// AUTO HIDE IN FULLSCREEN
// =========================

function watchFullscreen() {
  if (fullscreenWatchTimer) {
    clearInterval(fullscreenWatchTimer);
  }

  fullscreenWatchTimer = setInterval(() => {
    if (!win || win.isDestroyed()) return;

    const isFull =
      win.isFullScreen() ||
      win.isAlwaysOnTop() === false;

    if (isFull) {
      if (win.isVisible()) {
        win.hide();
      }
    } else if (!win.isVisible()) {
      win.showInactive();
    }
  }, 2000);
}

// =========================
// MAIN WINDOW
// =========================

function createWindow() {
  console.log("🪟 Creating window...");

  // ⭐ Auto-start with Windows
  app.setLoginItemSettings({
    openAtLogin: true,
    path: app.getPath("exe"),
  });

  // =========================
  // PERMISSIONS
  // =========================

  session.defaultSession.setPermissionRequestHandler(
    (webContents, permission, callback) => {
      if (
        permission === "media" ||
        permission === "audio-capture" ||
        permission === "video-capture"
      ) {
        console.log("✅ Media permission granted");
        callback(true);
      } else {
        callback(false);
      }
    }
  );

  session.defaultSession.setDevicePermissionHandler(() => true);

  // =========================
  // WINDOW POSITION
  // =========================

  const { width, height } =
    screen.getPrimaryDisplay().workAreaSize;

  win = new BrowserWindow({
    width: 220,
    height: 220,

    x: width - 240,
    y: height - 260,

    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    hasShadow: false,
    skipTaskbar: true,

    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      sandbox: false,
      enableRemoteModule: true,
      audio: true,
    },
  });

  win.setBackgroundColor("#00000000");

  // =========================
  // LOAD REACT WITH RETRY
  // =========================

  function loadApp() {
    console.log("🌐 Loading React...");

    win.loadURL("http://localhost:5173/")
      .catch(() => {
        console.log("⏳ Waiting for Vite...");
        setTimeout(loadApp, 1000);
      });
  }

  loadApp();

  watchFullscreen();

  // Debug (remove in production)
  win.webContents.openDevTools({ mode: "detach" });
}

// =========================
// APP EVENTS
// =========================

app.whenReady().then(() => {
  createWindow();
  powerMonitor.on("resume", watchFullscreen);
});

app.on("second-instance", () => {
  if (win) win.focus();
});

app.on("window-all-closed", () => {
  if (fullscreenWatchTimer) {
    clearInterval(fullscreenWatchTimer);
    fullscreenWatchTimer = null;
  }
  if (process.platform !== "darwin") {
    app.quit();
  }
});
