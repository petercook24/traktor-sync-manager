import sys
import os
import threading
import webbrowser
import time

# When bundled by PyInstaller, extracted files live in sys._MEIPASS
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UI_DIR = os.path.join(BASE_DIR, "public")
os.environ["TRAKTOR_UI_DIR"] = UI_DIR

import traktor_server as server

server.app.static_folder   = UI_DIR
server.app.static_url_path = ""

# Shared heartbeat state — the /api/heartbeat route updates this
server._heartbeat_state = {"last": time.time()}

# Watcher: if no heartbeat for 5 seconds, kill the process
def watch_heartbeat():
    # Give the app time to fully load before watching
    time.sleep(8)
    while True:
        time.sleep(3)
        elapsed = time.time() - server._heartbeat_state["last"]
        if elapsed > 5:
            os._exit(0)  # Hard exit — kills Flask and everything

def open_browser():
    webbrowser.open("http://localhost:5123")

if __name__ == "__main__":
    print("\n🎛  Traktor Exporter")
    print(f"   UI folder : {UI_DIR}")
    print("   Server    : http://localhost:5123\n")

    threading.Thread(target=watch_heartbeat, daemon=True).start()
    threading.Timer(2.0, open_browser).start()
    server.app.run(port=5123, debug=False, use_reloader=False)
