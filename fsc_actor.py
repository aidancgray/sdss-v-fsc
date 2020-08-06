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
import asyncio
import logging
import os
import sys
import time
import math
import threading

# Coordinate file read-in
def get_coordinates(fileName):
	# parse the CSV file to create a list of focal plane coordinates
	print("Reading coordinates file...")

# Message sending method

# Convert focal plane coordinates to stage coordinates

# Reset stages

# Run image display

# step through focus

# send exposure to camera

if __name__ == "__main__":
	print("Starting FSC Control Script...")
	# get focal plane coordinates
	# open image_display.py as a subprocess
	