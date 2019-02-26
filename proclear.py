"""                                produce

This program is to calibrate the BSR AltAcc and save results to a file
"""

import time
import argparse
import logging
from prodata import *

VERSION = "1.25c"
PORT = "/dev/ttyUSB0"
BAUD = 9600
TICK_CHAR = '.'
CLEAR_TIME = 55

Data = namedtuple('Data', "n, sum_ squares")
Samples = namedtuple('Samples', "acc pre")


def parse_commandline():
    global args, parser

    parser = argparse.ArgumentParser(prog='probate', description=f'Clear AltAcc flight data EEProm (v{VERSION})')
    parser.add_argument('-p', '--port', help='serial/com port')
    parser.add_argument('-n', '--nit', default=NIT_NAME, help='override init filename')
    parser.add_argument('-q', '--quiet', action='store_true', help="be quiet about it")
    parser.add_argument('-y', '--yes', action='store_true', help="assume yes to all prompts")
    parser.add_argument('--version', action='version', version=f'v{VERSION}')

    args = parser.parse_args()


def set_port(port):
    if port == 'MOCK':
        class SerMock:
            name = port

            def write(self, data):
                pass

            def read(self, count):
                return b'125 236\n'

        return SerMock()
    else:
        import serial
        com = serial.Serial(port=port, baudrate=BAUD)
        if not com:
            print(f"could not open {port}")
            sys.exit(1)

        return com


def main():

    parse_commandline()
    print()
    print(args)

    # go read the .nit file -- (v2) -- Moved here so CalFile, et al are set
    nit = read_nitfile(args.nit)
    print(nit)

    if not args.yes:
        s = input("\nDo you really mean to clear all data from the AltAcc? (y|n) ")
        if s.strip().lower() != 'y':
            sys.exit(3)

    # Open the com port
    port = args.port or nit['port'] or PORT
    com = set_port(port)

    if not args.quiet:
       print("clearing the AltAcc on ", port)
       print("|                                                     |")

    # discard any noise on the line
    com.reset_input_buffer()
    com.reset_output_buffer()

    com.write(b'/CC')

    # Wait...
    for _ in range(CLEAR_TIME):
        if not args.quiet:
            print(TICK_CHAR, end='')

        time.sleep(1)

    if not args.quiet:
        print()


main()