import sys, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl

TILE_DIR = "tiles"  # must contain zoom 12–18

# ---------------- TILE VERIFICATION ----------------

def verify_tiles():
    required_zooms = ["12", "13", "14", "15", "16", "17", "18"]

    if not os.path.isdir(TILE_DIR):
        print(f"ERROR: Missing tile directory: {TILE_DIR}")
        return False

    for z in required_zooms:
        zpath = os.path.join(TILE_DIR, z)
        if not os.path.isdir(zpath):
            print(f"ERROR: Missing zoom level folder: {z}")
            return False

        # Ensure the zoom folder contains at least one tile
        has_tiles = any(
            fname.endswith(".png")
            for root, dirs, files in os.walk(zpath)
            for fname in files
        )
        if not has_tiles:
            print(f"ERROR: Zoom level {z} exists but contains no .png tiles.")
            return False

    print("All required tiles (zoom 12–18) are present.")
    return True

# ---------------- LOCAL TILE SERVER ----------------

class TileServer(BaseHTTPRequestHandler):
    def log_message(self, *args):
        return

    def do_GET(self):
        parts = self.path.strip("/").split("/")
        if len(parts) != 3:
            self.send_error(404)
            return

        z, x, y_png = parts
        y = y_png.replace(".png", "")
        tile_path = f"{TILE_DIR}/{z}/{x}/{y}.png"

        if not os.path.exists(tile_path):
            self.send_error(404)
            return

        with open(tile_path, "rb") as f:
            data = f.read()

        self.send_response(200)
        self.send_header("Content-type", "image/png")
        self.end_headers()
        self.wfile.write(data)

def start_server():
    HTTPServer(("localhost", 5000), TileServer).serve_forever()

# ---------------- HTML MAP ----------------

HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8"/>
    <title>Liverpool Offline Map</title>
    <link rel="stylesheet" href="leaflet/leaflet.css"/>
    <script src="leaflet/leaflet.js"></script>
    <style>html, body, #map { height: 100%; margin: 0; }</style>
</head>
<body>
<div id="map"></div>

<script>
    var map = L.map('map', {
        minZoom: 12,
        maxZoom: 18
    }).setView([53.4066, -2.9665], 15);

    L.tileLayer('http://localhost:5000/{z}/{x}/{y}.png', {
        minZoom: 12,
        maxZoom: 18,
        noWrap: true,
        bounds: L.latLngBounds(
            L.latLng(53.38, -3.05),
            L.latLng(53.45, -2.90)
        ),
        attribution: "Offline tiles"
    }).addTo(map);

    var userLat = 53.4066;
    var userLon = -2.9665;

    L.marker([userLat, userLon]).addTo(map)
        .bindPopup("You are here");

    L.circle([userLat, userLon], {
        radius: 40,
        color: "blue",
        fillColor: "#3f8cff",
        fillOpacity: 0.3
    }).addTo(map);
</script>

</body>
</html>
"""

# ---------------- MAIN APP ----------------

class MapWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Liverpool Offline Map")
        view = QWebEngineView()
        view.setHtml(HTML, QUrl("file:///"))
        self.setCentralWidget(view)

if __name__ == "__main__":
    # Verify tiles before launching
    if not verify_tiles():
        print("Tile directory incomplete. Please download all required tiles (zoom 12–18).")
        sys.exit(1)

    Thread(target=start_server, daemon=True).start()
    app = QApplication(sys.argv)
    w = MapWindow()
    w.show()
    sys.exit(app.exec_())



