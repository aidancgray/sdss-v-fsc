#!/usr/bin/python3
# process_images.py
# 9/22/2020
# Aidan Gray
# aidan.gray@idg.jhu.edu
#
# This is a script to process a batch of images

from astropy.io import fits
import os
import sys
import numpy as np 

# give script folder location and dataset name
#	check if folder exists
# script goes through all files containing raw-########.fits
# 	open fits as numpy array
#	perform calibrations
#	search for stars
#	create list [r,theta,z,counts,fwhm]
#	add array to dataList
# when folder is complete, write dataList to csv file with given name

def write_to_csv(dataFile, dataList)
	with open(..., 'w', newline='') as dataFile:
	     wr = csv.writer(dataFile, quoting=csv.QUOTE_ALL)
	     wr.writerow(dataList)

if __name__ == "__main__":
	filePath = sys.argv[1]
	dataFile = sys.argv[2]

	dataList = [] # list to hold target locations

	if filePath[len(filePath)-1] != '/':
		filePath = filePath+'/'

	if not os.path.exists(filePath):
		print("ERROR: That file path does not exist.")
		sys.exit()


