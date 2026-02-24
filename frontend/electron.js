const { app, BrowserWindow, screen } = require("electron");

let win = null;

function createWindow() {

  const { width, height } = screen.getPrimaryDisplay().workAreaSize;

  win = new BrowserWindow({
    width: 300,
    height: 300,
    x: 100,
    y: 100,
    frame: true,
    transparent: false,
    alwaysOnTop: true,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    },
  });

  // Wait a little before loading React
  setTimeout(() => {
    win.loadURL("http://localhost:5173");
  }, 2000);

  win.webContents.openDevTools({ mode: "detach" });
}

app.whenReady().then(createWindow);