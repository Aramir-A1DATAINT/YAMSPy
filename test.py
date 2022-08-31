from ctypes.wintypes import MSG
import time
import curses
from collections import deque
from itertools import cycle

from yamspy import MSPy

import pygame
import sys
import time

# Max periods for:
CTRL_LOOP_TIME = 1/40
SLOW_MSGS_LOOP_TIME = 1/5 # these messages take a lot of time slowing down the loop...

NO_OF_CYCLES_AVERAGE_GUI_TIME = 3

SERIAL_PORT = "/dev/ttyACM0"

def joystick():
    js = pygame.joystick.Joystick(0)
    js.init()
    return js

def keyboard_controller():

    CMDS = {
            'roll':     1500,
            'pitch':    1500,
            'throttle': 1020,
            'yaw':      1500,
            'aux1':     1000,
            'aux2':     1000,
            'aux3':     1000,
            'aux4':     1000,
            'aux5':     1000,
            'aux6':     1000,
            }

    # This order is the important bit: it will depend on how your flight controller is configured.
    # Below it is considering the flight controller is set to use AETR.
    # The names here don't really matter, they just need to match what is used for the CMDS dictionary.
    # In the documentation, iNAV uses CH5, CH6, etc while Betaflight goes AUX1, AUX2...
    CMDS_ORDER = ['roll', 'pitch', 'throttle', 'yaw', 'aux1', 'aux2', 'aux3', 'aux4',
            'aux5', 'aux6'] 

    try:
        js = joystick()

        with MSG(device=SERIAL_PORT,  loglevel='WARNING', baudrate=115200) as board:
            if board == 1:
                print("Connection failed")
                return
            
            command_list = ['MSP_API_VERSION', 'MSP_FC_VARIANT', 'MSP_FC_VERSION', 'MSP_BUILD_INFO', 
                            'MSP_BOARD_INFO', 'MSP_UID', 'MSP_ACC_TRIM', 'MSP_NAME', 'MSP_STATUS', 'MSP_STATUS_EX',
                            'MSP_BATTERY_CONFIG', 'MSP_BATTERY_STATE', 'MSP_BOXNAMES']

            if board.INAV:
                command_list.append('MSPV2_INAV_ANALOG')
                command_list.append('MSP_VOLTAGE_METER_CONFIG')
            
            for msg in command_list: 
                if board.send_RAW_msg(MSPy.MSPCodes[msg], data=[]):
                    dataHandler = board.receive_msg()
                    board.process_recv_data(dataHandler)
            if board.INAV:
                cellCount = board.BATTERY_STATE['cellCount']
            else:
                cellCount = 0 # MSPV2_INAV_ANALOG is necessary
            min_voltage = board.BATTERY_CONFIG['vbatmincellvoltage']*cellCount
            warn_voltage = board.BATTERY_CONFIG['vbatwarningcellvoltage']*cellCount
            max_voltage = board.BATTERY_CONFIG['vbatmaxcellvoltage']*cellCount

            pygame.event.pump()

            last_loop_time  = time.time()

            for k in range(js.get_numaxes()):
                print(js.get_axis(k)) # 여기서 시그널 어떻게 나오는지 확인을 해야 할 것 같은데?

                CMDS['roll'] = 1500 + int(js.get_axis(0)*500)
                CMDS['pitch'] = 1500 + int(js.get_axis(1)*500)
                CMDS['throttle'] = 1020 + int(js.get_axis(2)*500)
                CMDS['yaw'] = 1500 + int(js.get_axis(3)*500)
                CMDS['aux1'] = 1000 + int(js.get_axis(4)*500)
                CMDS['aux2'] = 1000 + int(js.get_axis(5)*500)
                CMDS['aux3'] = 1000 + int(js.get_axis(6)*500)
                CMDS['aux4'] = 1000 + int(js.get_axis(7)*500)

                # 요 코드 삭제 reset 버튼은 aux4 로 실행
                # 요 코드는 계속 누적 

                if (time.time()-last_loop_time) >= CTRL_LOOP_TIME:
                    last_loop_time = time.time()
                    # Send the RC channel values to the FC
                    if board.send_RAW_RC([CMDS[ki] for ki in CMDS_ORDER]):
                        dataHandler = board.receive_msg()
                        board.process_recv_data(dataHandler)
    except:
        print('no joystick found')


if __name__ == "__main__":
    while True:
        keyboard_controller()
