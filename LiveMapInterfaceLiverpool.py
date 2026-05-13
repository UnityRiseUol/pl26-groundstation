import sys
import os
import math
import csv
import time
import random
import urllib.request
import urllib.error
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"

from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QTimer


# ---------------- CONFIG ----------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TILE_DIR = os.path.join(BASE_DIR, "tiles")

# Ashton Building, University of Liverpool
LAUNCH_LAT = 53.4065
LAUNCH_LON = -2.9665

SIM_DT = 0.03

RADIUS_KM = 1.0


# ---------------- 1KM AREA ----------------

def km_to_deg_lat(km):
    return km / 111.0

def km_to_deg_lon(km, lat):
    return km / (111.0 * math.cos(math.radians(lat)))


LAT_MIN = LAUNCH_LAT - km_to_deg_lat(RADIUS_KM)
LAT_MAX = LAUNCH_LAT + km_to_deg_lat(RADIUS_KM)
LON_MIN = LAUNCH_LON - km_to_deg_lon(RADIUS_KM, LAUNCH_LAT)
LON_MAX = LAUNCH_LON + km_to_deg_lon(RADIUS_KM, LAUNCH_LAT)


# ---------------- TILE SYSTEM ----------------

TILE_TIMEOUT = 6
PRINT_EVERY = 10


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
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "RocketTelemetry/1.0"}
        )

        with urllib.request.urlopen(req, timeout=TILE_TIMEOUT) as resp:
            data = resp.read()

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)

        return True

    except urllib.error.HTTPError as e:
        print(f"HTTP {z}/{x}/{y}: {e.code}")
        return False

    except Exception as e:
        print(f"tile error {z}/{x}/{y}: {e}")
        return False


def get_tile_bounds(z):
    x1, y1 = deg2tile(LAT_MIN, LON_MIN, z)
    x2, y2 = deg2tile(LAT_MAX, LON_MAX, z)

    return min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2)


def ensure_tiles():
    print("🛰 Building 1km tile cache (this may take a while)...")

    total = 0

    for z in range(12, 16):  # IMPORTANT: avoids massive freeze at high zoom
        x_min, x_max, y_min, y_max = get_tile_bounds(z)

        print(f"\n📦 Zoom {z} range x:{x_min}-{x_max} y:{y_min}-{y_max}")

        count = 0

        for x in range(x_min, x_max + 1):
            for y in range(y_min, y_max + 1):

                path = os.path.join(TILE_DIR, str(z), str(x), f"{y}.png")

                if not os.path.exists(path):
                    download_tile(z, x, y)

                count += 1
                total += 1

                if count % PRINT_EVERY == 0:
                    print(f"   zoom {z}: processed {count} tiles")

    print(f"\n✅ Tile cache ready ({total} tiles processed)")


def repair_missing_tiles():
    print("🔍 Repairing missing tiles...")

    for z in range(12, 19):
        x_min, x_max, y_min, y_max = get_tile_bounds(z)

        for x in range(x_min, x_max + 1):
            for y in range(y_min, y_max + 1):

                path = os.path.join(TILE_DIR, str(z), str(x), f"{y}.png")

                if not os.path.exists(path):
                    download_tile(z, x, y)


# ---------------- TILE SERVER ----------------

def start_tile_server():
    os.chdir(BASE_DIR)

    server = HTTPServer(("127.0.0.1", 8000), SimpleHTTPRequestHandler)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    print("🌐 Tile server running at http://127.0.0.1:8000")


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

L.tileLayer('tiles/{{z}}/{{x}}/{{y}}.png', {{
    minZoom: 12,
    maxZoom: 18
}}).addTo(map);

var launch = L.marker([LAUNCH_LAT, LAUNCH_LON], {{
    icon: L.divIcon({{ className: "launch", html: "Launch" }})
}}).addTo(map);

var rocket = L.marker([LAUNCH_LAT, LAUNCH_LON], {{
    icon: L.divIcon({{ className: "rocket" }})
}}).addTo(map);

// ALWAYS keep both visible
window.updateMarker = function(lat, lon) {{

    rocket.setLatLng([lat, lon]);

    let bounds = L.latLngBounds([
        [LAUNCH_LAT, LAUNCH_LON],
        [lat, lon]
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

        self.view = QWebEngineView()
        self.setCentralWidget(self.view)

        self.view.setHtml(HTML, QUrl.fromLocalFile(BASE_DIR + os.sep))

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

    # FIXED CSV PARSER
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


# ---------------- RUN ----------------

if __name__ == "__main__":
    os.makedirs(TILE_DIR, exist_ok=True)

    ensure_tiles()
    repair_missing_tiles()
    start_tile_server()

    app = QApplication(sys.argv)
    w = MapWindow()
    w.show()
    sys.exit(app.exec_())
