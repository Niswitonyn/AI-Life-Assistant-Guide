const { app, BrowserWindow, screen, session, ipcMain } = require("electron");

console.log("🚀 Electron starting...");

let win = null;
let chatWin = null;

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

  // Debug (remove in production)
  win.webContents.openDevTools({ mode: "detach" });
}

// =========================
// APP EVENTS
// =========================

app.whenReady().then(createWindow);

app.on("second-instance", () => {
  if (win) win.focus();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});