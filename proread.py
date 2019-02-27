"""                                produce

This program is to download the BSR AltAcc flight data to a file
"""

import time
import argparse
import logging
from prodata import *

VERSION = "1.25c"
PORT = "/dev/ttyUSB0"
BAUD = 9600
TICK_CHAR = '.'


def parse_commandline():
    global args, parser

    parser = argparse.ArgumentParser(prog='probate', description=f'Download AltAcc flight data to a file (v{VERSION})')
    parser.add_argument('-p', '--port', help='serial/com port')
    parser.add_argument('-n', '--nit', default=NIT_NAME, help='override init filename')
    parser.add_argument('-o', '--out', help='output flight data filename')

    parser.add_argument('-q', '--quiet', action='store_true', help="be quiet about it")
    parser.add_argument('--version', action='version', version=f'v{VERSION}')
    parser.add_argument('datafile', default=None, nargs='?', action='store',
                        help='output flight data filename (same as --out)')

    args = parser.parse_args()


def set_port(port):
    if port == 'MOCK':
        class SerMock:
            name = port

            def write(self, data):
                pass

            def read(self, _):
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
    if not args.quiet:
        print("reading", args.nit)
    nit = read_nitfile(args.nit)

    data_filename = args.datafile or args.out
    data_len = altacc_format.size

    # Open the com port
    port = args.port or nit['port'] or PORT
    com = set_port(port)

    if not args.quiet:
        print(f"downloading flight data from the AltAcc on {port}")

    # discard any noise on the line
    com.reset_input_buffer()
    com.reset_output_buffer()

    com.write(b'/R')

    chunk_size = 64
    bytes_read = 0
    chunks = []
    while bytes_read < data_len:
        chunk = com.read(min(data_len - bytes_read, chunk_size))
        chunks.append(chunk)
        bytes_read += len(chunk)

        if not args.quiet:
            print("\r%5d of %d bytes" % (bytes_read, data_len), end='')

    data = b''.join(chunks)

    if not args.quiet:
        print()

    fields = altacc_format.unpack(data)
    flight = AltAccDump._make(fields)

    checksum = sum(data[:-4]) % 0x10000

    if not args.quiet:
        print("AltAcc  CheckSum: %u = %02x %02x" % (flight.CkSum, data[-4], data[-3]))
        print("Proread CheckSum: %u = %02x %02x" % (checksum, checksum & 0x00ff, (checksum & 0xff00) >> 8))

    if len(data) != data_len:
        print("*** Warning ***  File Size error reading AltAcc !")
    if flight.CkSum != checksum:
        print("*** Warning ***  Check Sum error reading AltAcc !")

    try:
        with open(data_filename, "wb") as fp:
            fp.write(data)
        if not args.quiet:
            print(f"wrote {len(data)} bytes to {data_filename}")
    except TypeError:
        print("*** Warning ***  Bad filename specified.  Data not saved !")
    except IOError:
        print("*** Warning ***  IO error.  Data not saved !")


main()
