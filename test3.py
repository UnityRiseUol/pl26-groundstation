import sys
import time
import os
import json
import csv  # Added for backup logging purposes
import numpy as np
import serial
from collections import deque
from stl import mesh
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtCore import QUrl, QTimer, Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QComboBox, QStackedWidget
)
from PySide6.QtGui import QPixmap, QFont, QFontDatabase, QQuaternion, QMatrix4x4
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import pyqtgraph.opengl as gl

# -------------------- Platform-safe paths --------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "Assets")

FONT_PATH = os.path.join(ASSETS_DIR, "Orbitron-VariableFont_wght.ttf")
LASER_LOGO_PATH = os.path.join(ASSETS_DIR, "LASER_Logo.png")
UNITYRISE_LOGO_PATH = os.path.join(ASSETS_DIR, "unityrise_logo.png")
UOL_LOGO_PATH = os.path.join(ASSETS_DIR, "uol_logo.png")
STL_PATH = os.path.join(BASE_DIR, "rocket.stl") # Backup data file path definition
BACKUP_FILE_PATH = os.path.join(BASE_DIR, "telemetry_backup.csv")

# -------------------- UART Configuration --------------------
if sys.platform.startswith("win"):
    SERIAL_PORT = "COM3"
else:
    SERIAL_PORT = "/dev/ttyACM0"

BAUD_RATE = 115200
INTERVAL_MS = 30
UART_TIMEOUT_SEC = 2.0

LAUNCH_LAT = 52.668
LAUNCH_LON = -1.5245

# FIXED: Aligned structure indexing matching incoming raw hardware string (12 telemetry metrics array)
DATA_MAP = {
    "Lat": 0, "Lon": 1, "Alt": 2, "Veloc": 3, 
    "qR": 4, "qI": 5, "qJ": 6, "qK": 7,
    "insX": 8, "insY": 9, "insZ": 10, "RSSI": 11
}

# Conversion factor: Meters to Feet
M_TO_FT = 3.28084

# -------------------- Visualizers --------------------
class PlotLive2D(FigureCanvas):
    def __init__(self, title):
        self.fig = Figure(figsize=(5, 3), facecolor='white')
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.times, self.values = [], []
        self.ax.set_title(title)
        self.ax.grid(True, linestyle='--', alpha=0.7)
        self.line, = self.ax.plot([], [], lw=2, color='#212b58')
        self.fig.tight_layout()

    def updatePlot(self, new_title=None):
        if not self.times or not self.values: return
        if new_title: 
            self.ax.set_title(new_title)
        
        self.line.set_data(self.times, self.values)
        
        self.ax.set_xlim(min(self.times), max(self.times) + 0.1)
        ymin, ymax = min(self.values), max(self.values)
        padding = max((ymax - ymin) * 0.1, 1.0) 
        self.ax.set_ylim(ymin - padding, ymax + padding)
        
        self.draw_idle() 

class PlotLive3D(FigureCanvas):
    def __init__(self):
        self.fig = Figure(figsize=(6, 5))
        self.ax = self.fig.add_subplot(111, projection="3d")
        super().__init__(self.fig)
        self.posX, self.posY, self.posZ = [], [], []
        self.ax.set_title("Live INS Relative Position", fontweight="bold")
        
        self.line, = self.ax.plot([], [], [], lw=1.5, color="#212b58")
        self.scatter = self.ax.scatter([], [], [], s=60, color="red")
        self.fig.tight_layout()

    def updatePlot(self):
        if not self.posX: return
        
        self.line.set_data(self.posX, self.posY)
        self.line.set_3d_properties(self.posZ)
        
        self.scatter._offsets3d = (np.array([self.posX[-1]]), np.array([self.posY[-1]]), np.array([self.posZ[-1]]))
        
        self.ax.set_xlim(min(self.posX) - 1, max(self.posX) + 1)
        self.ax.set_ylim(min(self.posY) - 1, max(self.posY) + 1)
        self.ax.set_zlim(min(self.posZ) - 1, max(self.posZ) + 1)
        
        self.draw_idle()

class RocketRotationWidget(gl.GLViewWidget):
    def __init__(self):
        super().__init__()
        self.setBackgroundColor('w')
        self.grid = gl.GLGridItem()
        self.addItem(self.grid)
        self.setCameraPosition(distance=30)
        self.rocket_scale = 0.01 
        self.load_rocket(STL_PATH)

    def load_rocket(self, path):
        try:
            stl_mesh = mesh.Mesh.from_file(path)
            verts = stl_mesh.vectors.reshape(-1, 3)
            center = (verts.max(axis=0) + verts.min(axis=0)) / 2
            verts = (verts - center) * self.rocket_scale
            self.rocket = gl.GLMeshItem(vertexes=verts, faces=np.arange(len(verts)).reshape(-1, 3), smooth=True, shader='shaded', color=(1, 0, 0, 1))
            self.addItem(self.rocket)
        except:
            self.rocket = gl.GLBoxItem(color=(1, 0, 0, 1))
            self.addItem(self.rocket)

    def set_rotation(self, w, x, y, z):
        quat = QQuaternion(w, x, y, z).normalized()
        transform = QMatrix4x4()
        transform.rotate(quat)
        self.rocket.setTransform(transform)

class MapWidget(QWebEngineView):
    def __init__(self):
        super().__init__()
        self.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        self.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        
        self.last_lat = LAUNCH_LAT
        self.last_lon = LAUNCH_LON
        self.coordinates_history = []
        
        local_css = os.path.join(BASE_DIR, "leaflet.css")
        local_js = os.path.join(BASE_DIR, "leaflet.js")
        
        css_source = QUrl.fromLocalFile(local_css).toString() if os.path.exists(local_css) else "leaflet.css"
        js_source = QUrl.fromLocalFile(local_js).toString() if os.path.exists(local_js) else "leaflet.js"

        # FIXED: Build a fully qualified absolute file system URI for the local tiles folder
        local_tiles_dir = os.path.join(BASE_DIR, "tiles")
        if os.path.exists(local_tiles_dir):
            # Creates absolute string format: "file:///C:/path/to/tiles/{z}/{x}/{y}.png"
            tile_url = QUrl.fromLocalFile(local_tiles_dir).toString() + "/{z}/{x}/{y}.png"
        else:
            # Clean fallback rendering visual indicators
            tile_url = ""

        # CHANGED: Initial setView zoom level altered from 18 to 17 (one level less)
        self.osm_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <link rel="stylesheet" href="{css_source}" />
            <script src="{js_source}"></script>
            <style>
                body {{ margin: 0; padding: 0; background: #e5e9f2; font-family: sans-serif; overflow: hidden; }}
                #map {{ width: 100vw; height: 100vh; background-color: #e5e9f2; }}
                .offline-grid-active {{
                    background-color: #e5e9f2 !important;
                    background-image: 
                        linear-gradient(rgba(33, 43, 88, 0.15) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(33, 43, 88, 0.15) 1px, transparent 1px);
                    background-size: 40px 40px;
                    background-position: center;
                }}
                .leaflet-container {{ background: #e5e9f2 !important; }}
            </style>
        </head>
        <body>
            <div id="map" class="offline-grid-active"></div>
            <script>
                var map, rocketMarker, launchMarker, path;

                function initMap() {{
                    if (typeof L === 'undefined') {{
                        console.error("Leaflet.js failed to load!");
                        return;
                    }}

                    try {{
                        map = L.map('map', {{ 
                            fadeAnimation: false, 
                            trackResize: true,
                            minZoom: 10,
                            maxZoom: 19 
                        }}).setView([{LAUNCH_LAT}, {LAUNCH_LON}], 17);
                        
                        // Using the absolute file URL path string generated safely by PySide
                        L.tileLayer('{tile_url}', {{
                            minZoom: 10,
                            maxZoom: 19,
                            errorTileUrl: 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7',
                            fallbackOnUrlError: true,
                            attribution: '&copy; OpenStreetMap Offline'
                        }}).addTo(map);

                        launchMarker = L.circleMarker([{LAUNCH_LAT}, {LAUNCH_LON}], {{
                            radius: 8, fillColor: "#ff0000", color: "#ffffff", weight: 2, fillOpacity: 1
                        }}).addTo(map).bindPopup("Launch Site (UoL EEE)");

                        rocketMarker = L.circleMarker([{LAUNCH_LAT}, {LAUNCH_LON}], {{
                            radius: 10, fillColor: "#0078ff", color: "#ffffff", weight: 3, fillOpacity: 1
                        }}).addTo(map).bindPopup("Current Position");

                        path = L.polyline([], {{color: '#ffaa00', weight: 4}}).addTo(map);
                    }} catch (e) {{ 
                        console.log("Map Initialization Error: " + e); 
                    }}
                }}

                window.updateMarker = function(lat, lon) {{
                    if (typeof map !== 'undefined' && map && rocketMarker) {{
                        var newPos = [lat, lon];
                        rocketMarker.setLatLng(newPos);
                        path.addLatLng(newPos);
                        map.setView(newPos, map.getZoom(), {{ animate: false }}); 
                    }}
                }}
                
                window.restoreHistoricalPath = function(coordsJson) {{
                    if (typeof map !== 'undefined' && map && path && rocketMarker) {{
                        var coords = JSON.parse(coordsJson);
                        if (coords.length > 0) {{
                            path.setLatLngs(coords);
                            var lastCoord = coords[coords.length - 1];
                            rocketMarker.setLatLng(lastCoord);
                            map.setView(lastCoord, map.getZoom());
                        }}
                    }}
                }}
                window.onload = initMap;
            </script>
        </body>
        </html>
        """
        self.load_map_html()

    def load_map_html(self):
        baseUrl = QUrl.fromLocalFile(os.path.abspath(BASE_DIR) + "/")
        self.setHtml(self.osm_html, baseUrl)
        
    def refresh_and_restore(self):
        self.load_map_html()
        QTimer.singleShot(200, self._apply_restoration)

    def _apply_restoration(self):
        coords_json = json.dumps(self.coordinates_history)
        self.page().runJavaScript(f"if(window.restoreHistoricalPath) {{ window.restoreHistoricalPath('{coords_json}'); }}")

    def update_position(self, lat, lon):
        self.last_lat = lat
        self.last_lon = lon
        if not self.coordinates_history or self.coordinates_history[-1] != [lat, lon]:
            self.coordinates_history.append([lat, lon])
        self.page().runJavaScript(f"if(window.updateMarker) {{ window.updateMarker({lat}, {lon}); }}")

class PLOTSGroundStation(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LASER - UnityRise Mission Control - PL-26")
        self.resize(1280, 800) 
        self.packet_times = deque(maxlen=50)
        self.max_alt = -9999.0
        self.start_time = time.time()
        self.last_packet_time = time.time()  # Tracked for timeout events

        # Allocate historical tracking indices maps
        self.history = {k: [] for k in DATA_MAP.keys()}
        self.history_t = []

        # Initialize the backup log file with a clean header configuration if it doesn't exist
        if not os.path.exists(BACKUP_FILE_PATH):
            try:
                with open(BACKUP_FILE_PATH, mode='w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["System_Timestamp", "Mission_T", "Lat", "Lon", "Alt", "Veloc", "qR", "qI", "qJ", "qK", "insX", "insY", "insZ", "RSSI"])
            except Exception as backup_err:
                print(f"Failed to initialize backup log file: {backup_err}")

        # -------------------- UART Connection Initialization --------------------
        try:
            self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.01)
        except: 
            self.ser = None  # UI opens perfectly even if hardware is missing

        font_id = QFontDatabase.addApplicationFont(FONT_PATH)
        self.ui_font_family = QFontDatabase.applicationFontFamilies(font_id)[0] if font_id != -1 else "Arial"

        def ui_font(size, weight=QFont.Weight.Bold):
            f = QFont(self.ui_font_family, size)
            f.setWeight(weight)
            return f

        central_widget = QWidget()
        central_widget.setStyleSheet("background-color: white;")
        self.setCentralWidget(central_widget)
        root_layout = QVBoxLayout(central_widget)

        self.title_banner = QLabel("LASER – UnityRise Mission Control - PL-26")
        self.title_banner.setAlignment(Qt.AlignCenter)
        self.title_banner.setFixedHeight(50)
        self.title_banner.setFont(ui_font(18))
        self.title_banner.setStyleSheet("background: #212b58; color: white; border-radius: 5px;")
        root_layout.addWidget(self.title_banner)

        main_content = QHBoxLayout()
        root_layout.addLayout(main_content)

        # Left side: Graphs
        left_layout = QVBoxLayout()
        self.combo_top = QComboBox()
        self.combo_top.addItems(list(DATA_MAP.keys()))
        self.combo_top.setCurrentText("Alt")
        
        self.combo_bottom = QComboBox()
        self.combo_bottom.addItems(list(DATA_MAP.keys()))
        self.combo_bottom.setCurrentText("Veloc")

        for cb in [self.combo_top, self.combo_bottom]:
            cb.setStyleSheet("color: white; background-color: #212b58; border-radius:5px; padding:3px;")

        self.plot2D_top = PlotLive2D("Live Telemetry")
        self.plot2D_bottom = PlotLive2D("Secondary View")

        left_layout.addWidget(QLabel("Top Graph Variable:"))
        left_layout.addWidget(self.combo_top)
        left_layout.addWidget(self.plot2D_top, 1)
        left_layout.addWidget(QLabel("Bottom Graph Variable:"))
        left_layout.addWidget(self.combo_bottom)
        left_layout.addWidget(self.plot2D_bottom, 1)
        
        # FLIPPED: Decreased left stretch from 7 to 5 to make the graphs narrower
        main_content.addLayout(left_layout, 5)

        # Right side: Visuals and Labels
        right_layout = QVBoxLayout()
        logo_row = QHBoxLayout()
        
        laser_vbox = QVBoxLayout()
        self.laser_img = QLabel()
        if os.path.exists(LASER_LOGO_PATH):
            self.laser_img.setPixmap(QPixmap(LASER_LOGO_PATH).scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.laser_img.setText("[LASER LOGO]")
        self.laser_img.setAlignment(Qt.AlignCenter)
        self.phase_label = QLabel("Phase Of Flight: Test")
        self.phase_label.setAlignment(Qt.AlignCenter)
        self.phase_label.setFont(ui_font(10))
        self.phase_label.setStyleSheet("color: #212b58;")
        laser_vbox.addWidget(self.laser_img)
        laser_vbox.addWidget(self.phase_label)

        uol_vbox = QVBoxLayout()
        self.uol_img = QLabel()
        if os.path.exists(UOL_LOGO_PATH):
            self.uol_img.setPixmap(QPixmap(UOL_LOGO_PATH).scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.uol_img.setText("[UOL LOGO]")
        self.uol_img.setAlignment(Qt.AlignCenter)
        
        # Combined wrapper layout handling for dual references to the underlying status string
        self.status_label = QLabel("Status: Disarmed")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(ui_font(10))
        self.status_label.setStyleSheet("color: #cc0000; font-weight: bold; padding: 5px;")
        self.armed_label = self.status_label  # Linked to ensure programmatic aliases update seamlessly
        
        uol_vbox.addWidget(self.uol_img)
        uol_vbox.addWidget(self.status_label)

        unity_vbox = QVBoxLayout()
        self.unity_img = QLabel()
        if os.path.exists(UNITYRISE_LOGO_PATH):
            self.unity_img.setPixmap(QPixmap(UNITYRISE_LOGO_PATH).scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.unity_img.setText("[UNITYRISE LOGO]")
        self.unity_img.setAlignment(Qt.AlignCenter)
        
        # CHANGED: Label updated to use "ft" unit indicators instead of "m"
        self.alt_label = QLabel("Alt: ---ft")
        self.alt_label.setAlignment(Qt.AlignCenter)
        self.alt_label.setFont(ui_font(14)) 
        self.alt_label.setStyleSheet("color: #212b58; font-weight: bold; padding: 2px;")
        
        # ADDED: Apogee / Max Altitude Box tracking widget
        self.apogee_label = QLabel("Apogee: ---ft")
        self.apogee_label.setAlignment(Qt.AlignCenter)
        self.apogee_label.setFont(ui_font(11))
        self.apogee_label.setStyleSheet("color: #ffaa00; font-weight: bold; padding: 2px;")
        
        unity_vbox.addWidget(self.unity_img)
        unity_vbox.addWidget(self.alt_label)
        unity_vbox.addWidget(self.apogee_label)
        
        logo_row.addLayout(laser_vbox)
        logo_row.addStretch()
        logo_row.addLayout(uol_vbox)
        logo_row.addStretch()
        logo_row.addLayout(unity_vbox)
        right_layout.addLayout(logo_row)

        self.vis_selector = QComboBox()
        self.vis_selector.addItems(["Live Map", "3D Trajectory", "Rocket Attitude"])
        self.vis_selector.setStyleSheet("color: white; background-color: #212b58; border-radius:5px; padding:3px;")
        
        self.stacked_3d = QStackedWidget()
        self.mapWidget = MapWidget()
        self.plot3D = PlotLive3D()
        self.rotation3D = RocketRotationWidget()
        
        self.stacked_3d.addWidget(self.mapWidget)
        self.stacked_3d.addWidget(self.plot3D)
        self.stacked_3d.addWidget(self.rotation3D)
        
        self.vis_selector.currentIndexChanged.connect(self.handle_interface_switch)

        right_layout.addWidget(self.vis_selector)
        right_layout.addWidget(self.stacked_3d, 1)

        metadata_row = QHBoxLayout()
        self.rate_label = QLabel("Rate: 0.0 Hz")
        self.lat_label = QLabel("Lat: ---")
        self.lon_label = QLabel("Long: ---")
        self.rssi_label = QLabel("RSSI: --- dBm")
        
        for lbl in [self.rate_label, self.lat_label, self.lon_label, self.rssi_label]:
            lbl.setFont(ui_font(10))
            lbl.setStyleSheet("color: #212b58;")
            metadata_row.addWidget(lbl)
            if lbl != self.rssi_label: metadata_row.addStretch()
            
        right_layout.addLayout(metadata_row)
        
        # FLIPPED: Increased right layout stretch factor from 5 to 7 to make the map interface wider
        main_content.addLayout(right_layout, 7)

        # Timer setup combining telemetry data loops & status logic checks
        self.timer = QTimer()
        self.timer.timeout.connect(self.readNextPacket)
        self.timer.timeout.connect(self.updateConnectionStatus)
        self.timer.start(INTERVAL_MS) # 30 milliseconds

    def handle_interface_switch(self, index):
        self.stacked_3d.setCurrentIndex(index)
        if index == 0:  
            self.mapWidget.refresh_and_restore()

    def updateConnectionStatus(self):
        if not self.ser:
            self.status_label.setText("Status: NO HARDWARE")
            self.status_label.setStyleSheet("color: #cc0000; font-weight: bold;")
            self.alt_label.setText("Alt: ---ft")
            self.apogee_label.setText("Apogee: ---ft")
        elif self.ser and time.time() - self.last_packet_time > UART_TIMEOUT_SEC:
            self.status_label.setText("Status: Offline")
            self.armed_label.setText("Status: Disarmed")
            self.status_label.setStyleSheet("color: #cc0000; font-weight: bold;")

    def readNextPacket(self):
        if not self.ser or self.ser.in_waiting == 0: 
            return
            
        last_valid_line = None
        while self.ser.in_waiting:
            try:
                decoded = self.ser.readline().decode("ascii", errors="ignore").strip()
                # keeps overwriting last_valid_line until the buffer is empty
                if "," in decoded: 
                    last_valid_line = decoded
            except: 
                continue

        if not last_valid_line:
            return

        try:
            v = last_valid_line.split(",")
            if len(v) != 12:  # FIXED: Now matches the exact 12 values coming off the raw line
                return

            packet = {
                "T": time.time() - self.start_time,
                "Lat": float(v[0]),
                "Lon": float(v[1]),
                "Alt": float(v[2]),
                "Veloc": float(v[3]),
                "qR": float(v[4]),
                "qI": float(v[5]),
                "qJ": float(v[6]),
                "qK": float(v[7]),
                "insX": float(v[8]),
                "insY": float(v[9]),
                "insZ": float(v[10]),
                "RSSI": int(float(v[11].strip()))
            }

            self.last_packet_time = time.time()  # Keep-alive stroke tick reset

            # Export incoming live packet values immediately into the local data backup file
            try:
                with open(BACKUP_FILE_PATH, mode='a', newline='') as backup_file:
                    writer = csv.writer(backup_file)
                    writer.writerow([
                        time.time(), packet["T"], packet["Lat"], packet["Lon"], packet["Alt"],
                        packet["Veloc"], packet["qR"], packet["qI"], packet["qJ"], packet["qK"],
                        packet["insX"], packet["insY"], packet["insZ"], packet["RSSI"]
                    ])
            except Exception as write_err:
                print(f"Backup tracking file write failure: {write_err}")

            # CHANGED: Convert raw altitude and velocity from meters to feet for tracking and graphing logic
            alt_ft = packet["Alt"] * M_TO_FT
            veloc_ft = packet["Veloc"] * M_TO_FT

            # Track global state records metrics (computed in feet)
            if alt_ft > self.max_alt:
                self.max_alt = alt_ft

            # Text Label UI Updates
            self.lat_label.setText(f"Lat: {packet['Lat']:.5f}")
            self.lon_label.setText(f"Lon: {packet['Lon']:.5f}")
            self.alt_label.setText(f"Alt : {alt_ft:.2f} ft")
            self.apogee_label.setText(f"Apogee: {max(0.0, self.max_alt):.2f} ft")
            self.rssi_label.setText(f"RSSI: {packet['RSSI']:.0f} dBm")
            
            self.status_label.setText("Status: RECEIVING")
            self.status_label.setStyleSheet("color: #00aa00; font-weight: bold;")

            # Save arrays updates
            self.history_t.append(packet["T"])
            for key in DATA_MAP.keys():
                if key == "Alt":
                    self.history[key].append(alt_ft)
                elif key == "Veloc":
                    self.history[key].append(veloc_ft)
                else:
                    self.history[key].append(packet[key])

            # Flight Phase tracking calculation rules (Using converted units threshold parameters)
            is_moving = abs(veloc_ft) > (0.5 * M_TO_FT)
            if not is_moving:
                if self.max_alt < (10.0 * M_TO_FT) and alt_ft < (5.0 * M_TO_FT):
                    phase_val = "ON PAD (STATIONARY)"
                elif self.max_alt > (20.0 * M_TO_FT) and alt_ft < (5.0 * M_TO_FT):
                    phase_val = "LANDED (STATIONARY)"
                else:
                    phase_val = "STATIONARY"
            else:
                if alt_ft < (5.0 * M_TO_FT) and self.max_alt < (10.0 * M_TO_FT):
                    phase_val = "ON PAD (MOVING)"
                elif alt_ft > (self.history["Alt"][-2] if len(self.history["Alt"]) > 1 else alt_ft) + (0.2 * M_TO_FT):
                    phase_val = "ASCENT"
                elif alt_ft < self.max_alt - (2.0 * M_TO_FT) and alt_ft > (5.0 * M_TO_FT):
                    phase_val = "DESCENT"
                elif alt_ft < (5.0 * M_TO_FT) and self.max_alt > (20.0 * M_TO_FT):
                    phase_val = "LANDED"
                else:
                    phase_val = "COASTING"
            self.phase_label.setText(f"Phase Of Flight: {phase_val}")

            # Map Tracking Position Updates
            self.mapWidget.update_position(packet["Lat"], packet["Lon"])

            # 2D Chart Updates
            v_top = self.combo_top.currentText()
            self.plot2D_top.times = self.history_t
            self.plot2D_top.values = self.history[v_top]
            self.plot2D_top.updatePlot(f"Live {v_top}")

            v_btm = self.combo_bottom.currentText()
            self.plot2D_bottom.times = self.history_t
            self.plot2D_bottom.values = self.history[v_btm]
            self.plot2D_bottom.updatePlot(f"Live {v_btm}")

            # 3D Path Updates
            self.plot3D.posX.append(packet["insX"])
            self.plot3D.posY.append(packet["insY"])
            self.plot3D.posZ.append(packet["insZ"])
            if self.vis_selector.currentText() == "3D Trajectory":
                self.plot3D.updatePlot()

            # 3D Rocket Attitude Rotation Update
            self.rotation3D.set_rotation(packet["qR"], packet["qI"], packet["qJ"], packet["qK"])

            # Data frequency telemetry updates calculation
            now = time.time()
            self.packet_times.append(now)
            if len(self.packet_times) > 1:
                hz = len(self.packet_times) / (self.packet_times[-1] - self.packet_times[0])
                self.rate_label.setText(f"Rate: {hz:.1f} Hz")
                                                                                                    
        except Exception as e:
            print(f"Stream Error: {e}")

if __name__ == "__main__":
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--enable-gpu-rasterization --ignore-gpu-blocklist"
    app = QApplication(sys.argv)
    window = PLOTSGroundStation()
    window.show()
    sys.exit(app.exec())
