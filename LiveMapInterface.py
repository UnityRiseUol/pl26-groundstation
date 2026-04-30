import sys
import os
import math
import csv
import time
import random
import urllib.request
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

import os
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"

from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QTimer


# ---------------- CONFIG ----------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TILE_DIR = os.path.join(BASE_DIR, "tiles")

LAUNCH_LAT = 52.4609
LAUNCH_LON = -1.9027

SIM_DT = 0.03


# 📍 MIDLANDS ROCKETRY BOUNDING BOX (FIXED REGION)
LAT_MIN = 52.455
LAT_MAX = 52.467
LON_MIN = -1.915
LON_MAX = -1.890


# ---------------- TILE SYSTEM ----------------

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
        print(f"⬇ downloading z{z}/{x}/{y}")

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "MidlandsRocketryTelemetry/1.0"}
        )

        data = urllib.request.urlopen(req, timeout=10).read()

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)

        time.sleep(1.2 + random.random())  # respect OSM limits

        return True

    except Exception as e:
        print("❌ tile error:", e)
        return False


def get_tile_bounds(z):
    x_min, y_max = deg2tile(LAT_MIN, LON_MIN, z)
    x_max, y_min = deg2tile(LAT_MAX, LON_MAX, z)
    return x_min, x_max, y_min, y_max


def ensure_tiles():
    print("🛰 Building Midlands Rocketry tile cache...")

    ZOOMS = range(12, 19)

    for z in ZOOMS:
        print(f"📦 Zoom {z}")

        x_min, x_max, y_min, y_max = get_tile_bounds(z)

        for x in range(x_min, x_max + 1):
            for y in range(y_min, y_max + 1):

                path = os.path.join(TILE_DIR, str(z), str(x), f"{y}.png")

                if os.path.exists(path):
                    continue

                download_tile(z, x, y)

    print("✅ Tile cache ready (Midlands locked)")


# ---------------- OPTIONAL LOCAL TILE SERVER ----------------

def start_tile_server():
    os.chdir(BASE_DIR)

    server = HTTPServer(("127.0.0.1", 8000), SimpleHTTPRequestHandler)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    print("🌐 Tile server running at http://127.0.0.1:8000")


# ---------------- HTML ----------------

HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>

<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<style>
html, body, #map { height: 100%; margin: 0; }

.rocket {
  width: 14px;
  height: 14px;
  background: #00aaff;
  border-radius: 50%;
  box-shadow: 0 0 12px #00aaff;
}

.launch {
  width: 10px;
  height: 10px;
  background: red;
  border-radius: 50%;
  box-shadow: 0 0 10px red;
}
</style>
</head>

<body>
<div id="map"></div>

<script>

// ---------------- MAP ----------------
var map = L.map('map').setView([52.4609, -1.9027], 14);


// ---------------- TILE LAYER (LOCAL CACHE FIRST) ----------------
L.tileLayer('tiles/{z}/{x}/{y}.png', {
    minZoom: 12,
    maxZoom: 18,
    noWrap: true
}).addTo(map);


// ---------------- LAUNCH SITE ----------------
var launch = L.marker([52.4609, -1.9027], {
    icon: L.divIcon({
        className: "launch",
        html: `<div style="transform: translateY(-22px); color:white; font-size:12px;
        text-shadow:0 0 5px black;">Launch Site</div>`
    })
}).addTo(map);


// ---------------- ROCKET ----------------
var rocket = L.marker([52.4609, -1.9027], {
    icon: L.divIcon({ className: "rocket" })
}).addTo(map);


// ---------------- SAFE UPDATE ----------------
window.updateMarker = function(lat, lon, zoom) {

    rocket.setLatLng([lat, lon]);

    map.setView([lat, lon], zoom, {
        animate: true
    });
};

</script>
</body>
</html>
"""


# ---------------- MAIN APP ----------------

class MapWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Midlands Rocketry Telemetry")

        self.view = QWebEngineView()
        self.setCentralWidget(self.view)

        self.view.setHtml(HTML, QUrl.fromLocalFile(BASE_DIR + os.sep))
        self.view.loadFinished.connect(self.start)

        self.data = self.load_csv("telemetry.csv")

        self.current_time = 0.0
        self.i = 0

        self.s_lat = None
        self.s_lon = None
        self.alpha = 0.08

        self.timer = QTimer()
        self.timer.setInterval(int(SIM_DT * 1000))
        self.timer.timeout.connect(self.step)

    def start(self):
        self.timer.start()

    def load_csv(self, path):
        with open(path) as f:
            return [(float(r["t"]), float(r["lat"]), float(r["lon"]))
                    for r in csv.DictReader(f)]

    def interpolate(self, t):
        while self.i < len(self.data) - 2 and self.data[self.i + 1][0] < t:
            self.i += 1

        t1, lat1, lon1 = self.data[self.i]
        t2, lat2, lon2 = self.data[self.i + 1]

        if t2 == t1:
            return lat1, lon1

        r = (t - t1) / (t2 - t1)

        return (
            lat1 + (lat2 - lat1) * r,
            lon1 + (lon2 - lon1) * r
        )

    def step(self):
        if not self.data:
            return

        self.current_time += SIM_DT

        lat, lon = self.interpolate(self.current_time)

        if self.s_lat is None:
            self.s_lat, self.s_lon = lat, lon
        else:
            self.s_lat = self.alpha * lat + (1 - self.alpha) * self.s_lat
            self.s_lon = self.alpha * lon + (1 - self.alpha) * self.s_lon

        zoom = self.get_zoom(self.s_lat, self.s_lon)

        js = f"window.updateMarker({self.s_lat}, {self.s_lon}, {zoom});"
        self.view.page().runJavaScript(js)

    def get_zoom(self, lat, lon):
        d = math.hypot(lat - LAUNCH_LAT, lon - LAUNCH_LON)

        if d < 0.0005:
            return 18
        elif d < 0.002:
            return 16
        elif d < 0.01:
            return 14
        return 12


# ---------------- RUN ----------------

if __name__ == "__main__":

    os.makedirs(TILE_DIR, exist_ok=True)

    ensure_tiles()

    start_tile_server()

    app = QApplication(sys.argv)
    w = MapWindow()
    w.show()
    sys.exit(app.exec_())
