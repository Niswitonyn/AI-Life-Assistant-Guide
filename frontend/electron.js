const { app, BrowserWindow, screen } = require("electron");

console.log("🚀 Electron starting...");

let win = null;

function createWindow() {

  console.log("🪟 Creating window...");

  const { width, height } = screen.getPrimaryDisplay().workAreaSize;

  win = new BrowserWindow({
    width: 220,
    height: 220,
    x: width - 240,   // bottom-right
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
    },
  });

  // Important for Windows transparency
  win.setBackgroundColor("#00000000");

  // Retry loader (wait for Vite)
  function loadApp() {
    console.log("🌐 Loading React...");
    win.loadURL("http://localhost:5173/").catch(() => {
      console.log("⏳ Waiting for Vite...");
      setTimeout(loadApp, 1000);
    });
  }

  loadApp();

  // Debug (remove later if you want)
  win.webContents.openDevTools({ mode: "detach" });
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});