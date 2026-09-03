const { app, BrowserWindow, dialog } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

let backend;

function apiIsReady() {
  return new Promise((resolve) => {
    const request = http.get('http://127.0.0.1:8000/', (response) => {
      response.resume();
      resolve(response.statusCode === 200);
    });
    request.on('error', () => resolve(false));
    request.setTimeout(500, () => { request.destroy(); resolve(false); });
  });
}

async function waitForApi() {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    if (await apiIsReady()) return true;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  return false;
}

async function createWindow() {
  const backendDir = app.isPackaged
    ? path.join(process.resourcesPath, 'app.asar.unpacked', 'backend')
    : path.join(__dirname, '..', 'backend');
  backend = spawn('python', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'], {
    cwd: backendDir,
    windowsHide: true,
  });
  backend.on('error', (error) => dialog.showErrorBox('Backend xatosi', `Python ishga tushmadi: ${error.message}`));

  const ready = await waitForApi();
  if (!ready) {
    dialog.showErrorBox('ExcelYordamchi AI', 'Backend ishga tushmadi. Python va loyiha kutubxonalari o‘rnatilganini tekshiring.');
    app.quit();
    return;
  }
  const window = new BrowserWindow({
    width: 1450,
    height: 900,
    minWidth: 980,
    minHeight: 680,
    autoHideMenuBar: true,
    title: 'ExcelYordamchi AI',
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  });
  await window.loadFile(path.join(__dirname, '..', 'frontend', 'dist', 'index.html'));
}

app.whenReady().then(createWindow);
app.on('window-all-closed', () => app.quit());
app.on('before-quit', () => { if (backend && !backend.killed) backend.kill(); });
