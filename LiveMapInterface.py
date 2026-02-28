import sys, os, math, requests, csv
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QTimer

TILE_DIR = "tiles"  # must contain zoom 12–18

# ... all your tile helpers and TileServer unchanged ...
# ---------------- TILE DOWNLOAD HELPERS ----------------

LAT_MIN, LAT_MAX = 53.38, 53.45
LON_MIN, LON_MAX = -3.05, -2.90

OSM_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
HEADERS = {"User-Agent": "LiverpoolOfflineMap/1.0 (Educational)"}

def latlon_to_tile(lat, lon, zoom):
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    xtile = int((lon + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile

def download_tile(z, x, y):
    url = OSM_URL.format(z=z, x=x, y=y)
    save_path = f"{TILE_DIR}/{z}/{x}"
    os.makedirs(save_path, exist_ok=True)
    tile_file = f"{save_path}/{y}.png"

    if os.path.exists(tile_file):
        return True

    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            with open(tile_file, "wb") as f:
                f.write(r.content)
            return True
        else:
            print(f"Failed {url}: HTTP {r.status_code}")
            return False
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return False

def ensure_tiles():
    print("Checking for missing tiles...")
    required_zooms = range(12, 19)

    for z in required_zooms:
        x_min, y_max = latlon_to_tile(LAT_MIN, LON_MIN, z)
        x_max, y_min = latlon_to_tile(LAT_MAX, LON_MAX, z)

        x1, x2 = sorted([x_min, x_max])
        y1, y2 = sorted([y_min, y_max])

        total = (x2 - x1 + 1) * (y2 - y1 + 1)
        count = 0

        print(f"Zoom {z}: downloading {total} tiles if missing...")

        for x in range(x1, x2 + 1):
            for y in range(y1, y2 + 1):
                download_tile(z, x, y)
                count += 1
                if count % 50 == 0:
                    print(f"  {count}/{total} tiles processed...")

    print("Tile download complete. Offline map ready.")

def verify_tiles():
    required_zooms = ["12", "13", "14", "15", "16", "17", "18"]

    if not os.path.isdir(TILE_DIR):
        print("Tile directory missing. Creating and downloading tiles...")
        os.makedirs(TILE_DIR, exist_ok=True)
        ensure_tiles()
        return True

    missing = False

    for z in required_zooms:
        zpath = os.path.join(TILE_DIR, z)
        if not os.path.isdir(zpath):
            print(f"Missing zoom folder {z}, downloading tiles...")
            missing = True
            continue

        has_tiles = any(
            fname.endswith(".png")
            for root, dirs, files in os.walk(zpath)
            for fname in files
        )
        if not has_tiles:
            print(f"Zoom {z} folder empty, downloading tiles...")
            missing = True

    if missing:
        ensure_tiles()
    else:
        print("All required tiles already present.")

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

    var userMarker = L.marker([userLat, userLon]).addTo(map)
        .bindPopup("Telemetry position");

    var userCircle = L.circle([userLat, userLon], {
        radius: 40,
        color: "blue",
        fillColor: "#3f8cff",
        fillOpacity: 0.3
    }).addTo(map);

    function updateMarker(lat, lon) {
        userLat = lat;
        userLon = lon;
        userMarker.setLatLng([lat, lon]);
        userCircle.setLatLng([lat, lon]);
        // map.panTo([lat, lon], {animate: true});
    }
</script>

</body>
</html>
"""

# ---------------- MAIN APP ----------------

class MapWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Liverpool Offline Map")

        self.view = QWebEngineView()
        self.view.setHtml(HTML, QUrl("file:///"))
        self.setCentralWidget(self.view)

        # --- telemetry state ---
        self.telemetry = self.load_telemetry("telemetry.csv")
        self.telemetry_index = 0

        self.timer = QTimer(self)
        self.timer.setInterval(30)  # ~0.03 s
        self.timer.timeout.connect(self.step_telemetry)
        self.timer.start()

    def load_telemetry(self, path):
        data = []
        if not os.path.exists(path):
            print(f"Telemetry file {path} not found")
            return data
        with open(path, newline="") as f:
            r = csv.DictReader(f)
            for row in r:
                try:
                    lat = float(row["lat"])
                    lon = float(row["lon"])
                    data.append((lat, lon))
                except Exception:
                    continue
        print(f"Loaded {len(data)} telemetry points")
        return data

    def step_telemetry(self):
        if not self.telemetry:
            return
        lat, lon = self.telemetry[self.telemetry_index]
        js = f"updateMarker({lat}, {lon});"
        self.view.page().runJavaScript(js)

        self.telemetry_index += 1
        if self.telemetry_index >= len(self.telemetry):
            self.telemetry_index = 0  # loop, or call self.timer.stop()

if __name__ == "__main__":
    verify_tiles()
    Thread(target=start_server, daemon=True).start()
    app = QApplication(sys.argv)
    w = MapWindow()
    w.show()
    sys.exit(app.exec_())
