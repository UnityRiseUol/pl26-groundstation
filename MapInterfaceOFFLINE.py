import sys
import sqlite3
import io
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from PIL import Image

from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl

MBTILES_FILE = "liverpool.mbtiles"
HOST = "localhost"
PORT = 5000

# ---------- HTTP Server ----------
class MBTilesHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.strip("/").split("/")
        if len(path) != 3:
            self.send_error(404)
            return
        try:
            z_req, x_req, y_png = path
            z_req = int(z_req)
            x_req = int(x_req)
            y_req = int(y_png.split(".")[0])
            y_tms_req = (1 << z_req) - 1 - y_req
        except:
            self.send_error(400)
            return

        conn = sqlite3.connect(MBTILES_FILE)
        cur = conn.cursor()

        cur.execute(
            "SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
            (z_req, x_req, y_tms_req)
        )
        row = cur.fetchone()

        if row is None:
            cur.execute("SELECT MIN(zoom_level), MAX(zoom_level) FROM tiles")
            z_min, z_max = cur.fetchone()

            if z_req < z_min:
                z_src = z_min
            elif z_req > z_max:
                z_src = z_max
            else:
                z_src = z_req

            scale = 2 ** (z_src - z_req)
            x_src = x_req // scale
            y_src = ((1 << z_src) - 1 - ((1 << z_req) - 1 - y_req) // scale)

            cur.execute(
                "SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                (z_src, x_src, y_src)
            )
            row = cur.fetchone()

            if row is None:
                conn.close()
                self.send_error(404)
                return

            tile = Image.open(io.BytesIO(row[0])).resize((256, 256), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            tile.save(buf, format="PNG")
            tile_data = buf.getvalue()
        else:
            tile_data = row[0]

        conn.close()

        self.send_response(200)
        self.send_header("Content-type", "image/png")
        self.end_headers()
        self.wfile.write(tile_data)

def run_server():
    httpd = HTTPServer((HOST, PORT), MBTilesHandler)
    print(f"Serving MBTiles at http://{HOST}:{PORT}/{{z}}/{{x}}/{{y}}.png")
    httpd.serve_forever()

server_thread = Thread(target=run_server, daemon=True)
server_thread.start()

# ---------- HTML ----------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8"/>
    <title>Liverpool Map</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <link rel="stylesheet" href="leaflet/leaflet.css"/>
    <script src="leaflet/leaflet.js"></script>

    <style>
        html, body, #map { height: 100%; margin: 0; }
    </style>
</head>
<body>
<div id="map"></div>
<script>
    var map = L.map('map', {minZoom: 0, maxZoom: 18})
                .setView([53.4084, -2.9916], 12);

    L.tileLayer('http://localhost:5000/{z}/{x}/{y}.png', {
        maxZoom: 18,
        attribution: 'Liverpool MBTiles'
    }).addTo(map);

    var trajectory = [
        [53.4084, -2.9916],
        [53.4200, -2.9800]
    ];

    var path = L.polyline(trajectory, { color: 'red', weight: 3 }).addTo(map);

    L.marker(trajectory[0]).addTo(map).bindPopup("Launch");
    L.marker(trajectory[1]).addTo(map).bindPopup("End Point");

    map.fitBounds(path.getBounds());
</script>
</body>
</html>
"""

# ---------- PyQt5 Window ----------
class RocketMap(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Liverpool Rocket Map")

        self.browser = QWebEngineView()

        base_path = QUrl.fromLocalFile(os.path.abspath(".") + "/")
        self.browser.setHtml(HTML_TEMPLATE, base_path)

        self.setCentralWidget(self.browser)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RocketMap()
    window.show()
    sys.exit(app.exec_())
