# 🎛️ Traktor Sync Manager

A desktop tool to export Traktor playlists to a USB drive and sync iTunes/Apple Music playlists directly into Traktor — with a clean browser-based UI.

---

## Features

- **Export playlists** from Traktor as `.nml` files to any folder or USB drive
- **Copy audio files** alongside the playlists into the same destination folder
- **Sync from iTunes** — pick iTunes playlists and create/update them inside Traktor's `collection.nml`
- **Interactive playlist selector** — tick/untick individual playlists or use All/None
- **Folder browser** — navigate your drives and create new folders from within the app
- **Smart skip** — never overwrites existing files, skips them automatically
- **Auto-detects** your Traktor collection and iTunes library on startup

---

## Requirements

Only needed if running from source (not the `.exe`):

- Python 3.8+
- Flask — `pip install flask`

---

## Running from source

```
project/
├── launch.py
├── traktor_server.py
└── public/
     ├── index.html
     └── favicon.ico
```

```cmd
pip install flask
python launch.py
```

The app will open automatically in your browser at `http://localhost:5123`.  
Close the browser tab to shut the server down completely.

---

## Building the executable (Windows)

```cmd
pip install pyinstaller
python -m PyInstaller --onefile --noconsole --name "Traktor Exporter" --add-data "public;public" launch.py
```

The finished `.exe` will be in the `dist/` folder. Double-click it — no Python or terminal needed.

> **Note:** Windows Defender may show a SmartScreen warning on first run since the exe is unsigned. Click **More info → Run anyway** to proceed.

---

## How to use

### Export Tab

1. The app auto-fills your `collection.nml` path — or paste it manually and click **Load**
2. Tick the playlists you want to export
3. Use the folder browser on the right to pick a destination (your USB drive, a local folder, etc.)
4. Toggle **Copy audio** on if you want the actual track files copied alongside the `.nml`
5. Click **Export →**

Each playlist is saved as a separate `.nml` file that Traktor can import directly.

### Sync from iTunes Tab

1. The app auto-fills your iTunes library path — or paste it manually and click **Load**
2. Tick the iTunes playlists you want to bring into Traktor
3. Confirm the `collection.nml` path at the top
4. Click **Sync to Traktor →**

> ⚠️ **Close Traktor before syncing.** If Traktor is open it will overwrite the file when it exits and your changes will be lost.

Syncing will:
- Add any new tracks to Traktor's `COLLECTION`
- Create the playlist in Traktor if it doesn't exist
- Replace it if a playlist with the same name already exists
- Never move or copy audio files — only the references are updated

---

## File structure (source)

| File | Purpose |
|---|---|
| `launch.py` | Entry point — starts the server and opens the browser |
| `traktor_server.py` | Flask backend — all file parsing and export logic |
| `public/index.html` | React frontend UI |
| `public/favicon.ico` | Browser tab icon |

---

## Troubleshooting

**collection.nml not auto-detected**  
Paste the path manually. You can find it at:
```
C:\Users\<you>\Documents\Native Instruments\Traktor <version>\collection.nml
```

**iTunes library not auto-detected**  
Paste the path manually. It's usually at:
```
C:\Users\<you>\Music\iTunes\iTunes Music Library.xml
```

**Antivirus blocks the exe**  
This is normal for unsigned executables. Add an exception in Windows Defender or click "More info → Run anyway" on the SmartScreen popup.

**Port 5123 already in use**  
Another instance of the app is already running. Open Task Manager and kill any existing "Traktor Exporter" process, then try again.

**Tracks show as "not found" after export**  
The source audio files are missing from the paths stored in your Traktor collection. This usually means the files were moved or are on a drive that wasn't connected at the time of export.
