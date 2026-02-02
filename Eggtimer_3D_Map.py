# Program:
# Author:
# Module:
# Email:
# Student Number:
# -----------------------------------------------------------------------------------------------------------------------------
# Code
import sys
import pandas as pd
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox)
from PyQt5.QtCore import QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

FLIGHT_DATA_PATH = "/home/admin/PLOTS-DEV/dtl3.csv"
INTERVAL_MS = 30

UNITS = {
    "T": "s",
    "Alt": "m",
    "Veloc": "m/s",
    "FAlt": "m",
    "FVeloc": "m/s",
    "LDA": "bool",
    "LowV": "bool",
    "Apogee": "bool",
    "N-O": "bool",
    "Drogue": "bool",
    "Main": "bool",
    "Latitude": "deg",
    "Longitude": "deg",
    "Speed": "m/s",
    "Course": "deg"
}


class PlotLive2D(FigureCanvas):
    def __init__(self, title):
        self.fig = Figure(figsize=(5, 3))
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)

        self.ax.set_title(title)
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Alt (m)")
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
        self.ax.set_title("Altitude & Velocity vs Time")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Altitude (m)")
        self.ax.set_zlabel("Velocity (m/s)")
        self.ax.scatter(self.times, self.altitudes, self.velocities, c='b')
        self.draw_idle()


class PLOTSGroundStation(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LASER Mission Control - PLOTS Ground Station")
        self.resize(1200, 700)

        self.data = pd.read_csv(FLIGHT_DATA_PATH)
        self.index = 0

        self.plot2D_top = PlotLive2D("Alt vs Time")
        self.plot2D_bottom = PlotLive2D("Alt vs Time")
        self.plot3D = PlotLive3D()

        self.combo_top = QComboBox()
        self.combo_bottom = QComboBox()
        self.combo_top.addItems(self.data.columns[1:])
        self.combo_bottom.addItems(self.data.columns[1:])

        self.combo_top.currentTextChanged.connect(self.changeTopVariable)
        self.combo_bottom.currentTextChanged.connect(self.changeBottomVariable)

        self.var_top = self.combo_top.currentText()
        self.var_bottom = self.combo_bottom.currentText()

        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Top 2D Variable:"))
        left_layout.addWidget(self.combo_top)
        left_layout.addWidget(self.plot2D_top)

        left_layout.addWidget(QLabel("Bottom 2D Variable:"))
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

        self.plot2D_top.times = self.data["T"].values[:self.index].tolist()
        self.plot2D_top.values = self.data[var].values[:self.index].tolist()

        self.plot2D_top.ax.set_ylabel(f"{var} ({unit})")
        self.plot2D_top.ax.set_title(f"{var} vs Time")
        self.plot2D_top.updatePlot()

    def changeBottomVariable(self, var):
        self.var_bottom = var
        unit = UNITS.get(var, "")

        self.plot2D_bottom.times = self.data["T"].values[:self.index].tolist()
        self.plot2D_bottom.values = self.data[var].values[:self.index].tolist()

        self.plot2D_bottom.ax.set_ylabel(f"{var} ({unit})")
        self.plot2D_bottom.ax.set_title(f"{var} vs Time")
        self.plot2D_bottom.updatePlot()

    def readNextPacket(self):
        if self.index >= len(self.data):
            self.timer.stop()
            return

        row = self.data.iloc[self.index]
        t = row["T"]

        self.plot2D_top.times.append(t)
        self.plot2D_top.values.append(row[self.var_top])
        self.plot2D_top.updatePlot()

        self.plot2D_bottom.times.append(t)
        self.plot2D_bottom.values.append(row[self.var_bottom])
        self.plot2D_bottom.updatePlot()

        self.plot3D.times.append(t)
        self.plot3D.altitudes.append(row["Alt"])
        self.plot3D.velocities.append(row["Veloc"])
        self.plot3D.updatePlot()

        self.index = self.index + 1


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PLOTSGroundStation()
    window.show()
    sys.exit(app.exec_())
