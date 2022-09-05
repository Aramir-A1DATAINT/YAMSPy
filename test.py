import time
import curses
from collections import deque
from itertools import cycle

from yamspy import MSPy

import pygame
import sys
import time

# Max periods for:
CTRL_LOOP_TIME = 1/150


NO_OF_CYCLES_AVERAGE_GUI_TIME = 3

SERIAL_PORT = "/dev/tty.usbmodem2072355459311"
# def joystick():
#     pygame.display.init()
#     js = pygame.joystick.Joystick(0)
#     js.init()
#     return js

def keyboard_controller(js):

    # This order is the important bit: it will depend on how your flight controller is configured.
    # Below it is considering the flight controller is set to use AETR.
    # The names here don't really matter, they just need to match what is used for the CMDS dictionary.
    # In the documentation, iNAV uses CH5, CH6, etc while Betaflight goes AUX1, AUX2...
    CMDS_ORDER = ['roll', 'pitch', 'throttle', 'yaw', 'aux1', 'aux2', 'aux3', 'aux4'] 

    time.sleep(2)
    with MSPy(device=SERIAL_PORT,  loglevel='WARNING', baudrate=115200) as board:
        if board == 1:
            print("Connection failed")
            return
        CMDS = {
        'roll':     1500,
        'pitch':    1500,
        'throttle': 1020,
        'yaw':      1500,
        'aux1':     1500,
        'aux2':     1500,
        'aux3':     1500,
        'aux4':     1500,
        }
        tmp = 1000

        last_loop_time  = time.time()
        while True:
            pygame.event.pump()
            for action, i in zip(CMDS, range(js.get_numaxes())):
                if action == 'throttle':
                    CMDS[action] = 1000 + int((js.get_axis(i)+ 1) *500)
                
                if action == 'yaw':
                    CMDS[action] = 1500 + int(js.get_axis(i)*500)
                    CMDS['aux4'] += int(js.get_axis(i)*10)
                
                if action == "aux4":
                    pass

                if action == 'roll':
                    CMDS[action] = 1500 + int(js.get_axis(i)*500)
                
                if action == 'pitch':
                    CMDS[action] = 1500 + int(js.get_axis(i)*500)                

                if action == 'aux1':
                    CMDS[action] = 1500 + int(js.get_axis(i)*500)
            
                if action == 'aux2':
                    CMDS[action] = 1500 + int(js.get_axis(i)*500)

                if CMDS['aux3'] == 2000:
                    CMDS['aux4'] = 1500
                # 요 코드 삭제 reset 버튼은 aux4 로 실행
                # 요 코드는 계속 누적 

                if (time.time()-last_loop_time) >= CTRL_LOOP_TIME:
                    last_loop_time = time.time()
                    # Send the RC channel values to the FC
                    board.send_RAW_RC([CMDS[ki] for ki in CMDS_ORDER])
                print(CMDS['yaw'])
                print(CMDS['aux4'])
if __name__ == "__main__":
    pygame.display.init()
    pygame.joystick.init()
    js = pygame.joystick.Joystick(0)
    js.init()
    
    while True:
        keyboard_controller(js)
