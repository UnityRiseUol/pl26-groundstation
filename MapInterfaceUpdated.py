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

    L.tileLayer('tiles/{z}/{x}/{y}.png', { //
        maxZoom: 18,
    }).addTo(map);

    var trajectory = [
        [52.66461047839969, -1.521765762979944] //Midlands Rocketry Club for now
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
