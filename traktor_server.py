#!/usr/bin/env python3
"""
Traktor Exporter — Backend Server
Serves the React UI and handles all file operations via a JSON API.

Install deps:  pip install flask
Run:           python traktor_server.py
Then open:     http://localhost:5123
"""

import os, sys, re, shutil, json, threading, uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.dom import minidom
from flask import Flask, jsonify, request, send_from_directory

try:
    from flask_cors import CORS
    _has_cors = True
except ImportError:
    _has_cors = False

# Resolve UI folder — works both as a plain script and as a PyInstaller exe
def _get_base_dir():
    if getattr(__import__("sys"), "frozen", False):
        return __import__("sys")._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

_ui_dir = os.environ.get("TRAKTOR_UI_DIR", os.path.join(_get_base_dir(), "public"))

app = Flask(__name__, static_folder=_ui_dir, static_url_path="")
if _has_cors:
    CORS(app)
else:
    @app.after_request
    def add_cors(r):
        r.headers["Access-Control-Allow-Origin"] = "*"
        r.headers["Access-Control-Allow-Headers"] = "Content-Type"
        r.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return r

# ── Helpers ────────────────────────────────────────────────────────────────────

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip()

def human_size(n):
    for u in ("B","KB","MB","GB"):
        if n < 1024: return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"

def traktor_path_to_os(volume, path_str):
    if not path_str: return ""
    clean = re.sub(r"^/:", "", path_str).replace("/:", os.sep)
    if sys.platform == "win32":
        return str(Path(volume) / clean) if volume else clean
    return os.sep + clean

def os_path_to_traktor(path_str):
    """Convert a normal OS path to Traktor's volume / dir / file components."""
    p = Path(path_str)
    if sys.platform == "win32":
        drive    = p.drive                          # e.g. "G:"
        parts    = list(p.parts[1:])               # parts after drive
        filename = parts[-1] if parts else ""
        folders  = parts[:-1]
        dir_str  = "".join(f"/:{f}" for f in folders) + "/:" if folders else "/:"
        return drive, dir_str, filename
    else:
        parts    = list(p.parts)
        filename = parts[-1] if len(parts) > 1 else ""
        folders  = parts[1:-1]
        dir_str  = "".join(f"/:{f}" for f in folders) + "/:" if folders else "/:"
        return "", dir_str, filename

def traktor_key_to_path(key):
    """Convert a Traktor PRIMARYKEY value (G:/:Music/:track.mp3) to an OS path."""
    if not key: return ""
    m = re.match(r"^([A-Za-z]:)(.*)", key)
    if m:
        drive = m.group(1)
        rest  = re.sub(r"^/:", "", m.group(2))
        parts = rest.split("/:")
        return drive + "\\" + "\\".join(parts)
    clean = re.sub(r"^/:", "", key).replace("/:", os.sep)
    return os.sep + clean

# ── Traktor NML detection ──────────────────────────────────────────────────────

def find_collection_nml():
    """Auto-detect the latest Traktor version's collection.nml."""
    home = Path.home()

    # Search these parent directories for any Traktor versioned folder
    search_roots = [
        home / "Documents" / "Native Instruments",
        home / "OneDrive" / "Documents" / "Native Instruments",
        home / "OneDrive - Personal" / "Documents" / "Native Instruments",
        # Also search one level deeper in case there's a plain "Traktor" subfolder
        home / "Documents" / "Native Instruments" / "Traktor",
        home / "OneDrive" / "Documents" / "Native Instruments" / "Traktor",
    ]

    versioned = []

    for root in search_roots:
        if not root.exists():
            continue
        try:
            for d in root.iterdir():
                if not d.is_dir():
                    continue
                # Match "Traktor 3.11.1", "Traktor Pro 3.11.1", etc.
                m = re.search(r"(\d+)\.(\d+)\.(\d+)", d.name)
                if m and d.name.lower().startswith("traktor"):
                    nml = d / "collection.nml"
                    if nml.exists():
                        version_tuple = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
                        versioned.append((version_tuple, nml))
                # Plain "Traktor" folder with flat collection.nml inside
                if d.name.lower() == "traktor":
                    flat = d / "collection.nml"
                    if flat.exists():
                        versioned.append(((0, 0, 0), flat))
        except PermissionError:
            continue

        # Also check collection.nml directly inside the root itself
        flat = root / "collection.nml"
        if flat.exists():
            versioned.append(((0, 0, 0), flat))

    if versioned:
        versioned.sort(key=lambda x: x[0], reverse=True)
        return str(versioned[0][1])

    return None

# ── iTunes / Music library parsing ────────────────────────────────────────────

def find_itunes_library():
    """Try to auto-detect iTunes / Apple Music library XML."""
    candidates = []
    if sys.platform == "win32":
        candidates = [
            Path.home() / "Music" / "iTunes" / "iTunes Music Library.xml",
            Path.home() / "Music" / "iTunes" / "iTunes Library.xml",
        ]
    elif sys.platform == "darwin":
        candidates = [
            Path.home() / "Music" / "iTunes" / "iTunes Music Library.xml",
            Path.home() / "Music" / "Music" / "iTunes Music Library.xml",
            Path.home() / "Music" / "iTunes" / "iTunes Library.xml",
        ]
    for p in candidates:
        if p.exists(): return str(p)
    return None

def parse_itunes_library(xml_path):
    """
    Parse iTunes/Music Library XML and return list of playlists with tracks.
    iTunes XML uses Apple's plist format.
    """
    import plistlib
    with open(xml_path, "rb") as f:
        lib = plistlib.load(f)

    # Build track id -> track info map
    raw_tracks = lib.get("Tracks", {})
    tracks = {}
    for tid, t in raw_tracks.items():
        loc = t.get("Location", "")
        # Convert file:// URL to OS path
        if loc.startswith("file://"):
            from urllib.parse import unquote
            loc = unquote(loc[7:])
            if sys.platform == "win32":
                loc = loc.lstrip("/").replace("/", "\\")
        tracks[tid] = {
            "path":   loc,
            "title":  t.get("Name", ""),
            "artist": t.get("Artist", ""),
            "album":  t.get("Album", ""),
        }

    playlists = []
    for pl in lib.get("Playlists", []):
        name = pl.get("Name", "Unnamed")
        # Skip system playlists
        if pl.get("Master") or pl.get("Music") or pl.get("Movies") \
           or pl.get("TV Shows") or pl.get("Podcasts") or pl.get("Audiobooks") \
           or pl.get("Purchased Music") or pl.get("Distinguished Kind"):
            continue
        items = pl.get("Playlist Items", [])
        entries = []
        for item in items:
            tid = str(item.get("Track ID", ""))
            if tid in tracks:
                entries.append(tracks[tid])
        if entries:
            playlists.append({"name": name, "tracks": entries})

    return playlists

# ── Traktor NML parsing ────────────────────────────────────────────────────────

def parse_nml(nml_path):
    tree = ET.parse(nml_path)
    root = tree.getroot()

    tracks = {}
    collection = root.find("COLLECTION")
    if collection is not None:
        for entry in collection.findall("ENTRY"):
            loc = entry.find("LOCATION")
            if loc is None: continue
            volume    = loc.get("VOLUME", "")
            dir_attr  = loc.get("DIR", "")
            file_attr = loc.get("FILE", "")
            key  = volume + dir_attr + file_attr
            path = traktor_path_to_os(volume, dir_attr + file_attr)
            tracks[key] = {
                "path":   path,
                "title":  entry.get("TITLE", ""),
                "artist": entry.get("ARTIST", ""),
            }

    playlists = []

    def recurse(node, prefix=""):
        for child in list(node):
            tag   = child.tag
            name  = child.get("NAME", "Unnamed")
            ntype = child.get("TYPE", "")
            if tag == "SUBNODES":
                recurse(child, prefix=prefix)
            elif tag == "NODE" and ntype == "PLAYLIST":
                entries = []
                pl_node = child.find("PLAYLIST")
                if pl_node is not None:
                    for e in pl_node.findall("ENTRY"):
                        pk = e.find("PRIMARYKEY")
                        if pk is None: continue
                        k = pk.get("KEY", "")
                        if k in tracks:
                            entries.append(tracks[k])
                        else:
                            entries.append({"path": traktor_key_to_path(k), "title": "", "artist": ""})
                playlists.append({"name": (prefix + name) if prefix else name, "tracks": entries})
            elif tag == "NODE" and ntype == "FOLDER":
                new_prefix = (prefix + name + " - ") if name != "$ROOT" else prefix
                recurse(child, prefix=new_prefix)

    sets = root.find(".//PLAYLISTS")
    if sets is not None:
        recurse(sets)
    return playlists

# ── NML builder ───────────────────────────────────────────────────────────────

def build_nml_for_playlist(playlist, dest_path, copy_tracks):
    """Build a Traktor-compatible NML string for a single playlist."""
    nml = ET.Element("NML", attrib={"VERSION": "19"})
    ET.SubElement(nml, "HEAD", attrib={"COMPANY": "www.native-instruments.com", "PROGRAM": "Traktor"})
    collection = ET.SubElement(nml, "COLLECTION", attrib={"ENTRIES": str(len(playlist["tracks"]))})
    sets      = ET.SubElement(nml, "PLAYLISTS")
    root_node = ET.SubElement(sets, "NODE", attrib={"TYPE": "FOLDER", "NAME": "$ROOT"})
    subnodes  = ET.SubElement(root_node, "SUBNODES", attrib={"COUNT": "1"})
    pl_node   = ET.SubElement(subnodes, "NODE", attrib={"TYPE": "PLAYLIST", "NAME": playlist["name"]})
    pl_el     = ET.SubElement(pl_node, "PLAYLIST", attrib={
        "ENTRIES": str(len(playlist["tracks"])),
        "TYPE":    "LIST",
        "UUID":    uuid.uuid4().hex,
    })

    for t in playlist["tracks"]:
        src        = Path(t["path"])
        final_path = str(dest_path / src.name) if (copy_tracks and src.exists()) else t["path"]
        volume, dir_str, filename = os_path_to_traktor(final_path)

        entry = ET.SubElement(collection, "ENTRY", attrib={
            "TITLE":  t.get("title", src.stem),
            "ARTIST": t.get("artist", ""),
        })
        ET.SubElement(entry, "LOCATION", attrib={
            "DIR": dir_str, "FILE": filename,
            "VOLUME": volume, "VOLUMEID": volume,
        })
        pl_entry = ET.SubElement(pl_el, "ENTRY")
        ET.SubElement(pl_entry, "PRIMARYKEY", attrib={
            "TYPE": "TRACK",
            "KEY":  volume + dir_str + filename,
        })

    raw    = ET.tostring(nml, encoding="unicode")
    pretty = minidom.parseString(raw).toprettyxml(indent="\t", encoding=None)
    lines  = pretty.splitlines()
    if lines and lines[0].startswith("<?xml"):
        lines = lines[1:]
    return "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"no\" ?>\n" + "\n".join(lines)

# ── Traktor collection updater (iTunes sync) ──────────────────────────────────

def sync_itunes_to_traktor(nml_path, itunes_playlists):
    """
    Add/update iTunes playlists inside Traktor's collection.nml in-place.
    - Adds missing tracks to COLLECTION
    - Creates or replaces matching playlists under PLAYLISTS/$ROOT
    Returns (added_tracks, updated_playlists, created_playlists).
    """
    tree = ET.parse(nml_path)
    root = tree.getroot()

    # ── Existing tracks index by filename (best-effort match) ──
    collection = root.find("COLLECTION")
    if collection is None:
        collection = ET.SubElement(root, "COLLECTION", attrib={"ENTRIES": "0"})

    existing_keys = set()
    for entry in collection.findall("ENTRY"):
        loc = entry.find("LOCATION")
        if loc is not None:
            existing_keys.add(loc.get("VOLUME","") + loc.get("DIR","") + loc.get("FILE",""))

    # ── PLAYLISTS root node ──
    sets = root.find(".//PLAYLISTS")
    if sets is None:
        sets = ET.SubElement(root, "PLAYLISTS")
    root_folder = sets.find("NODE[@NAME='$ROOT']")
    if root_folder is None:
        root_folder = ET.SubElement(sets, "NODE", attrib={"TYPE":"FOLDER","NAME":"$ROOT"})
    subnodes = root_folder.find("SUBNODES")
    if subnodes is None:
        subnodes = ET.SubElement(root_folder, "SUBNODES", attrib={"COUNT":"0"})

    added_tracks     = 0
    updated_pls      = []
    created_pls      = []

    for pl in itunes_playlists:
        pl_name = pl["name"]

        # Build / update COLLECTION entries for this playlist's tracks
        pl_keys = []
        for t in pl["tracks"]:
            volume, dir_str, filename = os_path_to_traktor(t["path"])
            key = volume + dir_str + filename
            pl_keys.append(key)
            if key not in existing_keys:
                entry = ET.SubElement(collection, "ENTRY", attrib={
                    "TITLE":  t.get("title",""),
                    "ARTIST": t.get("artist",""),
                })
                ET.SubElement(entry, "LOCATION", attrib={
                    "DIR": dir_str, "FILE": filename,
                    "VOLUME": volume, "VOLUMEID": volume,
                })
                existing_keys.add(key)
                added_tracks += 1

        # Find existing playlist node by name
        existing_pl_node = subnodes.find(f"NODE[@NAME='{pl_name}'][@TYPE='PLAYLIST']")
        if existing_pl_node is not None:
            subnodes.remove(existing_pl_node)
            updated_pls.append(pl_name)
        else:
            created_pls.append(pl_name)

        # Create fresh playlist node
        new_node = ET.SubElement(subnodes, "NODE", attrib={"TYPE":"PLAYLIST","NAME":pl_name})
        new_pl   = ET.SubElement(new_node, "PLAYLIST", attrib={
            "ENTRIES": str(len(pl_keys)),
            "TYPE":    "LIST",
            "UUID":    uuid.uuid4().hex,
        })
        for key in pl_keys:
            e = ET.SubElement(new_pl, "ENTRY")
            ET.SubElement(e, "PRIMARYKEY", attrib={"TYPE":"TRACK","KEY":key})

    # Update counts
    collection.set("ENTRIES", str(len(collection.findall("ENTRY"))))
    subnodes.set("COUNT", str(len(subnodes)))

    # Write back
    raw    = ET.tostring(root, encoding="unicode")
    pretty = minidom.parseString(raw).toprettyxml(indent="\t", encoding=None)
    lines  = pretty.splitlines()
    if lines and lines[0].startswith("<?xml"):
        lines = lines[1:]
    output = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"no\" ?>\n" + "\n".join(lines)
    Path(nml_path).write_text(output, encoding="utf-8")

    return added_tracks, updated_pls, created_pls

# ── Progress state ─────────────────────────────────────────────────────────────
progress_log  = []
progress_done = False

# ── API Routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(_ui_dir, "index.html")

@app.route("/api/detect-nml")
def detect_nml():
    return jsonify({"path": find_collection_nml()})

@app.route("/api/parse-nml")
def api_parse_nml():
    path = request.args.get("path","")
    if not path or not Path(path).exists():
        return jsonify({"error": "File not found"}), 404
    try:
        playlists = parse_nml(path)
        result = [{"name": pl["name"], "count": len(pl["tracks"])} for pl in playlists]
        return jsonify({"playlists": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/detect-itunes")
def detect_itunes():
    return jsonify({"path": find_itunes_library()})

@app.route("/api/parse-itunes")
def api_parse_itunes():
    path = request.args.get("path","")
    if not path or not Path(path).exists():
        return jsonify({"error": "File not found"}), 404
    try:
        playlists = parse_itunes_library(path)
        result = [{"name": pl["name"], "count": len(pl["tracks"])} for pl in playlists]
        return jsonify({"playlists": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/sync-itunes", methods=["POST"])
def api_sync_itunes():
    global progress_log, progress_done
    data          = request.json
    itunes_path   = data.get("itunes_path","")
    nml_path      = data.get("nml_path","")
    selected      = data.get("selected", [])

    if not itunes_path or not nml_path or not selected:
        return jsonify({"error": "Missing parameters"}), 400

    progress_log  = []
    progress_done = False

    def run():
        global progress_done
        try:
            all_playlists = parse_itunes_library(itunes_path)
            chosen = [pl for pl in all_playlists if pl["name"] in selected]
            progress_log.append({"type":"ok","msg": f"Syncing {len(chosen)} playlist(s) to Traktor…"})

            added, updated, created = sync_itunes_to_traktor(nml_path, chosen)

            for name in created:
                progress_log.append({"type":"ok",   "msg": f"  ✓ Created:  {name}"})
            for name in updated:
                progress_log.append({"type":"ok",   "msg": f"  ↻ Updated:  {name}"})

            summary = {
                "pl_exported": len(created) + len(updated),
                "pl_skipped":  0,
                "tr_copied":   added,
                "tr_skipped":  0,
                "tr_missing":  0,
                "bytes_copied":"—",
                "dest": nml_path,
                "created": len(created),
                "updated": len(updated),
                "added_tracks": added,
            }
            progress_log.append({"type":"done","msg":"Sync complete","summary": summary})
        except Exception as e:
            progress_log.append({"type":"error","msg": str(e)})
        finally:
            progress_done = True

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"status": "started"})

@app.route("/api/browse")
def browse():
    path = request.args.get("path","")
    if not path:
        return jsonify({"drives": get_drives(), "dirs": [], "current": ""})
    p = Path(path)
    if not p.exists() or not p.is_dir():
        return jsonify({"error": "Not a directory"}), 404
    try:
        dirs = sorted([str(d) for d in p.iterdir() if d.is_dir()])
    except PermissionError:
        dirs = []
    parent = str(p.parent) if p.parent != p else None
    return jsonify({"current": str(p), "parent": parent, "dirs": dirs, "drives": get_drives()})

@app.route("/api/mkdir", methods=["POST"])
def mkdir():
    data   = request.json
    parent = data.get("parent","")
    name   = sanitize_filename(data.get("name",""))
    if not parent or not name:
        return jsonify({"error": "Missing parent or name"}), 400
    new_dir = Path(parent) / name
    new_dir.mkdir(parents=True, exist_ok=True)
    return jsonify({"path": str(new_dir)})

@app.route("/api/export", methods=["POST"])
def export():
    global progress_log, progress_done
    data        = request.json
    nml_path    = data.get("nml_path","")
    dest        = data.get("dest","")
    selected    = data.get("selected", [])
    copy_tracks = data.get("copy_tracks", True)

    if not nml_path or not dest or not selected:
        return jsonify({"error": "Missing parameters"}), 400

    progress_log  = []
    progress_done = False

    def run():
        global progress_done
        try:
            dest_path = Path(dest)
            dest_path.mkdir(parents=True, exist_ok=True)
            playlists = parse_nml(nml_path)
            chosen    = [pl for pl in playlists if pl["name"] in selected]

            pl_exported = pl_skipped = 0
            tr_copied = tr_skipped = tr_missing = 0
            bytes_copied = 0

            for pl in chosen:
                name = sanitize_filename(pl["name"])
                if not name or not pl["tracks"]:
                    progress_log.append({"type":"warn","msg": f"Skipped empty playlist: {pl['name']}"})
                    pl_skipped += 1
                    continue

                out_path = dest_path / f"{name}.nml"
                if out_path.exists():
                    progress_log.append({"type":"skip","msg": f"{name}.nml already exists — skipped"})
                    pl_skipped += 1
                else:
                    out_path.write_text(build_nml_for_playlist(pl, dest_path, copy_tracks), encoding="utf-8")
                    progress_log.append({"type":"ok","msg": f"✓ {name}.nml ({len(pl['tracks'])} tracks)"})
                    pl_exported += 1

                if copy_tracks:
                    for t in pl["tracks"]:
                        src = Path(t["path"])
                        if not src.exists():
                            tr_missing += 1; continue
                        dst = dest_path / src.name
                        if dst.exists():
                            tr_skipped += 1
                        else:
                            try:
                                shutil.copy2(src, dst)
                                size = src.stat().st_size
                                bytes_copied += size
                                tr_copied += 1
                                progress_log.append({"type":"track","msg": f"  + {src.name} ({human_size(size)})"})
                            except Exception as e:
                                tr_missing += 1
                                progress_log.append({"type":"error","msg": f"  ✗ {src.name}: {e}"})

            summary = {
                "pl_exported": pl_exported, "pl_skipped": pl_skipped,
                "tr_copied": tr_copied, "tr_skipped": tr_skipped,
                "tr_missing": tr_missing, "bytes_copied": human_size(bytes_copied),
                "dest": dest,
            }
            progress_log.append({"type":"done","msg":"Export complete","summary": summary})
        except Exception as e:
            progress_log.append({"type":"error","msg": str(e)})
        finally:
            progress_done = True

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"status": "started"})

@app.route("/api/progress")
def progress():
    return jsonify({"log": progress_log, "done": progress_done})

def get_drives():
    drives = []
    if sys.platform == "win32":
        import ctypes
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            if bitmask & 1:
                p = Path(f"{letter}:\\")
                if p.exists(): drives.append(str(p))
            bitmask >>= 1
    elif sys.platform == "darwin":
        for v in Path("/Volumes").iterdir():
            if v.is_dir() and v.name not in ("Macintosh HD","Preboot","Recovery","VM"):
                drives.append(str(v))
    else:
        drives.append(str(Path.home()))
    return drives



if __name__ == "__main__":
    import webbrowser
    print("\n🎛  Traktor Exporter UI")
    print("   Opening http://localhost:5123 …\n")
    threading.Timer(1.2, lambda: webbrowser.open("http://localhost:5123")).start()
    app.run(port=5123, debug=False, use_reloader=False)
