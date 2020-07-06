#! /usr/bin/env python3
# stage_server.py
# 7/6/2020
# Aidan Gray
# aidan.gray@idg.jhu.edu
#
# This a server for the 3 Standa stages R, Theta, Z

import asyncio
import threading
import subprocess
import astropy.io import fits
import os
import sys
import time

# create an event log
def log_start():
    scriptDir = os.path.dirname(os.path.abspath(__file__))
    scriptName = os.path.splitext(os.path.basename(__file__))[0]
    log = logging.getLogger('stage_server')
    hdlr = logging.FileHandler(scriptDir+'/'+scriptName+'.log')
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    hdlr.setFormatter(formatter)
    log.addHandler(hdlr)
    log.setLevel(logging.INFO)
    return log

async def main(HOST, PORT):
    print("Opening connection @"+HOST+":"+str(PORT))
    server = await asyncio.start_server(handle_client, HOST, PORT)
    await server.serve_forever()

if __name__ == "__main__":
    fileDir = os.path.expanduser('~')+'/Pictures/'
    log = log_start()

    # setup Remote TCP Server
    HOST, PORT = '', 9996

    try:
        asyncio.run(main(HOST,PORT))
    except KeyboardInterrupt:
        print('...Closing server...')
    except:
        print('Unknown error')
