#!/bin/bash
# This is a bash script to run the indiservers (for the camera/filter wheel),
# the camera control server, filter wheel server, stage server, and
# image display script.

indiserver indi_sx_ccd indi_sx_wheel &
nohup.out ./stage_server.py &
nohup.out ./trius_cam_server.py &
nohup.out ./sx_filter_server.py &
nohup.out ./image_display.py &
