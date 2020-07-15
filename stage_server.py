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
            devices_list.append(repr(enum_name))

    return devices_list, dev_count

# command handler, to parse the client's data more precisely
def handle_command(log, writer, data): 
    response = 'BAD: Invalid Command'
    commandList = data.split()

    # try:
    #     # check if command is Expose, Set, or Get
    #     if commandList[0] == 'expose':
    #         if len(commandList) == 3:
    #             if commandList[1] == 'object' or commandList[1] == 'flat' or commandList[1] == 'dark' or commandList[1] == 'bias':
    #                 expType = commandList[1]
    #                 expTime = commandList[2]
    #                 try:
    #                     float(expTime)
    #                     if float(expTime) > 0:                    
    #                         expTime = float(expTime)
    #                         fileName = exposure(expType, expTime)
    #                         response = 'OK\n'+'FILENAME: '+fileName
    #                     else:
    #                         response = 'BAD: Invalid Exposure Time'
    #                 except ValueError:
    #                     response = 'BAD: Invalid Exposure Time'
    #     elif commandList[0] == 'set':
    #         if len(commandList) >= 1:
    #             response = setParams(commandList[1:])
    # except IndexError:
    #     response = 'BAD: Invalid Command'
        
    # tell the client the result of their command & log it
    log.info('RESPONSE: '+response)
    writer.write((response+'\n').encode('utf-8'))
    writer.write(('---------------------------------------------------\n').encode('utf-8'))

# async client handler, for multiple connections
async def handle_client(reader, writer):
    request = None
    
    # loop to continually handle incoming data
    while request != 'quit':        
        request = (await reader.read(255)).decode('utf8')
        print(request.encode('utf8'))
        log.info('COMMAND: '+request)
        writer.write(('COMMAND: '+request.upper()).encode('utf8'))    

        response = 'BAD'
        # check if data is empty, a status query, or potential command
        dataDec = request
        if dataDec == '':
            break
        elif 'status' in dataDec.lower():
            # check if the command thread is running
            try:
                if comThread.is_alive():
                    response = 'BUSY'
                else:
                    response = 'IDLE'
            except:
                response = 'IDLE'

            response = response+\
                '\n*** ADD STAGE STATUS HERE ***'

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

        writer.write(('---------------------------------------------------\n').encode('utf-8'))                          
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

    from pyximc import *
    from pyximc import MicrostepMode

    dev_list, dev_count = scan_for_devices()

    print("Number of devices: "+str(dev_count))
    try:
        print("List of devices:")
        for i in dev_list:
        	print(i)

        	if '49E5' in repr(i):
        		axis_r = lib.open_device(i)
        	elif '49F3' in repr(i):
        		axis_z = lib.open_device(i)
        	elif '3F53' in repr(i):
        		axis_th = lib.open_device(i)
        	else:
        		print("No correct devices")

    except IndexError:
        print("No devices to list...")

    fileDir = os.path.expanduser('~')+'/Pictures/'
    log = log_start()

    # setup Remote TCP Server
    HOST, PORT = '', 9997

    try:
        asyncio.run(main(HOST,PORT))
    except KeyboardInterrupt:
        print('\n...Closing server...')
        for n in [axis_r, axis_z, axis_th]:
        	lib.close_device(byref(cast(n, POINTER(c_int))))
        print('Done')
    except:
        print('Unknown error')
