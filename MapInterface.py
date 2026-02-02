import sys
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8"/>
    <title>Map Interface</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <!-- Leaflet CSS -->
    <link
        rel="stylesheet"
        href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    />

    <!-- Leaflet JS -->
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

    <style>
        html, body, #map {
            height: 100%;
            margin: 0;
        }
    </style>
</head>

<body>
<div id="map"></div>

<script>
    var map = L.map('map').setView([28.5, -80.6], 6);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 18,
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    var trajectory = [
        [28.5623, -80.5774],  // Launch site (Cape Canaveral-ish)
        [29.0, -79.5],
        [30.0, -77.0],
        [31.5, -74.0],
        [33.0, -70.0]
    ];

    // Draw trajectory
    var path = L.polyline(trajectory, {
        color: 'red',
        weight: 3
    }).addTo(map);

    L.marker(trajectory[0]).addTo(map).bindPopup("Launch");
    L.marker(trajectory[trajectory.length - 1]).addTo(map).bindPopup("End Point");

    map.fitBounds(path.getBounds());
</script>
</body>
</html>
"""

class RocketMap(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Map Interface")

        self.browser = QWebEngineView()
        self.browser.setHtml(HTML_TEMPLATE)

        self.setCentralWidget(self.browser)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RocketMap()
    window.show()
    sys.exit(app.exec_())