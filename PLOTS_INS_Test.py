# Program: PLOTS_INS_Test.py
# Author:
# Module:
# Email:
# Student Number:
# -----------------------------------------------------------------------------------------------------------------------------
# Code:
import sys
import time
import serial
from collections import deque
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget,QVBoxLayout, QHBoxLayout, QLabel, QComboBox)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QPixmap, QFont, QFontDatabase
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

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
        self.ax.set_title(
            "Live INS Relative Position (XYZ)",
            pad=4,
            color="#212b58",
            fontweight="bold"
        )
        self.ax.set_xlabel("X (m)")
        self.ax.set_ylabel("Y (m)")
        self.ax.set_zlabel("Z (m)")

        self.ax.plot(self.posX, self.posY, self.posZ, lw=1.5, color="#212b58")
        x = self.posX[-1]
        y = self.posY[-1]
        z = self.posZ[-1]
        self.ax.scatter([x], [y], [z], s=60, color="red")
        offset = 0.0002
        self.ax.text(
            x + offset, y + offset, z + offset,
            f"({x:.2f}, {y:.2f}, {z:.2f})",
            color="green",
            fontsize=9,
            weight="bold",
            bbox=dict(
                facecolor="white",
                alpha=0.6,
                edgecolor="none",
                pad=2
            )
        )
        self.draw_idle()

class PLOTSGroundStation(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LASER - UnityRise Mission Control - PL-26")
        self.resize(1200, 700)

        font_id = QFontDatabase.addApplicationFont(
            "/home/admin/pl26-groundstation/Assets/Orbitron-VariableFont_wght.ttf"
        )
        self.ui_font_family = QFontDatabase.applicationFontFamilies(font_id)[0] if font_id != -1 else "Arial"

        def ui_font(size, weight=QFont.Medium):
            f = QFont(self.ui_font_family)
            f.setPointSize(size)
            f.setWeight(weight)
            return f

        self.title_banner = QLabel("LASER – UnityRise Mission Control - PL-26")
        self.title_banner.setAlignment(Qt.AlignCenter)
        self.title_banner.setFixedHeight(45)
        self.title_banner.setFont(ui_font(18, QFont.Bold))
        self.title_banner.setStyleSheet("""
            background-color: #212b58;
            color: white;
            letter-spacing: 2px;
            border-radius: 10px;
            padding: 5px;
        """)

        try:
            self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.05)
            self.ser.reset_input_buffer()
        except serial.SerialException:
            sys.exit(1)

        self.start_time = time.time()
        self.last_packet_time = 0
        self.packet_times = deque(maxlen=200)

        self.plot2D_top = PlotLive2D("Alt vs Time")
        self.plot2D_bottom = PlotLive2D("RSSI vs Time")
        self.plot3D = PlotLive3D(font_family=self.ui_font_family)  # pass NASA font to 3D plot

        blue_style = "color: #212b58;"

        self.status_label = QLabel("Status: Offline")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(ui_font(11, QFont.Bold))
        self.status_label.setStyleSheet(blue_style)

        self.armed_label = QLabel("Status: Disarmed")
        self.armed_label.setAlignment(Qt.AlignCenter)
        self.armed_label.setFont(ui_font(11, QFont.Bold))
        self.armed_label.setStyleSheet(blue_style)

        self.rate_label = QLabel("Rate: 0.0 Hz")
        self.rate_label.setFont(ui_font(11, QFont.Bold))
        self.rate_label.setStyleSheet(blue_style)

        self.lat_label = QLabel("Latitude: ---")
        self.lat_label.setFont(ui_font(11, QFont.Bold))
        self.lat_label.setStyleSheet(blue_style)

        self.lon_label = QLabel("Longitude: ---")
        self.lon_label.setFont(ui_font(11, QFont.Bold))
        self.lon_label.setStyleSheet(blue_style)

        self.rssi_label = QLabel("RSSI: --- dBm")
        self.rssi_label.setFont(ui_font(11, QFont.Bold))
        self.rssi_label.setStyleSheet(blue_style)

        self.alt_label = QLabel("Alt: --- m")
        self.alt_label.setAlignment(Qt.AlignCenter)
        self.alt_label.setFont(ui_font(12, QFont.Bold))
        self.alt_label.setStyleSheet("color: #212b58;")

        self.phase_label = QLabel("Phase Of Flight: Test")
        self.phase_label.setAlignment(Qt.AlignCenter)
        self.phase_label.setFont(ui_font(11, QFont.Bold))
        self.phase_label.setStyleSheet("color: #212b58;")

        vars_ = [k for k in UNITS.keys() if k != "T"]

        self.combo_top = QComboBox()
        self.combo_bottom = QComboBox()
        self.combo_top.addItems(vars_)
        self.combo_bottom.addItems(vars_)
        self.combo_top.setCurrentText("Alt")
        self.combo_bottom.setCurrentText("RSSI")
        self.combo_top.setFont(ui_font(10))
        self.combo_bottom.setFont(ui_font(10))
        self.combo_top.currentTextChanged.connect(self.changeTopVariable)
        self.combo_bottom.currentTextChanged.connect(self.changeBottomVariable)
        self.combo_top.setStyleSheet("color: white; background-color: #212b58; border-radius:5px; padding:3px;")
        self.combo_bottom.setStyleSheet("color: white; background-color: #212b58; border-radius:5px; padding:3px;")

        self.top_variable_label = QLabel("Top Plot Variable:")
        self.bottom_variable_label = QLabel("Bottom Plot Variable:")
        self.top_variable_label.setFont(ui_font(11, QFont.Bold))
        self.bottom_variable_label.setFont(ui_font(11, QFont.Bold))
        self.top_variable_label.setStyleSheet("color: #212b58;")
        self.bottom_variable_label.setStyleSheet("color: #212b58;")

        self.image_label1 = QLabel()
        self.image_label1.setPixmap(QPixmap("/home/admin/pl26-groundstation/Assets/unityrise_logo.png").scaled(100, 100, Qt.KeepAspectRatio))
        self.image_label1.setAlignment(Qt.AlignCenter)

        self.image_label2 = QLabel()
        self.image_label2.setPixmap(QPixmap("/home/admin/pl26-groundstation/Assets/uol_logo.png").scaled(200, 200, Qt.KeepAspectRatio))
        self.image_label2.setAlignment(Qt.AlignCenter)

        self.image_label3 = QLabel()
        self.image_label3.setPixmap(QPixmap("/home/admin/pl26-groundstation/Assets/LASER_Logo.png").scaled(100, 100, Qt.KeepAspectRatio))
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
        left_layout.addWidget(self.top_variable_label)
        left_layout.addWidget(self.combo_top)
        left_layout.addWidget(self.plot2D_top)
        left_layout.addWidget(self.bottom_variable_label)
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
        central.setStyleSheet("background-color: #FFFFFF;")
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
        if time.time() - self.last_packet_time > UART_TIMEOUT_SEC:
            self.status_label.setText("Status: Offline")
            self.status_label.setStyleSheet("color: #212b58;")
            self.rate_label.setText("Rate: 0.0 Hz")
            self.armed_label.setText("Status: Disarmed")
            self.armed_label.setStyleSheet("color: #212b58;")

    def readNextPacket(self):
        if self.ser.in_waiting == 0:
            return

        last_valid_line = None
        while self.ser.in_waiting:
            decoded = self.ser.readline().decode("ascii", errors="ignore").strip()
            if "," in decoded:
                last_valid_line = decoded

        if not last_valid_line:
            return

        v = last_valid_line.split(",")
        if len(v) != 13:
            return

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
                "RSSI": int(v[12])
            }
        except ValueError:
            return

        self.last_packet_time = time.time()
        self.status_label.setText("Status: Online")
        self.status_label.setStyleSheet("color: #00ff6a;")
        self.armed_label.setText("Status: Armed")
        self.armed_label.setStyleSheet("color: red;")

        self.packet_times.append(self.last_packet_time)
        now = time.time()
        while self.packet_times and now - self.packet_times[0] > 1.0:
            self.packet_times.popleft()
        self.rate_label.setText(f"Rate: {len(self.packet_times):.1f} Hz")

        self.lat_label.setText(f"Latitude: {packet['Lat']}")
        self.lon_label.setText(f"Longitude: {packet['Lon']}")
        self.rssi_label.setText(f"RSSI: {packet['RSSI']} dBm")
        self.alt_label.setText(f"Alt: {packet['Alt']:.2f} m")

        self.plot2D_top.times.append(packet["T"])
        self.plot2D_top.values.append(packet[self.combo_top.currentText()])
        self.plot2D_top.updatePlot()

        self.plot2D_bottom.times.append(packet["T"])
        self.plot2D_bottom.values.append(packet[self.combo_bottom.currentText()])
        self.plot2D_bottom.updatePlot()

        self.plot3D.posX.append(packet["insX"])
        self.plot3D.posY.append(packet["insY"])
        self.plot3D.posZ.append(packet["insZ"])
        self.plot3D.updatePlot()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PLOTSGroundStation()
    window.show()
    sys.exit(app.exec_())
