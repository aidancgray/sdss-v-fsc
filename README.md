# SDSS-V Focal Surface Camera (FSC) Control Software

## Components:
- Trius SXVR-H694 CCD Camera
- SX Filter Wheel
- Custom multi-axis stages from Standa Ltd.

## How to run servers:
1. Startup the indiserver with ```indiserver indi_sx_ccd indi_sx_wheel```.
2. Startup the hardware servers (as background processes) with ```nohup ./[server.py] &```.
3. Run the script to display new images with ```nohup ./image_display.py &```.

Alternatively, run the bash script ```./fsc_servers.sh```.

## How to connect to servers directly:
- Simple testing can be done with ```telnet [IP Address of NUC] [PORT]```.
  - Ports:
    - CCD Camera : 9999
    - Filter Wheel : 9998
    - Stage Controller : 9997

## How to run the FSC Actor, which controls all servers given a specified list of coordinates:
1. Startup all servers with ```./fsc_servers.sh```.
2. Run ```./fsc_actor.py```.
3. Follow the on-screen prompts:
  3.1 Specify the desired image directory (or default).
  3.2 Specify the CSV file containing the list of coordinates (or default for test file).
  3.3 Specify the measurement method to use.

