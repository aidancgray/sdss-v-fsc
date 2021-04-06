#!/bin/bash
# This is a bash script to run the indiservers (for the camera/filter wheel),
# the camera control server, filter wheel server, stage server, and
# image display script.

echo "Before starting the servers..."
/gitrepos/sdss-v-fsc/kill_servers.sh
sleep 1
echo "...starting new servers"
nohup indiserver indi_sx_ccd indi_sx_wheel >/dev/null 2>&1 &
sleep 2
nohup /gitrepos/sdss-v-fsc/servers/stage_server.py >/dev/null 2>&1 &
nohup /gitrepos/sdss-v-fsc/servers/trius_cam_server.py >/dev/null 2>&1 &
nohup /gitrepos/sdss-v-fsc/servers/sx_filter_server.py >/dev/null 2>&1 &
sleep 3
echo "~ servers are ready ~"
