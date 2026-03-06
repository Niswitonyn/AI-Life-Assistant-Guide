const { contextBridge, ipcRenderer, shell } = require("electron");

// Expose only the specific IPC channels the React app needs.
// The renderer has NO access to Node.js or Electron internals beyond this.
contextBridge.exposeInMainWorld("electronAPI", {
  // Window controls
  setClickThrough: (enabled) => ipcRenderer.send("set-click-through", enabled),
  openChat: () => ipcRenderer.send("open-chat"),
  closeChat: () => ipcRenderer.send("close-chat"),
  openSettings: () => ipcRenderer.send("open-settings"),
  openMain: () => ipcRenderer.send("open-main"),
  closeApp: () => ipcRenderer.send("close-app"),

  // Shell controls
  openExternal: (url) => shell.openExternal(url),

  // OAuth popup
  openOAuthPopup: (url) => ipcRenderer.invoke("open-oauth-popup", url),

  // Secure storage
  secureSet: (key, value) => ipcRenderer.invoke("secure-set", key, value),
  secureGet: (key) => ipcRenderer.invoke("secure-get", key),
  secureDelete: (key) => ipcRenderer.invoke("secure-delete", key),
});
