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

# give script folder location and dataset name
#	check if folder exists
# script goes through all files containing raw-########.fits
# 	open fits as numpy array
#	perform calibrations
#	search for stars
#	create list [r,theta,z,counts,fwhm]
#	add array to dataList
# when folder is complete, write dataList to csv file with given name

#### CCD Parameters for PyGuide init #################
BIAS_LEVEL = 0 # subtraction done using bias image
GAIN = 0.27 # e-/ADU
READ_NOISE = 3.5 # e-
MAX_COUNTS = 17000
######################################################

def write_to_csv(dataFile, dataList):
	with open(..., 'w', newline='') as dataFile:
	     wr = csv.writer(dataFile, quoting=csv.QUOTE_ALL)
	     wr.writerow(dataList)

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

def loop_thru_dir(filePath):
	"""
	Function to loop through given directory and open all raw FITS.

	Input:
	- filePath		Name of the directory containing the raw FITS files
	"""
	directoryList = glob.glob(filePath+'raw-*')
	directoryList.sort(key=lambda f: int(''.join(filter(str.isdigit, f))))

	print("Processing images in: "+filePath)
	print("List of filenames: "+repr(directoryList))
	for fileName in directoryList:
		#print(fileName)
		rawFile = fits.open(fileName)
		rawData = rawFile[0].data
		rawHdr = rawFile[0].header

		exp_check, DecExpTime = pyguide_checking(rawData)


if __name__ == "__main__":
	filePath = sys.argv[1]
	dataFile = sys.argv[2]

	dataList = [] # list to hold target locations

	CCDInfo = PyGuide.CCDInfo(
		bias = BIAS_LEVEL,    # image bias, in ADU
		readNoise = READ_NOISE, # read noise, in e-
		ccdGain = GAIN,  # inverse ccd gain, in e-/ADU
		)

	if filePath[len(filePath)-1] != '/':
		filePath = filePath+'/'

	if not os.path.exists(filePath):
		print("ERROR: That file path does not exist.")
		sys.exit()

	loop_thru_dir(filePath)



