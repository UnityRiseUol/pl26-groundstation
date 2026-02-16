import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import serial
import time
import sys
import numpy as np

# --- Configuration ---
SERIAL_PORT = "/dev/ttyAMA0" 
BAUD_RATE   = 115200

# --- State Variables ---
quat = [1.0, 0.0, 0.0, 0.0] 

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.01)
    ser.reset_input_buffer()
except Exception as e:
    print(f"Serial Error: {e}")
    sys.exit()

def get_rotation_matrix(q):
    """
    Converts Quaternion [r, i, j, k] to OpenGL Matrix.
    """
    w, x, y, z = q
    
    # Normalization (Ensures the model doesn't warp/shrink)
    mag = np.sqrt(w**2 + x**2 + y**2 + z**2)
    if mag == 0: return np.identity(4)
    w, x, y, z = w/mag, x/mag, y/mag, z/mag

    # Standard Quaternion to Matrix conversion
    return np.array([
        [1 - 2*y**2 - 2*z**2, 2*x*y - 2*z*w,     2*x*z + 2*y*w,     0],
        [2*x*y + 2*z*w,     1 - 2*x**2 - 2*z**2, 2*y*z - 2*x*w,     0],
        [2*x*z - 2*y*w,     2*y*z + 2*x*w,       1 - 2*x**2 - 2*y**2, 0],
        [0,                 0,                   0,                 1]
    ], dtype=np.float32).T

def read_uart():
    global quat
    if ser.in_waiting > 0:
        line = ser.readline().decode("ascii", errors="ignore").strip()
        v = line.split(",")
        if len(v) == 13:
            try:
                # BNO085 Order: R, I, J, K (v[5], v[6], v[7], v[8])
                qr = float(v[5]) # w
                qi = float(v[6]) # x
                qj = float(v[7]) # y
                qk = float(v[8]) # z

                # COORDINATE REMAPPING:
                # Sensor X (i) -> OpenGL X
                # Sensor Y (j) -> OpenGL Z
                # Sensor Z (k) -> OpenGL Y (This makes the rocket 'Up' match PCB 'Up')
                quat = [qr, qi, qk, qj] 
                
            except ValueError:
                pass

def draw_environment():
    glBegin(GL_LINES)
    # X-Axis (Red)
    glColor3f(1, 0, 0); glVertex3f(0, -2, 0); glVertex3f(3, -2, 0)
    # Y-Axis (Green)
    glColor3f(0, 1, 0); glVertex3f(0, -2, 0); glVertex3f(0, 1, 0)
    # Z-Axis (Blue)
    glColor3f(0, 0, 1); glVertex3f(0, -2, 0); glVertex3f(0, -2, 3)
    
    glColor3f(0.2, 0.2, 0.2)
    for i in range(-10, 11):
        glVertex3f(i, -2, -10); glVertex3f(i, -2, 10)
        glVertex3f(-10, -2, i); glVertex3f(10, -2, i)
    glEnd()

def draw_rocket():
    quad = gluNewQuadric()
    # Body
    glColor3f(0.8, 0.8, 0.8)
    glPushMatrix()
    glRotatef(-90, 1, 0, 0) # Cylinder is drawn along Z, rotate to Y (Up)
    glTranslatef(0, 0, -1.5)
    gluCylinder(quad, 0.4, 0.4, 3, 32, 32)
    glPopMatrix()
    
    # Nose
    glColor3f(1, 0, 0)
    glPushMatrix()
    glTranslatef(0, 1.5, 0)
    glRotatef(-90, 1, 0, 0)
    gluCylinder(quad, 0.4, 0, 1, 32, 32)
    glPopMatrix()

def main():
    pygame.init()
    display_res = (1280, 720)
    pygame.display.set_mode(display_res, DOUBLEBUF | OPENGL)
    glEnable(GL_DEPTH_TEST)

    while True:
        for event in pygame.event.get():
            if event.type == QUIT: pygame.quit(); sys.exit()

        read_uart()

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        
        gluPerspective(45, (display_res[0]/display_res[1]), 0.1, 100.0)
        glTranslatef(0, 0, -10)
        glRotatef(20, 1, 0, 0) 

        draw_environment()

        glPushMatrix()
        rmat = get_rotation_matrix(quat)
        glMultMatrixf(rmat)
        
        # FINAL OFFSET: If the rocket is lying down when the PCB is flat,
        # rotate it here to define the "Natural" position.
        glRotatef(90, 1, 0, 0) 
        
        draw_rocket()
        glPopMatrix()

        pygame.display.flip()
        pygame.time.wait(10)

if __name__ == "__main__":
    main()