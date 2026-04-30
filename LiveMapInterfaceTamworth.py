import sys
import os
import math
import csv
import time
import random
import urllib.request
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"

from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QTimer


# ---------------- CONFIG ----------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TILE_DIR = os.path.join(BASE_DIR, "tiles")

LAUNCH_LAT = 52.668
LAUNCH_LON = -1.5245

SIM_DT = 0.03
OFFLINE_MODE = False


# ---------------- TILE AREA (1km radius) ----------------

def km_to_deg_lat(km):
    return km / 111.0

def km_to_deg_lon(km, lat):
    return km / (111.0 * math.cos(math.radians(lat)))

RADIUS_KM = 1.0

LAT_MIN = LAUNCH_LAT - km_to_deg_lat(RADIUS_KM)
LAT_MAX = LAUNCH_LAT + km_to_deg_lat(RADIUS_KM)
LON_MIN = LAUNCH_LON - km_to_deg_lon(RADIUS_KM, LAUNCH_LAT)
LON_MAX = LAUNCH_LON + km_to_deg_lon(RADIUS_KM, LAUNCH_LAT)


# ---------------- DISTANCE (IMPORTANT FIX) ----------------

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))


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
        req = urllib.request.Request(url, headers={
            "User-Agent": "MidlandsRocketryTelemetry/1.0"
        })

        data = urllib.request.urlopen(req, timeout=10).read()

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)

        time.sleep(0.2)  # MUCH faster (was killing your app)
        return True

    except Exception:
        return False


def get_tile_bounds(z):
    x1, y1 = deg2tile(LAT_MIN, LON_MIN, z)
    x2, y2 = deg2tile(LAT_MAX, LON_MAX, z)

    return min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2)


def ensure_tiles_async():
    def worker():
        print("🛰 Building tile cache (background)...")

        for z in range(12, 18):
            x_min, x_max, y_min, y_max = get_tile_bounds(z)

            for x in range(x_min, x_max + 1):
                for y in range(y_min, y_max + 1):
                    download_tile(z, x, y)

        print("✅ Tile cache ready")

    threading.Thread(target=worker, daemon=True).start()


# ---------------- TILE SERVER ----------------

def start_tile_server():
    os.chdir(BASE_DIR)
    server = HTTPServer(("127.0.0.1", 8000), SimpleHTTPRequestHandler)

    threading.Thread(target=server.serve_forever, daemon=True).start()
    print("🌐 Tile server running")


# ---------------- HTML ----------------

HTML = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<style>
html, body, #map {{ height: 100%; margin: 0; }}

.rocket {{
  width: 14px; height: 14px;
  background: #00aaff;
  border-radius: 50%;
  box-shadow: 0 0 12px #00aaff;
}}

.launch {{
  width: 10px; height: 10px;
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

var map = L.map('map').setView([LAUNCH_LAT, LAUNCH_LON], 14);

L.tileLayer('tiles/{{z}}/{{x}}/{{y}}.png', {{
    minZoom: 12,
    maxZoom: 18,
    noWrap: true
}}).addTo(map);

// fallback (faded)
L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    opacity: 0.25
}}).addTo(map);

var launch = L.marker([LAUNCH_LAT, LAUNCH_LON], {{
    icon: L.divIcon({{className: "launch"}})
}}).addTo(map);

var rocket = L.marker([LAUNCH_LAT, LAUNCH_LON], {{
    icon: L.divIcon({{className: "rocket"}})
}}).addTo(map);

window.updateMarker = function(lat, lon, launchLat, launchLon) {{

    rocket.setLatLng([lat, lon]);

    // ---- AUTO ZOOM FIX ----
    var bounds = L.latLngBounds([
        [lat, lon],
        [launchLat, launchLon]
    ]);

    map.fitBounds(bounds.pad(0.3));
}};
</script>
</body>
</html>
"""


# ---------------- APP ----------------

class MapWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Midlands Rocketry Telemetry")

        self.view = QWebEngineView()
        self.setCentralWidget(self.view)

        self.view.setHtml(HTML, QUrl.fromLocalFile(BASE_DIR + os.sep))

        self.data = self.load_csv("telemetryTamworth.csv")

        self.t = 0
        self.i = 0

        self.s_lat = None
        self.s_lon = None

        self.timer = QTimer()
        self.timer.setInterval(int(SIM_DT * 1000))
        self.timer.timeout.connect(self.step)

        self.view.loadFinished.connect(self.timer.start)

    def load_csv(self, path):
        with open(path) as f:
            return [(float(r["t"]), float(r["lat"]), float(r["lon"]))
                    for r in csv.DictReader(f)]

    def interpolate(self, t):
        while self.i < len(self.data)-2 and self.data[self.i+1][0] < t:
            self.i += 1

        t1, lat1, lon1 = self.data[self.i]
        t2, lat2, lon2 = self.data[self.i+1]

        r = (t - t1) / (t2 - t1)

        return (
            lat1 + (lat2 - lat1) * r,
            lon1 + (lon2 - lon1) * r
        )

    def step(self):
        self.t += SIM_DT

        lat, lon = self.interpolate(self.t)

        if self.s_lat is None:
            self.s_lat, self.s_lon = lat, lon

        js = f"""
        window.updateMarker(
            {lat}, {lon},
            {LAUNCH_LAT}, {LAUNCH_LON}
        );
        """

        self.view.page().runJavaScript(js)


# ---------------- RUN ----------------

if __name__ == "__main__":
    os.makedirs(TILE_DIR, exist_ok=True)

    ensure_tiles_async()
    start_tile_server()

    app = QApplication(sys.argv)
    w = MapWindow()
    w.show()
    sys.exit(app.exec_())
