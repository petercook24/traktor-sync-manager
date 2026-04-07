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

## Getting Started

Open the application (.exe)
Your browser will launch automatically
Use the interface to export or sync playlists

Closing the browser tab will completely shut down the app.

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
