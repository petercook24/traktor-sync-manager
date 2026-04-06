// This is the main process file for Electron.
var _a = require('electron'), app = _a.app, BrowserWindow = _a.BrowserWindow;
function createWindow() {
    // Create the browser window.
    var mainWindow = new BrowserWindow({
        width: 800,
        height: 600,
        webPreferences: {
            nodeIntegration: true,
        }
    });
    // Load index.html into the new BrowserWindow.
    const indexPath = path.join(__dirname, '..', '..', 'public', 'index.html');
    console.log('index path is:' + indexPath);
        console.log(`__filename is ${__filename}`);
    console.log(`__dirname is ${__dirname}`);
    console.log(`indexPath is ${indexPath}`);
    mainWindow.loadFile(indexPath);    
}
app.whenReady().then(createWindow);
app.on('window-all-closed', function () {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});
app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
    }
});
