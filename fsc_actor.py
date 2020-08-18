#!/usr/bin/python3
# fsc_actor.py
# 8/5/2020
# Aidan Gray
# aidan.gray@idg.jhu.edu
#
# This is the actor script that controls all hardware servers for the
# Focal Surface Camera (FSC) System.

from astropy.io import fits
from ctypes import *
import socket
import logging
import os
import sys
import time
import math
import threading
import csv
import numpy as np
import subprocess

#############################
# TO-DO LIST:
# Create these methods
# - Reset stages
# Figure out 0deg
# Implement PyGuide checking 
#############################

# Coordinate file read-in
# input: name of the coordinate file
# output: list of x,y coordinates
def get_coordinates(fileName):
	# parse the CSV file to create a list of focal plane coordinates
	print("Reading coordinates file...")

	with open(fileName, 'rt', encoding='utf-8-sig') as csvfile:
	    data = [(float(x), float(y)) for x, y in csv.reader(csvfile, delimiter= ',')]

	return data

# Convert focal plane coordinates to stage coordinates
# input: list of x,y coordinates
# output: list of r,theta coordinates
def cart2polar(fp_coords):
	polar_coords = []

	for each in fp_coords:
		x = each[0]
		y = each[1]
		
		r = np.sqrt(x**2+y**2)
		
		# change this around depending on orientation on -scope
		if x == 0:
			t = 90
		elif y == 0:
			t = 0
		else:
			t = np.arctan2(y,x)

		polar_coords.append([r,t])

	return polar_coords

# edit fits header
# input: name of fits file, list of keywords and their data
def edit_fits(fileName, editList):
	try:
		fitsFile = fits.open(fileName, 'update')
		hdr = fitsFile[0].header

		# update the fits header with the given changes
		for n in editList:
			key = n[0]
			data = n[1]
			hdr.set(key, data)

		fitsFile.close() 
		return 0
	except:
		return 1

# Run image display
# input: file directory to watch
# output: subprocess id
def display_images(fileDir):
	# kill process if it's already running
	try:
		if p.poll() is None:
			p.kill()
		return subprocess.Popen([sys.executable, 'image_display.py', fileDir], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	except:
		return subprocess.Popen([sys.executable, 'image_display.py', fileDir], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

# Send an exposure to the camera
# input: expType (dark, bias, object, etc), expTime (in seconds)
# output: image fileName, rData
def expose(expType, expTime):
	data = 'expose '+expType+' '+expTime
	rData = send_data_tcp(9999, data)
	try:
		fileName = rData[rData.find('fsc-'):rData.find('fits')+4]
		return fileName, rData
	except:
		return 'NULL', rData

# Change the filter in the filter wheel
# input: slot number
# output: 
def change_filter(slotNum):
	data = 'set slot='+str(slotNum)
	rData = send_data_tcp(9998, data)
	return rData

# Send a command to the desired stage(s)
# input: command for the stage
# output: rData
def stage_command(data):
	rData = send_data_tcp(9998, data)
	return rData

# check busy/idle status of all hardware
def check_all_status():
	rData = send_data_tcp(9999, 'status')
	rData = rData + send_data_tcp(9998, 'status')
	rData = rData + send_data_tcp(9997, 'status')
	if 'BUSY' in rData:
		return 'BUSY'
	else:
		return 'IDLE'

# Focus Step & Camera Exposure
# input: current x/y coordinates
# output: 
def step_thru_focus(curCoords):
	for z in FOCUS_POS:
		moveCom = 'move z='+z
		# BLOCKING: wait until all hardware is idle before beginning focus sweep
		# !!! CHECK TELESCOPE MOVES HERE FOR CHASING SINGLE TARGET
		while check_all_status() == 'BUSY':
			time.sleep(0.01)	
		
		# move to next focus position
		stage_command(moveCom)

		# BLOCKING: wait until all hardware is idle before beginning exposure
		while check_all_status() == 'BUSY':
			time.sleep(0.01)

		# BLOCKING: Nothing should be happening while an exposure occurs	
		fileName, rData = expose(EXP_TYPE, EXP_TIME)

		# update the fits header with the current position
		resp = edit_fits(fileName, [['X_POSITION', curCoords[0]], 
							['Y_POSITION', curCoords[1]], 
							['Z_POSITION', z]])

	# return to the first focus position
	stage_command('move z='+FOCUS_POS[0])

# Traverse the focal plane positions
# input: polar coordinates list
# ouput: 
def go_to_fp_coords(polar_coords):
	for pos in polar_coords:
		moveCom = 'move r='+pos[0]+' t='+pos[1]

		# BLOCKING: wait until all hardware is idle before moving to next position
		# !!! FOR SINGLE TARGET CHASING: CHECK TELESCOPE MOVES HERE
		while check_all_status() == 'BUSY':
			time.sleep(0.01)	
		
		# move to next focal plane position
		# !!! FOR SINGLE TARGET CHASING: SEND TELESCOPE MOVE COMMAND HERE
		stage_command(moveCom)

		# BLOCKING: wait until all hardware is idle before beginning focus sweep
		while check_all_status() == 'BUSY':
			time.sleep(0.01)

		# BLOCKING: Nothing should be happening while an exposure occurs	
		step_thru_focus(pos)

	# return to the first focus position
	stage_command('move z='+FOCUS_POS[0])	

# Send data over TCP to the desired port
# input: port (cam: 9999, filters: 9999, stages:9997), data to send
# output: returned data
def send_data_tcp(port, data):
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.connect((socket.gethostname(), port))
	s.sendall(bytes(data + '\n','utf-8'))
	rData = ''
	while 'OK' not in rData:
		rData = rData + string(s.recv(1024), 'utf-8')
	s.close()
	return rData

# main script routine that calls the above methods
if __name__ == "__main__":
	print("Starting FSC Control Script...")
	
	# Defaults. This can be changed, or specified at script startup
	FOCUS_POS = ['0', '5', '10', '15', '20']
	EXP_TYPE = 'object'
	EXP_TIME = '1'
	FILE_DIR = os.path.expanduser('~')+'/Pictures/'
	COORD_FILE = 'test_coords.csv'

	userDir = input("Specify image directory or DEF for default: ")

	if 'DEF' in userDir.upper():
		pass
	elif os.path.isdir(userDir):
		FILE_DIR = userDir
		send_data_tcp(9999, 'set fileDir='+FILE_DIR)
	else:
		print("BAD: Invalid directory. Please create directory and try again.")

	userCoords = input("Specify coordinates CSV file or DEF for default: ")

	if 'DEF' in userCoords.upper():
		pass
	elif os.path.isfile(userCoords):
		COORD_FILE = userCoords
	else:
		print("BAD: Invalid coordinates CSV file. Please create file and try again.")

	# get focal plane coordinates
	fp_coords = get_coordinates(COORD_FILE)
	#for each in fp_coords:
	#	print(repr(each[0])+' : '+repr(each[1]))

	# convert the focal plane coordinates to polar coordinates for stages
	polar_coords = cart2polar(fp_coords)
	#for each in polar_coords:
	#	print(repr(each[0])+' : '+repr(each[1]))	

	# open image_display.py as a subprocess
	p = display_images(FILE_DIR)

	# Select the measurement method to use
	methodLoop = True
	while methodLoop:
		method = input("Specify measurement method\n\
			(1) Passive Scanning\n\
			(2) Single Target Chasing\n\
			(3) Multi-Target\n\
			..: ")

		if '1' in method:
			methodLoop = False
			go_to_fp_coords(polar_coords)
			
		elif '2' in method:
			print("Sorry, not yet implemented")
			#methodLoop = False
			
		elif '3' in method:
			methodLoop = False

			multiTargetLoop = True
			while multiTargetLoop:
				go_to_fp_coords(polar_coords)
				tdata = input("Clock rotator and run again (y) or quit (n): ")
				if 'n' in tdata.lower():
					multiTargetLoop = False
				elif 'y' in tdata.lower():
					print("Running again")
				else:
					print("Please type 'y' or 'n'")
			
		else:
			print("BAD: Select 1, 2, or 3")


