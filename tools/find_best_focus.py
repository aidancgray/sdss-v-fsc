#!/usr/bin/python3 
# find_best_focus.py
# 10/26/2020
# Aidan Gray
# aidan.gray@idg.jhu.edu
#
# This script finds the center of the circle 
# swept by the stars.

from matplotlib import pyplot as plt
import numpy as np
import sys
import csv
import os

def create_2d_plot(dataList, fit_x, fit_y, fit_x_min, fit_y_min):
    """
    Uses the supplied data to create a 2D plot.

    Input: 
    - data          List of coordinates
    - fit_x         polynomial fit x values
    - fit_y         polynomial fit y values
    - fit_x_min     x value of fit minimum
    - fit_y_min     y value of fit minimum

    Output:
    """
    fig = plt.figure()
    ax = fig.add_subplot(111)

    for point in dataList:
        zs = point[2]
        fwhms = point[7]
        plt_0 = ax.scatter(zs, fwhms, c='b', marker='o')

    plt_0.set_label('data')
    plt_fit = plt.plot(fit_x,fit_y, label='polyfit')
    fit_min_label = 'min='+repr(fit_x_min)
    plt_min = ax.scatter(fit_x_min, fit_y_min, c='r', marker='x', label=fit_min_label)

    plt.title('fwhm vs z-stage (mm)')
    ax.set_xlabel('z-stage (mm)')
    ax.set_ylabel('fwhm (pixels)')
    ax.grid(True, which='both', axis='both')
    ax.legend(loc=2, fontsize='small')

    pltDataName = os.path.basename(os.path.normpath(fileName))
    plt.savefig('best_focus_'+pltDataName[:-4]+'.png')
    plt.show()

    return plt

def fit_poly(data):
    z_vals = []
    fwhm_vals = []

    for target in data:
        z_vals.append(target[2])
        fwhm_vals.append(target[7])

    max_z_val = max(z_vals)
    min_z_val = min(z_vals)

    coeffs = np.polyfit(z_vals, fwhm_vals, 2)
    poly = np.poly1d(coeffs)
    fit_x = np.linspace(min_z_val,max_z_val)
    fit_y = poly(fit_x)
    fit_x_min = -1 * coeffs[1] / (2 * coeffs[0])    
    fit_y_min = poly(fit_x_min)

    return poly, fit_x, fit_y, fit_x_min, fit_y_min

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
    #print("Reading coordinates file...")

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

    poly, fit_x, fit_y, fit_x_min, fit_y_min = fit_poly(data)

    print('min z = '+repr(fit_x_min))

    plt = create_2d_plot(data, fit_x, fit_y, fit_x_min, fit_y_min)

