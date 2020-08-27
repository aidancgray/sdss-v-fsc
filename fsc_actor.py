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
import PyGuide

############# CCD Parameters #########################
# for PyGuide initialization
BIAS_LEVEL = 1100 # ADU NEED TO UPDATE
GAIN = 0.27 # e-/ADU
READ_NOISE = 3.5 # e-
######################################################

########### Encoder<->mm/deg/mm Conversion ###########
R_CONST = 0.00125
T_CONST = float(25.9/3600)
Z_CONST = 0.0000625
######################################################


# Stop the running hardware and close the program
def cancel():
	print("Cancelling routine, stopping all hardware")
	send_data_tcp(9999, 'stop')
	send_data_tcp(9997, 'stop')
	print('Done')

# Coordinate file read-in
# input: name of the coordinate file
# output: list of r,t,z coordinates
def get_coordinates(fileName):
	# parse the CSV file to create a list of focal plane coordinates
	print("Reading coordinates file...")

	with open(fileName, 'rt', encoding='utf-8-sig') as csvfile:
	    data = [(float(r), float(t), float(z)) for r, t, z in csv.reader(csvfile, delimiter= ',')]

	return data

# Convert focal plane coordinates to stage coordinates
# input: list of x,y coordinates
# output: list of r,theta coordinates
def cart2polar(fp_coords):
	polar_coords = []

	for tCoords in fp_coords:
		x = tCoords[0]
		y = tCoords[1]
		z = tCoords[2]
		
		r = np.sqrt(x**2+y**2)
		
		# change this around depending on orientation on -scope
		if x == 0:
			t = 90
		elif y == 0:
			t = 0
		else:
			t = np.arctan2(y,x)

		polar_coords.append([r,t,z])

	return polar_coords

# edit fits header
# input: name of fits file, list of keywords and their data
def edit_fits(fileName, editList):
	try:
		fitsFile = fits.open(FILE_DIR+fileName, 'update')
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
	if expType.lower() == 'bias':
		data = 'expose '+expType
	else:
		data = 'expose '+expType+' '+expTime

	rData = send_data_tcp(9999, data)
	
	if 'BAD' in rData:
		return 'NULL', rData
	else:
		try:
			fileName = rData[rData.find('raw-'):rData.find('fits')+4]
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
	rData = send_data_tcp(9997, data)
	return rData

# check busy/idle status of all hardware
def check_all_status():
	rData = send_data_tcp(9999, 'status')
	rData = rData + send_data_tcp(9998, 'status')
	rData = rData + send_data_tcp(9997, 'status')
	#print(rData)
	if 'BUSY' in rData:
		return 'BUSY'
	else:
		return 'IDLE'

# get the position from the encoder counts for all motors
def get_position_enc():
	rData = send_data_tcp(9997, 'status')

	# extract the encoder coders
	r_pos = rData[rData.find('r_e: ')+5:rData.find('\n\u03B8_e')]
	t_pos = rData[rData.find('\u03B8_e: ')+5:rData.find('\nz_e')]
	z_pos = rData[rData.find('z_e: ')+5:rData.find('\nSpeeds')]

	# convert to mm/deg/mm
	r_pos = float(r_pos)*R_CONST
	t_pos = float(t_pos)*T_CONST
	z_pos = float(z_pos)*Z_CONST

	return [r_pos, t_pos, z_pos]

# PyGuide Star Checking
# input: processed image array
# output: OK (no need for re-exposure), BAD (re-expose)
def pyguide_checking(img_array):
	# search image for stars
	centroidData, imageStats = PyGuide.findStars(
		img_array,
		mask = None,
		satMask = None,
		ccdInfo = CCDInfo
		)

	# analyze stars here
	# determine if more exposures are necessary

	return True

# Data reduction
# input: filename of the raw fits image
# output: bool (False: take another exposure), filename (new, processed file)
def data_reduction(fileName):
	try:
		fitsFile = fits.open(FILE_DIR+fileName)
		data = fitsFile[0].data
		hdr = fitsFile[0].header

		# process the data here

		prc_data = data
		exp_check = pyguide_checking(prc_data)
		
		if exp_check:
			# save the processed image as a new FITS file
			# with the processed data and the same header
			prc_fileName = 'prc'+fileName[3:]
			fits.writeto(FILE_DIR+prc_fileName, prc_data, hdr)

		fitsFile.close()
		return exp_check, prc_fileName
	
	except:
		return False, ''

# Single Image Script
# input: r position, theta position, z position, filter slot #, exposure type, exposure time
def single_image(r_pos, t_pos, z_pos, filt_slot, expType, expTime):
	moveCom = 'move r='+r_pos+' t='+t_pos+' z='+z_pos

	# BLOCKING: wait until all hardware is idle before moving to next position
	while check_all_status() == 'BUSY':
		time.sleep(0.01)	

	stage_command(moveCom)
	change_filter(filt_slot)
	time.sleep(0.1)

	# BLOCKING: wait until all hardware is idle before starting exposure routine
	while check_all_status() == 'BUSY':
		time.sleep(0.01)	

	exp_check = False
	while not exp_check:
		# BLOCKING: Nothing should be happening while an exposure occurs
		print('STARTING EXPOSURE...')	
		fileName, rData = expose(expType, expTime)
		print('...DONE EXPOSURE')

		if 'BAD' in rData:
			exp_check = True
		else:
			# get the encoder counts to obtain precise location
			enc_positions = get_position_enc()

			# update the fits header with the current position
			resp = edit_fits(fileName, [['R_POS', enc_positions[0]], ['T_POS', enc_positions[1]], ['Z_POS', enc_positions[2]]])

			# perform data reduction, search for stars, determine if exposure change is necessary
			exp_check, prc_fileName = data_reduction(fileName)
			exp_check = True

# Focus Step & Camera Exposure
# input: current x/y coordinates
# output: 
def step_thru_focus(curCoords):
	# positive offsets
	for z in range(0,FOCUS_SWEEP[0]+1):
		moveCom = 'offset z='+str(z*FOCUS_SWEEP[1])
		
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

	# return to the first focus position
	stage_command('move z='+curCoords[2])

	# negative offsets
	for z in range(1,FOCUS_SWEEP[0]+1):
		moveCom = 'offset z=-'+str(z*FOCUS_SWEEP[1])
		
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

# Traverse the focal plane positions
# input: polar coordinates list
# ouput: 
def go_to_fp_coords(polar_coords, filt_slot, expType):
	for pos in polar_coords:

		# BLOCKING: wait until all hardware is idle before moving to next position
		# !!! FOR SINGLE TARGET CHASING: CHECK TELESCOPE MOVES HERE
		while check_all_status() == 'BUSY':
			time.sleep(0.01)	
		
		# move to next focal plane position
		# !!! FOR SINGLE TARGET CHASING: SEND TELESCOPE MOVE COMMAND HERE
		single_image(pos[0], pos[1], pos[2], filt_slot, expType, pos[3])

		# BLOCKING: wait until all hardware is idle before beginning focus sweep
		while check_all_status() == 'BUSY':
			time.sleep(0.01)

		# BLOCKING: Nothing should be happening while an exposure occurs	
		step_thru_focus(pos)

# Send data over TCP to the desired port
# input: port (cam: 9999, filters: 9999, stages:9997), data to send
# output: returned data
def send_data_tcp(port, data):
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.connect((socket.gethostname(), port))
	s.sendall(bytes(data + '\n','utf-8'))
	rData = ''
	while 'OK' not in rData and 'BAD' not in rData:
		rData = rData + str(s.recv(1024), 'utf-8')
	s.close()
	return rData

# main script routine that calls the above methods
if __name__ == "__main__":
	try:
		print("Starting FSC Control Script...")

		# Defaults. This can be changed, or specified at script startup
		FOCUS_SWEEP = [5, 5] # [# of offset, distance b/w offsets]
		EXP_TYPE = 'object'
		EXP_TIME = '1'
		FILE_DIR = os.path.expanduser('~')+'/Pictures/'
		COORD_FILE = 'test_coords.csv'

		CCDInfo = PyGuide.CCDInfo(
    		bias = BIAS_LEVEL,    # image bias, in ADU
    		readNoise = READ_NOISE, # read noise, in e-
 	   		ccdGain = GAIN,  # inverse ccd gain, in e-/ADU
			)

		methodLoop = True
		
		userDir = input("Specify image directory or DEF for default: ")

		if 'DEF' in userDir.upper() or '' == userDir:
			pass
		elif os.path.isdir(userDir):
			FILE_DIR = userDir
			send_data_tcp(9999, 'set fileDir='+FILE_DIR)
		else:
			methodLoop = False
			print("BAD: Invalid directory. Please create directory and try again.")

		# open image_display.py as a subprocess
		p = display_images(FILE_DIR)

		# Select the measurement method to use
		while methodLoop:
			method = input("Specify measurement method\n(0) Single Image\n(1) Passive Scanning\n(2) Single Target Chasing\n(3) Multi-Target\n..: ")

			if '0' in method:
				singleImageLoop = True
				while singleImageLoop:
					r_pos = input("r position (mm): ")
					t_pos = input("t position (deg): ")
					z_pos = input("z position (mm): ")
					filt_slot = input("filter slot (1-5): ")
					expType = input("exposure type (light/dark/bias/flat): ")
					
					if expType.lower() == 'bias':
						expTime = 0
					else:
						expTime = input("Enter exposure time (s): ")

					single_image(r_pos, t_pos, z_pos, filt_slot, expType, expTime)

					tdata = input("Again (enter key) or quit (q)? ")

					if 'Q' in tdata.upper():
						singleImageLoop = False
						methodLoop = False

			elif '1' in method or '2' in method or '3' in method:
				
				userCoords = input("Specify coordinates CSV file or DEF for default: ")

				if 'DEF' in userCoords.upper() or '' == userCoords:
					print('derp')
					pass
				elif os.path.isfile(userCoords):
					COORD_FILE = userCoords
				else:
					print("BAD: Invalid coordinates CSV file. Please create file and try again.")
					continue

				filt_slot = input("filter slot (1-5): ")
				expType = input("exposure type (light/dark/bias/flat): ")
				
				if expType.lower() == 'bias':
					expTime = 0
				else:
					expTime = input("Enter exposure time (s): ")

				# get focal plane coordinates
				fp_coords = get_coordinates(COORD_FILE)

				# convert the focal plane coordinates to polar coordinates for stages
				#polar_coords = cart2polar(fp_coords)
				polar_coords = fp_coords

				if '1' in method:
					methodLoop = False
					go_to_fp_coords(polar_coords, filt_slot, expType)
					
				elif '2' in method:
					print("Not yet implemented")
					#methodLoop = False
					
				elif '3' in method:
					methodLoop = False

					multiTargetLoop = True
					while multiTargetLoop:
						go_to_fp_coords(polar_coords, filt_slot, expType)
						tdata = input("Clock rotator and run again (y) or quit (n): ")
						if 'n' in tdata.lower():
							multiTargetLoop = False
						elif 'y' in tdata.lower():
							print("Running again")
						else:
							print("Please type 'y' or 'n'")
				
			else:
				print("BAD: Select 1, 2, or 3")
		
		cancel()

	except KeyboardInterrupt:
		cancel()

