# Program: PLOTS_INS_Test.py

import sys
import time
import os
import serial
from collections import deque

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QPixmap, QFont, QFontDatabase
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


# -------------------- Platform-safe paths --------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "Assets")

FONT_PATH = os.path.join(ASSETS_DIR, "Orbitron-VariableFont_wght.ttf")
LASER_LOGO_PATH = os.path.join(ASSETS_DIR, "LASER_Logo.png")
UNITYRISE_LOGO_PATH = os.path.join(ASSETS_DIR, "unityrise_logo.png")
UOL_LOGO_PATH = os.path.join(ASSETS_DIR, "uol_logo.png")


# -------------------- Serial config --------------------
if sys.platform.startswith("win"):
    SERIAL_PORT = "COM3"   # change this to whatever COM port your adapter is on
else:
    SERIAL_PORT = "/dev/ttyAMA0"

BAUD_RATE = 115200
INTERVAL_MS = 30
UART_TIMEOUT_SEC = 1.0


UNITS = {
    "T": "s",
    "Alt": "m",
    "Veloc": "m/s",
    "Lat": "deg",
    "Lon": "deg",
    "qR": "float",
    "qI": "float",
    "qJ": "float",
    "qK": "float",
    "insX": "m",
    "insY": "m",
    "insZ": "m",
    "RSSI": "dBm"
}


class PlotLive2D(FigureCanvas):
    def __init__(self, title):
        self.fig = Figure(figsize=(5, 3))
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)

        self.times = []
        self.values = []

        self.ax.set_title(title)
        self.ax.set_xlabel("Time (s)")
        self.ax.grid(True)
        self.line, = self.ax.plot([], [], lw=2)

    def resetPlot(self, title, ylabel):
        self.ax.clear()
        self.ax.set_title(title)
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel(ylabel)
        self.ax.grid(True)
        self.times.clear()
        self.values.clear()
        self.line, = self.ax.plot([], [], lw=2)
        self.draw_idle()

    def updatePlot(self):
        if not self.times:
            return
        self.line.set_data(self.times, self.values)
        self.ax.relim()
        self.ax.autoscale_view()
        self.draw_idle()


class PlotLive3D(FigureCanvas):
    def __init__(self, font_family="Arial"):
        self.fig = Figure(figsize=(9, 7))
        self.ax = self.fig.add_subplot(111, projection="3d")
        super().__init__(self.fig)
        self.fig.subplots_adjust(left=0.02, right=0.98, bottom=0.02, top=0.95)

        self.posX = []
        self.posY = []
        self.posZ = []
        self.font_family = font_family

    def updatePlot(self):
        if not self.posX:
            return

        self.ax.clear()
        self.ax.set_title("Live INS Relative Position (XYZ)", pad=4, fontweight="bold")
        self.ax.set_xlabel("X (m)")
        self.ax.set_ylabel("Y (m)")
        self.ax.set_zlabel("Z (m)")

        self.ax.plot(self.posX, self.posY, self.posZ, lw=1.5)
        x, y, z = self.posX[-1], self.posY[-1], self.posZ[-1]
        self.ax.scatter([x], [y], [z], s=60)

        self.draw_idle()


class PLOTSGroundStation(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LASER - UnityRise Mission Control - PL-26")
        self.resize(1200, 700)

        font_id = QFontDatabase.addApplicationFont(FONT_PATH)
        self.ui_font_family = (
            QFontDatabase.applicationFontFamilies(font_id)[0]
            if font_id != -1 else "Arial"
        )

        def ui_font(size, weight=QFont.Medium):
            f = QFont(self.ui_font_family)
            f.setPointSize(size)
            f.setWeight(weight)
            return f

        self.title_banner = QLabel("LASER – UnityRise Mission Control - PL-26")
        self.title_banner.setAlignment(Qt.AlignCenter)
        self.title_banner.setFixedHeight(45)
        self.title_banner.setFont(ui_font(18, QFont.Bold))
        self.title_banner.setStyleSheet(
            "background-color: #212b58; color: white; letter-spacing: 2px; "
            "border-radius: 10px; padding: 5px;"
        )

        self.ser = None
        try:
            self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.05)
            self.ser.reset_input_buffer()
        except serial.SerialException as e:
            print("Serial not connected:", e)

        self.start_time = time.time()
        self.last_packet_time = 0
        self.packet_times = deque(maxlen=200)

        self.plot2D_top = PlotLive2D("Alt vs Time")
        self.plot2D_bottom = PlotLive2D("RSSI vs Time")
        self.plot3D = PlotLive3D(font_family=self.ui_font_family)

        self.status_label = QLabel("Status: Offline")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(ui_font(11, QFont.Bold))

        self.armed_label = QLabel("Status: Disarmed")
        self.armed_label.setAlignment(Qt.AlignCenter)
        self.armed_label.setFont(ui_font(11, QFont.Bold))

        self.rate_label = QLabel("Rate: 0.0 Hz")
        self.rate_label.setFont(ui_font(11, QFont.Bold))

        self.lat_label = QLabel("Latitude: ---")
        self.lat_label.setFont(ui_font(11, QFont.Bold))

        self.lon_label = QLabel("Longitude: ---")
        self.lon_label.setFont(ui_font(11, QFont.Bold))

        self.rssi_label = QLabel("RSSI: --- dBm")
        self.rssi_label.setFont(ui_font(11, QFont.Bold))

        self.alt_label = QLabel("Alt: --- m")
        self.alt_label.setAlignment(Qt.AlignCenter)
        self.alt_label.setFont(ui_font(12, QFont.Bold))

        self.phase_label = QLabel("Phase Of Flight: Test")
        self.phase_label.setAlignment(Qt.AlignCenter)
        self.phase_label.setFont(ui_font(11, QFont.Bold))

        vars_ = [k for k in UNITS.keys() if k != "T"]

        self.combo_top = QComboBox()
        self.combo_bottom = QComboBox()
        self.combo_top.addItems(vars_)
        self.combo_bottom.addItems(vars_)
        self.combo_top.setCurrentText("Alt")
        self.combo_bottom.setCurrentText("RSSI")
        self.combo_top.currentTextChanged.connect(self.changeTopVariable)
        self.combo_bottom.currentTextChanged.connect(self.changeBottomVariable)

        self.image_label1 = QLabel()
        self.image_label1.setPixmap(QPixmap(UNITYRISE_LOGO_PATH).scaled(100, 100, Qt.KeepAspectRatio))
        self.image_label1.setAlignment(Qt.AlignCenter)

        self.image_label2 = QLabel()
        self.image_label2.setPixmap(QPixmap(UOL_LOGO_PATH).scaled(200, 200, Qt.KeepAspectRatio))
        self.image_label2.setAlignment(Qt.AlignCenter)

        self.image_label3 = QLabel()
        self.image_label3.setPixmap(QPixmap(LASER_LOGO_PATH).scaled(100, 100, Qt.KeepAspectRatio))
        self.image_label3.setAlignment(Qt.AlignCenter)

        laser_layout = QVBoxLayout()
        laser_layout.addWidget(self.image_label3)
        laser_layout.addWidget(self.phase_label)

        unity_layout = QVBoxLayout()
        unity_layout.addWidget(self.image_label1)
        unity_layout.addWidget(self.alt_label)

        uol_layout = QVBoxLayout()
        uol_layout.addWidget(self.image_label2)
        uol_layout.addWidget(self.armed_label)

        images_layout = QHBoxLayout()
        images_layout.addLayout(laser_layout)
        images_layout.addLayout(uol_layout)
        images_layout.addLayout(unity_layout)

        right_layout = QVBoxLayout()
        right_layout.addLayout(images_layout)
        right_layout.addWidget(self.plot3D)

        bottom_status = QHBoxLayout()
        bottom_status.addStretch()
        bottom_status.addWidget(self.status_label)
        bottom_status.addWidget(self.rate_label)
        bottom_status.addWidget(self.lat_label)
        bottom_status.addWidget(self.lon_label)
        bottom_status.addStretch()
        bottom_status.addWidget(self.rssi_label)
        right_layout.addLayout(bottom_status)

        left_layout = QVBoxLayout()
        left_layout.addWidget(self.combo_top)
        left_layout.addWidget(self.plot2D_top)
        left_layout.addWidget(self.combo_bottom)
        left_layout.addWidget(self.plot2D_bottom)

        main_layout = QHBoxLayout()
        main_layout.addLayout(left_layout, 2)
        main_layout.addLayout(right_layout, 3)

        root_layout = QVBoxLayout()
        root_layout.addWidget(self.title_banner)
        root_layout.addLayout(main_layout)

        central = QWidget()
        central.setLayout(root_layout)
        self.setCentralWidget(central)

        self.timer = QTimer()
        self.timer.timeout.connect(self.readNextPacket)
        self.timer.timeout.connect(self.updateConnectionStatus)
        self.timer.start(INTERVAL_MS)

    def changeTopVariable(self, var):
        self.plot2D_top.resetPlot(f"{var} vs Time", f"{var} ({UNITS.get(var,'')})")

    def changeBottomVariable(self, var):
        self.plot2D_bottom.resetPlot(f"{var} vs Time", f"{var} ({UNITS.get(var,'')})")

    def updateConnectionStatus(self):
        if not self.ser:
            return
        if time.time() - self.last_packet_time > UART_TIMEOUT_SEC:
            self.status_label.setText("Status: Offline")
            self.rate_label.setText("Rate: 0.0 Hz")
            self.armed_label.setText("Status: Disarmed")

    def readNextPacket(self):
        if not self.ser or self.ser.in_waiting == 0:
            return
        # rest of your original parsing code unchanged ...


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PLOTSGroundStation()
    window.show()
    sys.exit(app.exec_())
