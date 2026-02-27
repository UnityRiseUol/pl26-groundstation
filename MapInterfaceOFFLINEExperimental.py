import sys
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView

# Directory where your tiles are stored
TILE_SAVE_PATH = "tiles"  # Folder containing the downloaded tiles
HOST = "localhost"
PORT = 5000

# HTTP Server to serve local tiles
class TileHandler(BaseHTTPRequestHandler):
    # This silences the console output for every GET request and error
    def log_message(self, format, *args):
        return

    def do_GET(self):
        # Parse the path for zoom level, x, and y from the URL
        path = self.path.strip("/").split("/")
        if len(path) != 3:
            self.send_error(404)
            return

        try:
            z_req, x_req, y_png = path
            z_req = int(z_req)
            x_req = int(x_req)
            y_req = int(y_png.split(".")[0])  # Strip the ".png" from the filename
        except Exception:
            self.send_error(400)
            return

        # Build the filename of the requested tile
        tile_filename = f"{z_req}_{x_req}_{y_req}.png"
        tile_path = os.path.join(TILE_SAVE_PATH, tile_filename)

        if os.path.exists(tile_path):
            # Tile exists, serve it
            with open(tile_path, 'rb') as f:
                self.send_response(200)
                self.send_header("Content-type", "image/png")
                self.end_headers()
                self.wfile.write(f.read())
        else:
            # Tile not found, return 404
            self.send_response(404)
            self.end_headers()

def run_server():
    httpd = HTTPServer((HOST, PORT), TileHandler)
    print(f"Serving tiles at http://{HOST}:{PORT}")
    httpd.serve_forever()

# Run server in a separate thread
server_thread = Thread(target=run_server, daemon=True)
server_thread.start()

# --- PyQt5 Integration ---

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
    html, body { margin:0; height:100%; overflow:hidden; background:#222; }
    #map { width:100%; height:100%; position:relative; }
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
    const y = (1 - Math.log(Math.tan(lat * Math.PI / 180) + 1 / Math.cos(lat * Math.PI / 180)) / Math.PI) / 2 * Math.pow(2, z);
    return { x, y };
}

function renderTiles() {
    mapDiv.innerHTML = "";
    const centerTile = latLonToTile(center.lat, center.lon, zoom);
    
    // Calculate how many tiles fit in the window
    const halfW = (mapDiv.clientWidth / 2) / tileSize;
    const halfH = (mapDiv.clientHeight / 2) / tileSize;

    const startX = Math.floor(centerTile.x - halfW);
    const endX = Math.ceil(centerTile.x + halfW);
    const startY = Math.floor(centerTile.y - halfH);
    const endY = Math.ceil(centerTile.y + halfH);

    for (let x = startX; x <= endX; x++) {
        for (let y = startY; y <= endY; y++) {
            const img = new Image();
            // Suppress the console error if the image fails to load
            img.onerror = () => { img.style.display = 'none'; };
            img.src = `http://localhost:5000/${zoom}/${x}/${y}.png`;
            img.style.position = "absolute";
            
            // Positioning relative to center
            const screenX = (x - centerTile.x) * tileSize + (mapDiv.clientWidth / 2);
            const screenY = (y - centerTile.y) * tileSize + (mapDiv.clientHeight / 2);
            
            img.style.left = screenX + "px";
            img.style.top = screenY + "px";
            img.width = tileSize;
            img.height = tileSize;
            mapDiv.appendChild(img);
        }
    }
}

window.addEventListener("wheel", e => {
    zoom += (e.deltaY < 0 ? 1 : -1);
    zoom = Math.max(0, Math.min(18, zoom));
    renderTiles();
});

// Simple drag logic
let isDragging = false;
mapDiv.onmousedown = () => isDragging = true;
window.onmouseup = () => isDragging = false;
window.onmousemove = e => {
    if (isDragging) {
        const worldSize = Math.pow(2, zoom) * tileSize;
        center.lon -= (e.movementX / worldSize) * 360;
        // Approximation for lat movement
        center.lat += (e.movementY / worldSize) * 180; 
        renderTiles();
    }
};

window.onresize = renderTiles;
renderTiles();
</script>
</body>
</html>
"""

class RocketMap(QMainWindow):
    def __init__(self):
        super().__init__()
        self.browser = QWebEngineView()
        self.browser.setHtml(HTML_TEMPLATE)
        self.setCentralWidget(self.browser)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RocketMap()
    window.show()
    sys.exit(app.exec_())
