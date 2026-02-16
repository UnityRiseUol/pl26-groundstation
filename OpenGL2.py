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
tare_quat = [1.0, 0.0, 0.0, 0.0] # Used to "zero" the sensor

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.01)
    ser.reset_input_buffer()
except Exception as e:
    print(f"Serial Error: {e}")
    sys.exit()

def quaternion_multiply(q1, q2):
    """Multiplies two quaternions to apply offsets/calibration."""
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
    x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
    y = w1 * y2 + y1 * w2 + z1 * x2 - x1 * z2
    z = w1 * z2 + z1 * w2 + x1 * y2 - y1 * x2
    return [w, x, y, z]

def quaternion_conjugate(q):
    """Returns the conjugate of a quaternion (inverts the rotation)."""
    return [q[0], -q[1], -q[2], -q[3]]

def get_rotation_matrix(q):
    w, x, y, z = q
    mag = np.sqrt(w**2 + x**2 + y**2 + z**2)
    if mag == 0: return np.identity(4)
    w, x, y, z = w/mag, x/mag, y/mag, z/mag

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
                # BNO085 Order: R, I, J, K
                qr, qi, qj, qk = float(v[5]), float(v[6]), float(v[7]), float(v[8])
                
                # AXIS CORRECTION:
                # If it 'jumps' or flips, try changing signs: [qr, qi, -qk, qj]
                current_raw = [qr, qi, qk, qj] 
                
                # Apply Calibration (Tare)
                # This subtracts the 'tare' orientation from the 'current' orientation
                quat = quaternion_multiply(current_raw, quaternion_conjugate(tare_quat))
                
            except ValueError:
                pass

def draw_rocket():
    quad = gluNewQuadric()
    # Align the cylinder model to point UP (+Y)
    glColor3f(0.8, 0.8, 0.8)
    glPushMatrix()
    glRotatef(-90, 1, 0, 0)
    glTranslatef(0, 0, -1.5)
    gluCylinder(quad, 0.4, 0.4, 3, 32, 32)
    glPopMatrix()
    
    glColor3f(1, 0, 0) # Red Nose
    glPushMatrix()
    glTranslatef(0, 1.5, 0)
    glRotatef(-90, 1, 0, 0)
    gluCylinder(quad, 0.4, 0, 1, 32, 32)
    glPopMatrix()

def main():
    global tare_quat
    pygame.init()
    display_res = (1280, 720)
    pygame.display.set_mode(display_res, DOUBLEBUF | OPENGL)
    glEnable(GL_DEPTH_TEST)

    print("Press 'C' to Calibrate (Tare) the orientation.")

    while True:
        for event in pygame.event.get():
            if event.type == QUIT: pygame.quit(); sys.exit()
            if event.type == KEYDOWN:
                if event.key == K_c:
                    # Capture the current raw quaternion as the new 'Zero'
                    tare_quat = list(quat) 
                    print("Calibrated!")

        read_uart()
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        
        gluPerspective(45, (display_res[0]/display_res[1]), 0.1, 100.0)
        glTranslatef(0, 0, -10)
        glRotatef(20, 1, 0, 0) 

        # Draw Coordinate Axes for reference
        glBegin(GL_LINES)
        glColor3f(1,0,0); glVertex3f(0,-2,0); glVertex3f(2,-2,0) # X
        glColor3f(0,1,0); glVertex3f(0,-2,0); glVertex3f(0,0,0)  # Y
        glColor3f(0,0,1); glVertex3f(0,-2,0); glVertex3f(0,-2,2) # Z
        glEnd()

        glPushMatrix()
        rmat = get_rotation_matrix(quat)
        glMultMatrixf(rmat)
        
        # This rotation aligns the Standing Rocket with the Sensor's Flat Pose
        glRotatef(90, 1, 0, 0) 
        
        draw_rocket()
        glPopMatrix()

        pygame.display.flip()
        pygame.time.wait(10)

if __name__ == "__main__":
    main()