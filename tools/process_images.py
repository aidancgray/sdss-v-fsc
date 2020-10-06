#!/usr/bin/python3
# process_images.py
# 9/22/2020
# Aidan Gray
# aidan.gray@idg.jhu.edu
#
# This is a script to process a batch of images

from astropy.io import fits
from matplotlib import pyplot as plt
import os
import sys
import numpy as np 
import glob
import PyGuide
import csv

#### Switches ########################################
DISPLAY_TARGETS = False
POLAR_OUTPUT = False
######################################################

#### Constants #######################################
ZERO_PIXEL = [1375,1100] # center of 2750x2200
PIXEL_SIZE = 0.00454 # mm
######################################################

#### CCD Parameters for PyGuide init #################
BIAS_LEVEL = 0 # subtraction done using bias image
GAIN = 0.27 # e-/ADU
READ_NOISE = 3.5 # e-
MAX_COUNTS = 17000
######################################################

def write_to_csv(dataFile, dataList):
    print("Writing data to "+dataFile)
    with open(dataFile, 'w', newline='') as dF:
        wr = csv.writer(dF, dialect='excel', delimiter = ',')
        if POLAR_OUTPUT:
            wr.writerow(['r','theta','z','expTime','filter','flux','counts','fwhm','bkgnd','chiSq'])
        else:
            wr.writerow(['x','y','z','expTime','filter','flux','counts','fwhm','bkgnd','chiSq'])

        for imageData in dataList:
            wr.writerows(imageData)
    print("Done")

def cart2polar(fp_coords):
    """
    Takes a list of cartesian coordinates and converts them to polar coordinates.
    This isn't normally used, but if the CSV file must contain cartesian coords,
    this function may be implemented after reading in CSV.

    Input:
    - fp_coords     List of cartesian coordinates

    Output:
    - polar_coords  List of polar coordinates
    """

    polar_coords = []

    for tCoords in fp_coords:
        x = tCoords[0]
        y = tCoords[1]

        r = np.sqrt(x**2+y**2)
        
        # change this around depending on orientation on -scope
        if x == 0:
            t = 90
        elif y == 0:
            t = 0
        else:
            t = np.arctan2(y,x)

        t = np.rad2deg(t)
        polar_coords.append([r,t])

    return polar_coords

def convert_pixel_to_rtheta(xPixel, yPixel, rStage, tStage):
    tTemp = np.deg2rad(-1*tStage) #convert the stage's position(deg) to radians and change sign
    tCos = np.cos(tTemp)
    tSin = np.sin(tTemp)

    xTemp = rStage * np.cos(np.deg2rad(90-tStage))
    yTemp = rStage * np.sin(np.deg2rad(90-tStage))

    transformMatrix = [[tCos,   -tSin,  xTemp],
                       [tSin,   tCos,   yTemp],
                       [0,      0,      1]]    
    
    # convert from Pixel coordinates to mm from ccd center
    xPixCoord = (xPixel - ZERO_PIXEL[0]) * PIXEL_SIZE
    yPixCoord = (yPixel - ZERO_PIXEL[1]) * PIXEL_SIZE

    ccdMatrix = [[xPixCoord],
                 [yPixCoord],
                 [1]]

    trans_cart = np.dot(transformMatrix, ccdMatrix)

    if POLAR_OUTPUT:
        polar_coords = cart2polar([[trans_cart[0][0],trans_cart[1][0]]])
        rVal = polar_coords[0][0]
        thetaVal = polar_coords[0][1]
        return rVal,thetaVal
    else:
        xTmp = trans_cart[0][0]
        yTmp = trans_cart[1][0]
        return xTmp, yTmp


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

    ### highlight detections
    ### size of green circle scales with total counts
    ### bigger circles for brigher stars
    if DISPLAY_TARGETS:
        plt.clf()
        plt.imshow(imgArray, cmap="gray", vmin=200, vmax=MAX_COUNTS) # vmin/vmax help with contrast
        plt.ion()
        plt.show()
        for centroid in centroidData:
            xyCtr = centroid.xyCtr + np.array([-0.5, -0.5]) # offset by half a pixel to match imshow with 0,0 at pixel center rather than edge
            counts = centroid.counts
            plt.scatter(xyCtr[0], xyCtr[1], s=counts/MAX_COUNTS, marker="o", edgecolors="lime", facecolors="none")
        plt.gca().invert_yaxis()
        plt.draw()
        plt.pause(0.1)

    # Successful exposure, return True. The False is thrown away
    return goodTargets

def single_image(fileName):
    """
    Function to process a single raw FITS.

    Input:
    - fileName      Name of absolute path to the raw FITS file

    Output:
    - dataList      List of coordinate points & data
    """
    rawFile = fits.open(fileName)
    rawData = rawFile[0].data
    rawHdr = rawFile[0].header

    dataList = []

    rStage = rawHdr['R_POS']
    tStage = rawHdr['T_POS']
    zTarg = rawHdr['Z_POS']
    #filtTarg = rawHdr['FILTER']
    filtTarg = '1'
    expTime = rawHdr['EXPTIME']
    
    goodTargets = pyguide_checking(rawData)

    if len(goodTargets) > 0:
        #dataList.append([fileName])
        for target in goodTargets:
            xPixel = target[0].xyCtr[0]
            yPixel = target[0].xyCtr[1]

            #convert xPixel,yPixel to r,t
            rTarg, thetaTarg = convert_pixel_to_rtheta(xPixel, yPixel, rStage, tStage)

            fluxTarg = target[0].counts
            countsTarg = target[1].ampl
            fwhmTarg = target[1].fwhm
            bkgndTarg = target[1].bkgnd
            chiSqTarg = target[1].chiSq

            targetData = [rTarg, thetaTarg, zTarg, expTime, filtTarg, fluxTarg, countsTarg, fwhmTarg, bkgndTarg, chiSqTarg]
            dataList.append(targetData)

    return dataList

def loop_thru_dir(filePath):
    """
    Function to loop through given directory and open all raw FITS.

    Input:
    - filePath      Name of the directory containing the raw FITS files

    Output:
    - dataList      List of coordinate points & data
    """
    dataList = []
    directoryList = glob.glob(filePath+'raw-*')
    directoryList.sort(key=lambda f: int(''.join(filter(str.isdigit, f))))

    print("Processing images in: "+filePath)
    #print("List of filenames: "+repr(directoryList))
    
    for fileName in directoryList:
        dataListTemp = single_image(fileName)
        dataList.append(dataListTemp)

    return dataList

if __name__ == "__main__":
    filePath = sys.argv[1]
    dataFile = sys.argv[2]

    CCDInfo = PyGuide.CCDInfo(
        bias = BIAS_LEVEL,    # image bias, in ADU
        readNoise = READ_NOISE, # read noise, in e-
        ccdGain = GAIN,  # inverse ccd gain, in e-/ADU
        )

    if filePath[len(filePath)-5:] == '.fits':
        dataListTemp = single_image(filePath)
        dataList = []
        dataList.append(dataListTemp)
        write_to_csv(dataFile, dataList)

    else:
        if filePath[len(filePath)-1] != '/':
            filePath = filePath+'/'

        if not os.path.exists(filePath):
            print("ERROR: That file path does not exist.")
            sys.exit()
        else:
            dataList = loop_thru_dir(filePath)
            print(dataList)
            write_to_csv(dataFile, dataList)

    input("Press ENTER to exit")
