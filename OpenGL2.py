import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import serial
import time
import sys
import numpy as np

# --- Configuration ---
SERIAL_PORT = "/dev/serial0" 
BAUD_RATE   = 115200
UART_TIMEOUT_SEC = 1.0

# --- State Variables ---
quat = [1.0, 0.0, 0.0, 0.0] 
altitude = 0.0
rssi = 0
last_packet_time = 0

# --- Serial Setup ---
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.01)
    ser.reset_input_buffer()
except Exception as e:
    print(f"Serial Error: {e}")
    sys.exit()

def get_rotation_matrix(q):
    w, x, y, z = q
    return np.array([
        [1 - 2*y**2 - 2*z**2, 2*x*y - 2*z*w,     2*x*z + 2*y*w,     0],
        [2*x*y + 2*z*w,     1 - 2*x**2 - 2*z**2, 2*y*z - 2*x*w,     0],
        [2*x*z - 2*y*w,     2*y*z + 2*x*w,       1 - 2*x**2 - 2*y**2, 0],
        [0,                 0,                   0,                 1]
    ], dtype=np.float32).T

def read_uart():
    global quat, altitude, rssi, last_packet_time
    if ser.in_waiting > 0:
        last_valid_line = None
        while ser.in_waiting:
            line = ser.readline().decode("ascii", errors="ignore").strip()
            if "," in line:
                last_valid_line = line
        
        if last_valid_line:
            v = last_valid_line.split(",")
            if len(v) == 13:
                try:
                    altitude = float(v[1])
                    quat = [float(v[5]), float(v[6]), float(v[7]), float(v[8])]
                    rssi = int(v[12])
                    last_packet_time = time.time()
                except ValueError:
                    pass

def draw_text(position, text, font):
    """Renders 2D text overlaying the 3D scene."""
    text_surface = font.render(text, True, (255, 255, 0)) # Yellow text
    text_data = pygame.image.tostring(text_surface, "RGBA", True)
    width, height = text_surface.get_size()

    glWindowPos2d(position[0], position[1])
    glDrawPixels(width, height, GL_RGBA, GL_UNSIGNED_BYTE, text_data)

def draw_environment():
    glBegin(GL_LINES)
    glColor3f(0.2, 0.2, 0.2)
    for i in range(-10, 11):
        glVertex3f(i, -5, -10); glVertex3f(i, -5, 10)
        glVertex3f(-10, -5, i); glVertex3f(10, -5, i)
    glEnd()

def draw_rocket():
    quad = gluNewQuadric()
    # Body
    glColor3f(0.8, 0.8, 0.8)
    glPushMatrix()
    glRotatef(-90, 1, 0, 0)
    glTranslatef(0, 0, -2)
    gluCylinder(quad, 0.4, 0.4, 4, 32, 32)
    glPopMatrix()
    # Nose
    glColor3f(1.0, 0.0, 0.0)
    glPushMatrix()
    glTranslatef(0, 2, 0)
    glRotatef(-90, 1, 0, 0)
    gluCylinder(quad, 0.4, 0, 1.2, 32, 32)
    glPopMatrix()
    # Fins
    glColor3f(0.2, 0.2, 0.9)
    for angle in [0, 90, 180, 270]:
        glPushMatrix()
        glRotatef(angle, 0, 1, 0)
        glBegin(GL_TRIANGLES)
        glVertex3f(0.4, -2, 0); glVertex3f(1.1, -2, 0); glVertex3f(0.4, -1, 0)
        glEnd()
        glPopMatrix()

def main():
    pygame.init()
    display_res = (1280, 720)
    pygame.display.set_mode(display_res, DOUBLEBUF | OPENGL)
    pygame.display.set_caption("PL-26 Telemetry Visualizer")
    
    # HUD Font
    font = pygame.font.SysFont('Consolas', 24)

    gluPerspective(45, (display_res[0]/display_res[1]), 0.1, 100.0)
    glEnable(GL_DEPTH_TEST)
    clock = pygame.time.Clock()

    while True:
        for event in pygame.event.get():
            if event.type == QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
                pygame.quit(); sys.exit()

        read_uart()

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        
        # 3D Scene
        glTranslatef(0, 0, -12) 
        glRotatef(20, 1, 0, 0) # Camera angle
        draw_environment()

        glPushMatrix()
        matrix = get_rotation_matrix(quat)
        glMultMatrixf(matrix)
        draw_rocket()
        glPopMatrix()

        # 2D HUD (Digital Readout)
        status = "ONLINE" if (time.time() - last_packet_time < UART_TIMEOUT_SEC) else "OFFLINE"
        draw_text((20, 680), f"STATUS: {status}", font)
        draw_text((20, 650), f"ALTITUDE: {altitude:.2f} m", font)
        draw_text((20, 620), f"RSSI: {rssi} dBm", font)

        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()