#!/bin/bash
# This is a bash script to run the indiservers (for the camera/filter wheel),
# the camera control server, filter wheel server, stage server, and
# image display script.

./kill_servers.sh
sleep 1
echo "...starting new servers"
indiserver indi_sx_ccd indi_sx_wheel &
sleep 2
nohup ./stage_server.py >/dev/null 2>&1 &
nohup ./trius_cam_server.py >/dev/null 2>&1 &
nohup ./sx_filter_server.py >/dev/null 2>&1 &
sleep 3
echo "~servers are ready~"
