# SDSS-V Focal Surface Camera (FSC) Control Software

## Components:
- Trius SXVR-H694 CCD Camera
- SX Filter Wheel
- Custom multi-axis stages from Standa Ltd.

## How to run servers:
Run the bash script ```./start_servers.sh```.

Alternatively...
1. Startup the indiserver with ```indiserver indi_sx_ccd indi_sx_wheel```.
2. Startup the hardware servers (as background processes) with ```nohup ./[server.py] &```.
3. Run the script to display new images with ```nohup ./image_display.py &```.

## How to connect to servers directly:
- Simple testing can be done with ```telnet [IP Address of NUC] [PORT]```.
  - Ports:
    - CCD Camera : 9999
    - Filter Wheel : 9998
    - Stage Controller : 9997

## Homing
If you'd like to rehome the stages, connect to the stage controller server using the procedure above.
Then send a ```home``` command and wait for the DONE response.

## How to run the FSC Actor, which controls all servers given a specified list of coordinates:
1. Startup all servers with ```./start_servers.sh```.
2. Run ```./fsc_actor.py```.
3. Follow the on-screen prompts:
   1. Specify the desired image directory (or default).
   2. Specify the measurement method to use.

## Measurement Methods
1. Single Image (sends the camera to desired location and takes one image (or focus sweep)):
   1. Prompts will be given for the following inputs:
      - r position (mm): position along the r-stage axis (0 to 340)
      - t position (deg): theta-stage clocking (-180 to 180)
      - z position (mm): position along the z-stage axis (-12.5 to 12.5)
      - filter slot (1-5): which filter to use in order (ET365LP, u', g', r', i')
      - exposure type (light/dark/bias/flat): the type of exposure
      - exposure time (s): the exposure time in seconds
      - Focus sweep offset (mm): the distance between focus sweep positions
      - Focus sweep #: the number of focus sweep positions in one direction
   2. If no input is provided, defaults will be used. 
      - Position and filter wheel defaults are no change from the current position.
      - Exposure Type default is 'light'. 
      - Exposure Time default is not taking any image.
      - Focus Sweep Offset default is 0.
      - Focus Sweep # default is 0.
2. Passive Scan (sends the camera a list of desired locations given by CSV file and takes one image (or focus sweep)):  
   1. Specify the CSV file containing the list of coordinates (or default for test file).
   2. Provide Focus Sweep settings if desired, default is just single images at each location.
3. Multi-Target:
   1. Same as passive scan, except it repeats the scan, prompting the user to rotate the telescope 
   after each scan.

## Controlling Power to Camera and Stage Controllers
The camera and stage controllers can be power cycled manually using the power.py script or
with the power_on.sh and power_off.sh scripts.

There are two (2) stage controllers: 
  - stageA controller has the Theta Stage
  - stageB controller has the R and Z stages

The power_on.sh will power on all three devices at once, and power_off.sh will power off all
three devices at one.

The individual devices can be powered on/off using the following script and convention:
  ```./power.py [camera/stageA/stageB] [on/off]```