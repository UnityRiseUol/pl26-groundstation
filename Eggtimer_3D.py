# Program:
# Author:
# Module:
# Email:
# Student Number:
# -----------------------------------------------------------------------------------------------------------------------------
# Code
import sys
import pandas as pd
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QComboBox)
from PyQt5.QtCore import QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D


FLIGHT_DATA_PATH = "/home/admin/PLOTS-DEV/dtl3.csv"
INTERVAL_MS = 30

class PlotLiveCanvas(FigureCanvas):
    def __init__(self):
        self.fig = Figure(figsize=(10, 5))
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.ax.set_title("Data vs Time")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Value")
        self.ax.grid(True)
        self.line, = self.ax.plot([], [], lw=2)
        self.times = []
        self.data_values = []

    def updatePlot(self):
        if len(self.times) == 0 or len(self.data_values) == 0:
            return
        self.line.set_data(self.times, self.data_values)
        self.ax.relim()
        self.ax.autoscale_view()
        self.draw_idle()


class PlotLive3D(FigureCanvas):
    def __init__(self):
        self.fig = Figure(figsize=(10, 5))
        self.ax = self.fig.add_subplot(111, projection='3d')
        super().__init__(self.fig)
        self.ax.set_title("Altitude and Velocity vs Time")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Altitude (m)")
        self.ax.set_zlabel("Velocity (m/s)")
        self.times = []
        self.altitudes = []
        self.velocities = []

    def updatePlot(self):
        self.ax.clear()
        self.ax.set_title("Altitude and Velocity vs Time")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Altitude (m)")
        self.ax.set_zlabel("Velocity (m/s)")
        self.ax.scatter(self.times, self.altitudes, self.velocities, c='b', marker='o')
        self.draw_idle()

class PLOTSGroundStation(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LASER Mission Control - PLOTS Ground Station")
        self.resize(1024, 600)
        self.data = pd.read_csv(FLIGHT_DATA_PATH)
        self.index = 0
        self.canvas = PlotLiveCanvas()
        self.canvas3D = PlotLive3D()
        self.variable_select = QComboBox(self)
        self.variable_select.addItems(self.data.columns[1:])
        self.variable_select.currentTextChanged.connect(self.changePlotVariable)

        h_layout = QHBoxLayout()
        h_layout.addWidget(self.canvas)
        h_layout.addWidget(self.canvas3D)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(QLabel("Select Variable To Plot (2D): "))
        layout.addWidget(self.variable_select)
        layout.addLayout(h_layout)

        self.setCentralWidget(central)
        self.timer = QTimer()
        self.timer.timeout.connect(self.readNextPacket)
        self.timer.start(INTERVAL_MS)
        self.selected_variable = 'Alt'
        self.initializeData()

    def initializeData(self):
        self.canvas.times = self.data["T"].values.tolist()[:10]
        self.canvas.data_values = self.data[self.selected_variable].values.tolist()[:10]
        self.canvas.updatePlot()
        self.canvas3D.times = self.data["T"].values.tolist()[:10]
        self.canvas3D.altitudes = self.data["Alt"].values.tolist()[:10]
        self.canvas3D.velocities = self.data["Veloc"].values.tolist()[:10]
        self.canvas3D.updatePlot()

    def changePlotVariable(self, variable):
        self.selected_variable = variable
        self.canvas.ax.set_ylabel(variable)
        self.canvas.ax.set_title(f"{variable} vs Time")
        self.canvas.data_values = self.data[self.selected_variable].values.tolist()[:self.index + 10]
        self.canvas.updatePlot()

    def readNextPacket(self):
        if self.index < len(self.data):
            time = self.data.iloc[self.index]["T"]
            altitude = self.data.iloc[self.index]["Alt"]
            velocity = self.data.iloc[self.index]["Veloc"]
            self.canvas.times.append(time)
            self.canvas.data_values.append(self.data.iloc[self.index][self.selected_variable])
            self.canvas.updatePlot()
            
            self.canvas3D.times.append(time)
            self.canvas3D.altitudes.append(altitude)
            self.canvas3D.velocities.append(velocity)
            self.canvas3D.updatePlot()
            self.index = self.index + 1
        else:
            self.timer.stop()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PLOTSGroundStation()
    window.show()
    sys.exit(app.exec_())


