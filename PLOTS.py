# Program: PLOTS.py
# Author:
# Module:
# Email:
# Student Number:
# -----------------------------------------------------------------------------------------------------------------------------
# Code
import sys
import time
import os
import json
import csv
import glob
import re
import numpy as np
import serial
from collections import deque
from stl import mesh

from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtCore import QUrl, QTimer, Qt
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QStackedWidget)
from PySide6.QtGui import QPixmap, QFont, QFontDatabase, QQuaternion, QMatrix4x4

import matplotlib as mpl
import matplotlib.font_manager as fm
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import pyqtgraph.opengl as gl

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "Assets")
DATA_DIR = os.path.join(BASE_DIR, "Data")
FONT_PATH = os.path.join(ASSETS_DIR, "Orbitron-VariableFont_wght.ttf")
LASER_LOGO_PATH = os.path.join(ASSETS_DIR, "LASER_Logo.png")
UNITYRISE_LOGO_PATH = os.path.join(ASSETS_DIR, "unityrise_logo.png")
UOL_LOGO_PATH = os.path.join(ASSETS_DIR, "uol_logo.png")
STL_PATH = os.path.join(BASE_DIR, "Assets/rocket.stl") 

#Matplotlib font setup
try:
    fm.fontManager.addfont(FONT_PATH)
    custom_font = fm.FontProperties(fname=FONT_PATH)
    mpl.rcParams['font.family'] = custom_font.get_name()
except Exception as e:
    print(f"Failed to load custom font for Matplotlib: {e}")

#CSV file logging
def getNextCSVFile():
    baseName = "Ground_Station_Flight_Data"
    pattern = os.path.join(DATA_DIR, f"{baseName}_*.csv")
    existingFiles = glob.glob(pattern)
    
    max_num = 0
    for filepath in existingFiles:
        filename = os.path.basename(filepath)
        match = re.search(r'_(\d+)\.csv$', filename)
        if match:
            num = int(match.group(1))
            if num > max_num:
                max_num = num
    
    nextNumber = max_num + 1
    return os.path.join(DATA_DIR, f"{baseName}_{nextNumber}.csv")

BACKUP_FILE_PATH = getNextCSVFile()

#UART configuration
if sys.platform.startswith("win"):
    SERIAL_PORT = "COM3"
else:
    SERIAL_PORT = "/dev/ttyACM0"

BAUD_RATE = 115200
INTERVAL_MS = 30
UART_TIMEOUT_SEC = 2.0
METRE_TO_FEET = 3.28084
LAUNCH_LAT = 52.668
LAUNCH_LON = -1.5245

#Data mapping
DATA_MAP = {
    "Lat": "deg", "Lon": "deg", "Alt": "ft", "Veloc": "m/s", 
    "qR": "float", "qI": "float", "qJ": "float", "qK": "float",
    "insX": "m", "insY": "m", "insZ": "m", "RSSI": "dBm"
}

class PlotLive2D(FigureCanvas):
    def __init__(self, title, ylabel=None, window_size=20.0):
        self.fig = Figure(figsize=(5, 3), facecolor='white')
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.times, self.values = [], []
        self.window_size = window_size # Determines how many seconds to show
        
        self.ax.set_title(title, color='#212b58', fontweight='bold')
        self.ax.set_xlabel("Time (s)", color='#212b58', fontweight='bold') 
        
        if ylabel:
            self.ax.set_ylabel(ylabel, color='#212b58', fontweight='bold')
            
        self.ax.tick_params(colors='#212b58') 
        for spine in self.ax.spines.values():
            spine.set_color('#212b58')
        
        self.ax.grid(True, linestyle='--', alpha=0.7)
        self.line, = self.ax.plot([], [], lw=2, color='#212b58')
        self.fig.tight_layout()

    def updatePlot(self, new_title=None, ylabel=None):
        if new_title: 
            self.ax.set_title(new_title, color='#212b58', fontweight='bold')
        if ylabel:
            self.ax.set_ylabel(ylabel, color='#212b58', fontweight='bold')
        
        if not self.times or not self.values: 
            self.draw_idle()
            return
            
        self.line.set_data(self.times, self.values)
        
        # Calculate the rolling X-axis window limits
        current_time = self.times[-1]
        start_time = max(self.times[0], current_time - self.window_size)
        self.ax.set_xlim(start_time, current_time + 0.1)
        
        # Dynamically scale the Y-axis based ONLY on the data visible in the current window
        visible_values = [v for t, v in zip(self.times, self.values) if t >= start_time]
        if visible_values:
            ymin, ymax = min(visible_values), max(visible_values)
            padding = max((ymax - ymin) * 0.1, 1.0) 
            self.ax.set_ylim(ymin - padding, ymax + padding)
        
        self.draw_idle() 

class PlotLive3D(FigureCanvas):
    def __init__(self):
        self.fig = Figure(figsize=(6, 5))
        self.ax = self.fig.add_subplot(111, projection="3d")
        super().__init__(self.fig)
        self.posX, self.posY, self.posZ = [], [], []
        
        self.ax.set_title("INS Relative Position (XYZ)", fontweight="bold", color="#212b58")
        self.ax.set_xlabel("X (m)", color='#212b58', fontweight='bold')
        self.ax.set_ylabel("Y (m)", color='#212b58', fontweight='bold')
        self.ax.set_zlabel("Z (m)", color='#212b58', fontweight='bold')
        self.ax.tick_params(colors='#212b58')
        
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
        self.grid.setColor((150, 150, 150, 255))
        self.addItem(self.grid)
        self.setCameraPosition(distance=10)
        self.rocket_scale = 0.01 
        
        self.overlay = QLabel(self)
        self.overlay.setStyleSheet(
            "color: white; background-color: rgba(33, 43, 88, 220); "
            "padding: 8px; font-family: monospace; border-radius: 5px;"
        )
        self.load_rocket(STL_PATH)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.overlay.move(10, self.height() - self.overlay.height() - 10)

    def load_rocket(self, path):
        try:
            stlMesh = mesh.Mesh.from_file(path)
            verts = stlMesh.vectors.reshape(-1, 3)
            center = (verts.max(axis=0) + verts.min(axis=0)) / 2
            verts = (verts - center) * self.rocket_scale
            self.rocket = gl.GLMeshItem(vertexes=verts, faces=np.arange(len(verts)).reshape(-1, 3), smooth=True, shader='shaded', color=(0, 0, 1, 1))
            self.addItem(self.rocket)
        except:
            self.rocket = gl.GLBoxItem(color=(0, 0, 1, 1))
            self.addItem(self.rocket)

    def set_rotation(self, w, x, y, z):
        quat = QQuaternion(w, x, y, z).normalized()
        transform = QMatrix4x4()
        transform.rotate(90, 90, 90, 1) 
        transform.rotate(quat)
        self.rocket.setTransform(transform)
        
        self.overlay.setText(f"W: {w:.3f} | X: {x:.3f} | Y: {y:.3f} | Z: {z:.3f}")
        self.overlay.adjustSize()
        self.overlay.move(10, self.height() - self.overlay.height() - 10)

class MapWidget(QWebEngineView):
    def __init__(self):
        super().__init__()
        self.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        self.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        
        self.last_lat = LAUNCH_LAT
        self.last_lon = LAUNCH_LON
        self.coordinatesHistory = []
        
        local_css = os.path.join(BASE_DIR, "leaflet.css")
        local_js = os.path.join(BASE_DIR, "leaflet.js")
        
        css_source = QUrl.fromLocalFile(local_css).toString() if os.path.exists(local_css) else "leaflet.css"
        js_source = QUrl.fromLocalFile(local_js).toString() if os.path.exists(local_js) else "leaflet.js"

        local_tiles_dir = os.path.join(BASE_DIR, "tiles")
        if os.path.exists(local_tiles_dir):
            tile_url = QUrl.fromLocalFile(local_tiles_dir).toString() + "/{z}/{x}/{y}.png"
        else:
            tile_url = ""

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
                    if (typeof L === 'undefined') return;

                    try {{
                        map = L.map('map', {{ 
                            fadeAnimation: false, trackResize: true, minZoom: 10, maxZoom: 19 
                        }}).setView([{LAUNCH_LAT}, {LAUNCH_LON}], 17);
                        
                        L.tileLayer('{tile_url}', {{
                            minZoom: 10, maxZoom: 19,
                            errorTileUrl: 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7',
                            fallbackOnUrlError: true, attribution: '&copy; OpenStreetMap Offline'
                        }}).addTo(map);

                        launchMarker = L.circleMarker([{LAUNCH_LAT}, {LAUNCH_LON}], {{
                            radius: 8, fillColor: "#ff0000", color: "#ffffff", weight: 2, fillOpacity: 1
                        }}).addTo(map).bindPopup("Launch Site");

                        rocketMarker = L.circleMarker([{LAUNCH_LAT}, {LAUNCH_LON}], {{
                            radius: 10, fillColor: "#0078ff", color: "#ffffff", weight: 3, fillOpacity: 1
                        }}).addTo(map).bindPopup("Current Position");

                        path = L.polyline([], {{color: '#ffaa00', weight: 4}}).addTo(map);
                    }} catch (e) {{ console.log("Map Error: " + e); }}
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
        coords_json = json.dumps(self.coordinatesHistory)
        self.page().runJavaScript(f"if(window.restoreHistoricalPath) {{ window.restoreHistoricalPath('{coords_json}'); }}")

    def update_position(self, lat, lon):
        self.last_lat = lat
        self.last_lon = lon
        if not self.coordinatesHistory or self.coordinatesHistory[-1] != [lat, lon]:
            self.coordinatesHistory.append([lat, lon])
        self.page().runJavaScript(f"if(window.updateMarker) {{ window.updateMarker({lat}, {lon}); }}")

class PLOTSGroundStation(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PLOTS - Ground Station")
        self.resize(1280, 800) 
        self.packet_times = deque(maxlen=50)
        self.max_alt = -9999.0
        self.start_time = time.time()
        self.last_packet_time = time.time() 

        self.history = {k: [] for k in DATA_MAP.keys()}
        self.history_t = []
        if not os.path.exists(BACKUP_FILE_PATH):
            try:
                with open(BACKUP_FILE_PATH, mode='w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["System_Timestamp", "Mission_T", "Lat", "Lon", "Alt_m", "Veloc_m_s", "qR", "qI", "qJ", "qK", "insX", "insY", "insZ", "RSSI"])
            except: pass

        try:
            self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.01)
            self.ser.reset_input_buffer()
        except: 
            self.ser = None

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

        self.title_banner = QLabel("PLOTS  |  Ground Station  |  LASER - UnityRise - PL-26")
        self.title_banner.setAlignment(Qt.AlignCenter)
        self.title_banner.setFixedHeight(45)
        self.title_banner.setFont(ui_font(18))
        self.title_banner.setStyleSheet("background-color: #212b58; color: white; border-radius: 10px; padding: 5px;")
        root_layout.addWidget(self.title_banner)

        main_content = QHBoxLayout()
        root_layout.addLayout(main_content)

        left_layout = QVBoxLayout()
        self.combo_top = QComboBox()
        self.combo_top.addItems(list(DATA_MAP.keys()))
        self.combo_top.setCurrentText("Alt")
        
        self.combo_bottom = QComboBox()
        self.combo_bottom.addItems(list(DATA_MAP.keys()))
        self.combo_bottom.setCurrentText("RSSI") 

        for cb in [self.combo_top, self.combo_bottom]:
            cb.setStyleSheet("color: white; background-color: #212b58; border-radius:5px; padding:3px;")
 
        v_top_init = self.combo_top.currentText()
        v_btm_init = self.combo_bottom.currentText()
        
        # Setting a 20-second rolling window for the graphs
        self.plot2D_top = PlotLive2D(f"{v_top_init} vs Time", ylabel=f"{v_top_init} ({DATA_MAP[v_top_init]})", window_size=20.0)
        self.plot2D_bottom = PlotLive2D(f"{v_btm_init} vs Time", ylabel=f"{v_btm_init} ({DATA_MAP[v_btm_init]})", window_size=20.0)

        self.combo_top.currentTextChanged.connect(self.on_top_combo_changed)
        self.combo_bottom.currentTextChanged.connect(self.on_bottom_combo_changed)

        lbl_top = QLabel("Top Graph Variable:")
        lbl_top.setFont(ui_font(11))
        lbl_top.setStyleSheet("color: #212b58;")
        left_layout.addWidget(lbl_top)
        left_layout.addWidget(self.combo_top)
        left_layout.addWidget(self.plot2D_top)
        
        lbl_btm = QLabel("Bottom Graph Variable:")
        lbl_btm.setFont(ui_font(11))
        lbl_btm.setStyleSheet("color: #212b58;")
        left_layout.addWidget(lbl_btm)
        left_layout.addWidget(self.combo_bottom)
        left_layout.addWidget(self.plot2D_bottom)
        
        right_layout = QVBoxLayout()
        
        self.image_label1 = QLabel()
        self.image_label1.setPixmap(QPixmap(UNITYRISE_LOGO_PATH).scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.image_label2 = QLabel()
        self.image_label2.setPixmap(QPixmap(UOL_LOGO_PATH).scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.image_label3 = QLabel()
        self.image_label3.setPixmap(QPixmap(LASER_LOGO_PATH).scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        self.phase_label = QLabel("Phase Of Flight: Test")
        self.armed_label = QLabel("Status: Disarmed")
        self.alt_label = QLabel("Alt: --- ft")
        self.apogee_label = QLabel("Apogee: --- ft") 
        
        for lbl in [self.phase_label, self.armed_label, self.alt_label, self.apogee_label]:
            lbl.setFont(ui_font(11))
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color: #212b58;")

        logo_row = QHBoxLayout()
        logo_row.addWidget(self.image_label3, 1, alignment=Qt.AlignCenter) # LASER
        logo_row.addWidget(self.image_label2, 1, alignment=Qt.AlignCenter) # UoL
        logo_row.addWidget(self.image_label1, 1, alignment=Qt.AlignCenter) # UnityRise

        label_row = QHBoxLayout()
        label_row.addWidget(self.phase_label, 1, alignment=Qt.AlignCenter)
        label_row.addWidget(self.armed_label, 1, alignment=Qt.AlignCenter)
        
        alt_apogee_row = QHBoxLayout()
        alt_apogee_row.addWidget(self.alt_label, alignment=Qt.AlignCenter)
        alt_apogee_row.addWidget(self.apogee_label, alignment=Qt.AlignCenter)
        label_row.addLayout(alt_apogee_row, 1)

        right_layout.addLayout(logo_row)
        right_layout.addLayout(label_row)

        self.vis_selector = QComboBox()
        self.vis_selector.addItems(["Live Map", "INS Relative Position (XYZ)", "Rocket 3D Rotation"])
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

        self.status_label = QLabel("Status: Offline")
        self.rate_label = QLabel("Rate: 0.0 Hz")
        self.lat_label = QLabel("Latitude: ---")
        self.lon_label = QLabel("Longitude: ---")
        self.rssi_label = QLabel("RSSI: --- dBm")
        
        status_bar = QHBoxLayout()
        for lbl in [self.status_label, self.rate_label, self.lat_label, self.lon_label, self.rssi_label]:
            lbl.setFont(ui_font(10))
            lbl.setStyleSheet("color: #212b58;")
            status_bar.addWidget(lbl)
            if lbl == self.lon_label: status_bar.addStretch()
            
        right_layout.addLayout(status_bar)

        main_content.addLayout(left_layout, 2)
        main_content.addLayout(right_layout, 3)

        self.timer = QTimer()
        self.timer.timeout.connect(self.readNextPacket)
        self.timer.timeout.connect(self.updateConnectionStatus)
        self.timer.start(INTERVAL_MS)

    def on_top_combo_changed(self, text):
        self.plot2D_top.updatePlot(new_title=f"{text} vs Time", ylabel=f"{text} ({DATA_MAP[text]})")

    def on_bottom_combo_changed(self, text):
        self.plot2D_bottom.updatePlot(new_title=f"{text} vs Time", ylabel=f"{text} ({DATA_MAP[text]})")

    def handle_interface_switch(self, index):
        self.stacked_3d.setCurrentIndex(index)
        if index == 0:  
            self.mapWidget.refresh_and_restore()

    def updateConnectionStatus(self):
        if self.ser and time.time() - self.last_packet_time > UART_TIMEOUT_SEC:
            self.status_label.setText("Status: Offline")
            self.status_label.setStyleSheet("color: #212b58;")
            self.rate_label.setText("Rate: 0.0 Hz")
            self.armed_label.setText("Status: Disarmed")
            self.armed_label.setStyleSheet("color: #212b58;")

    def readNextPacket(self):
        if not self.ser or self.ser.in_waiting == 0: 
            return
            
        last_valid_line = None
        while self.ser.in_waiting:
            try:
                decoded = self.ser.readline().decode("ascii", errors="ignore").strip()
                if "," in decoded: 
                    last_valid_line = decoded
            except: 
                continue

        if not last_valid_line:
            return

        try:
            v = last_valid_line.split(",")
            if len(v) != 13: 
                return

            packet = {
                "T": time.time() - self.start_time,
                "Alt": float(v[1]),
                "Veloc": float(v[2]),
                "Lat": float(v[3]),
                "Lon": float(v[4]),
                "qR": float(v[5]),
                "qI": float(v[6]),
                "qJ": float(v[7]),
                "qK": float(v[8]),
                "insX": float(v[9]),
                "insY": float(v[10]),
                "insZ": float(v[11]),
                "RSSI": int(float(v[12].strip()))
            }

            self.last_packet_time = time.time() 

            # CSV writes RAW hardware data (meters)
            try:
                with open(BACKUP_FILE_PATH, mode='a', newline='') as backup_file:
                    writer = csv.writer(backup_file)
                    writer.writerow([
                        time.time(), packet["T"], packet["Lat"], packet["Lon"], packet["Alt"],
                        packet["Veloc"], packet["qR"], packet["qI"], packet["qJ"], packet["qK"],
                        packet["insX"], packet["insY"], packet["insZ"], packet["RSSI"]
                    ])
            except: pass

            if packet["Alt"] > self.max_alt:
                self.max_alt = packet["Alt"]

            alt_ft = packet["Alt"] * METRE_TO_FEET
            max_alt_ft = self.max_alt * METRE_TO_FEET

            self.lat_label.setText(f"Lat: {packet['Lat']:.5f}")
            self.lon_label.setText(f"Lon: {packet['Lon']:.5f}")
            self.alt_label.setText(f"Alt: {alt_ft:.2f} ft")
            self.apogee_label.setText(f"Apogee: {max(0.0, max_alt_ft):.2f} ft")
            self.rssi_label.setText(f"RSSI: {packet['RSSI']} dBm")
            
            self.status_label.setText("Status: Online")
            self.status_label.setStyleSheet("color: #00ff6a; font-weight: bold;")
            self.armed_label.setText("Status: Armed")
            self.armed_label.setStyleSheet("color: red; font-weight: bold;")

            self.history_t.append(packet["T"])
            for key in DATA_MAP.keys():
                if key == "Alt":
                    self.history[key].append(alt_ft)
                else:
                    self.history[key].append(packet[key])

            is_moving = abs(packet["Veloc"]) > 0.5
            if not is_moving:
                if self.max_alt < 10.0 and packet["Alt"] < 5.0:
                    phase_val = "ON PAD (STATIONARY)"
                elif self.max_alt > 20.0 and packet["Alt"] < 5.0:
                    phase_val = "LANDED (STATIONARY)"
                else:
                    phase_val = "STATIONARY"
            else:
                last_alt_m = self.history["Alt"][-2] / METRE_TO_FEET if len(self.history["Alt"]) > 1 else packet["Alt"]
                if packet["Alt"] < 5.0 and self.max_alt < 10.0:
                    phase_val = "ON PAD (MOVING)"
                elif packet["Alt"] > last_alt_m + 0.2:
                    phase_val = "ASCENT"
                elif packet["Alt"] < self.max_alt - 2.0 and packet["Alt"] > 5.0:
                    phase_val = "DESCENT"
                elif packet["Alt"] < 5.0 and self.max_alt > 20.0:
                    phase_val = "LANDED"
                else:
                    phase_val = "COASTING"
            self.phase_label.setText(f"Phase Of Flight: {phase_val}")

            self.mapWidget.update_position(packet["Lat"], packet["Lon"])

            v_top = self.combo_top.currentText()
            self.plot2D_top.times = self.history_t
            self.plot2D_top.values = self.history[v_top]
            self.plot2D_top.updatePlot(new_title=f"{v_top} vs Time", ylabel=f"{v_top} ({DATA_MAP[v_top]})")

            v_btm = self.combo_bottom.currentText()
            self.plot2D_bottom.times = self.history_t
            self.plot2D_bottom.values = self.history[v_btm]
            self.plot2D_bottom.updatePlot(new_title=f"{v_btm} vs Time", ylabel=f"{v_btm} ({DATA_MAP[v_btm]})")

            self.plot3D.posX.append(packet["insX"])
            self.plot3D.posY.append(packet["insY"])
            self.plot3D.posZ.append(packet["insZ"])
            if self.vis_selector.currentText() == "INS Relative Position (XYZ)":
                self.plot3D.updatePlot()

            self.rotation3D.set_rotation(packet["qR"], packet["qI"], packet["qJ"], packet["qK"])

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