#!/usr/bin/env python3
"""
Traktor Exporter — Backend Server
Serves the React UI and handles all file operations via a JSON API.

Install deps:  pip install flask
Run:           python traktor_server.py
Then open:     http://localhost:5123
"""

import os, sys, re, shutil, json, threading, time
import xml.etree.ElementTree as ET
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
try:
    from flask_cors import CORS
    _has_cors = True
except ImportError:
    _has_cors = False

app = Flask(__name__, static_folder="traktor_ui", static_url_path="")
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

def find_collection_nml():
    base = Path.home() / "Documents" / "Native Instruments" / "Traktor 3.11.1"
    candidates = sorted(base.glob("*/collection.nml"), reverse=True)
    candidates += [base / "collection.nml"]
    for p in candidates:
        if Path(p).exists(): return str(p)
    return None

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

def traktor_key_to_path(key):
    """
    Convert a Traktor PRIMARYKEY value to an OS path.
    Keys look like: G:/:peter/:Music/:track.mp3
    The drive letter prefix (e.g. G:) is followed by /: separated folders.
    """
    if not key:
        return ""
    # Match optional drive letter at start: e.g. "G:"
    m = re.match(r"^([A-Za-z]:)(.*)", key)
    if m:
        drive = m.group(1)          # e.g. "G:"
        rest  = m.group(2)          # e.g. "/:peter/:Music/:track.mp3"
        # strip leading /: then split on /:
        rest  = re.sub(r"^/:", "", rest)
        parts = rest.split("/:")
        return drive + "\\" + "\\".join(parts)
    else:
        # macOS / Linux style: /:Users/:name/:Music/:track.mp3
        clean = re.sub(r"^/:", "", key).replace("/:", os.sep)
        return os.sep + clean

def parse_nml(nml_path):
    tree = ET.parse(nml_path)
    root = tree.getroot()

    # Build track lookup from COLLECTION: key -> track info
    # Keys are built the same way Traktor stores them in PRIMARYKEY
    tracks = {}
    collection = root.find("COLLECTION")
    if collection is not None:
        for entry in collection.findall("ENTRY"):
            loc = entry.find("LOCATION")
            if loc is None: continue
            volume    = loc.get("VOLUME", "")
            dir_attr  = loc.get("DIR", "")
            file_attr = loc.get("FILE", "")
            # Reconstruct the key as it appears in PRIMARYKEY KEY="..."
            # e.g. volume="G:" dir="/:peter/:Music/:" file="track.mp3"
            # -> "G:/:peter/:Music/:track.mp3"
            key = volume + dir_attr + file_attr
            path = traktor_path_to_os(volume, dir_attr + file_attr)
            tracks[key] = {
                "path":   path,
                "title":  entry.get("TITLE", ""),
                "artist": entry.get("ARTIST", ""),
            }

    playlists = []

    def recurse(node, prefix=""):
        # Iterate direct NODE children (Traktor wraps them in SUBNODES too)
        for child in list(node):
            tag   = child.tag
            name  = child.get("NAME", "Unnamed")
            ntype = child.get("TYPE", "")

            if tag == "SUBNODES":
                # Transparent wrapper — just recurse into it
                recurse(child, prefix=prefix)

            elif tag == "NODE" and ntype == "PLAYLIST":
                entries = []
                # Tracks live inside a <PLAYLIST> child of the NODE
                pl_node = child.find("PLAYLIST")
                if pl_node is not None:
                    for e in pl_node.findall("ENTRY"):
                        pk = e.find("PRIMARYKEY")
                        if pk is None: continue
                        k = pk.get("KEY", "")
                        if k in tracks:
                            entries.append(tracks[k])
                        else:
                            # Key not in collection — derive path directly from key
                            entries.append({
                                "path":   traktor_key_to_path(k),
                                "title":  "",
                                "artist": "",
                            })
                playlists.append({
                    "name":   (prefix + name) if prefix else name,
                    "tracks": entries,
                })

            elif tag == "NODE" and ntype == "FOLDER":
                # Skip the $ROOT folder name itself but recurse into its children
                new_prefix = (prefix + name + " - ") if name != "$ROOT" else prefix
                recurse(child, prefix=new_prefix)

    sets = root.find(".//PLAYLISTS")
    if sets is not None:
        recurse(sets)
    return playlists

# Progress state (simple global for SSE streaming)
progress_log = []
progress_done = False

# ── API Routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("traktor_ui", "index.html")

@app.route("/api/detect-nml")
def detect_nml():
    p = find_collection_nml()
    return jsonify({"path": p})

@app.route("/api/parse-nml")
def api_parse_nml():
    path = request.args.get("path","")
    if not path or not Path(path).exists():
        return jsonify({"error": "File not found"}), 404
    try:
        playlists = parse_nml(path)
        # don't send all track paths to frontend, just counts + names
        result = [{"name": pl["name"], "count": len(pl["tracks"])} for pl in playlists]
        return jsonify({"playlists": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/browse")
def browse():
    path = request.args.get("path", "")
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
    data = request.json
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
    data         = request.json
    nml_path     = data.get("nml_path","")
    dest         = data.get("dest","")
    selected     = data.get("selected", [])   # list of playlist names
    copy_tracks  = data.get("copy_tracks", True)

    if not nml_path or not dest or not selected:
        return jsonify({"error": "Missing parameters"}), 400

    progress_log  = []
    progress_done = False

    def os_path_to_traktor(path_str):
        """Convert a normal OS path back to Traktor's /:folder/:file format."""
        p = Path(path_str)
        if sys.platform == "win32":
            # e.g. G:\Music\track.mp3 -> volume="G:", dir="/:Music/:", file="track.mp3"
            drive = p.drive          # "G:"
            parts = list(p.parts[1:])  # everything after the drive
            filename = parts[-1] if parts else ""
            folders  = parts[:-1]
            dir_str  = "".join(f"/:{part}" for part in folders) + "/:" if folders else "/:"
            return drive, dir_str, filename
        else:
            parts    = list(p.parts)   # ['/', 'Users', 'name', 'Music', 'track.mp3']
            filename = parts[-1] if len(parts) > 1 else ""
            folders  = parts[1:-1]
            dir_str  = "".join(f"/:{part}" for part in folders) + "/:" if folders else "/:"
            return "", dir_str, filename

    def build_nml(playlist, dest_path, copy_tracks):
        """Build a Traktor-compatible NML string for a single playlist."""
        import xml.etree.ElementTree as ET2
        from xml.dom import minidom

        nml = ET2.Element("NML", attrib={"VERSION": "19"})
        head = ET2.SubElement(nml, "HEAD", attrib={"COMPANY": "www.native-instruments.com", "PROGRAM": "Traktor"})
        collection = ET2.SubElement(nml, "COLLECTION", attrib={"ENTRIES": str(len(playlist["tracks"]))})
        sets = ET2.SubElement(nml, "PLAYLISTS")
        root_node = ET2.SubElement(sets, "NODE", attrib={"TYPE": "FOLDER", "NAME": "$ROOT"})
        subnodes = ET2.SubElement(root_node, "SUBNODES", attrib={"COUNT": "1"})
        pl_node = ET2.SubElement(subnodes, "NODE", attrib={"TYPE": "PLAYLIST", "NAME": playlist["name"]})
        pl_el = ET2.SubElement(pl_node, "PLAYLIST", attrib={
            "ENTRIES": str(len(playlist["tracks"])),
            "TYPE": "LIST",
            "UUID": __import__("uuid").uuid4().hex
        })

        for t in playlist["tracks"]:
            src = Path(t["path"])
            # If copying tracks, path in NML points to dest folder
            final_path = str(dest_path / src.name) if (copy_tracks and src.exists()) else t["path"]

            volume, dir_str, filename = os_path_to_traktor(final_path)

            # Add to COLLECTION
            entry = ET2.SubElement(collection, "ENTRY", attrib={
                "TITLE":  t.get("title", src.stem),
                "ARTIST": t.get("artist", ""),
            })
            ET2.SubElement(entry, "LOCATION", attrib={
                "DIR":    dir_str,
                "FILE":   filename,
                "VOLUME": volume,
                "VOLUMEID": volume,
            })

            # Add to PLAYLIST
            pl_entry = ET2.SubElement(pl_el, "ENTRY")
            ET2.SubElement(pl_entry, "PRIMARYKEY", attrib={
                "TYPE": "TRACK",
                "KEY":  volume + dir_str + filename,
            })

        # Pretty-print
        raw = ET2.tostring(nml, encoding="unicode")
        pretty = minidom.parseString(raw).toprettyxml(indent="\t", encoding=None)
        # Remove the <?xml ...?> declaration minidom adds (Traktor adds its own)
        lines = pretty.splitlines()
        if lines and lines[0].startswith("<?xml"):
            lines = lines[1:]
        return "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"no\" ?>\n" + "\n".join(lines)

    def run():
        global progress_done
        try:
            dest_path = Path(dest)
            dest_path.mkdir(parents=True, exist_ok=True)
            playlists = parse_nml(nml_path)
            chosen = [pl for pl in playlists if pl["name"] in selected]

            pl_exported = pl_skipped = 0
            tr_copied = tr_skipped = tr_missing = 0
            bytes_copied = 0

            for pl in chosen:
                name = sanitize_filename(pl["name"])
                if not name or not pl["tracks"]:
                    progress_log.append({"type":"warn","msg": f"Skipped empty playlist: {pl['name']}"})
                    pl_skipped += 1
                    continue

                nml_out_path = dest_path / f"{name}.nml"

                if nml_out_path.exists():
                    progress_log.append({"type":"skip","msg": f"{name}.nml already exists — skipped"})
                    pl_skipped += 1
                else:
                    nml_content = build_nml(pl, dest_path, copy_tracks)
                    nml_out_path.write_text(nml_content, encoding="utf-8")
                    progress_log.append({"type":"ok","msg": f"✓ {name}.nml ({len(pl['tracks'])} tracks)"})
                    pl_exported += 1

                if copy_tracks:
                    for t in pl["tracks"]:
                        src = Path(t["path"])
                        if not src.exists():
                            tr_missing += 1
                            continue
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
                "dest": dest
            }
            progress_log.append({"type":"done","msg":"Export complete", "summary": summary})
        except Exception as e:
            progress_log.append({"type":"error","msg": str(e)})
        finally:
            progress_done = True

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"status": "started"})

@app.route("/api/progress")
def progress():
    """Simple polling endpoint — returns all log lines so far."""
    return jsonify({"log": progress_log, "done": progress_done})

if __name__ == "__main__":
    import webbrowser
    print("\n🎛  Traktor Exporter UI")
    print("   Opening http://localhost:5123 …\n")
    threading.Timer(1.2, lambda: webbrowser.open("http://localhost:5123")).start()
    app.run(port=5123, debug=False)
