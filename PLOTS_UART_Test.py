# Program:   PLOTS Ground Station (Updated)
# Author:    [Your Name]
# Module:    Telemetry Visualization
# Description: Visualizes High-Speed LoRa Packets via UART

import sys
import time
import serial
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox)
from PyQt5.QtCore import QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D

# --- CONFIGURATION ---
SERIAL_PORT = "/dev/ttyAMA0" # CHANGE TO COMPORT IF ON WINDOWS (e.g., "COM3")
BAUD_RATE = 115200
INTERVAL_MS = 30 

# --- UNITS DEFINITION ---
# Matches the new 9-column CSV format + Generated Time
UNITS = {
    "T": "s",          # Local Computer Time
    "Alt": "m",
    "Veloc": "m/s",
    "Lat": "deg",
    "Lon": "deg",
    "qR": "float",     # Quaternion Real
    "qI": "float",     # Quaternion i
    "qJ": "float",     # Quaternion j
    "qK": "float",     # Quaternion k
    "RSSI": "dBm"      # Signal Strength
}

class PlotLive2D(FigureCanvas):
    def __init__(self, title):
        self.fig = Figure(figsize=(5, 3))
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)

        self.ax.set_title(title)
        self.ax.set_xlabel("Time (s)")
        self.ax.grid(True)

        self.line, = self.ax.plot([], [], lw=2)
        self.times = []
        self.values = []

    def updatePlot(self):
        if not self.times:
            return
        self.line.set_data(self.times, self.values)
        self.ax.relim()
        self.ax.autoscale_view()
        self.draw_idle()

class PlotLive3D(FigureCanvas):
    def __init__(self):
        self.fig = Figure(figsize=(6, 6))
        self.ax = self.fig.add_subplot(111, projection='3d')
        super().__init__(self.fig)

        self.times = []
        self.altitudes = []
        self.velocities = []

    def updatePlot(self):
        self.ax.clear()
        self.ax.set_title("Flight Path Analysis")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Altitude (m)")
        self.ax.set_zlabel("Velocity (m/s)")
        # Plot trajectory
        self.ax.plot(self.times, self.altitudes, self.velocities, lw=1, c='gray')
        # Plot current point
        if self.times:
            self.ax.scatter([self.times[-1]], [self.altitudes[-1]], [self.velocities[-1]], c='red', s=20)
        self.draw_idle()

class PLOTSGroundStation(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LASER Mission Control - PLOTS Ground Station")
        self.resize(1200, 700)

        # Initialize Serial
        try:
            self.ser = serial.Serial(
                port=SERIAL_PORT,
                baudrate=BAUD_RATE,
                timeout=0.05
            )
        except serial.SerialException as e:
            print(f"Error opening serial port: {e}")
            sys.exit(1)

        # Data Storage
        self.start_time = time.time()

        # UI Setup
        self.plot2D_top = PlotLive2D("Variable 1 vs Time")
        self.plot2D_bottom = PlotLive2D("Variable 2 vs Time")
        self.plot3D = PlotLive3D()

        vars = list(UNITS.keys())
        vars.remove("T") # Time is always X-axis

        self.combo_top = QComboBox()
        self.combo_bottom = QComboBox()
        self.combo_top.addItems(vars)
        self.combo_bottom.addItems(vars)

        # Set defaults
        self.combo_top.setCurrentText("Alt")
        self.combo_bottom.setCurrentText("RSSI")

        self.combo_top.currentTextChanged.connect(self.changeTopVariable)
        self.combo_bottom.currentTextChanged.connect(self.changeBottomVariable)

        self.var_top = self.combo_top.currentText()
        self.var_bottom = self.combo_bottom.currentText()

        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Top Plot Variable:"))
        left_layout.addWidget(self.combo_top)
        left_layout.addWidget(self.plot2D_top)
        left_layout.addWidget(QLabel("Bottom Plot Variable:"))
        left_layout.addWidget(self.combo_bottom)
        left_layout.addWidget(self.plot2D_bottom)

        right_layout = QVBoxLayout()
        right_layout.addWidget(self.plot3D)

        main_layout = QHBoxLayout()
        main_layout.addLayout(left_layout, 2)
        main_layout.addLayout(right_layout, 3)

        central = QWidget()
        central.setLayout(main_layout)
        self.setCentralWidget(central)

        self.timer = QTimer()
        self.timer.timeout.connect(self.readNextPacket)
        self.timer.start(INTERVAL_MS)

    def changeTopVariable(self, var):
        self.var_top = var
        unit = UNITS.get(var, "")
        self.plot2D_top.ax.set_ylabel(f"{var} ({unit})")
        self.plot2D_top.ax.set_title(f"{var} vs Time")
        # Clear data on switch to avoid scale issues
        self.plot2D_top.times = []
        self.plot2D_top.values = []

    def changeBottomVariable(self, var):
        self.var_bottom = var
        unit = UNITS.get(var, "")
        self.plot2D_bottom.ax.set_ylabel(f"{var} ({unit})")
        self.plot2D_bottom.ax.set_title(f"{var} vs Time")
        self.plot2D_bottom.times = []
        self.plot2D_bottom.values = []

    def readNextPacket(self):
        try:
            line = self.ser.readline().decode("ascii", errors="ignore").strip()
            if not line:
                return
            
            # Debug: Print raw line to console
            print(f"RAW: {line}") 

            values = line.split(",")
            
            # Expecting 9 columns based on new Arduino code
            if len(values) != 9:
                return

            # Create local timestamp (since Arduino isn't sending one)
            current_t = time.time() - self.start_time

            packet = {
                "T":     current_t,
                "Alt":   float(values[0]),
                "Veloc": float(values[1]),
                "Lat":   float(values[2]),
                "Lon":   float(values[3]),
                "qR":    float(values[4]),
                "qI":    float(values[5]),
                "qJ":    float(values[6]),
                "qK":    float(values[7]),
                "RSSI":  int(values[8])
            }

        except ValueError:
            return

        # Update Top Plot
        self.plot2D_top.times.append(packet["T"])
        self.plot2D_top.values.append(packet[self.var_top])
        # Keep buffer size manageable (optional, remove if you want full history)
        if len(self.plot2D_top.times) > 500:
            self.plot2D_top.times.pop(0)
            self.plot2D_top.values.pop(0)
        self.plot2D_top.updatePlot()

        # Update Bottom Plot
        self.plot2D_bottom.times.append(packet["T"])
        self.plot2D_bottom.values.append(packet[self.var_bottom])
        if len(self.plot2D_bottom.times) > 500:
            self.plot2D_bottom.times.pop(0)
            self.plot2D_bottom.values.pop(0)
        self.plot2D_bottom.updatePlot()

        # Update 3D Plot (Always Alt vs Veloc vs Time)
        self.plot3D.times.append(packet["T"])
        self.plot3D.altitudes.append(packet["Alt"])
        self.plot3D.velocities.append(packet["Veloc"])
        if len(self.plot3D.times) > 500:
            self.plot3D.times.pop(0)
            self.plot3D.altitudes.pop(0)
            self.plot3D.velocities.pop(0)
        self.plot3D.updatePlot()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PLOTSGroundStation()
    window.show()
    sys.exit(app.exec_())
