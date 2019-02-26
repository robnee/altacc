"""                                produce

This program is to calibrate the BSR AltAcc and save results to a file
"""

import math
import argparse
import logging
from prodata import *

VERSION = "1.25c"
PORT = "/dev/ttyUSB0"
BAUD = 9600
TICK_CHAR = '.'

Data = namedtuple('Data', "n, sum_ squares")
Samples = namedtuple('Samples', "acc pre")


def parse_commandline():
    global args, parser

    parser = argparse.ArgumentParser(prog='probate', description=f'AltAcc calibration program (v{VERSION})')
    parser.add_argument('-p', '--port', help='serial/com port')
    parser.add_argument('-n', '--nit', default=NIT_NAME, help='override init filename')
    parser.add_argument('-o', '--out', help='output calibration filename')

    parser.add_argument('-q', '--quiet', action='store_true', help="be quiet about it")
    parser.add_argument('--version', action='version', version=f'v{VERSION}')
    parser.add_argument('calfile', default=None, nargs='?', action='store',
                        help='output calibration filename (same as --out)')

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
            print("could not open", port)
            sys.exit(1)

        return com


def get_samples(com):
    # discard any noise on the line
    com.reset_input_buffer()
    com.reset_output_buffer()

    com.write(b'/T')

    samples = []
    for i in range(256):
        line = com.read(8)
        if len(line) < 8:
            break

        # Due to the LED sharing the serial line check for and discard noise
        if b'\x00' in line:
            # attempt to sync with the end of line
            while True:
                c = com.read(1)
                if c == b'\n':
                    break
            continue

        a, p = [int(x) for x in line.strip().split()]
        
        samples.append(Samples._make((a, p)))
        
        if i % 8 == 0:
            print(TICK_CHAR, end='')
            sys.stdout.flush()
    print()

    return samples


def get_data(com, what):
    while True:
        data = get_samples(com)

        print(f"received {len(data)} of 256 samples from the AltAcc on {com.name}")

        s = input("accept AltAcc data? ( y-yes | n-no | x-exit ) ")

        if s in ('x', 'X'):
            sys.exit(3)

        if s not in ('n', 'N'):  # i.e.default answer == 'y'
            break

    count = len(data)
    sum_ = 0.0
    squares = 0.0

    for i in range(count):
        dtemp = data[i].pre if what == 'pre' else data[i].acc
        sum_ += dtemp
        squares += dtemp * dtemp

    return Data._make((count, sum_, squares))


def main():

    parse_commandline()
    print()
    print(args)

    cal_filename = args.calfile or args.out
    if not cal_filename:
        parser.print_help()
        sys.exit(1)

    # Create a skeleton cal dict
    cal = {k: None for k in cal_info.keys()}

    # go read the .nit file -- (v2) -- Moved here so CalFile, et al are set
    nit = read_nitfile(args.nit)
    print(nit)

    # Open the com port
    port = args.port or nit['port'] or PORT
    com = set_port(port)

    print(f"gathering calibration data from the AltAcc on {port}")

    s = input("\nEnter the absolute Barometric Pressure ( x to exit ) ")
    if s.strip() in ('x', 'X'):
        sys.exit(3)

    cal['ActBP'] = float(s)

    s = input("\nEnter the actual altitude ( x to exit ) ")
    if s.strip() in ('x', 'X'):
        sys.exit(3)

    cal['ActAlt'] = float(s)

    # get_load (1, 0)
    pre = get_data(com, "pre")

    cal['AvgBP'] = pre.sum_ / pre.n
    cal['StDBP'] = math.sqrt((pre.squares - (pre.sum_ * pre.sum_ / pre.n)) / (pre.n - 1))

    # Work out offset
    cal['OffBP'] = calc_offset(cal['ActBP'], cal['AvgBP'])

    dump_calfile(None, cal)

    # Accelerometer calibration
    print("\nSet the AltAcc Upside Down to Measure -1 G")
    input("then press enter when ready ( x to quit ) ")
    if s.strip() in ('x', 'X'):
        sys.exit(3)

    # get_load (0, 1)
    neg = get_data(com, "acc")

    cal['AvgNegG'] = neg.sum_ / neg.n
    cal['StDNegG'] = math.sqrt((neg.squares - (neg.sum_ * neg.sum_ / neg.n)) / (neg.n - 1))

    print("\nSet the AltAcc Flat to Measure Zero G")
    input("then press enter when ready ( x to quit ) ")
    if s.strip() in ('x', 'X'):
        sys.exit(3)

    # GetaLoadaData(0, 2);
    zero = get_data(com, "acc")

    cal['AvgZeroG'] = zero.sum_ / zero.n
    cal['StDZeroG'] = math.sqrt((zero.squares - (zero.sum_ * zero.sum_ / zero.n)) / (zero.n - 1))

    cal['FiDNegG'] = cal['AvgZeroG'] - cal['AvgNegG']

    print("\nSet the AltAcc Right side Up to Measure Plus One G")
    input("then press enter when ready ( x to quit ) ")

    # GetaLoadaData(0, 3);
    one = get_data(com, "acc")

    cal['AvgOneG'] = one.sum_ / one.n
    cal['StDOneG'] = math.sqrt((one.squares - (one.sum_ * one.sum_ / one.n)) / (one.n - 1))

    cal['FiDZeroG'] = cal['AvgOneG'] - cal['AvgZeroG']

    # calculate slope.  Least Squares is simplified with X = { -1,0,+1 }
    cal['Slope'] = (one.sum_ - neg.sum_) / (one.n + neg.n)

    # Y-Intercept is the Avg G Value:
    cal['YZero'] = (one.sum_ + zero.sum_ + neg.sum_) / (one.n + zero.n + neg.n)

    # Correlation Coefficient = 1 - std^2_y_x / std_y^2

    # Estimate Output at G = -1, do sum of diff squared
    dtemp = cal['AvgNegG'] - (-1 * cal['Slope'] + cal['YZero'])
    std_y_x = neg.sum_ * neg.sum_ * dtemp * dtemp

    # Estimate Output at G = 0
    dtemp = cal['AvgZeroG'] - cal['YZero']
    std_y_x += (zero.sum_ * zero.sum_ * dtemp * dtemp)

    # Estimate Output at G = 1
    dtemp = cal['AvgOneG'] - (cal['Slope'] + cal['YZero'])
    std_y_x = one.sum_ * one.sum_ * dtemp * dtemp

    dtemp = one.sum_ + zero.sum_ + neg.sum_
    n = one.n + zero.n + neg.n

    std_y_x /= n - 2

    std_y = ((one.squares + zero.squares + neg.squares) - ((dtemp * dtemp) / n)) / (n - 1)
    if std_y > 0:
        cal['CCoff'] = 1.0 - (std_y_x / std_y)

    # Test for proper operation and a good unit
    if cal['FiDNegG'] <= 0.0 or cal['FiDZeroG'] <= 0.0:
        print("\n*** Warning *** Average Values indicate calibration error")
        s = input("                or a defective unit.  Save data? ( y | n ) ")
        if s in ('y', 'Y'):
            sys.exit(3)
 
    dump_calfile(cal_filename, cal)

    if not args.quiet:
        dump_calfile(None, cal)


if "win" not in sys.platform:
    # For Pythonsita bug in debug
    sys.argv = ['probate.py', 'pb.cal']

main()
