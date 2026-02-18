import sys
import time
import os
import serial
import re
import numpy as np
from collections import deque
from stl import mesh

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QComboBox, QStackedWidget
)
from PySide6.QtCore import QTimer, Qt
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
STL_PATH = os.path.join(BASE_DIR, "rocket.stl") 
CALIB_FILE = os.path.join(BASE_DIR, "quaternion_calibration.txt")

# -------------------- Serial config --------------------
if sys.platform.startswith("win"):
    SERIAL_PORT = "COM3"
else:
    SERIAL_PORT = "/dev/ttyAMA0"

BAUD_RATE = 115200
INTERVAL_MS = 30
UART_TIMEOUT_SEC = 1.0

UNITS = {
    "T": "s", "Alt": "m", "Veloc": "m/s", "Lat": "deg", "Lon": "deg",
    "qR": "float", "qI": "float", "qJ": "float", "qK": "float",
    "insX": "m", "insY": "m", "insZ": "m", "RSSI": "dBm"
}

# -------------------- Visualization Classes --------------------

class PlotLive2D(FigureCanvas):
    def __init__(self, title):
        self.fig = Figure(figsize=(5, 3))
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.times, self.values = [], []
        self.ax.set_title(title)
        self.ax.grid(True)
        self.line, = self.ax.plot([], [], lw=2)

    def resetPlot(self, title, ylabel):
        self.ax.clear()
        self.ax.set_title(title)
        self.ax.set_ylabel(ylabel)
        self.ax.grid(True)
        self.times.clear()
        self.values.clear()
        self.line, = self.ax.plot([], [], lw=2)
        self.draw()

    def updatePlot(self):
        if not self.times: return
        self.line.set_data(self.times, self.values)
        self.ax.relim()
        self.ax.autoscale_view()
        self.draw_idle()

class PlotLive3D(FigureCanvas):
    def __init__(self):
        self.fig = Figure(figsize=(9, 7))
        self.ax = self.fig.add_subplot(111, projection="3d")
        super().__init__(self.fig)
        self.posX, self.posY, self.posZ = [], [] ,[]

    def updatePlot(self):
        if not self.posX: return
        self.ax.clear()
        self.ax.set_title("Live INS Relative Position (XYZ)", fontweight="bold", color="#212b58")
        self.ax.set_xlabel("X (m)")
        self.ax.set_ylabel("Y (m)")
        self.ax.set_zlabel("Z (m)")
        self.ax.plot(self.posX, self.posY, self.posZ, lw=1.5, color="#212b58")
        self.ax.scatter([self.posX[-1]], [self.posY[-1]], [self.posZ[-1]], s=60, color="red")
        self.draw_idle()

class RocketRotationWidget(gl.GLViewWidget):
    def __init__(self):
        super().__init__()
        self.setBackgroundColor('w')
        self.grid = gl.GLGridItem()
        self.grid.setColor((150, 150, 150, 255))
        self.addItem(self.grid)
        self.setCameraPosition(distance=30)
        self.rocket_scale = 0.01 
        
        # Initialize calibration offset
        self.offset_q = QQuaternion(1, 0, 0, 0) # Default identity
        self.load_calibration()

        self.overlay = QLabel(self)
        self.overlay.setStyleSheet("color: white; background-color: rgba(33, 43, 88, 220); padding: 8px; font-family: monospace; border-radius: 5px;")
        self.load_rocket(STL_PATH)

    def load_calibration(self):
        """Parses the text file for the last 'LEVEL' pose to use as offset."""
        if not os.path.exists(CALIB_FILE):
            print("No calibration file found. Using default identity.")
            return

        try:
            with open(CALIB_FILE, "r") as f:
                lines = f.readlines()
            
            # Search backwards for the last 'LEVEL' pose
            for line in reversed(lines):
                if "Pose: LEVEL" in line:
                    # Regex to find numbers inside [ ]
                    match = re.search(r"\[(.*?),(.*?),(.*?),(.*?)\]", line)
                    if match:
                        w, i, j, k = map(float, match.groups())
                        # The offset is the INVERSE of the physical level position
                        self.offset_q = QQuaternion(w, i, j, k).inverted()
                        print(f"Loaded Calibration Offset: W:{w} I:{i} J:{j} K:{k}")
                        return
        except Exception as e:
            print(f"Error loading calibration: {e}")

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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.overlay.move(10, self.height() - self.overlay.height() - 10)

    def set_rotation(self, w, x, y, z):
        # Current raw sensor reading
        raw_quat = QQuaternion(w, x, y, z).normalized()
        
        # Apply calibration offset (Raw * Offset_Inv)
        # This makes the 'LEVEL' physical orientation look 'level' in 3D
        calibrated_quat = raw_quat * self.offset_q
        
        transform = QMatrix4x4()
        transform.rotate(calibrated_quat)
        self.rocket.setTransform(transform)
        
        self.overlay.setText(f"RAW -> W: {w:.3f} | X: {x:.3f} | Y: {y:.3f} | Z: {z:.3f}")
        self.overlay.adjustSize()
        self.overlay.move(10, self.height() - self.overlay.height() - 10)

# -------------------- Main Mission Control --------------------

class PLOTSGroundStation(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LASER - UnityRise Mission Control - PL-26")
        self.resize(1200, 800)

        font_id = QFontDatabase.addApplicationFont(FONT_PATH)
        self.ui_font_family = QFontDatabase.applicationFontFamilies(font_id)[0] if font_id != -1 else "Arial"

        def ui_font(size, weight=QFont.Weight.Bold):
            f = QFont(self.ui_font_family, size)
            f.setWeight(weight)
            return f

        self.title_banner = QLabel("LASER – UnityRise Mission Control - PL-26")
        self.title_banner.setAlignment(Qt.AlignCenter)
        self.title_banner.setFixedHeight(45)
        self.title_banner.setFont(ui_font(18))
        self.title_banner.setStyleSheet("background-color: #212b58; color: white; border-radius: 10px; padding: 5px;")

        try:
            self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.01)
            self.ser.reset_input_buffer()
        except: self.ser = None
        
        self.start_time = time.time()
        self.last_packet_time = 0
        self.packet_times = deque(maxlen=200)

        # UI Labels
        blue_style = "color: #212b58;"
        self.status_label = QLabel("Status: Offline")
        self.armed_label = QLabel("Status: Disarmed")
        self.rate_label = QLabel("Rate: 0.0 Hz")
        self.lat_label = QLabel("Lat: ---")
        self.lon_label = QLabel("Lon: ---")
        self.rssi_label = QLabel("RSSI: --- dBm")
        self.alt_label = QLabel("Alt: --- m")
        self.phase_label = QLabel("Phase: Test")

        for lbl in [self.status_label, self.armed_label, self.rate_label, self.lat_label, self.lon_label, self.rssi_label, self.alt_label, self.phase_label]:
            lbl.setFont(ui_font(11))
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(blue_style)

        self.visualizer_selector = QComboBox()
        self.visualizer_selector.addItems(["3D Relative Position", "Rocket Attitude (3D Rotation)"])
        self.visualizer_selector.currentIndexChanged.connect(lambda i: self.stacked_3d.setCurrentIndex(i))
        self.visualizer_selector.setStyleSheet("color: white; background-color: #212b58; border-radius:5px; padding:3px;")

        self.plot3D = PlotLive3D()
        self.rotation3D = RocketRotationWidget()
        self.stacked_3d = QStackedWidget()
        self.stacked_3d.addWidget(self.plot3D)
        self.stacked_3d.addWidget(self.rotation3D)

        self.image_label1 = QLabel(); self.image_label1.setPixmap(QPixmap(UNITYRISE_LOGO_PATH).scaled(100, 100, Qt.KeepAspectRatio))
        self.image_label2 = QLabel(); self.image_label2.setPixmap(QPixmap(UOL_LOGO_PATH).scaled(200, 200, Qt.KeepAspectRatio))
        self.image_label3 = QLabel(); self.image_label3.setPixmap(QPixmap(LASER_LOGO_PATH).scaled(100, 100, Qt.KeepAspectRatio))

        img_row = QHBoxLayout()
        for l, b in [(self.image_label3, self.phase_label), (self.image_label2, self.armed_label), (self.image_label1, self.alt_label)]:
            v = QVBoxLayout(); v.addWidget(l, alignment=Qt.AlignCenter); v.addWidget(b); img_row.addLayout(v)

        right_layout = QVBoxLayout()
        right_layout.addLayout(img_row)
        right_layout.addWidget(self.visualizer_selector)
        right_layout.addWidget(self.stacked_3d)
        
        status_bar = QHBoxLayout()
        status_bar.addWidget(self.status_label); status_bar.addWidget(self.rate_label); status_bar.addWidget(self.lat_label)
        status_bar.addWidget(self.lon_label); status_bar.addStretch(); status_bar.addWidget(self.rssi_label)
        right_layout.addLayout(status_bar)

        left_layout = QVBoxLayout()
        self.plot2D_top = PlotLive2D("Alt vs Time")
        self.plot2D_bottom = PlotLive2D("RSSI vs Time")
        self.combo_top = QComboBox(); self.combo_bottom = QComboBox()
        vars_ = [k for k in UNITS.keys() if k != "T"]
        self.combo_top.addItems(vars_); self.combo_bottom.addItems(vars_)
        self.combo_top.setCurrentText("Alt"); self.combo_bottom.setCurrentText("RSSI")
        self.combo_top.setStyleSheet("color: white; background-color: #212b58; border-radius:5px; padding:3px;")
        self.combo_bottom.setStyleSheet("color: white; background-color: #212b58; border-radius:5px; padding:3px;")
        
        self.combo_top.currentTextChanged.connect(self.changeTopVariable)
        self.combo_bottom.currentTextChanged.connect(self.changeBottomVariable)

        left_layout.addWidget(QLabel("Top Plot Variable:")); left_layout.addWidget(self.combo_top); left_layout.addWidget(self.plot2D_top)
        left_layout.addWidget(QLabel("Bottom Plot Variable:")); left_layout.addWidget(self.combo_bottom); left_layout.addWidget(self.plot2D_bottom)

        main_layout = QHBoxLayout()
        main_layout.addLayout(left_layout, 2)
        main_layout.addLayout(right_layout, 3)

        root = QVBoxLayout(); root.addWidget(self.title_banner); root.addLayout(main_layout)
        container = QWidget(); container.setLayout(root); container.setStyleSheet("background-color: white;")
        self.setCentralWidget(container)

        self.timer = QTimer()
        self.timer.timeout.connect(self.readNextPacket)
        self.timer.timeout.connect(self.updateConnectionStatus)
        self.timer.start(INTERVAL_MS)

    def changeTopVariable(self, var): self.plot2D_top.resetPlot(f"{var} vs Time", f"{var} ({UNITS.get(var,'')})")
    def changeBottomVariable(self, var): self.plot2D_bottom.resetPlot(f"{var} vs Time", f"{var} ({UNITS.get(var,'')})")
    
    def updateConnectionStatus(self):
        if self.ser and time.time() - self.last_packet_time > UART_TIMEOUT_SEC:
            self.status_label.setText("Status: Offline")
            self.status_label.setStyleSheet("color: #212b58;")
            self.rate_label.setText("Rate: 0.0 Hz")
            self.armed_label.setText("Status: Disarmed")
            self.armed_label.setStyleSheet("color: #212b58;")

    def readNextPacket(self):
        if not self.ser or self.ser.in_waiting == 0: return
        last_valid_line = None
        while self.ser.in_waiting:
            try:
                decoded = self.ser.readline().decode("ascii", errors="ignore").strip()
                if "," in decoded: last_valid_line = decoded
            except: continue
        if not last_valid_line: return
        
        v = last_valid_line.split(",")
        if len(v) != 13: return
        
        try:
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
            self.packet_times.append(self.last_packet_time)
            
            # Rate Calculation
            now = time.time()
            while self.packet_times and now - self.packet_times[0] > 1.0:
                self.packet_times.popleft()
            
            # UI Updates
            self.status_label.setText("Status: Online")
            self.status_label.setStyleSheet("color: #00ff6a;")
            self.rate_label.setText(f"Rate: {len(self.packet_times):.1f} Hz")
            self.armed_label.setText("Status: Armed")
            self.armed_label.setStyleSheet("color: red;")
            
            self.lat_label.setText(f"Lat: {packet['Lat']:.5f}")
            self.lon_label.setText(f"Lon: {packet['Lon']:.5f}")
            self.rssi_label.setText(f"RSSI: {packet['RSSI']} dBm")
            self.alt_label.setText(f"Alt : {packet['Alt']:.2f} m")

            # Update Plots
            self.plot2D_top.times.append(packet["T"])
            self.plot2D_top.values.append(packet.get(self.combo_top.currentText(), 0))
            self.plot2D_top.updatePlot()

            self.plot2D_bottom.times.append(packet["T"])
            self.plot2D_bottom.values.append(packet.get(self.combo_bottom.currentText(), 0))
            self.plot2D_bottom.updatePlot()
            
            self.plot3D.posX.append(packet["insX"])
            self.plot3D.posY.append(packet["insY"])
            self.plot3D.posZ.append(packet["insZ"])
            self.plot3D.updatePlot()
            
            self.rotation3D.set_rotation(packet["qR"], packet["qI"], packet["qJ"], packet["qK"])
        except Exception as e: 
            print(f"Error: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PLOTSGroundStation()
    window.show()
    sys.exit(app.exec())