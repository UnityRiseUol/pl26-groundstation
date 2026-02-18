# Program: PLOTS_INS_Test.py
# Purpose: Professional Ground Station for PL-26 with BNO085 Sync & Calibration
import sys
import time
import os
import serial
import numpy as np
from collections import deque
from stl import mesh

# Using PySide6 for maximum performance on Raspberry Pi 5
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QComboBox, QStackedWidget, QFrame
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
INTERVAL_MS = 20  # 50Hz refresh rate for smooth visuals
UART_TIMEOUT_SEC = 1.0

UNITS = {
    "T": "s", "Alt": "m", "Veloc": "m/s", "Lat": "deg", "Lon": "deg",
    "qR": "float", "qI": "float", "qJ": "float", "qK": "float",
    "insX": "m", "insY": "m", "insZ": "m", "RSSI": "dBm"
}

# -------------------- Visualization Classes --------------------

class PlotLive2D(FigureCanvas):
    def __init__(self, title):
        self.fig = Figure(figsize=(5, 3), dpi=100)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.times, self.values = [], []
        self.ax.set_title(title, fontweight='bold', color='#212b58')
        self.ax.grid(True, linestyle='--', alpha=0.6)
        self.line, = self.ax.plot([], [], lw=2, color='#212b58')

    def resetPlot(self, title, ylabel):
        self.ax.clear()
        self.ax.set_title(title, fontweight='bold', color='#212b58')
        self.ax.set_ylabel(ylabel)
        self.ax.grid(True, linestyle='--', alpha=0.6)
        self.times.clear(); self.values.clear()
        self.line, = self.ax.plot([], [], lw=2, color='#212b58')
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
        
        # Calibration Storage
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
        
        # Initial Auto-Calibration: Sets the first orientation as "Up"
        if self.tare_quat is None:
            self.tare_quat = raw_quat.inverted()
        
        final_quat = raw_quat * self.tare_quat
        
        transform = QMatrix4x4()
        transform.rotate(final_quat)
        self.rocket.setTransform(transform)
        self.overlay.setText(f"QUAT: W:{w:.2f} X:{x:.2f} Y:{y:.2f} Z:{z:.2f}")
        self.overlay.adjustSize()

# -------------------- Main Mission Control --------------------

class PLOTSGroundStation(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LASER - UnityRise Mission Control")
        self.resize(1200, 850)

        # UI Styling
        font_path = os.path.join(ASSETS_DIR, "Orbitron-VariableFont_wght.ttf")
        font_id = QFontDatabase.addApplicationFont(font_path)
        self.ui_font_family = QFontDatabase.applicationFontFamilies(font_id)[0] if font_id != -1 else "Arial"

        def ui_font(size, bold=True):
            f = QFont(self.ui_font_family, size)
            if bold: f.setWeight(QFont.Bold)
            return f

        # Serial & Data Management
        try:
            self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.001)
            self.ser.reset_input_buffer()
        except: self.ser = None
        
        self.start_time = time.time()
        self.last_packet_time = 0
        self.packet_times = deque(maxlen=100)

        # --- UI LAYOUT ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_vbox = QVBoxLayout(central_widget)

        # Header Banner
        self.banner = QLabel("LASER – UNITYRISE MISSION CONTROL – PL-26")
        self.banner.setAlignment(Qt.AlignCenter)
        self.banner.setFont(ui_font(20))
        self.banner.setStyleSheet("background-color: #212b58; color: white; padding: 10px; border-radius: 10px;")
        main_vbox.addWidget(self.banner)

        # Content Area
        main_hbox = QHBoxLayout()
        main_vbox.addLayout(main_hbox)

        # Left Column: 2D Plots
        left_col = QVBoxLayout()
        main_hbox.addLayout(left_col, 2)

        self.plot2D_top = PlotLive2D("Altitude")
        self.plot2D_bottom = PlotLive2D("RSSI")
        self.combo_top = QComboBox(); self.combo_bottom = QComboBox()
        vars_list = list(UNITS.keys())[1:] # Skip Time
        self.combo_top.addItems(vars_list); self.combo_bottom.addItems(vars_list)
        self.combo_top.setCurrentText("Alt"); self.combo_bottom.setCurrentText("RSSI")

        for cb in [self.combo_top, self.combo_bottom]:
            cb.setStyleSheet("background-color: #212b58; color: white; border-radius: 5px; padding: 5px;")
            cb.setFont(ui_font(10))

        left_col.addWidget(QLabel("PRIMARY TELEMETRY:")); left_col.addWidget(self.combo_top); left_col.addWidget(self.plot2D_top)
        left_col.addWidget(QLabel("SECONDARY TELEMETRY:")); left_col.addWidget(self.combo_bottom); left_col.addWidget(self.plot2D_bottom)

        # Right Column: 3D Visualization & Status
        right_col = QVBoxLayout()
        main_hbox.addLayout(right_col, 3)

        self.visualizer_selector = QComboBox()
        self.visualizer_selector.addItems(["3D INS Path", "Rocket Attitude (Calibration Mode)"])
        self.visualizer_selector.setStyleSheet("background-color: #212b58; color: white; padding: 5px;")
        self.visualizer_selector.currentIndexChanged.connect(lambda i: self.stacked_3d.setCurrentIndex(i))

        self.stacked_3d = QStackedWidget()
        self.plot3D = PlotLive3D()
        self.rotation3D = RocketRotationWidget()
        self.stacked_3d.addWidget(self.plot3D); self.stacked_3d.addWidget(self.rotation3D)
        
        right_col.addWidget(self.visualizer_selector); right_col.addWidget(self.stacked_3d)

        # Status Bar
        self.status_frame = QFrame()
        self.status_frame.setStyleSheet("background-color: #f0f0f0; border-radius: 10px;")
        status_layout = QHBoxLayout(self.status_frame)
        self.rate_lbl = QLabel("RATE: 0.0 Hz"); self.rssi_lbl = QLabel("RSSI: --- dBm"); self.stat_lbl = QLabel("STATUS: OFFLINE")
        for lbl in [self.rate_lbl, self.rssi_lbl, self.stat_lbl]: lbl.setFont(ui_font(12)); status_layout.addWidget(lbl)
        main_vbox.addWidget(self.status_frame)

        # Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.readNextPacket)
        self.timer.start(INTERVAL_MS)

    def changeTopVariable(self, var): self.plot2D_top.resetPlot(f"{var} vs Time", f"{var} ({UNITS.get(var,'')})")

    def readNextPacket(self):
        if not self.ser or self.ser.in_waiting == 0: return
        
        last_line = None
        while self.ser.in_waiting > 0:
            try:
                raw = self.ser.readline().decode("ascii", errors="ignore").strip()
                if raw.count(',') == 12: last_line = raw
            except: continue

        if not last_line: return
        
        try:
            v = last_line.split(",")
            packet = {
                "T": time.time() - self.start_time, "Alt": float(v[1]), "Veloc": float(v[2]),
                "Lat": float(v[3]), "Lon": float(v[4]), "qR": float(v[5]), "qI": float(v[6]),
                "qJ": float(v[7]), "qK": float(v[8]), "insX": float(v[9]), "insY": float(v[10]),
                "insZ": float(v[11]), "RSSI": int(float(v[12].strip()))
            }
            
            # Update Live Visuals
            self.last_packet_time = time.time()
            self.packet_times.append(self.last_packet_time)
            self.rotation3D.set_rotation(packet["qR"], packet["qI"], packet["qJ"], packet["qK"])
            
            # Status Updates
            self.stat_lbl.setText("STATUS: ONLINE"); self.stat_lbl.setStyleSheet("color: green;")
            self.rssi_lbl.setText(f"RSSI: {packet['RSSI']} dBm")
            now = time.time()
            while self.packet_times and now - self.packet_times[0] > 1.0: self.packet_times.popleft()
            self.rate_lbl.setText(f"RATE: {len(self.packet_times)} Hz")
            
            # Plotting
            self.plot2D_top.times.append(packet["T"]); self.plot2D_top.values.append(packet.get(self.combo_top.currentText(), 0))
            self.plot2D_top.updatePlot()
            self.plot2D_bottom.times.append(packet["T"]); self.plot2D_bottom.values.append(packet.get(self.combo_bottom.currentText(), 0))
            self.plot2D_bottom.updatePlot()

            self.plot3D.posX.append(packet["insX"]); self.plot3D.posY.append(packet["insY"]); self.plot3D.posZ.append(packet["insZ"])
            self.plot3D.updatePlot()

        except Exception as e: print(f"Parse Error: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PLOTSGroundStation()
    window.show()
    sys.exit(app.exec())