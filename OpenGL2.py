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

# --- State Variables ---
quat = [1.0, 0.0, 0.0, 0.0] # Default: No rotation

# --- Serial Setup ---
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.01)
    ser.reset_input_buffer()
    print("Serial Connected. Waiting for data...")
except Exception as e:
    print(f"Serial Error: {e}")
    sys.exit()

def get_rotation_matrix(q):
    """Converts Quaternion to OpenGL-friendly Matrix."""
    w, x, y, z = q
    # Normalizing to ensure no scaling issues
    norm = np.sqrt(w*w + x*x + y*y + z*z)
    w, x, y, z = w/norm, x/norm, y/norm, z/norm
    
    return np.array([
        [1 - 2*y**2 - 2*z**2, 2*x*y - 2*z*w,     2*x*z + 2*y*w,     0],
        [2*x*y + 2*z*w,     1 - 2*x**2 - 2*z**2, 2*y*z - 2*x*w,     0],
        [2*x*z - 2*y*w,     2*y*z + 2*x*w,       1 - 2*x**2 - 2*y**2, 0],
        [0,                 0,                   0,                 1]
    ], dtype=np.float32).T

def read_uart():
    global quat
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
                    # Capture Quaternions (Indices 5,6,7,8)
                    quat = [float(v[5]), float(v[6]), float(v[7]), float(v[8])]
                    # DEBUG PRINT: Watch this in your terminal to see if values change!
                    print(f"Quat: {quat[0]:.2f}, {quat[1]:.2f}, {quat[2]:.2f}, {quat[3]:.2f}")
                except ValueError:
                    pass

def draw_environment():
    glBegin(GL_LINES)
    glColor3f(0.5, 0.5, 0.5)
    for i in range(-10, 11):
        glVertex3f(i, -2, -10); glVertex3f(i, -2, 10)
        glVertex3f(-10, -2, i); glVertex3f(10, -2, i)
    glEnd()

def draw_rocket():
    quad = gluNewQuadric()
    # Main Body
    glColor3f(1.0, 1.0, 1.0) # White body
    glPushMatrix()
    glRotatef(-90, 1, 0, 0)
    gluCylinder(quad, 0.5, 0.5, 3.5, 32, 32)
    glPopMatrix()
    # Nose
    glColor3f(1.0, 0.0, 0.0) # Red nose
    glPushMatrix()
    glTranslatef(0, 3.5, 0)
    glRotatef(-90, 1, 0, 0)
    gluCylinder(quad, 0.5, 0, 1.0, 32, 32)
    glPopMatrix()

def main():
    pygame.init()
    display_res = (1280, 720)
    pygame.display.set_mode(display_res, DOUBLEBUF | OPENGL)
    
    glEnable(GL_DEPTH_TEST)
    glClearColor(0.1, 0.1, 0.1, 1)

    clock = pygame.time.Clock()

    while True:
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit(); sys.exit()

        read_uart()

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        
        # Camera Positioning
        gluPerspective(45, (display_res[0]/display_res[1]), 0.1, 100.0)
        glTranslatef(0, -1, -10) 
        glRotatef(15, 1, 0, 0)

        draw_environment()

        # APPLY ROTATION
        glPushMatrix()
        rmat = get_rotation_matrix(quat)
        glMultMatrixf(rmat)
        draw_rocket()
        glPopMatrix()

        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()