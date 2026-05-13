import sys
import os
import math
import csv
import time
import random
import urllib.request
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

# Force software rendering to avoid GPU issues in some environments
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"

from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QTimer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TILE_DIR = os.path.join(BASE_DIR, "tiles")

LAUNCH_LAT = 52.668
LAUNCH_LON = -1.5245

SIM_DT = 0.03

# Calculations for tile boundaries
def km_to_deg_lat(km):
    return km / 111.0

def km_to_deg_lon(km, lat):
    return km / (111.0 * math.cos(math.radians(lat)))

RADIUS_KM = 1.0

LAT_MIN = LAUNCH_LAT - km_to_deg_lat(RADIUS_KM)
LAT_MAX = LAUNCH_LAT + km_to_deg_lat(RADIUS_KM)
LON_MIN = LAUNCH_LON - km_to_deg_lon(RADIUS_KM, LAUNCH_LAT)
LON_MAX = LAUNCH_LON + km_to_deg_lon(RADIUS_KM, LAUNCH_LAT)

def deg2tile(lat, lon, z):
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.log(
        math.tan(math.radians(lat)) +
        1 / math.cos(math.radians(lat))
    ) / math.pi) / 2.0 * n)
    return x, y

def download_tile(z, x, y):
    path = os.path.join(TILE_DIR, str(z), str(x), f"{y}.png")
    if os.path.exists(path):
        return True

    url = f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MidlandsRocketryTelemetry/1.0"})
        data = urllib.request.urlopen(req, timeout=10).read()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        time.sleep(0.1) 
        return True
    except Exception:
        return False

def get_tile_bounds(z):
    x1, y1 = deg2tile(LAT_MIN, LON_MIN, z)
    x2, y2 = deg2tile(LAT_MAX, LON_MAX, z)
    return min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2)

def ensure_tiles_async():
    def worker():
        print("🛰 Checking/Downloading tile cache...")
        for z in range(12, 18):
            x_min, x_max, y_min, y_max = get_tile_bounds(z)
            for x in range(x_min, x_max + 1):
                for y in range(y_min, y_max + 1):
                    download_tile(z, x, y)
        print("✅ Tile cache ready")
    threading.Thread(target=worker, daemon=True).start()

def start_tile_server():
    # Simple server to serve tiles and local JS/CSS files
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, format, *args): return # Keep console clean

    def serve():
        os.chdir(BASE_DIR)
        server = HTTPServer(("127.0.0.1", 8000), QuietHandler)
        server.serve_forever()
    
    threading.Thread(target=serve, daemon=True).start()
    print("🌐 Local server running on port 8000")

# HTML Template updated for local JS/CSS
HTML = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8"/>
    <link rel="stylesheet" href="leaflet.css"/>
    <script src="leaflet.js"></script>

    <style>
    html, body, #map {{ height: 100%; margin: 0; background: #222; }}
    .rocket {{ width: 14px; height: 14px; background: #00aaff; border-radius: 50%; box-shadow: 0 0 12px #00aaff; }}
    .launch {{ width: 10px; height: 10px; background: red; border-radius: 50%; box-shadow: 0 0 10px red; }}
    </style>
</head>
<body>
    <div id="map"></div>
    <script>
    const LAUNCH_LAT = {LAUNCH_LAT};
    const LAUNCH_LON = {LAUNCH_LON};

    var map = L.map('map').setView([LAUNCH_LAT, LAUNCH_LON], 14);

    // Primary Local Tile Layer
    L.tileLayer('tiles/{{z}}/{{x}}/{{y}}.png', {{
        minZoom: 12,
        maxZoom: 17,
        noWrap: true
    }}).addTo(map);

    var launch = L.marker([LAUNCH_LAT, LAUNCH_LON], {{
        icon: L.divIcon({{className: "launch"}})
    }}).addTo(map);

    var rocket = L.marker([LAUNCH_LAT, LAUNCH_LON], {{
        icon: L.divIcon({{className: "rocket"}})
    }}).addTo(map);

    window.updateMarker = function(lat, lon, launchLat, launchLon) {{
        rocket.setLatLng([lat, lon]);
        var bounds = L.latLngBounds([[lat, lon], [launchLat, launchLon]]);
        map.fitBounds(bounds.pad(0.3));
    }};
    </script>
</body>
</html>
"""

class MapWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Midlands Rocketry Telemetry (Offline Capable)")
        self.resize(1000, 700)

        self.view = QWebEngineView()
        self.setCentralWidget(self.view)

        # We load via the local server URL to ensure relative paths for JS/CSS/Tiles work
        self.view.setHtml(HTML, QUrl("http://127.0.0.1:8000/"))

        self.data = self.load_csv("telemetryTamworth.csv")
        self.t = 0
        self.i = 0

        self.timer = QTimer()
        self.timer.setInterval(int(SIM_DT * 1000))
        self.timer.timeout.connect(self.step)
        self.view.loadFinished.connect(self.timer.start)

    def load_csv(self, path):
        try:
            with open(path) as f:
                return [(float(r["t"]), float(r["lat"]), float(r["lon"]))
                        for r in csv.DictReader(f)]
        except FileNotFoundError:
            print(f"Error: {path} not found.")
            return [(0, LAUNCH_LAT, LAUNCH_LON), (10, LAUNCH_LAT, LAUNCH_LON)]

    def interpolate(self, t):
        while self.i < len(self.data)-2 and self.data[self.i+1][0] < t:
            self.i += 1
        t1, lat1, lon1 = self.data[self.i]
        t2, lat2, lon2 = self.data[self.i+1]
        r = (t - t1) / (t2 - t1) if t2 != t1 else 0
        return (lat1 + (lat2 - lat1) * r, lon1 + (lon2 - lon1) * r)

    def step(self):
        self.t += SIM_DT
        lat, lon = self.interpolate(self.t)
        js = f"window.updateMarker({lat}, {lon}, {LAUNCH_LAT}, {LAUNCH_LON});"
        self.view.page().runJavaScript(js)

if __name__ == "__main__":
    os.makedirs(TILE_DIR, exist_ok=True)
    
    # Start background services
    ensure_tiles_async()
    start_tile_server()

    app = QApplication(sys.argv)
    w = MapWindow()
    w.show()
    sys.exit(app.exec_())
