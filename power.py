#!/usr/bin/python3
# power.py
# 02/01/2021
# Aidan Gray
# aidan.gray@idg.jhu.edu
#
# This script is used to remotely control power to
# the camera and two stage controllers for the FSC System.

import sys
import serial

PORT_NAME = '/dev/ttyACM0'	# USB port of the Numato GPIO module
GPIO_CAMERA = [0,5]			# [READ, WRITE]
GPIO_STAGE_A = [2,6]
GPIO_STAGE_B = [3,7]
USAGE = "Usage: power.py [camera/stageA/stageB] [on/off/read]"

# parse args
if(len(sys.argv) < 2):
	print(f'{USAGE}')
	sys.exit(0)
else:
	deviceTmp = sys.argv[1]
	commandTmp = sys.argv[2]

# check which device to control
if deviceTmp.lower() == 'camera':
	device = GPIO_CAMERA
elif deviceTmp.lower() == 'stagea':
	device = GPIO_STAGE_A
elif deviceTmp.lower() == 'stageb':
	device = GPIO_STAGE_B
else:
	print(f'{USAGE}')
	sys.exit(0)

# check what to do with device
if commandTmp.lower() == 'on':
	command = 'clear '+str(device[1])
elif commandTmp.lower() == 'off':
	command = 'set '+str(device[1])
elif commandTmp.lower() == 'read':
	command = 'read '+str(device[0])
else:
	print(f'{USAGE}')
	sys.exit(0)

#Open port for communication
serPort = serial.Serial(PORT_NAME, 19200, timeout=1)

#Send the command
serPort.write(str.encode("gpio "+ command + "\r"))
reply = serPort.read(25).decode()
replyList = reply.split('\n\r')
print(replyList[1])

#Close the port
serPort.close()
