import sys
import time
import os
import numpy as np
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

CSV_PATH = os.path.join(BASE_DIR, "telemetryTamworth.csv")
FONT_PATH = os.path.join(ASSETS_DIR, "Orbitron-VariableFont_wght.ttf")
LASER_LOGO_PATH = os.path.join(ASSETS_DIR, "LASER_Logo.png")
UNITYRISE_LOGO_PATH = os.path.join(ASSETS_DIR, "unityrise_logo.png")
UOL_LOGO_PATH = os.path.join(ASSETS_DIR, "uol_logo.png")
STL_PATH = os.path.join(BASE_DIR, "rocket.stl") 

# -------------------- Configuration --------------------
INTERVAL_MS = 100
LAUNCH_LAT = 52.668
LAUNCH_LON = -1.5245

DATA_MAP = {
    "T": 0, "Lat": 1, "Lon": 2, "Alt": 3, "Veloc": 4, 
    "qR": 5, "qI": 6, "qJ": 7, "qK": 8,
    "insX": 9, "insY": 10, "insZ": 11, "RSSI": 12
}

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

    def updatePlot(self, new_title=None):
        if not self.times or not self.values: return
        if new_title: self.ax.set_title(new_title)
        self.line.set_data(self.times, self.values)
        self.ax.relim()
        self.ax.autoscale_view()
        self.draw_idle()

class PlotLive3D(FigureCanvas):
    def __init__(self):
        self.fig = Figure(figsize=(9,7))
        self.ax = self.fig.add_subplot(111, projection="3d")
        super().__init__(self.fig)
        self.posX, self.posY, self.posZ = [], [] ,[]

    def updatePlot(self):
        if not self.posX: return
        self.ax.clear()
        self.ax.set_title("Live INS Relative Position", fontweight="bold")
        self.ax.plot(self.posX, self.posY, self.posZ, lw=1.5, color="#212b58")
        self.ax.scatter([self.posX[-1]], [self.posY[-1]], [self.posZ[-1]], s=60, color="red")
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
        
        self.osm_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <link rel="stylesheet" href="leaflet.css" />
            <script src="leaflet.js"></script>
            <style>
                body {{ margin: 0; padding: 0; background: #212b58; font-family: sans-serif; overflow: hidden; }}
                #map {{ width: 100vw; height: 100vh; background: #ccd; }}
            </style>
        </head>
        <body>
            <div id="map"></div>
            <script>
                var map, rocketMarker, launchMarker, path;
                var initialSet = false;

                function initMap() {{
                    try {{
                        map = L.map('map').setView([{LAUNCH_LAT}, {LAUNCH_LON}], 16);
                        
                        L.tileLayer('tiles/{{z}}/{{x}}/{{y}}.png', {{
                            maxZoom: 18,
                            attribution: 'Offline Map'
                        }}).addTo(map);

                        launchMarker = L.circleMarker([{LAUNCH_LAT}, {LAUNCH_LON}], {{
                            radius: 8, fillColor: "#ff0000", color: "#000", weight: 2, fillOpacity: 1
                        }}).addTo(map).bindPopup("Launch Site");

                        rocketMarker = L.circleMarker([{LAUNCH_LAT}, {LAUNCH_LON}], {{
                            radius: 10, fillColor: "#0078ff", color: "#ffffff", weight: 3, fillOpacity: 1
                        }}).addTo(map).bindPopup("Current Position");

                        path = L.polyline([], {{color: '#212b58', weight: 4}}).addTo(map);
                    }} catch (e) {{
                        console.log("Map Error: " + e);
                    }}
                }}

                window.updateMarker = function(lat, lon) {{
                    if (typeof map !== 'undefined' && map && rocketMarker) {{
                        var newPos = [lat, lon];
                        rocketMarker.setLatLng(newPos);
                        path.addLatLng(newPos);
                        map.panTo(newPos);
                        
                        if(!initialSet) {{
                            launchMarker.setLatLng(newPos);
                            initialSet = true;
                        }}
                    }}
                }};
                window.onload = initMap;
            </script>
        </body>
        </html>
        """
        baseUrl = QUrl.fromLocalFile(os.path.join(BASE_DIR, "index.html"))
        self.setHtml(self.osm_html, baseUrl)

    def update_position(self, lat, lon):
        self.page().runJavaScript(f"if(window.updateMarker) {{ window.updateMarker({lat}, {lon}); }}")

# -------------------- Main Mission Control --------------------

class PLOTSGroundStation(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LASER - UnityRise Mission Control - PL-26")
        self.resize(1280, 800) 
        self.last_row_index = 0 
        self.packet_times = deque(maxlen=50)
        self.max_alt = -9999.0

        self.history = {k: [] for k in DATA_MAP.keys()}
        self.history_t = []

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
        left_layout.addWidget(self.plot2D_top)
        left_layout.addWidget(QLabel("Bottom Graph Variable:"))
        left_layout.addWidget(self.combo_bottom)
        left_layout.addWidget(self.plot2D_bottom)

        # Right side: Visuals and Labels
        right_layout = QVBoxLayout()
        logo_row = QHBoxLayout()
        
        laser_vbox = QVBoxLayout()
        self.laser_img = QLabel()
        self.laser_img.setPixmap(QPixmap(LASER_LOGO_PATH).scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.laser_img.setAlignment(Qt.AlignCenter)
        self.phase_label = QLabel("PHASE: PRE-LAUNCH")
        self.phase_label.setAlignment(Qt.AlignCenter)
        self.phase_label.setFont(ui_font(10))
        self.phase_label.setStyleSheet("color: #212b58; background: #f0f0f0; padding: 5px; border-radius: 3px;")
        laser_vbox.addWidget(self.laser_img)
        laser_vbox.addWidget(self.phase_label)

        uol_vbox = QVBoxLayout()
        self.uol_img = QLabel()
        self.uol_img.setPixmap(QPixmap(UOL_LOGO_PATH).scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.uol_img.setAlignment(Qt.AlignCenter)
        self.status_label = QLabel("STATUS: OFFLINE")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(ui_font(10))
        uol_vbox.addWidget(self.uol_img)
        uol_vbox.addWidget(self.status_label)

        unity_vbox = QVBoxLayout()
        self.unity_img = QLabel()
        self.unity_img.setPixmap(QPixmap(UNITYRISE_LOGO_PATH).scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.unity_img.setAlignment(Qt.AlignCenter)
        self.alt_label = QLabel("ALT: 0.00 m")
        self.alt_label.setAlignment(Qt.AlignCenter)
        self.alt_label.setFont(ui_font(14)) 
        self.alt_label.setStyleSheet("color: #212b58; font-weight: bold;")
        unity_vbox.addWidget(self.unity_img)
        unity_vbox.addWidget(self.alt_label)
        
        logo_row.addLayout(laser_vbox); logo_row.addStretch()
        logo_row.addLayout(uol_vbox); logo_row.addStretch()
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
        self.vis_selector.currentIndexChanged.connect(self.stacked_3d.setCurrentIndex)

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

        main_content.addLayout(left_layout, 2)
        main_content.addLayout(right_layout, 3)

        self.timer = QTimer()
        self.timer.timeout.connect(self.readNextPacket)
        self.timer.start(INTERVAL_MS)

    def readNextPacket(self):
        if not os.path.exists(CSV_PATH): 
            self.status_label.setText("STATUS: NO FILE")
            return
            
        try:
            with open(CSV_PATH, 'r') as f:
                lines = f.readlines()
                
                if len(lines) > self.last_row_index:
                    line = lines[self.last_row_index].strip()
                    self.last_row_index += 1
                    
                    if not line or line.lower().startswith('t') or "," not in line:
                        return
                    
                    raw_data = [x.strip() for x in line.split(",")]
                    
                    def get_val(idx, default=0.0):
                        if idx < len(raw_data):
                            try: return float(raw_data[idx])
                            except: return default
                        return default

                    t = get_val(DATA_MAP["T"])
                    lat = get_val(DATA_MAP["Lat"])
                    lon = get_val(DATA_MAP["Lon"])
                    alt = get_val(DATA_MAP["Alt"])
                    rssi_val = get_val(DATA_MAP["RSSI"], -70.0)
                    
                    self.history_t.append(t)
                    for key, index in DATA_MAP.items():
                        self.history[key].append(get_val(index, 1.0 if key=="qR" else 0.0))

                    qr, qi, qj, qk = (get_val(DATA_MAP[k], 1.0 if k=="qR" else 0.0) for k in ["qR", "qI", "qJ", "qK"])
                    ix, iy, iz = (get_val(DATA_MAP[k]) for k in ["insX", "insY", "insZ"])

                    if self.max_alt == -9999.0: self.max_alt = alt
                    if alt > self.max_alt: self.max_alt = alt
                    
                    if alt < 5.0 and self.max_alt < 10.0:
                        phase_val = "ON PAD"
                    elif alt > (self.history["Alt"][-2] if len(self.history["Alt"])>1 else alt) + 0.2:
                        phase_val = "ASCENT"
                    elif alt < self.max_alt - 2.0 and alt > 5.0:
                        phase_val = "DESCENT"
                    elif alt < 5.0 and self.max_alt > 20.0:
                        phase_val = "LANDED"
                    else:
                        phase_val = "COASTING"

                    self.phase_label.setText(f"PHASE: {phase_val}")
                    self.alt_label.setText(f"ALT: {alt:.2f} m")
                    self.lat_label.setText(f"Lat: {lat:.5f}")
                    self.lon_label.setText(f"Long: {lon:.5f}")
                    self.rssi_label.setText(f"RSSI: {rssi_val:.0f} dBm")
                    self.status_label.setText("STATUS: RECEIVING")
                    self.status_label.setStyleSheet("color: #00aa00; font-weight: bold;")

                    self.mapWidget.update_position(lat, lon)
                    
                    v_top = self.combo_top.currentText()
                    self.plot2D_top.times = self.history_t
                    self.plot2D_top.values = self.history[v_top]
                    self.plot2D_top.updatePlot(f"Live {v_top}")

                    v_btm = self.combo_bottom.currentText()
                    self.plot2D_bottom.times = self.history_t
                    self.plot2D_bottom.values = self.history[v_btm]
                    self.plot2D_bottom.updatePlot(f"Live {v_btm}")

                    self.plot3D.posX.append(ix); self.plot3D.posY.append(iy); self.plot3D.posZ.append(iz)
                    if self.vis_selector.currentText() == "3D Trajectory":
                        self.plot3D.updatePlot()
                    
                    self.rotation3D.set_rotation(qr, qi, qj, qk)

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
