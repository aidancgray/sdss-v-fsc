# SDSS-V Focal Surface Camera (FSC) Control Software

## Components:
- Trius SXVR-H694 CCD Camera
- SX Filter Wheel
- Custom multi-axis stages from Standa Ltd.

## How to run servers:
1. Startup the indiserver with ```indiserver indi_sx_ccd indi_sx_wheel```.
2. Startup the hardware servers with ```python3 [server.py]```.
3. Run the script to display new images with ```python3 file_watcher.py```.

## How to connect to servers:
- Simple testing can be done with ```telnet [IP Address of NUC] [PORT]```.
  - Ports:
    - CCD Camera : 9999
    - Filter Wheel : 9998
    - Stage Controller : 9997  
