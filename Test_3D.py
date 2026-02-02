# Program:
# Author:
# Module:
# Email:
# Student Number:
# -----------------------------------------------------------------------------------------------------------------------------
# Code
import sys
import pandas as pd
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QComboBox, QLabel)
from PyQt5.QtCore import QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D

FLIGHT_DATA_PATH = "/home/admin/PLOTS-DEV/dtl3.csv"
INTERVAL_MS = 30

class PlotLive3D(FigureCanvas):
    def __init__(self):
        self.fig = Figure()
        self.ax = self.fig.add_subplot(111, projection='3d')
        super().__init__(self.fig)
        self.ax.set_title("3D Data Plot")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Altitude (m)")
        self.ax.set_zlabel("Velocity (m/s)")
        
        self.times = []
        self.altitudes = []
        self.velocities = []

    def updatePlot(self):
        self.ax.clear()
        self.ax.set_title("3D Data Plot")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Altitude (m)")
        self.ax.set_zlabel("Velocity (m/s)")
        
        self.ax.scatter(self.times, self.altitudes, self.velocities, c='b', marker='o')
        self.draw_idle()

class PLOTSGroundStation(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PLOTS Ground Station")
        self.resize(800, 600)

        self.data = pd.read_csv(FLIGHT_DATA_PATH)
        self.index = 0
        self.canvas = PlotLive3D()
        self.variable_select = QComboBox(self)

        self.variable_select.addItems(self.data.columns[1:])  
        self.variable_select.setEnabled(False)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(QLabel("Altitude and Velocity over Time"))
        layout.addWidget(self.canvas)
        self.setCentralWidget(central)

        self.timer = QTimer()
        self.timer.timeout.connect(self.readNextPacket)
        self.timer.start(INTERVAL_MS)

    def readNextPacket(self):
        if self.index < len(self.data):
            time = self.data.iloc[self.index]["T"]
            altitude = self.data.iloc[self.index]["Alt"]
            velocity = self.data.iloc[self.index]["Veloc"]
            self.canvas.times.append(time)
            self.canvas.altitudes.append(altitude)
            self.canvas.velocities.append(velocity)


            self.canvas.updatePlot()
            self.index = self.index + 1
        else:
            self.timer.stop()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PLOTSGroundStation()
    window.show()
    sys.exit(app.exec_())

