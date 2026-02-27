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

<style>
    html, body { margin:0; height:100%; overflow:hidden; }
    #map { width:100%; height:100%; background:#ddd; position:relative; }
    .marker { width:12px; height:12px; background:red; border-radius:50%; position:absolute; }
    .polyline { position:absolute; pointer-events:none; }
</style>
</head>

<body>
<div id="map"></div>

<script>
const mapDiv = document.getElementById("map");

let zoom = 12;
let center = { lat: 53.4084, lon: -2.9916 };
let tileSize = 256;

function latLonToTile(lat, lon, z) {
    const x = (lon + 180) / 360 * Math.pow(2, z);
    const y = (1 - Math.log(Math.tan(lat*Math.PI/180) + 1/Math.cos(lat*Math.PI/180)) / Math.PI) / 2 * Math.pow(2, z);
    return { x, y };
}

function render() {
    mapDiv.innerHTML = "";

    const tilesX = Math.ceil(mapDiv.clientWidth / tileSize) + 2;
    const tilesY = Math.ceil(mapDiv.clientHeight / tileSize) + 2;

    const centerTile = latLonToTile(center.lat, center.lon, zoom);

    const startX = Math.floor(centerTile.x - tilesX/2);
    const startY = Math.floor(centerTile.y - tilesY/2);

    for (let dx = 0; dx < tilesX; dx++) {
        for (let dy = 0; dy < tilesY; dy++) {
            const x = startX + dx;
            const y = startY + dy;

            const img = document.createElement("img");
            img.src = `http://localhost:5000/${zoom}/${x}/${y}.png`;
            img.style.position = "absolute";
            img.style.left = (dx * tileSize) + "px";
            img.style.top = (dy * tileSize) + "px";
            img.width = tileSize;
            img.height = tileSize;

            mapDiv.appendChild(img);
        }
    }

    drawMarkers();
    drawPolyline();
}

const markers = [
    { lat: 53.4084, lon: -2.9916, label: "Launch" },
    { lat: 53.4200, lon: -2.9800, label: "End Point" }
];

function drawMarkers() {
    markers.forEach(m => {
        const t = latLonToTile(m.lat, m.lon, zoom);
        const centerTile = latLonToTile(center.lat, center.lon, zoom);

        const dx = (t.x - centerTile.x) * tileSize + mapDiv.clientWidth/2;
        const dy = (t.y - centerTile.y) * tileSize + mapDiv.clientHeight/2;

        const el = document.createElement("div");
        el.className = "marker";
        el.style.left = dx + "px";
        el.style.top = dy + "px";
        el.title = m.label;

        mapDiv.appendChild(el);
    });
}

const trajectory = [
    [53.4084, -2.9916],
    [53.4200, -2.9800]
];

function drawPolyline() {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.classList.add("polyline");
    svg.style.position = "absolute";
    svg.style.left = "0";
    svg.style.top = "0";
    svg.style.width = mapDiv.clientWidth + "px";
    svg.style.height = mapDiv.clientHeight + "px";

    const poly = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
    poly.setAttribute("stroke", "red");
    poly.setAttribute("stroke-width", "3");
    poly.setAttribute("fill", "none");

    const centerTile = latLonToTile(center.lat, center.lon, zoom);

    const points = trajectory.map(([lat, lon]) => {
        const t = latLonToTile(lat, lon, zoom);
        const dx = (t.x - centerTile.x) * tileSize + mapDiv.clientWidth/2;
        const dy = (t.y - centerTile.y) * tileSize + mapDiv.clientHeight/2;
        return `${dx},${dy}`;
    }).join(" ");

    poly.setAttribute("points", points);
    svg.appendChild(poly);
    mapDiv.appendChild(svg);
}

let dragging = false;
let lastX = 0, lastY = 0;

mapDiv.addEventListener("mousedown", e => {
    dragging = true;
    lastX = e.clientX;
    lastY = e.clientY;
});

window.addEventListener("mouseup", () => dragging = false);

window.addEventListener("mousemove", e => {
    if (!dragging) return;

    const dx = e.clientX - lastX;
    const dy = e.clientY - lastY;

    center.lon -= dx / (tileSize * Math.pow(2, zoom)) * 360;
    center.lat += dy / (tileSize * Math.pow(2, zoom)) * 360;

    lastX = e.clientX;
    lastY = e.clientY;

    render();
});

mapDiv.addEventListener("wheel", e => {
    zoom += (e.deltaY < 0 ? 1 : -1);
    zoom = Math.max(0, Math.min(18, zoom));
    render();
});

render();
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
