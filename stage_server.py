#! /usr/bin/env python3
# stage_server.py
# 7/6/2020
# Aidan Gray
# aidan.gray@idg.jhu.edu
#
# This a server for the 3 Standa stages R, Theta, Z

from astropy.io import fits
from ctypes import *
import asyncio
import threading
import subprocess
import logging
import os
import sys
import time
import math

# change depending on input (mm/deg/arcsec/rad/etc)
R_CONST = 0.025 # mm
T_CONST = 0.144 # deg
Z_CONST = 0.00125 # mm

# create an event log
def log_start():
    scriptDir = os.path.dirname(os.path.abspath(__file__))
    scriptName = os.path.splitext(os.path.basename(__file__))[0]
    log = logging.getLogger('stage_server')
    hdlr = logging.FileHandler(scriptDir+'/'+scriptName+'.log')
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    hdlr.setFormatter(formatter)
    log.addHandler(hdlr)
    log.setLevel(logging.INFO)
    return log

# Scans for all available devices.
# Returns a list of devices and the # of devices 
def scan_for_devices():
    probe_flags = EnumerateFlags.ENUMERATE_PROBE
    devenum = lib.enumerate_devices(probe_flags, None)
    dev_count = lib.get_device_count(devenum)
    controller_name = controller_name_t()

    devices_list = []
    for dev_ind in range(0, dev_count):
        enum_name = lib.get_device_name(devenum, dev_ind)
        result = lib.get_enumerate_device_controller_name(devenum, dev_ind, byref(controller_name))

        if result == Result.Ok:
            devices_list.append(enum_name)

    return devices_list, dev_count

# Returns relevant status information for all 3 devices
def get_status(lib, open_devs):
    all_status = ''
    r_status = status_t()
    t_status = status_t()
    z_status = status_t()

    r_result = lib.get_status(open_devs[0], byref(r_status))
    t_result = lib.get_status(open_devs[1], byref(t_status))
    z_result = lib.get_status(open_devs[2], byref(z_status))

    if r_result == Result.Ok and t_result == Result.Ok and z_result == Result.Ok:
        response, all_pos = get_position(lib, open_devs)
        r_speed, r_uspeed = get_speed(lib, open_devs[0])
        t_speed, t_uspeed = get_speed(lib, open_devs[1])
        z_speed, z_uspeed = get_speed(lib, open_devs[2])

        r_speed = R_CONST*(r_speed + (r_uspeed/256))
        t_speed = T_CONST*(t_speed + (t_uspeed/256))
        z_speed = Z_CONST*(z_speed + (z_uspeed/256))

        if response == 'OK':
            all_status = "\nr: "+str(all_pos[0][0])+" mm\
                        \n\u03B8: "+str(all_pos[1][0])+" deg\
                        \nz: "+str(all_pos[2][0])+" mm\
                        \nEncoder counts: "+str(all_pos[0][1])+" : "+str(all_pos[1][1])+" : "+str(all_pos[2][1])+"\
                        \nSpeeds: "+str(r_speed)+" mm/s : "+str(t_speed)+" deg/s : "+str(z_speed)+" mm/s"
    else:
        response = 'BAD: lib.get_status() failed'
    return response, all_status

# Returns the current position of the devices
def get_position(lib, open_devs):
    response = 'OK'
    r_pos = get_position_t()
    t_pos = get_position_t()
    z_pos = get_position_t()

    r_result = lib.get_position(open_devs[0], byref(r_pos))
    t_result = lib.get_position(open_devs[1], byref(t_pos))
    z_result = lib.get_position(open_devs[2], byref(z_pos))

    all_pos = []

    if r_result == Result.Ok and t_result == Result.Ok and z_result == Result.Ok:
        # Convert the position from steps to mm (linear stages)
        # or arcsecs for the rotation stage
        r_pos_mm = R_CONST*(r_pos.Position + (r_pos.uPosition / 256))
        t_pos_am = T_CONST*(t_pos.Position + (t_pos.uPosition / 256))
        z_pos_mm = Z_CONST*(z_pos.Position + (z_pos.uPosition / 256))

        # Convert the encoder positions to mm (liinear stages)
        # or arcsecs for the rotation stage

        # r_pos_enc = 0.000625*r_pos.EncPosition
        # t_pos_enc = (25.9/60)*t_pos.EncPosition
        # z_pos_enc = 0.0000625*z_pos.EncPosition

        r_pos_enc = r_pos.EncPosition
        t_pos_enc = t_pos.EncPosition
        z_pos_enc = z_pos.EncPosition

        all_pos = [[r_pos_mm, r_pos_enc], [t_pos_am, t_pos_enc], [z_pos_mm, z_pos_enc]]
    else:
        response = 'BAD: lib.get_position() failed'
    return response, all_pos

# return the set speed of the motors
def get_speed(lib, device_id):
    mvst = move_settings_t()
    result = lib.get_move_settings(device_id, byref(mvst))
    if result == Result.Ok:    
        return mvst.Speed, mvst.uSpeed
    else:
        return 0

# sets the speed of the desired motor
def set_speed(lib, device_id, speed):
    mvst = move_settings_t()
    result = lib.get_move_settings(device_id, byref(mvst))

    if result == Result.Ok:
        # split the integer from the decimal
        u_speed, speed = math.modf(speed)

        # convert the decimal to #/256
        u_speed = u_speed * 256

        # prepare move_settings_t struct
        mvst.Speed = int(speed)
        mvst.uSpeed = int(u_speed)
        result = lib.set_move_settings(device_id, byref(mvst))
        if result == Result.Ok:
            return 'OK'
        else:
            return 'BAD: set_move_settings() failed'
    else:
        return 'BAD: get_move_settings() failed'

def move(lib, device_id, distance):
    # split the integer from the decimal
    u_distance, distance = math.modf(distance)

    # convert the decimal to #/256
    u_distance = u_distance * 256

    result = lib.command_move(device_id, int(distance), int(u_distance))
    if result == Result.Ok:
        return 'OK'
    else:
        return 'BAD: Move command failed'

# command handler, to parse the client's data more precisely
def handle_command(log, writer, data): 
    response = ''
    commandList = data.split()

    try:
        # check if command is move, offset, or ...
        if commandList[0] == 'move' and len(commandList) > 1:
            # send move commands (create new threads) for each axis given
            #print('...Moving...')
            for axis in commandList[1:]:
                if axis[:2] == 'r=':
                    try:
                        # move r axis
                        r_move = float(axis[2:]) / R_CONST
                        response = move(lib, open_devs[0], r_move)

                    except ValueError:
                        response = 'BAD: Invalid move'

                elif axis[:2] == 't=':
                    try:
                        # move theta axis
                        t_move = float(axis[2:]) / T_CONST
                        response = move(lib, open_devs[1], t_move)
                        
                    except ValueError:
                        response = 'BAD: Invalid move'

                elif axis[:2] == 'z=':
                    try:
                        # move z axis
                        z_move = float(axis[2:]) / Z_CONST
                        response = move(lib, open_devs[2], z_move)

                    except ValueError:
                        response = 'BAD: Invalid speed'

                else:
                    response = 'BAD: Invalid set speed command' 

        elif commandList[0] == 'offset' and len(commandList) > 1:
            # send offset commands (create new threads) for each axis given
            print('...Offsetting...')

        elif commandList[0] == 'home' and len(commandList) >= 1:
            # home given axes or all axes if len(commandList) == 1 
            print('...Homing...')

        elif commandList[0] == 'speed' and len(commandList) > 1:
            # set the given axes to the given speeds
            #print('...Setting speeds...')
            for axis in commandList[1:]:
                if axis[:2] == 'r=':
                    try:
                        # set r axis speed
                        r_set_speed = float(axis[2:]) / R_CONST
                        response = set_speed(lib, open_devs[0], r_set_speed)

                    except ValueError:
                        response = 'BAD: Invalid speed'

                elif axis[:2] == 't=':
                    try:
                        # set theta axis speed
                        t_set_speed = float(axis[2:]) / T_CONST
                        response = set_speed(lib, open_devs[1], t_set_speed)
                        
                    except ValueError:
                        response = 'BAD: Invalid speed'

                elif axis[:2] == 'z=':
                    try:
                        # set z axis speed
                        z_set_speed = float(axis[2:]) / Z_CONST
                        response = set_speed(lib, open_devs[2], z_set_speed)

                    except ValueError:
                        response = 'BAD: Invalid speed'

                else:
                    response = 'BAD: Invalid set speed command' 
        else:
            response = 'BAD: Invalid Command'

    except IndexError:
        response = 'BAD: Invalid Command'
        
    # tell the client the result of their command & log it
    log.info('RESPONSE: '+response)
    writer.write((response+'\n').encode('utf-8'))
    #writer.write(('---------------------------------------------------\n').encode('utf-8'))

# async client handler, for multiple connections
async def handle_client(reader, writer):
    request = None
    
    # loop to continually handle incoming data
    while request != 'quit':        
        request = (await reader.read(255)).decode('utf8').strip()
        print(request.encode('utf8'))
        log.info('COMMAND: '+request)
        writer.write(('COMMAND: '+request.upper()+'\n').encode('utf8'))    

        # get a list of all current threads
        threadList = threading.enumerate()

        response = 'BAD'
        # check if data is empty, a status query, or potential command
        dataDec = request
        if dataDec == '':
            break
        elif 'status' in dataDec.lower():
            # check if the command thread is running
            try:
                if comThread.is_alive():
                    busyState = 'BUSY'
                else:
                    busyState = 'IDLE'
            except:
                busyState = 'IDLE'

            response, all_status = get_status(lib, open_devs)

            response = response + '\n' + busyState + '\n' + all_status

            # send current status to open connection & log it
            log.info('RESPONSE: '+response)
            writer.write((response+'\n').encode('utf-8'))
            
        elif 'stop' in dataDec.lower():
            # check if the command thread is running
            try:
                if comThread.is_alive():
                    response = 'OK: aborting move'
                    #### ABORT CODE GOES HERE
                    response = response+'\nMove Aborted'
                else:
                    response = 'BAD: idle'
            except:
                response = 'BAD: idle'

            # send current status to open connection & log it
            log.info('RESPONSE: '+response)
        
        else:
            # check if the command thread is running, may fail if not created yet, hence try/except
            try:
                if comThread.is_alive():
                    response = 'BAD: busy'
                    # send current status to open connection & log it
                    log.info('RESPONSE: '+response)
                    writer.write((response+'\n').encode('utf-8'))
                else:
                    # create a new thread for the command
                    comThread = threading.Thread(target=handle_command, args=(log, writer, dataDec,))
                    comThread.start()
            except:
                # create a new thread for the command
                comThread = threading.Thread(target=handle_command, args=(log, writer, dataDec,))
                comThread.start()

        #writer.write(('---------------------------------------------------\n').encode('utf-8'))                          
        await writer.drain()
    writer.close()

async def main(HOST, PORT):
    print("Opening connection @"+HOST+":"+str(PORT))
    server = await asyncio.start_server(handle_client, HOST, PORT)
    await server.serve_forever()

if __name__ == "__main__":

    # Check if Python version is >= 3.0
    if sys.version_info >= (3,0):
        import urllib.parse

    # Set the current directory and get the path to pyximc.py
    cur_dir = os.path.abspath(os.path.dirname(__file__))
    ximc_dir = os.path.join(cur_dir, "ximc-2.12.1/ximc")
    ximc_package_dir = os.path.join(ximc_dir, "crossplatform", "wrappers", "python")
    sys.path.append(ximc_package_dir)

    try: 
        from pyximc import *
    except ImportError as err:
        print ("Can't import pyximc module. The most probable reason is that you changed the relative location of the testpython.py and pyximc.py files. See developers' documentation for details.")
        exit()

    dev_list, dev_count = scan_for_devices()
    open_devs = ['','','']

    print("Number of devices: "+str(dev_count))
    try:
        #print("List of devices:")
        all_device_check = True
        for i in dev_list:
            #print(repr(i))

            if '49E5' in repr(i):
                axis_r = lib.open_device(i)
                #print('r id: ' + repr(axis_r))
                if axis_r > 0:
                    open_devs[0] = axis_r
                else:
                    all_device_check = False
                    #print('BAD, R stage connection failed')

            elif '3F53' in repr(i):
                axis_t = lib.open_device(i)
                #print('\u03B8 id: ' + repr(axis_t))
                if axis_t > 0:
                    open_devs[1] = axis_t
                else:
                    all_device_check = False
                    #print('BAD, Theta stage connection failed')

            elif '49F3' in repr(i):
                axis_z = lib.open_device(i)
                #print('z id: ' + repr(axis_z))
                if axis_z > 0:
                    open_devs[2] = axis_z
                else:
                    all_device_check = False
                    #print('BAD, Z stage connection failed')

        if all_device_check:
            # for i in open_devs:
            #     print(repr(i))

            fileDir = os.path.expanduser('~')+'/Pictures/'
            log = log_start()

            # setup Remote TCP Server
            HOST, PORT = '', 9997

            try:
                asyncio.run(main(HOST,PORT))
            except KeyboardInterrupt:
                print('\n...Closing server...')
                for n in open_devs:
                	lib.close_device(byref(cast(n, POINTER(c_int))))
                print('Done')
            except:
                print('Unknown error')

    except IndexError:
        print("No devices to list...")
