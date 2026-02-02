# Program:
# Author:
# Module:
# Email:
# Student Number:
# -----------------------------------------------------------------------------------------------------------------------------
# Code
import sys
import pandas as pd
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QComboBox, QLabel)
from PyQt5.QtCore import QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

FLIGHT_DATA_PATH = "/home/admin/PLOTS-DEV/dtl3.csv"
INTERVAL_MS = 30

class PlotLiveCanvas(FigureCanvas):
    def __init__(self):
        self.fig = Figure()
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

class PLOTSGroundStation(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LASER Mission Control - PLOTS Ground Station")
        self.resize(800, 600)

        self.data = pd.read_csv(FLIGHT_DATA_PATH)
        self.index = 0
        self.canvas = PlotLiveCanvas()
        self.variable_select = QComboBox(self)
        self.variable_select.addItems(self.data.columns[1:])
        self.variable_select.currentTextChanged.connect(self.changePlotVariable)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(QLabel("Select Variable To Plot: "))
        layout.addWidget(self.variable_select)
        layout.addWidget(self.canvas)
        self.setCentralWidget(central)

		#pretend to plot data live
        self.timer = QTimer()
        self.timer.timeout.connect(self.readNextPacket)
        self.timer.start(INTERVAL_MS)

        self.selected_variable = self.variable_select.currentText()
        self.initializeData()

    def initializeData(self):
        self.canvas.times = self.data["T"].values.tolist()[:10]
        self.canvas.data_values = self.data[self.selected_variable].values.tolist()[:10]
        self.canvas.updatePlot()

    def changePlotVariable(self, variable):
        self.selected_variable = variable
        self.canvas.ax.set_ylabel(variable)

        self.canvas.ax.set_title(f"{variable} vs Time")
        if self.index < len(self.data):
            self.canvas.data_values = self.data[self.selected_variable].values.tolist()[:self.index + 10]
            self.canvas.updatePlot()

    def readNextPacket(self):
        if self.index < len(self.data):
            time = self.data.iloc[self.index]["T"]
            data_value = self.data.iloc[self.index][self.selected_variable]
            self.canvas.times.append(time)  
            self.canvas.data_values.append(data_value)
            self.canvas.updatePlot()
            self.index = self.index + 1
        else:
            self.timer.stop()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PLOTSGroundStation()
    window.show()
    sys.exit(app.exec_())















