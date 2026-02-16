import sys
import csv
import numpy as np
from stl import mesh
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QStackedLayout
from PySide6.QtGui import QQuaternion, QMatrix4x4
from PySide6.QtCore import QTimer, Qt
import pyqtgraph.opengl as gl

class RocketLiveTelemetry(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rocket Rotation Visualisation")
        self.setMinimumSize(900, 700)
        
        # 1. Load CSV Data
        self.telemetry_data = []
        try:
            with open('telemetry_data.csv', 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.telemetry_data.append([
                        float(row['w']), float(row['x']), 
                        float(row['y']), float(row['z'])
                    ])
        except FileNotFoundError:
            print("Error: telemetry_data.csv not found.")
            sys.exit()

        self.current_frame = 0

        # 2. UI Setup - Using a QWidget as a container for the overlay
        self.container = QWidget()
        self.setCentralWidget(self.container)
        
        # Stacked layout allows the label to "float" over the 3D view
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # 3D Viewport
        self.view = gl.GLViewWidget()
        self.view.setBackgroundColor('k')
        self.view.addItem(gl.GLGridItem())
        self.view.setCameraPosition(distance=20)
        self.layout.addWidget(self.view)

        # Bottom Overlay Label
        self.overlay = QLabel(self.view) # Parented to the view
        self.overlay.setStyleSheet("""
            color: rgba(255, 255, 255, 200); 
            background-color: rgba(0, 0, 0, 100); 
            padding: 4px;
            font-family: Consolas, monospace;
            font-size: 10pt;
            border-top-right-radius: 5px;
        """)
        self.overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        # 3. Load the Red Rocket
        self.load_rocket("rocket.stl")

        # 4. Playback Timer (10Hz)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_telemetry)
        self.timer.start(100)

    def resizeEvent(self, event):
        """Keep the overlay at the bottom left when window is resized."""
        super().resizeEvent(event)
        self.overlay.move(10, self.view.height() - self.overlay.height() - 10)

    def load_rocket(self, path):
        try:
            stl_mesh = mesh.Mesh.from_file(path)
            verts = stl_mesh.vectors.reshape(-1, 3)
            center = (verts.max(axis=0) + verts.min(axis=0)) / 2
            verts -= center
            
            self.rocket = gl.GLMeshItem(
                vertexes=verts, 
                faces=np.arange(len(verts)).reshape(-1, 3),
                smooth=True, 
                shader='shaded', 
                color=(1, 0, 0, 1)
            )
            self.view.addItem(self.rocket)
        except:
            self.rocket = gl.GLBoxItem(color=(1,0,0,1))
            self.view.addItem(self.rocket)

    def update_telemetry(self):
        if not self.telemetry_data:
            return

        if self.current_frame >= len(self.telemetry_data):
            self.current_frame = 0
        
        w, x, y, z = self.telemetry_data[self.current_frame]
        quat = QQuaternion(w, x, y, z).normalized()
        
        transform = QMatrix4x4()
        transform.scale(0.01, 0.01, 0.01)
        transform.rotate(quat)
        self.rocket.setTransform(transform)
        
        # Update the small overlay text
        self.overlay.setText(f"W: {w:.3f} | X: {x:.3f} | Y: {y:.3f} | Z: {z:.3f}")
        self.overlay.adjustSize()
        
        # Position the overlay (bottom-left)
        self.overlay.move(10, self.view.height() - self.overlay.height() - 10)
        
        self.current_frame += 1

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = RocketLiveTelemetry()
    win.show()
    sys.exit(app.exec())
