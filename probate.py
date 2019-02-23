"""                                produce

This program is to calibrate the BSR AltAcc and save results to a file
"""

import math
import serial
import argparse
import datetime
import logging
from prodata import *

VERSION = "1.25c"

PORT = "/dev/ttyUSB0"
BAUD = 9600
EchoIsOff = 0  # for error recovery */
Verbose = True

ALTACC_LINE_MAX = 8
ALTACC_TALK_MAX = 256
ALTACC_BUFF_MAX = ALTACC_LINE_MAX * ALTACC_TALK_MAX + 2

N = []
Sum = []
SumSquares = []

TICK_CHAR = '.'
ALTACC_DUMP_LEN = 8196


def parse_commandline():
    global args, parser

    parser = argparse.ArgumentParser(prog='probate', description=f'AltAcc calibration program (v{VERSION})')
    parser.add_argument('-p', '--port', help='serial/com port')
    parser.add_argument('-n', '--nit', default=NIT_NAME, help='override init filename')
    parser.add_argument('-o', '--out', help='output calibration filename')

    parser.add_argument('-q', '--quiet', action='store_true', help="be quiet about it")
    parser.add_argument('--version', action='version', version=f'v{VERSION}')
    parser.add_argument('calfile', default=None, nargs='?', action='store', help='calibration filename')

    args = parser.parse_args()


def set_port(port):
    com = serial.Serial(port=port, baudrate=BAUD)
    if not com:
        print(f"could not open {port}")
        sys.exit(1)

    return com


"""
u16 LoadAltAccAry ( Ary )
/* ------------------------------------------------------------------------ */
    AltAccTalk    * Ary ;
/* ------------------------------------------------------------------------ */
{

#define  PARSE_MAX      3

   u16            i = 0 ;                    /* Array Cursor */
   u16            j = 0 ;                    /* Line Cursor  */

   int k = 0 ;

   char * BuffPtr = AltAccBuff ;
   char * TokPtr ;

   u16            NumArg ;
   char         * ParsePtr [ PARSE_MAX ] ;

   char  TalkCmd [] = "/T" ;

   write ( ComPort, TalkCmd, 2 ) ;
   tcflush ( ComPort, TCIOFLUSH );

   /* we are gonna load up a 256 * 8 + 2 char array here ... */

   while ( i < ALTACC_BUFF_MAX )
   {
      j = read ( ComPort, BuffPtr, 8 ) ;          /* AAA PPP\n == 8 chars */

      i += j ;
      k += j ;
      BuffPtr += j ;

      if ( k >= 48 )
      {
         putc ( TICK_CHAR, stderr );
         k = 0 ;
      }
   }

   if ( i > 2048 )
      i = 2048 ;

   tcflush ( ComPort, TCIOFLUSH );

   AltAccBuff [ i ] = '\0' ;
   BuffPtr = AltAccBuff ;

   i = 1 ;                     /* Number of good pairs in AltAccData[0].A */
   j = 0 ;                     /* Number of bad  pairs in AltAccData[0].P */

   TokPtr = strtok ( BuffPtr, "\n" ) ;    /* let the c-lib extract a line */

   while (( TokPtr != NULL ) && ( i < 256 ))
   {
      NumArg = Parse ( TokPtr, PARSE_MAX, ParsePtr ) ;

      if ( NumArg == 2 )
      {
         AltAccAry [i].A = (byte) atoi ( ParsePtr [0] );
         AltAccAry [i].P = (byte) atoi ( ParsePtr [1] );
      }
      else
         j ++ ;

      TokPtr = strtok ( NULL, "\n" );

      i ++ ;
   }

   AltAccAry [0].A = (byte) ( -- i ) ;
   AltAccAry [0].P = (byte) j ;

   fprintf ( stdout, "\n" ) ;

   return ( i + 1 ) ;
}
"""


def altacc_talk(com):
    Samples = namedtuple('Samples', "acc pre")
    return [Samples._make((125, 236))] * 256


def get_data(com, what):
    while True:
        # TODO read the data
        data = altacc_talk(com)

        print(f"read {len(data)} lines from the AltAcc on {com.name}")

        s = input("accept AltAcc data? ( y-yes | n-no | x-exit ) ")

        if s in ('x', 'X'):
            sys.exit(3)

        if s not in ('n', 'N'):  # i.e.default answer == 'y'
            break

    count = data[0].a  # Why?
    sum_ = 0.0
    squares = 0.0

    for i in range(count):
        dtemp = data[i][what]
        sum_ += dtemp
        squares += dtemp * dtemp

    Data = namedtuple('Data', "n, sum_ squares")
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
    print(cal)

    # go read the .nit file -- (v2) -- Moved here so CalFile, et al are set
    nit = read_nitfile(args.nit)
    print(nit)

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

    print("Set the AltAcc Upside Down to Measure -1 G")
    input("then press enter when ready ( x to quit ) ")
    if s.strip() in ('x', 'X'):
        sys.exit(3)

    # get_load (0, 1)
    neg = get_data(com, "acc")

    cal['AvgNegG'] = neg.sum_ / neg.n
    cal['StDNegG'] = math.sqrt((neg.squares - (neg.sum_ * neg.sum_ / neg.n)) / (neg.n - 1))

    print("Set the AltAcc Flat to Measure Zero G")
    input("then press enter when ready ( x to quit ) ")
    if s.strip() in ('x', 'X'):
        sys.exit(3)

    # GetaLoadaData(0, 2);
    zero = get_data(com, "acc")

    cal['AvgZeroG'] = zero.sum_ / zero.n
    cal['StDZeroG'] = math.sqrt((zero.squares - (zero.sum_ * zero.sum_ / zero.n)) / (zero.n - 1))

    cal['FiDNegG'] = cal['AvgZeroG'] - cal['AvgNegG']

    print("Stand the AltAcc Right side Up to Measure Plus One G")
    input("then press enter when ready ( x to quit ) ")

    # GetaLoadaData(0, 3);
    one = get_data(com, "acc")

    cal['AvgOneoG'] = one.sum_ / one.n
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

    cal['CCoff'] = 1.0 - (std_y_x / std_y)

    # Test for proper operation and a good unit
    if cal['FiDNegG'] <= 0.0 or cal['FiDZeroG'] <= 0.0:
        print("\n*** Warning *** Average Values indicate calibration error")
        s = input("                or a defective unit.  Save data? ( y | n ) ")
        if s in ('y', 'Y'):
            sys.exit(3)

    header = "#\n# AltAcc Calibration Data %s\n#\n" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    # dump_calfile(cal_filename, cal, header)

    if not args.quiet:
        dump_calfile(None, cal, header)


main()
