import sys
import os
import threading
import webbrowser

# When bundled by PyInstaller, extracted files live in sys._MEIPASS
# When run as a plain script, use the script's own directory
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UI_DIR = os.path.join(BASE_DIR, "public")

# Set env var BEFORE importing the server so Flask picks up the right folder
os.environ["TRAKTOR_UI_DIR"] = UI_DIR

import traktor_server as server

# Override static folder after import too, just in case
server.app.static_folder    = UI_DIR
server.app.static_url_path  = ""

def open_browser():
    webbrowser.open("http://localhost:5123")

if __name__ == "__main__":
    print("\n🎛  Traktor Exporter")
    print(f"   UI folder : {UI_DIR}")
    print(f"   UI exists : {os.path.exists(UI_DIR)}")
    print("   Server    : http://localhost:5123\n")
    threading.Timer(2.0, open_browser).start()
    server.app.run(port=5123, debug=False, use_reloader=False)
