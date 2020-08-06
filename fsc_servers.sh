#!/bin/bash
# This is a bash script to run the indiservers (for the camera/filter wheel),
# the camera control server, filter wheel server, stage server, and
# image display script.

indiserver indi_sx_ccd indi_sx_wheel &
nohup ./stage_server.py &
nohup ./trius_cam_server.py &
nohup ./sx_filter_server.py &
