#!/bin/bash
# This is a bash script to kill all the servers relating to the FSC control
# system. It will kill: indiserver, image_display.py, trius_cam_server.py,
# sx_filter_server.py, and stage_server.py.

for pid in $(pgrep -f indiserver); do kill $pid; done
for pid in $(pgrep -f image_display.py); do kill $pid; done
for pid in $(pgrep -f trius_cam_server.py); do kill $pid; done
for pid in $(pgrep -f sx_filter_server.py); do kill $pid; done
for pid in $(pgrep -f stage_server.py); do kill $pid; done

			       
