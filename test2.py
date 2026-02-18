# Program: PLOTS_INS_Test.py
import sys
import time
import os
import serial
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
STL_PATH = os.path.join(BASE_DIR, "rocket.stl") 

# -------------------- Serial config --------------------
SERIAL_PORT = "COM3" if sys.platform.startswith("win") else "/dev/ttyAMA0"
BAUD_RATE = 115200
INTERVAL_MS = 20  # Increased speed for better sync
UART_TIMEOUT_SEC = 1.0

UNITS = {
    "T": "s", "Alt": "m", "Veloc": "m/s", "Lat": "deg", "Lon": "deg",
    "qR": "float", "qI": "float", "qJ": "float", "qK": "float",
    "insX": "m", "insY": "m", "insZ": "m", "RSSI": "dBm"
}

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
        self.times.clear(); self.values.clear()
        self.line, = self.ax.plot([], [], lw=2)
        self.draw()

    def updatePlot(self):
        if not self.times: return
        self.line.set_data(self.times, self.values)
        self.ax.relim(); self.ax.autoscale_view(); self.draw_idle()

class PlotLive3D(FigureCanvas):
    def __init__(self):
        self.fig = Figure(figsize=(9, 7))
        self.ax = self.fig.add_subplot(111, projection="3d")
        super().__init__(self.fig)
        self.posX, self.posY, self.posZ = [], [], []

    def updatePlot(self):
        if not self.posX: return
        self.ax.clear()
        self.ax.set_title("Live INS Relative Position (XYZ)", fontweight="bold", color="#212b58")
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
        
        # Tare storage
        self.tare_quat = None 
        
        self.overlay = QLabel(self)
        self.overlay.setStyleSheet("color: white; background-color: rgba(33, 43, 88, 220); padding: 8px; font-family: monospace; border-radius: 5px;")
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
        raw_quat = QQuaternion(w, x, y, z).normalized()
        
        # Initial Tare calibration
        if self.tare_quat is None:
            self.tare_quat = raw_quat.inverted()
        
        # Apply tare to get relative rotation
        final_quat = raw_quat * self.tare_quat
        
        transform = QMatrix4x4()
        transform.rotate(final_quat)
        self.rocket.setTransform(transform)
        
        self.overlay.setText(f"W: {w:.3f} | X: {x:.3f} | Y: {y:.3f} | Z: {z:.3f}")
        self.overlay.adjustSize()

class PLOTSGroundStation(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LASER - Mission Control")
        self.resize(1200, 800)
        
        # UI Font Setup
        font_id = QFontDatabase.addApplicationFont(os.path.join(ASSETS_DIR, "Orbitron-VariableFont_wght.ttf"))
        self.ui_font_family = QFontDatabase.applicationFontFamilies(font_id)[0] if font_id != -1 else "Arial"

        # Serial Port
        try:
            self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.001) # Low timeout to prevent jumps
            self.ser.reset_input_buffer()
        except: self.ser = None
        
        self.start_time = time.time()
        self.last_packet_time = 0
        self.packet_times = deque(maxlen=200)

        # UI Components
        self.status_label = QLabel("Status: Offline")
        self.rate_label = QLabel("Rate: 0.0 Hz")
        self.lat_label = QLabel("Lat: ---"); self.lon_label = QLabel("Lon: ---")
        self.rssi_label = QLabel("RSSI: --- dBm"); self.alt_label = QLabel("Alt: --- m")
        
        self.rotation3D = RocketRotationWidget()
        self.plot3D = PlotLive3D()
        self.stacked_3d = QStackedWidget()
        self.stacked_3d.addWidget(self.plot3D); self.stacked_3d.addWidget(self.rotation3D)

        self.visualizer_selector = QComboBox()
        self.visualizer_selector.addItems(["3D Position", "Rocket Rotation"])
        self.visualizer_selector.currentIndexChanged.connect(lambda i: self.stacked_3d.setCurrentIndex(i))

        # Build UI (Simplified for brevity, similar to your working layout)
        layout = QVBoxLayout()
        banner = QLabel("LASER – UnityRise Mission Control - PL-26")
        banner.setStyleSheet("background-color: #212b58; color: white; padding: 10px; font-size: 18pt; font-weight: bold; border-radius: 10px;")
        banner.setAlignment(Qt.AlignCenter)
        
        main_h = QHBoxLayout()
        left = QVBoxLayout()
        self.plot2D_top = PlotLive2D("Alt")
        self.plot2D_bottom = PlotLive2D("RSSI")
        self.combo_top = QComboBox(); self.combo_top.addItems(list(UNITS.keys())[1:])
        self.combo_bottom = QComboBox(); self.combo_bottom.addItems(list(UNITS.keys())[1:])
        left.addWidget(self.combo_top); left.addWidget(self.plot2D_top)
        left.addWidget(self.combo_bottom); left.addWidget(self.plot2D_bottom)
        
        right = QVBoxLayout()
        right.addWidget(self.visualizer_selector); right.addWidget(self.stacked_3d)
        
        main_h.addLayout(left, 2); main_h.addLayout(right, 3)
        layout.addWidget(banner); layout.addLayout(main_h)
        
        central = QWidget(); central.setLayout(layout); central.setStyleSheet("background-color: white;")
        self.setCentralWidget(central)

        self.timer = QTimer()
        self.timer.timeout.connect(self.readNextPacket)
        self.timer.start(INTERVAL_MS)

    def readNextPacket(self):
        if not self.ser or self.ser.in_waiting == 0: return
        
        last_valid_line = None
        while self.ser.in_waiting > 0:
            try:
                line = self.ser.readline().decode("ascii", errors="ignore").strip()
                if line.count(',') == 12: last_valid_line = line
            except: continue

        if not last_valid_line: return
        
        try:
            v = last_valid_line.split(",")
            packet = {
                "T": time.time() - self.start_time,
                "Alt": float(v[1]), "Veloc": float(v[2]),
                "Lat": float(v[3]), "Lon": float(v[4]),
                "qR": float(v[5]), "qI": float(v[6]),
                "qJ": float(v[7]), "qK": float(v[8]),
                "insX": float(v[9]), "insY": float(v[10]), "insZ": float(v[11]),
                "RSSI": int(float(v[12].strip()))
            }
            
            # --- LIVE UPDATE ---
            self.last_packet_time = time.time()
            self.packet_times.append(self.last_packet_time)
            
            # Rotation (Live Calibration Applied Inside)
            # IMPORTANT: Swapping axes here if movement is inverted
            # Try: (qR, qI, qJ, qK) or (qR, qJ, qI, qK) etc.
            self.rotation3D.set_rotation(packet["qR"], packet["qI"], packet["qJ"], packet["qK"])
            
            # Update Hz
            now = time.time()
            while self.packet_times and now - self.packet_times[0] > 1.0: self.packet_times.popleft()
            self.rate_label.setText(f"Rate: {len(self.packet_times)} Hz")
            self.rssi_label.setText(f"RSSI: {packet['RSSI']} dBm")
            
            # Update 3D path and 2D plots
            self.plot3D.posX.append(packet["insX"])
            self.plot3D.posY.append(packet["insY"])
            self.plot3D.posZ.append(packet["insZ"])
            self.plot3D.updatePlot()
            
        except Exception as e: print(f"Error: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PLOTSGroundStation()
    window.show()
    sys.exit(app.exec())