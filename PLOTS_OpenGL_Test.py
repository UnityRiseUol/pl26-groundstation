from OpenGL.GL import *
from OpenGL.GLU import *
import pygame
from pygame.locals import *
import numpy as np
import serial
import math
import sys


SERIAL_PORT = "/dev/serial0"   # Change if needed
BAUD_RATE   = 115200
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.01)
    print("Connected")
except:
    print("Failed")
    sys.exit()


pygame.init()
info = pygame.display.Info()
display = (info.current_w, info.current_h)
pygame.display.set_mode(display, DOUBLEBUF | OPENGL | FULLSCREEN)
glEnable(GL_DEPTH_TEST)
gluPerspective(45, display[0]/display[1], 0.1, 100.0)
glTranslatef(0, 0, -20)

###########
yaw = 0
pitch = 0
roll = 0
altitude = 0

###########
def draw_rocket():
    quad = gluNewQuadric()

    glColor3f(0.8, 0.8, 0.8)
    glPushMatrix()
    glRotatef(-90, 1, 0, 0)
    gluCylinder(quad, 1, 1, 8, 32, 32)
    glPopMatrix()

    glColor3f(1, 0, 0)
    glPushMatrix()
    glTranslatef(0, 8, 0)
    glRotatef(-90, 1, 0, 0)
    gluCylinder(quad, 1, 0, 3, 32, 32)
    glPopMatrix()

    glColor3f(0.2, 0.2, 1)
    for angle in [0, 90, 180, 270]:
        glPushMatrix()
        glRotatef(angle, 0, 1, 0)
        glBegin(GL_TRIANGLES)
        glVertex3f(1, 0, 0)
        glVertex3f(2.5, 0, 0)
        glVertex3f(1, 3, 0)
        glEnd()
        glPopMatrix()


def read_uart():
    global yaw, altitude
    try:
        line = ser.readline().decode("utf-8").strip()
        if not line:
            return
        data = line.split(",")

        if len(data) >= 15: #MAK ESURE THIS MATCHES MICROCONTROLLER STUFF
            t = float(data[0])
            altitude = float(data[1])
            velocity = float(data[2])
            yaw = float(data[14])

    except:
        pass #test c1


#############
clock = pygame.time.Clock()

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()
    read_uart()
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    glTranslatef(0, 0, -20)

    #rotate now -not before like other file
    glRotatef(yaw, 0, 1, 0)

    draw_rocket()

    pygame.display.flip()
    clock.tick(60)


'''
NOTES
=====

- Familarise with X.Y jargon
- Get actual rocket on screen to point in direction

'''