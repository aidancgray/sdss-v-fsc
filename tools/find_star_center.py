#!/usr/bin/python3 
# find_star_center.py
# 10/26/2020
# Aidan Gray
# aidan.gray@idg.jhu.edu
#
# This script finds the center of the circle 
# swept by the stars.

import circle_fit as cf
import numpy as np
import os
import sys
import csv

def get_data(fileName):
    """
    Reads in a CSV file containing coordinates, exposure time, and filter slot.
    
    CSV should be of format:
        float,float,float,float,str/int,float,float,float,float,float

    Input:
    - fileName  Filename of the CSV file, ending in .csv

    Output:
    - data      List of coordinates
    """

    # parse the CSV file to create a list of focal plane coordinates
    print("Reading coordinates file...")

    with open(fileName, 'rt', encoding='utf-8-sig') as csvfile:
        next(csvfile)
        # x, y, z, expTime, filter, flux, counts, fwhm, bkgnd, chiSq
        # r, t, z, expTime, filter, flux, counts, fwhm, bkgnd, chiSq
        data = [(float(x), float(y), float(z), float(expTime), str(filt_slot), float(flux), float(counts), float(fwhm), float(bkgnd), float(chiSq)) 
                for x, y, z, expTime, filt_slot, flux, counts, fwhm, bkgnd, chiSq in csv.reader(csvfile, delimiter= ',')]

    return data

if __name__ == "__main__":
    fileName = sys.argv[1]
    
    if fileName[0] == '~':
        fileName = os.path.expanduser('~')+fileName[1:]


    data = get_data(fileName)

    xyData = []
    
    #scrub everything but x & y from data
    for target in data:
        xyData.append(target[:2])

    xc, yc, r, mse = cf.least_squares_circle(xyData)

    print("XCenter (mm from ccd center) = "+repr(xc))
    print("YCenter (mm from ccd center) = "+repr(yc))
    print("Radius (mm) = "+repr(r))
    print("MSE = "+repr(mse))