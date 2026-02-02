# Program: PLOTS_UART_Test.py
# Author:
# Module:
# Email:
# Student Number:
# -----------------------------------------------------------------------------------------------------------------------------
import sys
import time
import serial
from collections import deque
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSpacerItem, QSizePolicy
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QPixmap
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D

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
    def __init__(self):
        self.fig = Figure(figsize=(9, 7))
        self.ax = self.fig.add_subplot(111, projection="3d")
        super().__init__(self.fig)
        self.fig.subplots_adjust(left=0.02, right=0.98, bottom=0.02, top=0.95)
        self.times = []
        self.altitudes = []
        self.velocities = []

    def updatePlot(self):
        if not self.times:
            return

        self.ax.clear()
        self.ax.set_title("Flight Path Analysis", pad=4)
        self.ax.set_xlabel("Time (s)", labelpad=4)
        self.ax.set_ylabel("Altitude (m)", labelpad=4)
        self.ax.set_zlabel("Velocity (m/s)", labelpad=4)

        self.ax.plot(self.times, self.altitudes, self.velocities, lw=1)

        self.ax.scatter(
            [self.times[-1]],
            [self.altitudes[-1]],
            [self.velocities[-1]],
            s=30
        )

        self.ax.set_xlim(min(self.times), max(self.times))
        self.ax.set_ylim(min(self.altitudes), max(self.altitudes))
        self.ax.set_zlim(min(self.velocities), max(self.velocities))

        try:
            self.ax.set_box_aspect((1, 1, 0.7))
        except Exception:
            pass

        self.draw_idle()

class PLOTSGroundStation(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LASER Mission Control - PLOTS Ground Station")
        self.resize(1200, 700)

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
        self.plot3D = PlotLive3D()

        self.status_label = QLabel("Status: Offline")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: red; font-weight: bold;")

        self.rate_label = QLabel("Rate: 0.0 Hz")
        self.lat_label = QLabel("Latitude: ---")
        self.lon_label = QLabel("Longitude: ---")
        self.rssi_label = QLabel("RSSI: --- dBm")

        for lbl in [self.rate_label, self.lat_label, self.lon_label, self.rssi_label]:
            lbl.setStyleSheet("color: white; font-weight: bold;")

        vars_ = [k for k in UNITS.keys() if k != "T"]

        self.combo_top = QComboBox()
        self.combo_bottom = QComboBox()
        self.combo_top.addItems(vars_)
        self.combo_bottom.addItems(vars_)
        self.combo_top.setCurrentText("Alt")
        self.combo_bottom.setCurrentText("RSSI")

        self.combo_top.setStyleSheet("color: white; background-color: #333; font-weight: bold;")
        self.combo_bottom.setStyleSheet("color: white; background-color: #333; font-weight: bold;")

        self.combo_top.currentTextChanged.connect(self.changeTopVariable)
        self.combo_bottom.currentTextChanged.connect(self.changeBottomVariable)

        self.var_top = "Alt"
        self.var_bottom = "RSSI"

        top_label = QLabel("Top Plot Variable:")
        bottom_label = QLabel("Bottom Plot Variable:")
        for lbl in [top_label, bottom_label]:
            lbl.setStyleSheet("color: white; font-weight: bold;")

        self.image_label1 = QLabel()
        pixmap1 = QPixmap("/home/admin/pl26-groundstation/Assets/unityrise_logo.png")
        self.image_label1.setPixmap(pixmap1.scaled(100, 100, Qt.KeepAspectRatio))
        self.image_label1.setAlignment(Qt.AlignTop | Qt.AlignRight)

        self.image_label2 = QLabel()
        pixmap2 = QPixmap("/home/admin/pl26-groundstation/Assets/uol_logo.png")
        self.image_label2.setPixmap(pixmap2.scaled(200, 200, Qt.KeepAspectRatio))
        self.image_label2.setAlignment(Qt.AlignTop | Qt.AlignCenter)

        self.image_label3 = QLabel()
        pixmap3 = QPixmap("/home/admin/pl26-groundstation/Assets/LASER_Logo.png")
        self.image_label3.setPixmap(pixmap3.scaled(100, 100, Qt.KeepAspectRatio))
        self.image_label3.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        right_layout = QVBoxLayout()

        right_widget = QWidget()
        right_widget.setLayout(right_layout)

        images_layout = QHBoxLayout()
        images_layout.addWidget(self.image_label3)
        images_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Fixed, QSizePolicy.Minimum))
        images_layout.addWidget(self.image_label2)
        images_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Fixed, QSizePolicy.Minimum))
        images_layout.addWidget(self.image_label1)
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
        left_layout.addWidget(top_label)
        left_layout.addWidget(self.combo_top)
        left_layout.addWidget(self.plot2D_top)
        left_layout.addWidget(bottom_label)
        left_layout.addWidget(self.combo_bottom)
        left_layout.addWidget(self.plot2D_bottom)

        main_layout = QHBoxLayout()
        main_layout.addLayout(left_layout, 2)
        main_layout.addWidget(right_widget, 3)

        central = QWidget()
        central.setLayout(main_layout)
        central.setStyleSheet("background-color: #212b58;")
        self.setCentralWidget(central)

        self.timer = QTimer()
        self.timer.timeout.connect(self.readNextPacket)
        self.timer.timeout.connect(self.updateConnectionStatus)
        self.timer.start(INTERVAL_MS)

    def changeTopVariable(self, var):
        self.var_top = var
        self.plot2D_top.resetPlot(f"{var} vs Time", f"{var} ({UNITS.get(var,'')})")

    def changeBottomVariable(self, var):
        self.var_bottom = var
        self.plot2D_bottom.resetPlot(f"{var} vs Time", f"{var} ({UNITS.get(var,'')})")

    def updateConnectionStatus(self):
        if time.time() - self.last_packet_time > UART_TIMEOUT_SEC:
            self.status_label.setText("Status: Offline")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            self.rate_label.setText("Rate: 0.0 Hz")

    def updateRate(self):
        now = time.time()
        while self.packet_times and now - self.packet_times[0] > 1.0:
            self.packet_times.popleft()
        self.rate_label.setText(f"Rate: {len(self.packet_times):.1f} Hz")

    def readNextPacket(self):
        if self.ser.in_waiting == 0:
            return

        last_valid_line = None
        while self.ser.in_waiting:
            raw = self.ser.readline()
            decoded = raw.decode("ascii", errors="ignore").strip()
            if "," in decoded:
                last_valid_line = decoded

        if not last_valid_line:
            return

        try:
            v = last_valid_line.split(",")
            if len(v) != 9:
                return
            packet = {
                "T": time.time() - self.start_time,
                "Alt": float(v[0]),
                "Veloc": float(v[1]),
                "Lat": float(v[2]),
                "Lon": float(v[3]),
                "qR": float(v[4]),
                "qI": float(v[5]),
                "qJ": float(v[6]),
                "qK": float(v[7]),
                "RSSI": int(v[8])
            }
        except ValueError:
            return

        self.last_packet_time = time.time()
        self.status_label.setText("Status: Online")
        self.status_label.setStyleSheet("color: #00ff6a; font-weight: bold;")

        self.packet_times.append(self.last_packet_time)
        self.updateRate()

        self.lat_label.setText(f"Latitude: {packet['Lat']}")
        self.lon_label.setText(f"Longitude: {packet['Lon']}")
        self.rssi_label.setText(f"RSSI: {packet['RSSI']} dBm")

        self.plot2D_top.times.append(packet["T"])
        self.plot2D_top.values.append(packet[self.var_top])
        self.plot2D_top.updatePlot()

        self.plot2D_bottom.times.append(packet["T"])
        self.plot2D_bottom.values.append(packet[self.var_bottom])
        self.plot2D_bottom.updatePlot()

        self.plot3D.times.append(packet["T"])
        self.plot3D.altitudes.append(packet["Alt"])
        self.plot3D.velocities.append(packet["Veloc"])
        self.plot3D.updatePlot()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PLOTSGroundStation()
    window.show()
    sys.exit(app.exec_())


