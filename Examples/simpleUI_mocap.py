"""simpleUI.py: Simple UI (toy one really) to test YAMSPy using a SSH connection.

Copyright (C) 2019 Ricardo de Azambuja

This file is part of YAMSPy.

YAMSPy is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

YAMSPy is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with YAMSPy.  If not, see <https://www.gnu.org/licenses/>.


WARNING:
This UI is not fit for flying your drone, it is only useful for testing stuff in a safe place, ok?

Acknowledgement:
This work was possible thanks to the financial support from IVADO.ca (postdoctoral scholarship 2019/2020).

Disclaimer (adapted from Wikipedia):
None of the authors, contributors, supervisors, administrators, employers, friends, family, vandals, or anyone else 
connected (or not) with this project, in any way whatsoever, can be made responsible for your use of the information (code) 
contained or linked from here.


TODO:
1) The integrator makes too hard to control things (it winds up). Probably a non-linear thing would be helpful here...

"""

__author__ = "Ricardo de Azambuja"
__copyright__ = "Copyright 2019, MISTLab.ca"
__credits__ = [""]
__license__ = "GPL"
__version__ = "0.0.1"
__maintainer__ = "Ricardo de Azambuja"
__email__ = "ricardo.azambuja@gmail.com"
__status__ = "Development"

import time
import curses
from collections import deque
from itertools import cycle

from yamspy import MSPy
import sys
import time
import serial
import socket
import struct
import pickle
import random

from yamspy import MSPy
from multiprocessing import Process,Queue,Pipe
from OptiTrackPython_example import get_data_mocap

serial_port = "/dev/ttyS0"
UDP_IP = "192.168.0.101"
UDP_PORT = 5409
sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM) # UDP
sock.bind((UDP_IP, UDP_PORT))
L = [0,0,0,0,0]
# Max periods for:
CTRL_LOOP_TIME = 1/100
SLOW_MSGS_LOOP_TIME = 1/5 # these messages take a lot of time slowing down the loop...

NO_OF_CYCLES_AVERAGE_GUI_TIME = 10

def run_curses(external_function):
    result=1

    try:
        # get the curses screen window
        screen = curses.initscr()

        # turn off input echoing
        curses.noecho()

        # respond to keys immediately (don't wait for enter)
        curses.cbreak()

        # non-blocking
        screen.timeout(0)

        # map arrow keys to special values
        screen.keypad(True)

        screen.addstr(1, 0, "Press 'q' to quit, 'r' to reboot, 'm' to change mode, 'a' to arm, 'd' to disarm and arrow keys to control", curses.A_BOLD)
        
        result = external_function(screen)

    finally:
        # shut down cleanly
        curses.nocbreak(); screen.keypad(0); curses.echo()
        curses.endwin()
        if result==1:
            print("An error occurred... probably the serial port is not available ;)")

def keyboard_controller(screen):

    CMDS = {
            'roll':     1500,
            'pitch':    1500,
            'throttle': 900,
            'yaw':      1500,
            'aux1':     1000,
            'aux2':     1000
            }

    CMDS_ORDER = ['roll', 'pitch', 'throttle', 'yaw', 'aux1', 'aux2']

    # print doesn't work with curses, use addstr instead

    try:
        screen.addstr(15, 0, "Connecting to the FC...")

        # with MSPy(device="/dev/ttyACM0", loglevel='WARNING', baudrate=115200) as board:
        with MSPy(device=serial_port, loglevel='WARNING', baudrate=115200) as board:
            if board == 1: # an error occurred...
                return 1

            screen.addstr(15, 0, "Connecting to the FC... connected!")
            screen.clrtoeol()
            screen.move(1,0)

            test_mocap = [1,2,3,4,5]
            DATA = board.convert(test_mocap, 16)

            average_cycle = deque([0]*NO_OF_CYCLES_AVERAGE_GUI_TIME)

            # It's necessary to send some messages or the RX failsafe will be active
            # and it will not be possible to arm.
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

            screen.addstr(15, 0, "apiVersion: {}".format(board.CONFIG['apiVersion']))
            screen.clrtoeol()
            screen.addstr(15, 50, "flightControllerIdentifier: {}".format(board.CONFIG['flightControllerIdentifier']))
            screen.addstr(16, 0, "flightControllerVersion: {}".format(board.CONFIG['flightControllerVersion']))
            screen.addstr(16, 50, "boardIdentifier: {}".format(board.CONFIG['boardIdentifier']))
            screen.addstr(17, 0, "boardName: {}".format(board.CONFIG['boardName']))
            screen.addstr(17, 50, "name: {}".format(board.CONFIG['name']))


            slow_msgs = cycle(['MSP_ANALOG', 'MSP_STATUS_EX', 'MSP_MOTOR', 'MSP_RC'])

            cursor_msg = ""
            last_loop_time = last_slow_msg_time = last_cycleTime = time.time()
            while True:
                start_time = time.time()
                
                # if board.send_RAW_msg(30, DATA):
                #     dataHandler = board.receive_msg()
                #     codestr = MSPy.MSPCodes2Str.get(dataHandler['code'])
                #     if codestr:
                #         # print('Received >>> {}'.format(codestr))
                #         board.process_recv_data(dataHandler)
                #     elif dataHandler['packet_error'] == 1:
                #         # print('Received >>> ERROR!')
                #         print(' ')
                # time.sleep(.05)

                # print(f"Debug content: {board.SENSOR_DATA['debug']}")
                # if board.send_RAW_msg(MSPy.MSPCodes['MSP_DEBUG'], data=[]):
                #     dataHandler = board.receive_msg()
                #     codestr = MSPy.MSPCodes2Str.get(dataHandler['code'])
                #     if codestr:
                #         # print('Received >>> {}'.format(codestr))
                #         board.process_recv_data(dataHandler)
                        # print(f"Debug content: {board.SENSOR_DATA['debug']}")
                    # elif dataHandler['packet_error'] == 1:
                    #     # print('Received >>> ERROR!')
                    #     print(' ')

                ## receive data from the optitrack script and prepare it to be sent to fc
                Data, addr = sock.recvfrom(1024*4) 
                L = pickle.loads(Data)
                # print(L)
                for ii in range(3):
                    test_mocap[ii+1] = int(L[ii]*100) 
                    # print(test_mocap[ii+1])
                test_mocap[4] = int(L[3]*10)
                test_mocap[0] = test_mocap[0]+1
                # print(test_mocap)
                DATA = board.convert(test_mocap, 16)
                mocap_result = board.SENSOR_DATA['debug']
                # mocap_result2 = dataHandler[dataHandler.find("[")+1:dataHandler.rfind("]")]
                # mocap_result = re.search(r"\[([A-Za-z0-9_]+)\]", codestr)



                # screen.addstr(12, 0, "mocap: {}".format(codestr))
                # screen.clrtoeol()

                #
                # Key input processing
                #

                #
                # KEYS (NO DELAYS)
                #
                char = screen.getch() # get keypress
                curses.flushinp() # flushes buffer
                if char == ord('q') or char == ord('Q'):
                    break

                elif char == ord('d') or char == ord('D'):
                    cursor_msg = 'Disarming...'
                    CMDS['aux1'] = 1000

                elif char == ord('r') or char == ord('R'):
                    screen.addstr(3, 0, 'Rebooting...')
                    screen.clrtoeol()
                    board.reboot()
                    time.sleep(0.5)
                    break

                elif char == ord('a') or char == ord('A'):
                    cursor_msg = 'Arming...'
                    CMDS['aux1'] = 1800

                elif char == ord('p') or char == ord('A'):
                    cursor_msg = 'rebooting...'
                    if board.reboot():
                        try:
                            dataHandler = board.receive_msg()
                            board.process_recv_data(dataHandler)
                        except serial.SerialException:
                            print("Serial error... it's rebooting :)")

                elif char == ord('t') or char == ord('T'):
                    CMDS['throttle'] = 1300
                    cursor_msg = 'takeoff throttle:{}'.format(CMDS['throttle'])

                elif char == ord('l') or char == ord('L'):
                    CMDS['throttle'] = 900
                    cursor_msg = 'landing throttle:{}'.format(CMDS['throttle'])

                elif char == ord('m') or char == ord('M'):
                    if CMDS['aux2'] <= 1300:
                        cursor_msg = 'Horizon Mode...'
                        CMDS['aux2'] = 1500
                    elif 1700 > CMDS['aux2'] > 1300:
                        cursor_msg = 'Flip Mode...'
                        CMDS['aux2'] = 2000
                    elif CMDS['aux2'] >= 1700:
                        cursor_msg = 'Angle Mode...'
                        CMDS['aux2'] = 1000

                elif char == ord('w') or char == ord('W'):
                    CMDS['throttle'] = CMDS['throttle'] + 10 if CMDS['throttle'] + 10 <= 2000 else CMDS['throttle']
                    cursor_msg = 'W Key - throttle(+):{}'.format(CMDS['throttle'])

                elif char == ord('e') or char == ord('E'):
                    CMDS['throttle'] = CMDS['throttle'] - 10 if CMDS['throttle'] - 10 >= 1000 else CMDS['throttle']
                    cursor_msg = 'E Key - throttle(-):{}'.format(CMDS['throttle'])

                elif char == curses.KEY_RIGHT:
                    CMDS['roll'] = CMDS['roll'] + 10 if CMDS['roll'] + 10 <= 2000 else CMDS['roll']
                    cursor_msg = 'Right Key - roll(-):{}'.format(CMDS['roll'])

                elif char == curses.KEY_LEFT:
                    CMDS['roll'] = CMDS['roll'] - 10 if CMDS['roll'] - 10 >= 1000 else CMDS['roll']
                    cursor_msg = 'Left Key - roll(+):{}'.format(CMDS['roll'])

                elif char == curses.KEY_UP:
                    CMDS['pitch'] = CMDS['pitch'] + 10 if CMDS['pitch'] + 10 <= 2000 else CMDS['pitch']
                    cursor_msg = 'Up Key - pitch(+):{}'.format(CMDS['pitch'])

                elif char == curses.KEY_DOWN:
                    CMDS['pitch'] = CMDS['pitch'] - 10 if CMDS['pitch'] - 10 >= 1000 else CMDS['pitch']
                    cursor_msg = 'Down Key - pitch(-):{}'.format(CMDS['pitch'])

                #
                # IMPORTANT MESSAGES (CTRL_LOOP_TIME based)
                #
                if (time.time()-last_loop_time) >= CTRL_LOOP_TIME:
                    last_loop_time = time.time()
                    # Send the RC channel values to the FC
                    if board.send_RAW_RC([CMDS[ki] for ki in CMDS_ORDER]):
                        dataHandler = board.receive_msg()
                        board.process_recv_data(dataHandler)
                        
                    # if board.send_RAW_msg(30, DATA):
                    #     dataHandler = board.receive_msg()
                    #     codestr = MSPy.MSPCodes2Str.get(dataHandler['code'])
                    #     if codestr:
                    #         # print('Received >>> {}'.format(codestr))
                    #         board.process_recv_data(dataHandler)
                    #     elif dataHandler['packet_error'] == 1:
                    #         # print('Received >>> ERROR!')
                    #         print(' ')
                    # time.sleep(.05)    

                #
                # SLOW MSG processing (user GUI)
                #
                if (time.time()-last_slow_msg_time) >= SLOW_MSGS_LOOP_TIME:
                    last_slow_msg_time = time.time()

                    next_msg = next(slow_msgs) # circular list

                    # Read info from the FC
                    if board.send_RAW_msg(MSPy.MSPCodes[next_msg], data=[]):
                        dataHandler = board.receive_msg()
                        board.process_recv_data(dataHandler)
                        
                    if next_msg == 'MSP_ANALOG':
                        voltage = board.ANALOG['voltage']
                        voltage_msg = ""
                        if min_voltage < voltage <= warn_voltage:
                            voltage_msg = "LOW BATT WARNING"
                        elif voltage <= min_voltage:
                            voltage_msg = "ULTRA LOW BATT!!!"
                        elif voltage >= max_voltage:
                            voltage_msg = "VOLTAGE TOO HIGH"

                        screen.addstr(8, 0, "Battery Voltage: {:2.2f}V".format(board.ANALOG['voltage']))
                        screen.clrtoeol()
                        screen.addstr(8, 24, voltage_msg, curses.A_BOLD + curses.A_BLINK)
                        screen.clrtoeol()

                    elif next_msg == 'MSP_STATUS_EX':
                        ARMED = board.bit_check(board.CONFIG['mode'],0)
                        screen.addstr(5, 0, "ARMED: {}".format(ARMED), curses.A_BOLD)
                        screen.clrtoeol()

                        screen.addstr(5, 50, "armingDisableFlags: {}".format(board.process_armingDisableFlags(board.CONFIG['armingDisableFlags'])))
                        screen.clrtoeol()

                        screen.addstr(6, 0, "cpuload: {}".format(board.CONFIG['cpuload']))
                        screen.clrtoeol()
                        screen.addstr(6, 50, "cycleTime: {}".format(board.CONFIG['cycleTime']))
                        screen.clrtoeol()

                        screen.addstr(7, 0, "mode: {}".format(board.CONFIG['mode']))
                        screen.clrtoeol()

                        screen.addstr(7, 50, "Flight Mode: {}".format(board.process_mode(board.CONFIG['mode'])))
                        screen.clrtoeol()


                    elif next_msg == 'MSP_MOTOR':
                        screen.addstr(9, 0, "Motor Values: {}".format(board.MOTOR_DATA))
                        screen.clrtoeol()

                    elif next_msg == 'MSP_RC':
                        screen.addstr(10, 0, "RC Channels Values: {}".format(board.RC['channels']))
                        screen.clrtoeol()

                    screen.addstr(11, 0, "GUI cycleTime: {0:2.2f}ms (average {1:2.2f}Hz)".format((last_cycleTime)*1000,                                                                          1/(sum(average_cycle)/len(average_cycle))))
                    screen.clrtoeol()
                    
                    screen.addstr(3, 0, cursor_msg)
                    screen.clrtoeol()

                    # screen.addstr(19, 0, "mocap: {}".format(mocap_result))
                    # screen.clrtoeol()
                    # screen.addstr(21,0,"test_mocap:{}".format(test_mocap))
                    # screen.clrtoeol()

                end_time = time.time()
                last_cycleTime = end_time-start_time
                if (end_time-start_time)<CTRL_LOOP_TIME:
                    time.sleep(CTRL_LOOP_TIME-(end_time-start_time))
                    
                average_cycle.append(end_time-start_time)
                average_cycle.popleft()
    except KeyboardInterrupt:
        # print("Keyboard Interrupt received!")
        # print("Board is rebooting...")
        if board.reboot():
            try:
                dataHandler = board.receive_msg()
                board.process_recv_data(dataHandler)
            except serial.SerialException:
                print("Serial error... it's rebooting :)")
    finally:
        screen.addstr(5, 0, "Disconneced from the FC!")
        screen.clrtoeol()
        print("Board is rebooting...")
        if board.reboot():
            try:
                dataHandler = board.receive_msg()
                board.process_recv_data(dataHandler)
            except serial.SerialException:
                print("Serial error... it's rebooting :)")


if __name__ == "__main__":
    run_curses(keyboard_controller)