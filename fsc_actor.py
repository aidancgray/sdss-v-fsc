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
from datetime import datetime
from matplotlib import pyplot as plt
from photutils.datasets import make_random_gaussians_table, make_gaussian_sources_image
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
import random

#### Process Raw Images ##############################
PROCESS_RAW = True
BIAS_FILE = 'bias.fits'
FAKE_STARS = True
EXP_TIME_FACTOR = 0.5 # Must be >0 and <1
MAX_EXP_COUNT = 3
######################################################

#### CCD Parameters for PyGuide init #################
BIAS_LEVEL = 0 # subtraction done using bias image
GAIN = 0.27 # e-/ADU
READ_NOISE = 3.5 # e-
MAX_COUNTS = 17000
######################################################

#### Encoder<->mm/deg/mm Conversion ##################
R_CONST = 0.00125
T_CONST = float(25.9/3600)
Z_CONST = 0.0000625
######################################################

#### Simulated Star Parameters #######################
N_STARS = 10
SKY_LEVEL = 20 # brightness of night sky
######################################################

def show_image(imgData):
    plt.imshow(imgData, cmap="gray")

def cancel():
    """
    Sends stop commands to the CCD and Stages
    """

    print("Stopping routine and all hardware")
    send_data_tcp(9999, 'stop')
    send_data_tcp(9997, 'stop')
    print('Done')

def get_coordinates(fileName):
    """
    Reads in a CSV file containing coordinates, exposure time, and filter slot.
    
    CSV should be of format:
        float,float,float,float,int

    Input:
    - fileName  Filename of the CSV file, ending in .csv

    Output:
    - data      List of coordinates+exposureTime+filterSlot [[r,t,z,expTime,filt_slot] , ... , [r,t,z,expTime,filt_slot]]
    """

    # parse the CSV file to create a list of focal plane coordinates
    print("Reading coordinates file...")

    with open(fileName, 'rt', encoding='utf-8-sig') as csvfile:
        data = [(float(r), float(t), float(z), float(expTime), str(filt_slot)) for r, t, z, expTime, filt_slot in csv.reader(csvfile, delimiter= ',')]

    return data

def cart2polar(fp_coords):
    """
    Takes a list of cartesian coordinates and converts them to polar coordinates.
    This isn't normally used, but if the CSV file must contain cartesian coords,
    this function may be implemented after reading in CSV.

    Input:
    - fp_coords     List of cartesian coordinates (+ exposure time + filter slot)

    Output:
    - polar_coords  List of polar coordinates (+ exposure time + filter slot)
    """

    polar_coords = []

    for tCoords in fp_coords:
        x = tCoords[0]
        y = tCoords[1]
        z = tCoords[2]
        expTime = tCoords[3]
        filt_slot = tCoords[4]

        r = np.sqrt(x**2+y**2)
        
        # change this around depending on orientation on -scope
        if x == 0:
            t = 90
        elif y == 0:
            t = 0
        else:
            t = np.arctan2(y,x)

        polar_coords.append([r,t,z,expTime,filt_slot])

    return polar_coords

def edit_fits(fileName, editList):
    """
    Edits a FITS file header with whatever keywords|data given.

    Input:
    - fileName  Name of the FITS file
    - editList  A list of keywords and their data

    Output:
    - 0         Success
    - 1         Fail
    """

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

def display_images(fileDir):
    """
    Runs the image_display.py script on the given directory.
    This script watches for FITS files starting with 'raw-'
    and displays them in a DS9 window.

    Input:
    - fileDir   Directory on THIS MACHINE to watch.

    Output:
    - subprocess object
    """
    # kill process if it's already running
    try:
        if p.poll() is None:
            p.kill()
        print("Image_Display script watching dir: "+fileDir)
        return subprocess.Popen([sys.executable, 'tools/image_display.py', fileDir], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except:
        print("Image_Display script watching dir: "+fileDir)
        return subprocess.Popen([sys.executable, 'tools/image_display.py', fileDir], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

def expose(expType, expTime):
    """
    Sends exposure command to the CCD server.

    Input:
    - expType   type of the exposure: light/dark/bias/flat
    - expTime   decimal in seconds

    Output:
    - fileName  name of the FITS file for the exposure when it's completed
    - rData     returned data containing success/failure information
    """

    if expType.lower() == 'bias':
        data = 'expose '+str(expType)
    else:
        data = 'expose '+str(expType)+' '+str(expTime)

    rData = send_data_tcp(9999, data)
    
    if 'BAD' in rData:
        return 'NULL', rData
    else:
        try:
            fileName = rData[rData.find('raw-'):rData.find('fits')+4]
            return fileName, rData
        except:
            return 'NULL', rData

def change_filter(slotNum):
    """
    Sends a command to move the filter wheel to the desired slot
    
    Input:
    - slotNum   The slot number to move to

    Output:
    - rData     returned data containing success/failure information
    """

    data = 'set slot='+str(slotNum)
    rData = send_data_tcp(9998, data)
    return rData

def stage_command(data):
    """
    Sends a command to move the stage server
    
    Input:
    - data  The data to send to the stage server

    Output:
    - rData returned data containing success/failure information
    """
    rData = send_data_tcp(9997, data)
    return rData

def check_all_status():
    """
    Returns BUSY if ANY hardware is busy, IDLE otherwise
    """
    rData = send_data_tcp(9999, 'status')
    rData = rData + send_data_tcp(9998, 'status')
    rData = rData + send_data_tcp(9997, 'status')
    #print(rData)
    if 'BUSY' in rData:
        return 'BUSY'
    else:
        #print(rData)
        return 'IDLE'

def get_position_enc():
    """
    Returns the current positions of each motor in encoder counts
    """
    rData = send_data_tcp(9997, 'status')

    # extract the encoder coders
    r_pos = rData[rData.find('r_e = ')+6:rData.find('\n\u03B8_e')]
    t_pos = rData[rData.find('\u03B8_e = ')+6:rData.find('\nz_e')]
    z_pos = rData[rData.find('z_e = ')+6:rData.find('\nr_s')]

    # convert to mm/deg/mm
    r_pos = float(r_pos)*R_CONST
    t_pos = float(t_pos)*T_CONST
    z_pos = float(z_pos)*Z_CONST

    return [r_pos, t_pos, z_pos]

def check_CCD_temp():
    """
    Returns the current temperature of the CCD
    """
    rData = send_data_tcp(9999, 'status')
    ccdTemp = float(rData[rData.find('CCD TEMP = ')+11:rData.find('C\nLAST')])
    return ccdTemp

def add_fake_stars(image, expTime, number=N_STARS, max_counts=MAX_COUNTS, sky_counts=SKY_LEVEL, gain=GAIN):
    """
    Adds fake stars to a dark image from the CCD. Used for testing while not on-telescope

    Input:
    - image         The numpy array from the CCD.
    - number        The number of stars to add
    - max_counts    The max counts for the stars to have
    - sky_counts    Counts to use for adding sky background
    - gain          CCD gain
    - expTime       The exposure time of the raw image, to scale star brightness

    Output:
    - fakeData      A numpy array containing the fake star image
    """
    # create sky background
    sky_im = np.random.poisson(sky_counts * gain, size=image.shape) / gain

    #flux_range = [max_counts/10, max_counts] # this the range for brightness, flux or counts
    flux_range = [float(expTime) * (max_counts/10), float(expTime) * (max_counts/1)]

    y_max, x_max = image.shape
    xmean_range = [0.1 * x_max, 0.9 * x_max] # this is where on the chip they land
    ymean_range = [0.1 * y_max, 0.9 * y_max]
    xstddev_range = [4,4] # this is a proxy for gaussian width, FWHM, or focus I think.
    ystddev_range = [4,4]
    params = dict([('amplitude', flux_range),
                  ('x_mean', xmean_range),
                  ('y_mean', ymean_range),
                  ('x_stddev', xstddev_range),
                  ('y_stddev', ystddev_range),
                  ('theta', [0, 2*np.pi])])

    randInt = random.randint(11111,99999)

    sources = make_random_gaussians_table(number, params,
                                          random_state=randInt)
    star_im = make_gaussian_sources_image(image.shape, sources)

    fakeData = image + sky_im + star_im

    return fakeData

def pyguide_checking(imgArray):
    """
    Uses PyGuide to find stars, get counts, and determine if new exposure time is necessary.

    Input:
    - imgArray  numpy array from the CCD

    Output:
    - True if exposure was good, False if bad
    - True if exposure time should be decreased, False if increased
    """
    # search image for stars
    centroidData, imageStats = PyGuide.findStars(
        imgArray,
        mask = None,
        satMask = None,
        ccdInfo = CCDInfo
        )

    # keep track of targets
    goodTargets = []
    lowTargets = 0
    highTargets = 0

    print("these are the %i stars pyguide found in descending order of brightness:"%len(centroidData))
    for centroid in centroidData:
        # for each star, measure its shape
        shapeData = PyGuide.starShape(
            np.asarray(imgArray, dtype="float32"), # had to explicitly cast for some reason
            mask = None,
            xyCtr = centroid.xyCtr,
            rad = centroid.rad
        )
        if not shapeData.isOK:
            print("starShape failed: %s" % (shapeData.msgStr,))
        else:
            print("xyCenter=[%.2f, %.2f] CCD Pixel Counts=%.1f, FWHM=%.1f, BKGND=%.1f, chiSq=%.2f" %\
                (centroid.xyCtr[0], centroid.xyCtr[1], shapeData.ampl,shapeData.fwhm, shapeData.bkgnd, shapeData.chiSq))
            if shapeData.ampl < 0.2*MAX_COUNTS:
                lowTargets+=1
            elif shapeData.ampl > 0.9*MAX_COUNTS:
                highTargets+=1
            else:
                goodTargets.append([centroid,shapeData])
    print()

    print(str(len(goodTargets))+" targets are in the linear (20-90%) range --- "+str(lowTargets)+" low targets --- "+str(highTargets)+" high targets")
    
    # return False if there are no good stars found
    if len(goodTargets) == 0:
        if lowTargets < highTargets:
            return False, True
        else:
            return False, False

    ### highlight detections
    ### size of green circle scales with total counts
    ### bigger circles for brigher stars
    plt.clf()
    plt.imshow(imgArray, cmap="gray", vmin=200, vmax=MAX_COUNTS) # vmin/vmax help with contrast
    plt.ion()
    plt.show()
    for centroid in centroidData:
        xyCtr = centroid.xyCtr + np.array([-0.5, -0.5]) # offset by half a pixel to match imshow with 0,0 at pixel center rather than edge
        counts = centroid.counts
        plt.scatter(xyCtr[0], xyCtr[1], s=counts/MAX_COUNTS, marker="o", edgecolors="lime", facecolors="none")
    plt.draw()
    plt.pause(0.1)

    # Successful exposure, return True. The False is thrown away
    return True, False

def data_reduction(fileName, expTime):
    """
    Data processing function. Subtracts bias from raw and saves as processed (if good).

    Input:
    - fileName      Name of the FITS file for the raw image
    - expTime       The image's exposure time

    Output:
    - exp_check     True: no more exposure necessary. False: take another.
    - prcFileName   name of the processed FITS file.
    """

    try:
        # raw file
        rawFile = fits.open(FILE_DIR+fileName)
        rawData = rawFile[0].data
        rawHdr = rawFile[0].header
        
        if FAKE_STARS:
            synthetic_image = np.zeros([2200, 2750])
            fakeData = add_fake_stars(synthetic_image, expTime, number=N_STARS, max_counts=MAX_COUNTS, sky_counts=SKY_LEVEL, gain=GAIN)
            rawData = rawData + fakeData
        
        # bias file
        biasFile = fits.open(BIAS_FILE)
        biasData = biasFile[0].data
        
        #prcData = np.subtract(rawData,biasData)
        prcData = rawData

        exp_check, DecExpTime = pyguide_checking(prcData)
        newExpTime = 0
        prcFileName = ''

        if exp_check:
            # save the processed image as a new FITS file
            # with the processed data and the same header
            prcFileName = 'prc'+fileName[3:]
            fits.writeto(FILE_DIR+prcFileName, prcData, rawHdr)
        else:
            print("Exposure unsuccessful, altering expTime and trying again")
            if DecExpTime:
                newExpTime = (1-EXP_TIME_FACTOR)*float(expTime)
            else:
                newExpTime = (1+EXP_TIME_FACTOR)*float(expTime)

        rawFile.close()
        biasFile.close()

        return exp_check, prcFileName, newExpTime
    
    except:
        print("ERR: "+repr(sys.exc_info()[0])+" "+repr(sys.exc_info()[1])+" "+repr(sys.exc_info()[2]))
        
        return True, 'DATA REDUCTION FAILED', 0

def single_image(coords, expType):
    """
    Script to take a single image. Moves to the desired coordinates (r,t,z) and desired
    filter slot, then takes an exposure. If the PROCESS_RAW global var is True, the raw
    image will be processed and checked if there are sufficient counts.

    Input:
    - coords    list containing the image coordinates, exposure time, and filter slot
    - expType   light/dark/bias/flat
    """
    r_pos = coords[0]
    t_pos = coords[1]
    z_pos = coords[2]
    expTime = coords[3]
    filt_slot = coords[4]

    moveCom = 'move r='+str(r_pos)+' t='+str(t_pos)+' z='+str(z_pos)

    # BLOCKING: wait until all hardware is idle before moving to next position
    while check_all_status() == 'BUSY':
        time.sleep(0.1)	

    rDataF = change_filter(filt_slot)
    rDataS = stage_command(moveCom)

    # BLOCKING: wait until all hardware is idle before starting exposure routine
    while check_all_status() == 'BUSY':
        time.sleep(0.1)	

    if 'BAD' not in rDataF and 'BAD' not in rDataS:
        exp_check = False
    else:
        exp_check = True
        print(rDataF+rDataS)

    tmpExpTime = expTime
    expCount = 0
    while not exp_check and expCount <= MAX_EXP_COUNT:
        # ensure the CCD hasn't entered an error state
        ccdTemp = check_CCD_temp()
        if ccdTemp < -40 or ccdTemp > 30:
            sys.exit("Error with CCD, as noted by incorrect CCD Temp. Please disconnect and reconnect CCD power & data.")

        # BLOCKING: Nothing should be happening while an exposure occurs
        print('STARTING EXPOSURE...')	
        fileName, rDataC = expose(expType, tmpExpTime)
        print('...DONE EXPOSURE: '+fileName)

        if 'BAD' in rDataC:
            exp_check = True
            print(rDataC)
        else:
            # get the encoder counts to obtain precise location
            enc_positions = get_position_enc()

            # update the fits header with the current position
            resp = edit_fits(fileName, [['R_POS', enc_positions[0]], ['T_POS', enc_positions[1]], ['Z_POS', enc_positions[2]]])

            # perform data reduction, search for stars, determine if exposure change is necessary
            if PROCESS_RAW:
                print("Processing raw image. This may take a moment...")
                exp_check, prc_fileName, tmpExpTime = data_reduction(fileName, tmpExpTime)
                print("...done processing")
            else:
                exp_check = True

            expCount+=1
            if not exp_check and expCount <= MAX_EXP_COUNT:
                print("Retrying exposure at "+str(tmpExpTime)+"s")
                

def step_thru_focus(coords, expType, focusOffset, focusNum):
    """
    Performs a focus sweep, offsetting by the given distance, for the given number of times
    IN ONE DIRECTION. Moves in the positive direction first, then repeats in the negative 
    direction from original focus position.

    Input:
    - coords        list containing the image coordinates, exposure time, and filter slot
    - expType       light/dark/bias/flat
    - focusOffset   distance to offset each focus shift
    - focusNum      the number of offsets (in one direction)
    """
    r_pos = coords[0]
    t_pos = coords[1]
    z_pos = coords[2]
    expTime = coords[3]
    filt_slot = coords[4]

    # positive offsets
    for n in range(1,int(focusNum)+1):
        z_off_pos = float(z_pos) + (float(focusOffset) * float(n))
        single_image([r_pos, t_pos, z_off_pos, expTime, filt_slot], expType)

    # negative offsets
    for n in range(1,int(focusNum)+1):
        z_off_pos = float(z_pos) - (float(focusOffset) * float(n))
        single_image([r_pos, t_pos, z_off_pos, expTime, filt_slot], expType)		

def go_to_fp_coords(polar_coords, expType, focusOffset, focusNum):
    """
    Sends the camera to each of the positions given by the CSV coordinates file. Then 
    performs the focus sweep.

    Input:
    - polar_coords  list containing the image coordinates, exposure time, and filter slot
    - expType       light/dark/bias/flat
    - focusOffset   distance to offset each focus shift
    - focusNum      the number of offsets (in one direction)
    """
    for pos in polar_coords:
        # BLOCKING: wait until all hardware is idle before moving to next position
        # !!! FOR SINGLE TARGET CHASING: CHECK TELESCOPE MOVES HERE
        while check_all_status() == 'BUSY':
            time.sleep(0.1)	
        
        # move to next focal plane position
        # !!! FOR SINGLE TARGET CHASING: SEND TELESCOPE MOVE COMMAND HERE
        single_image(pos, expType)

        # BLOCKING: wait until all hardware is idle before beginning focus sweep
        while check_all_status() == 'BUSY':
            time.sleep(0.1)
    
        step_thru_focus(pos, expType, focusOffset, focusNum)

def send_data_tcp(port, data):
    """
    Send data over TCP Socket to the desired server

    Input:
    - port  This determine which server to send to (9999: CCD, 9998: Filter Wheel, 9997: Stages)
    - data  The data to send to the server

    Output:
    - rData The response from the server
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((socket.gethostname(), port))
    s.sendall(bytes(data + '\n','utf-8'))
    rData = ''
    while 'OK' not in rData and 'BAD' not in rData:
        rData = rData + str(s.recv(1024), 'utf-8')
    s.close()
    return rData

if __name__ == "__main__":
    try:
        print("Starting FSC Control Script...")

        # Defaults. This can be changed, or specified at script startup
        FILE_DIR = os.path.expanduser('~')+'/Pictures/'+datetime.now().strftime("%m-%d-%Y")+'/'
        COORD_FILE = 'test_coords.csv'

        CCDInfo = PyGuide.CCDInfo(
            bias = BIAS_LEVEL,    # image bias, in ADU
            readNoise = READ_NOISE, # read noise, in e-
                ccdGain = GAIN,  # inverse ccd gain, in e-/ADU
            )

        methodLoop = True

        print("Checking connection to hardware...")
        try:
            send_data_tcp(9999, 'status')
            send_data_tcp(9998, 'status')
            send_data_tcp(9997, 'status')
        except ConnectionRefusedError as err:
            print("...FAILED. Check hardware servers are running.")
            sys.exit(err)

        print("...SUCCESS.")

        ccdTemp = check_CCD_temp()
        if ccdTemp < -40 or ccdTemp > 30:
            sys.exit("Error with CCD, as noted by incorrect CCD Temp. Please disconnect and reconnect CCD power & data.")
        #print("CCD Temp is: "+str(check_CCD_temp()))

        userDir = input("Specify image directory or DEF for default: ")

        if 'DEF' in userDir.upper() or '' == userDir:
            send_data_tcp(9999, 'set fileDir='+FILE_DIR)
        elif os.path.isdir(userDir):
            if userDir[len(userDir)-1] != '/':
                userDir = userDir+'/'
            FILE_DIR = userDir
        else:
            print("Directory does not exist. An attempt will be made to create it.")
            if userDir[len(userDir)-1] != '/':
                userDir = userDir+'/'
            FILE_DIR = userDir
            send_data_tcp(9999, 'set fileDir='+FILE_DIR)

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

                    # open image_display.py as a subprocess
                    #p = display_images(FILE_DIR)   
                    
                    single_image([r_pos, t_pos, z_pos, expTime, filt_slot], expType)

                    tdata = input("Again (enter key) or quit (q)? ")

                    if 'Q' in tdata.upper():
                        singleImageLoop = False
                        methodLoop = False

            elif '1' in method or '2' in method or '3' in method:
                
                userCoords = input("Specify coordinates CSV file or DEF for default: ")

                if 'DEF' in userCoords.upper() or '' == userCoords:
                    pass
                elif os.path.isfile(userCoords):
                    COORD_FILE = userCoords
                else:
                    print("BAD: Invalid coordinates CSV file. Please create file and try again.")
                    continue

                expType = input("exposure type (light/dark/bias/flat): ")

                focusOffset = input("Focus sweep offset (mm): ")
                focusNum = input("Focus sweep #: ")

                try:
                    float(focusOffset)
                    int(focusNum)
                except ValueError:
                    print("BAD: Offset must be float and sweep # must be int")
                    continue

                # get focal plane coordinates
                fp_coords = get_coordinates(COORD_FILE)

                # convert the focal plane coordinates to polar coordinates for stages
                #polar_coords = cart2polar(fp_coords)
                polar_coords = fp_coords

                if '1' in method:
                    methodLoop = False

                    # open image_display.py as a subprocess
                    #p = display_images(FILE_DIR)

                    go_to_fp_coords(polar_coords, expType, focusOffset, focusNum)
                    
                elif '2' in method:
                    print("Not yet implemented")
                    #methodLoop = False
                    
                    # open image_display.py as a subprocess
                    #p = display_images(FILE_DIR)
                    
                elif '3' in method:
                    methodLoop = False

                    # open image_display.py as a subprocess
                    #p = display_images(FILE_DIR)

                    multiTargetLoop = True
                    while multiTargetLoop:
                        go_to_fp_coords(polar_coords, expType, focusOffset, focusNum)
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

