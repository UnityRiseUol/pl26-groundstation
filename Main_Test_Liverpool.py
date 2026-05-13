import sys
import os
import math
import csv
import urllib.request
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"

from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, QTimer


# ================= CONFIG =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TILE_DIR = os.path.join(BASE_DIR, "tiles")

LAUNCH_LAT = 53.4065
LAUNCH_LON = -2.9665

SIM_DT = 0.03


# ================= TILE SERVER =================
def start_tile_server():
    os.chdir(BASE_DIR)

    server = HTTPServer(("127.0.0.1", 8000), SimpleHTTPRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    print("🌐 Server running at http://127.0.0.1:8000")


# ================= TILE SYSTEM =================
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
        return

    url = f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "QtRocketSim/1.0"}
        )

        with urllib.request.urlopen(req, timeout=8) as r:
            data = r.read()

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)

    except Exception:
        pass


def ensure_tiles():
    print("📦 Downloading tiles...")

    for z in range(12, 16):
        cx, cy = deg2tile(LAUNCH_LAT, LAUNCH_LON, z)
        radius = 5

        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                download_tile(z, cx + dx, cy + dy)

    print("✅ Tiles ready")


# ================= HTML =================
HTML = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>

<!-- LOCAL FILES (NO leaflet folder) -->
<link rel="stylesheet" href="http://127.0.0.1:8000/leaflet.css"/>
<script src="http://127.0.0.1:8000/leaflet.js"></script>

<style>
html, body, #map {{ height: 100%; margin: 0; }}

.rocket {{
  width: 14px;
  height: 14px;
  background: #00aaff;
  border-radius: 50%;
  box-shadow: 0 0 12px #00aaff;
}}

.launch {{
  width: 10px;
  height: 10px;
  background: red;
  border-radius: 50%;
  box-shadow: 0 0 10px red;
}}
</style>
</head>

<body>
<div id="map"></div>

<script>

const LAUNCH_LAT = {LAUNCH_LAT};
const LAUNCH_LON = {LAUNCH_LON};

var map = L.map('map').setView([LAUNCH_LAT, LAUNCH_LON], 16);

L.tileLayer('http://127.0.0.1:8000/tiles/{{z}}/{{x}}/{{y}}.png', {{
    minZoom: 12,
    maxZoom: 18
}}).addTo(map);

// markers
var launch = L.marker([LAUNCH_LAT, LAUNCH_LON], {{
    icon: L.divIcon({{ className: "launch" }})
}}).addTo(map);

var rocket = L.marker([LAUNCH_LAT, LAUNCH_LON], {{
    icon: L.divIcon({{ className: "rocket" }})
}}).addTo(map);

// JS bridge (safe)
window.updateMarker = function(lat, lon) {{
    rocket.setLatLng([lat, lon]);

    map.fitBounds(
        L.latLngBounds([
            [LAUNCH_LAT, LAUNCH_LON],
            [lat, lon]
        ]).pad(0.3)
    );
}};

</script>
</body>
</html>
"""


# ================= APP =================
class MapWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.view = QWebEngineView()
        self.setCentralWidget(self.view)

        self.view.setHtml(HTML, QUrl("http://127.0.0.1:8000/"))

        self.view.loadFinished.connect(self.start)

        self.data = self.load_csv("telemetry.csv")

        self.t = 0.0
        self.i = 0

        self.s_lat = None
        self.s_lon = None
        self.alpha = 0.1

        self.timer = QTimer()
        self.timer.setInterval(int(SIM_DT * 1000))
        self.timer.timeout.connect(self.step)

    def start(self):
        self.timer.start()

    def load_csv(self, path):
        data = []
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                data.append((float(r["t"]), float(r["lat"]), float(r["lon"])))
        return data

    def interpolate(self, t):
        while self.i < len(self.data) - 2 and self.data[self.i + 1][0] < t:
            self.i += 1

        t1, lat1, lon1 = self.data[self.i]
        t2, lat2, lon2 = self.data[self.i + 1]

        r = (t - t1) / (t2 - t1 + 1e-9)

        return (
            lat1 + (lat2 - lat1) * r,
            lon1 + (lon2 - lon1) * r
        )

    def step(self):
        self.t += SIM_DT

        lat, lon = self.interpolate(self.t)

        if self.s_lat is None:
            self.s_lat, self.s_lon = lat, lon
        else:
            self.s_lat = self.alpha * lat + (1 - self.alpha) * self.s_lat
            self.s_lon = self.alpha * lon + (1 - self.alpha) * self.s_lon

        js = f"window.updateMarker({self.s_lat}, {self.s_lon});"
        self.view.page().runJavaScript(js)


# ================= RUN =================
if __name__ == "__main__":
    os.makedirs(TILE_DIR, exist_ok=True)

    start_tile_server()
    ensure_tiles()

    app = QApplication(sys.argv)
    w = MapWindow()
    w.resize(1200, 800)
    w.show()

    sys.exit(app.exec())
