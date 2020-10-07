#!/usr/bin/python3
# plot_data.py
# 10/6/2020
# Aidan Gray
# aidan.gray@idg.jhu.edu
#
# This script reads in the provided CSV file and plots the 3D data

from matplotlib import pyplot as plt
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

def create_3d_plot(dataList):
    """
    Uses the supplied data to create a 3D plot.

    Input:
    - data      List of coordinates

    Output:
    """
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    for point in dataList:
        xs = point[0]
        ys = point[1]
        zs = point[2]
        ax.scatter(xs, ys, zs, c='b', marker='o')

    ax.set_xlabel('X Label')
    ax.set_ylabel('Y Label')
    ax.set_zlabel('Z Label')
    ax.set_xlim(-340,340)
    ax.set_ylim(-340,340)
    ax.set_zlim(-12.5,12.5)
    plt.show()

if __name__ == "__main__":
    fileName = sys.argv[1]
    data = get_data(fileName)
    print("Number of data points = "+repr(len(data)))
    create_3d_plot(data)
    