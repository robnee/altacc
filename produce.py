"""                                produce

This Is a Python Program For Converting binary data from the BSR AltAcc
to ASCII Data with nice little Headers.

This is the structure of the AltAcc data file ( 8196 bytes )

byte  Version   ;                /* Starting at v2-125, we have V! */
byte  kjh_toy [3] ;              /* play data for 'special models' */
byte  DrogueSec ;                /* Time of Drogue Deploy, Seconds */
byte  Drogue16s ;                /* Time of Drogue Deploy, 1/16sec */
byte  DrogueAcc ;                /* Accel at Drogue Deploy         */
byte  DroguePre ;                /* Pressure at Drogue Deploy      */
byte  MainSec ;                  /* Time of Main Deploy, Seconds   */
byte  Main16s ;                  /* Time of Main Deploy, 1/16sec   */
byte  MainAcc ;                  /* Accel at Main Deploy           */
byte  MainPre ;                  /* Pressure at Main Deploy        */
byte  BSFlags ;                  /* AltAcc Launch Status Flags     */
byte  BasePre ;                  /* Pressure Reading, Win [Ptr]    */
byte  LastPre ;                  /* Pressure Reading, Win [Ptr+3]  */
byte  WinPtr  ;                  /* Pointer to Beginning of Win [] */
byte  Window [4] ;               /* 4-byte circular buffer, Accel  */
byte  AvgAcc ;                   /* Average of Window [] Data      */
byte  NitAcc [4];                /* T={1,2,3,4} / 16 (Liftoff Acc) */
byte  SumLob ;                   /* Lo Byte of Sum of NitAcc []    */
byte  SumHib ;                   /* Hi Byte of Sum of NitAcc []    */
byte  foo2 [5] ;                 /* Reserved                       */
AP    Data [ NUM_PAIRS ] ;       /* This is the 8160 Byte Flight   */
byte  CkSumLob ;                 /* AltAcc's Version of check sum  */
byte  CkSumHib ;                 /* Hi Byte of same                */
byte  O ;                        /* AltAcc sez 'O'                 */
byte  K ;                        /* AltAcc sez 'K'                 */


  Rev  Who  Date        Description
=====  ===  ==========  ========================================
1.25c  kjh  09-28-1998  Eliminated stderr output for DOS version
"""

import sys
import struct
import argparse
import logging
from math import log, exp
from collections import namedtuple

VERSION = "1.25c"

Header = (
    "      Time  Accel  Press    Sum  Accelerat   Velocity   Altitude  PressAlt\n"
    "       sec  units  units  units   ft/sec^2     ft/sec       feet      feet\n"
    " =========  =====  =====  =====  =========  =========  =========  ========\n"
)

ExHead = (
    '''"Time","Accel","Press","Vel","Accel","Velocity","IAlt","PAlt",'''
    '''"sec","GHarrys","Orvilles","Verns","ft/sec^2","ft/sec","feet","feet"'''
)

flight_modes = (
    "Main Only Mode",
    "Drogue to Main Mode",
    "Drogue to Main Mode -- !! No Drogue Fire !!"
)

UNITS = [
    "sec",
    "in",
    "ft",
    "cm",
    "m",
    "km",
    "oz",
    "lb",
    "gm",
    "kg",
    "inhg",
    "mmhg",
    "torr",
    "kpa",
]

# default units
U = {
    "alt": 2,
    "mass": 7,
    "time": 0,
    "pressure": 10
}

# PALT_GAIN_4100 = 0.1113501786   # this is the 4100 xducer
# PALT_OFFSET_4100 = 3.418657     # these are average lines
# PALT_GAIN_5100 = 0.1354567027   # this is the 5100 xducer
# PALT_OFFSET_5100 = 1.475092     # this is 40 mV / KPa
# PALT_GAIN_4100   0.1760937134  /* this is the 4100 xducer
# PALT_OFFSET_4100 -12.341491    /* this is 52 mV / KPA !!!
# PALT_GAIN_5100   0.1447552322  /* this is the 5100 xducer
# PALT_OFFSET_5100 -0.478599     /* this is from test1

XducerParam = namedtuple('XducerParam', 'desc gain offset')
xducer_info = {
    "MPX4100": XducerParam._make(("Motorola MPX5100", 0.1113501786, 3.418657)),
    "MPX5100": XducerParam._make(("Motorola MPX4100", 0.1354567027, 1.475092))
}

# AltAcc init/config file ( be careful with spelling! )

nit_info = {
    "port": "where do you plug in the AltAcc ( oride: -p COM#",
    "time": "time units preference ( not implemented yet )",
    "alt": "altitude preference",
    "vel": "velocity preference",
    "acc": "acceleration preference",
    "press": "pressure units preference",
    "cal": "calibration file path",
    "xducer": "Motorola pressure transducer type"
}

cal_info = {
    "ActAlt": ("actalt", "Actual Altitude"),
    "ActBP": ("actbp", "Actual Barometric Pressure"),
    "AvgBP": ("avgbp", "AltAcc Pressure Avg"),
    "StDBP": ("stdbp", "AltAcc Pressure Std Dev"),
    "OffBP": ("offbp", "Barometric Pressure Offset"),
    "GainBP": ("gainbp", "Barometric Pressure Gain Factor"),
    "AvgNegG": ("avg-1g", "Minus One Gee Avg"),
    "StdNegG": ("std-1g", "Minus One Gee Std Dev"),
    "FiDNegG": ("fid(0)", "Finite Difference on [-1, 0]"),
    "AvgZeroG": ("avg0g", "Zero Gee Avg"),
    "StDZeroG": ("std0g", "Zero Gee Std Dev"),
    "FiDZeroG": ("fid(1)", "Finite Difference on [0, 1]"),
    "AvgOneG": ("avg+1g", "Plus One Gee Avg"),
    "StDOneG": ("std+1g", "Plus One Gee Std Dev"),
    "Slope": ("do/dg", "Slope of AltAcc Output per G"),
    "YZero": ("y[0]", "Y-Intercept of AltAcc Output"),
    "CCoff": ("ccoff", "Correlation Coefficient"),
    "XDucer": ("xducer", "Motorola Pressure XDucer Type"),
}

NIT_NAME = "prodata.nit"
CAL_NAME = "prodata.cal"
OUT_NAME = "prodata.dat"

PALT_IDEAL_5100 = 210    # what _my_ test unit sez
LAUNCH_THOLD = 16.0      # about 1/4 sec of 1.33 G
TICK_CHAR = '.'
COMMENT_CHAR = '#'
DROGUE_TO_MAIN = 1
NUM_PAIRS = 4080
DEFAULT_GAIN = 2.5500    # +/- 50 G over 255 units
GEE = 32.17              # you know, Newton and all
dT = 0.0625              # AltAcc dt 1/16sec
TWO_dT = 0.1250          # 2 * dT for 2-step derivs


def parse_commandline():
    global args, parser

    parser = argparse.ArgumentParser(prog='produce', description=f'AltAcc data reduction program (v{VERSION})')
    parser.add_argument('-c', '--cal', default=CAL_NAME, help='calibration (probate) filename')
    parser.add_argument('-n', '--nit', default=NIT_NAME, help='override init filename')
    parser.add_argument('-f', '--data', help='AltAcc data (proread) filename')
    parser.add_argument('-o', '--out', help='output results filename')

    parser.add_argument('-z', '--zor', action='store', help='one gee override value (overrides data file one gee)')
    parser.add_argument('-g', '--gain', action='store', help='gain override (overrides cal file gain value)')
    parser.add_argument('-F', '--fmt', action='store', default='A', help='output file format (C)SV (A)SCII')
    parser.add_argument('-m', '--nomsl', action='store_true', help='do not show MSL pressure alt along with AGL')
    parser.add_argument('-a', '--all', action='store_true', help='force all the data out, even after touchdown')
    parser.add_argument('-q', '--quiet', action='store_true', help="be quiet about it")
    parser.add_argument('--version', action='version', version=f'v{VERSION}')
    parser.add_argument('datafile', default=None, nargs='?', action='store', help='data filename')

    args = parser.parse_args()


altacc_format = struct.Struct("<B3x4B4BBBBB4sB4sBB5x8160sH2s")
AltAccDump = namedtuple('AltAccDump',
                        "Version DrogueSec Drogue16s DrogueAcc DroguePre "
                        "MainSec Main16s MainAcc MainPre BSFlags BasePre "
                        "LastPre WinPtr Window AvgAcc NitAcc SumLob SumHib Data CkSum OK")


def read_datafile(path: str):
    """ read a flight data file and unpack it """

    with open(path, 'rb') as fp:
        data = fp.read()

    if len(data) != altacc_format.size:
        logging.warning(f"invalid data file length, {len(data)} bytes!")

    fields = altacc_format.unpack(data)
    flight = AltAccDump._make(fields)

    checksum = sum(data[:-4]) % 0x10000
    if flight.CkSum != checksum:
        raise ValueError(f"checksum mismatch datafile={flight.CkSum} computed:{checksum}")

    return flight


def read_nitfile(path: str):
    """ read and parse the "nit" (config) file and return as a dict """

    logging.info(f"opening nit file {path}")

    nit = {}
    with open(path) as fp:
        for line in fp.readlines():
            if '#' in line:
                line, comment = line.split('#', maxsplit=1)
            if line:
                tag, val, *junk = line.strip().split()
                if tag in nit_info.keys():
                    nit[tag] = val
                else:
                    logging.info(f"unknown nit tag: {tag} {val}")

    # CaliData [ GainBP ].Val = PALT_GAIN_4100   ;
    # CaliData [ OffBP ].Val  = PALT_OFFSET_4100 ;

    return nit


def read_calfile(path: str):
    """ read and parse the calibration file and return as a dict """

    logging.info(f"opening calibration file {path}")

    tag_map = {t[0]: k for k, t in cal_info.items()}

    cal = {}
    with open(path) as fp:
        for line in fp.readlines():
            if '#' in line:
                line, comment = line.split('#', maxsplit=1)
            if line:
                tag, val, *junk = line.strip().split()
                if tag in tag_map.keys():
                    key = tag_map[tag]
                    try:
                        cal[key] = float(val)
                    except ValueError:
                        cal[key] = 0.0
                        logging.error(f"bad calibration value {tag} {val}")
                else:
                    logging.info(f"unknown calibration tag: {tag}")

    return cal


def trapeziod(ptr, data, dt):
    """I tried Simpson's rule but the noise in the accelerometer output made
    the output less accurate than a simple trapezoid integral.  This also
    made the 3-element array for Altitude ( s[] ) moot but it is easier
    """

    return (data[ptr - 1] + data[ptr]) / 2.0 * dt


def simpson(ptr, data, dt):
    # dt is actually dt / 3 here
    return (data[ptr - 1] + 4 * data[ptr] + data[ptr + 1]) * dt


def taylor(ptr, data, dt):
    # dt is actually dt * 12 here !!!
    return (data[ptr - 2] - 8 * data[ptr - 1] + 8 * data[ptr + 1] - data[ptr + 2]) / dt


def pressure_alt(press, press_0, cal):
    """The Motorolla data sheet sez 4.5 V / 14.5 PSI which implies 4.56 V
    at 14.7 PSI.  The unit output is 209 / 14.7 while the ideal is
    229.5 at 14.5 ( assume 255 / 5 Unit / volt ).  This means the
    readings are offset low 23.3 units.  PALT_OFFSET is hardcoded
    for now to +23.3 and all readings are adjusted up by this value.
    """

    if press <= 0:
        return None

    if cal["OffBP"] != 1.00:
        p0 = press_0 * cal['GainBP'] + cal['OffBP']
        p1 = press   * cal['GainBP'] + cal['OffBP']
        dp = p1 / p0
    else:
        dp = (press + cal['OffBP']) / (press_0 + cal['OffBP'])

    ln_dp = log(dp)

    alt = (1 - exp(ln_dp / 5.2556)) / 0.00000688

    return alt


def main():

    parse_commandline()
    print(args)

    # go read the .nit file -- (v2) -- Moved here so CalFile, et al are set
    nit = read_nitfile(args.nit)
    print(nit)

    cal_filename = args.cal or nit['cal'] or CAL_NAME
    cal = read_calfile(cal_filename)
    print(cal)

    data_filename = args.datafile or args.data
    if not data_filename:
        parser.print_help()
        sys.exit(1)
    flight = read_datafile(data_filename)
    print(flight)

    # TODO: Version 1.25 -- use the offset from the .cal file so actbp is on
    xducer_type = 'MPX4100'
    if 'xDucer' in cal:
        if cal['XDucer'] == '5100':
            xducer_type = 'MPX5100'
        elif cal['XDucer'] == '4100':
            xducer_type = 'MPX4100'

    if 'Slope' not in cal or cal['Slope'] == 0.0:
        logging.error(f"Calibration file {args.cal} did not have Slope value!")

    # Version 1.25b -- moved from Calibrate ()
    if cal['OffBP'] == 0.00:
        logging.info(f"Calibration file {args.cal} did not have OffBP value!")
        cal['GainBP'] = xducer_info[xducer_type].gain
        logging.info(f"assuming GainBP = {cal['GainBP']} based on {xducer_type}")

        cal['OffBp'] = cal['ActBP'] - cal['GainBP'] * cal['AvgBP']
        logging.info(f"assuming OffBP = {cal['OffBP']} based on ActBP: {cal['ActBP']}")

    if flight.Version != 0xfe:
        ver = "AltAcc II - v2.%03d" % flight.Version
    else:
        ver = "AltAcc II"

    gain = DEFAULT_GAIN             # aka slope of curve */
    if args.gain:
        gain = float(args.gain)

    onegee = 0.0                    # AltAcc output @ +1 */
    if args.zor:
        onegee = float(args.zor)
    else:
        onegee = sum(flight.Window) / 4.0
           
    zerogee = onegee - gain         # AltAcc output @ 0G */
    neggee = zerogee - gain         # AltAcc output @ -1 */
    goffset = onegee                # experimental ...   */

    # pre = ( byte ) floor ( CaliData [ AvgBP ].Val ) ;
    # /*
    # if ( CaliData [ AvgBP ].Val != 0.0 )
    #   palt_0 = CaliData [ AvgBP ].Val ;
    # else
    #   palt_0 = PALT_IDEAL_5100 ;
    # */

    # v1.25 */
    # TODO: display these?
    palt_0 = (29.921 - cal['OffBP']) / cal['GainBP']
    # launch site alt
    alt_0 = pressure_alt(flight.BasePre, palt_0, cal)

    flight_mode = flight.BSFlags & 0x01

    def convert_time(sec, sec_16):
        return sec + (sec_16 & 0xE0) * 8.0 + (sec_16 & 0x0F) / 16.0

    main_time = convert_time(flight.MainSec, flight.Main16s)
    if flight_mode == DROGUE_TO_MAIN:
        drouge_time = convert_time(flight.DrogueSec, flight.Drogue16s)
        ptime = drouge_time
    else:
        drogue_time = -1.0
        ptime = main_time

    def report1(fp, com=''):
        print("%s" % com, file=fp)
        print("%sAltAcc Firmware:          %s" % (com, ver), file=fp)
        print("%sXDucer Type:              %s" % (com, xducer_info[xducer_type].desc), file=fp)
        print("%sFlight Mode:              %s" % (com, flight_modes[flight_mode]), file=fp)
        print("%sAltAcc Data file:         %s" % (com, data_filename), file=fp)
        print("%sCalibration file:         %s" % (com, cal_filename), file=fp)
        print("%s" % com, file=fp)
        print("%sAltAcc Gain Factor:    %11.4f GHarrys / G" % (com, gain), file=fp)
        print("%sAltAcc Minus One Gee:  %11.4f GHarrys" % (com, neggee), file=fp)
        print("%sAltAcc Zero Gee:       %11.4f GHarrys" % (com, zerogee), file=fp)
        print("%sAltAcc Plus One Gee:   %11.4f GHarrys" % (com, onegee), file=fp)
        print("%sLaunch Site Pressure:  %6d      Orvilles" % (com, flight.BasePre), file=fp, end='')

        if cal['OffBP'] != 0.00:
            print("   ( %.2f in Hg )" % (flight.BasePre * cal['GainBP'] + cal['OffBP']), file=fp)
        else:
            print(file=fp)

        print("%sLaunch Site Altitude:  %6.0f      %s MSL" % (com, alt_0, UNITS[U['alt']]), file=fp)

        # v1.25
        # alt_0 + CaliData [ ActAlt ].Val, Units [ U[0]] ) ;

        print("%s" % com, file=fp)

        if flight_mode == DROGUE_TO_MAIN:
            drogue_alt = pressure_alt(flight.DroguePre, flight.BasePre, cal)
            print("%sDrogue Fired at Time:  %11.4f %s      ( %6.0f %s AGL )" %
                  (com, drogue_time, UNITS[U['time']], drogue_alt, UNITS[U['alt']]), file=fp)

        main_alt = pressure_alt(flight.MainPre, flight.BasePre, cal)
        print("%sMain Fired at Time:    %11.4f %s      ( %6.0f %s AGL )" %
              (com, main_time, UNITS[U['time']], main_alt, UNITS[U['alt']]), file=fp)

        print("%s" % com, file=fp)
        print("%s" % com, file=fp)

    if args.out:
        outf = open(args.out, 'w')

        if args.fmt == 'A':
            report1(outf, "# ")
            print(Header, file=outf)
        else:
            print(ExHead, file=outf)

    if not args.quiet:
        report1(sys.stdout)

    # I want to use Simpson's rule for altitude and Taylor's 2nd order
    # 2-step derivative to back acceleration from velocity.  The simple
    # way is to precalc the velocity into an array then work with that.
    # Velocity is computed using the trapezoidal rule cause the data is
    # noisy anyway. Here we go ...

    # Fill the time, velocity array ... pad 2 then do Countdown data

    tee, vee, gee, pre = [], [], [], []

    win_ptr = flight.WinPtr

    for i in range(6):
        tee.append((i - 5) * dT)
        vee.append(0.0)
        pre.append(flight.BasePre)

        win_ptr = (win_ptr + 1) % 4
        gee.append(flight.Window[win_ptr])

    oacc = 0.0                     # last accel reading for Trapeziod () */
    vel  = 0.0                     # Sum of Accel == Velocity == vel */
    multiplier = dT * GEE / gain / 2.0  # replace slow Trap () w/ inline */

    # oldest, older, old, cur acceleration go in next
    for i in range(4):
        cacc = flight.NitAcc[i] - onegee
        vel += (oacc + cacc) * multiplier

        tee.append((i + 1) * dT)
        vee.append(vel)
        pre.append(flight.BasePre)
        gee.append(flight.NitAcc[i])

        oacc = cacc

    # Now do the flight data stored as alternating samples A P A P A P ...
    t = 4 * dT
    for i in range(NUM_PAIRS):
        cacc = flight.Data[i * 2] - onegee
        vel += (oacc + cacc) * multiplier

        # 0.25 sec are lost when firing pyros
        if t in (main_time, drogue_time):
            t += dT * 4
        else:
            t += dT
        tee.append(t)
        vee.append(vel)
        gee.append(flight.Data[i * 2])
        pre.append(flight.Data[i * 2 + 1])

        if flight.Data[i * 2 + 1] == 254:
            break

        oacc = cacc

    # Finally,  pad the end with zeros for Taylor ()
    tee.extend((0.0, 0.0))
    vee.extend((0.0, 0.0))
    gee.extend((0.0, 0.0))
    pre.extend((0.0, 0.0))

    oalt = 0.0  # Simpson() does 2dT
    gsum = 0  # Gee - onegee temp
    launch = False  # set when gsum>thold
    end_of_time = None  # All the data (v2)
    maxp = flight.DroguePre if flight_mode == DROGUE_TO_MAIN else flight.MainPre

    maxialt = 0.0                   # max inertial alt   */
    tmaxialt = 0.0                  # time of max i-alt  */
    maxpalt = 0.0                   # press alt at minvel*/

    maxvel = 0.0
    tmaxvel = 0.0
    minacc = 0.0
    tminacc = -1.0                  # tminacc controls derivative mode
    maxacc = 0.0
    tmaxacc = 0.0

    atime = ptime
    atime_oride = False             # set when gsum = 0
    acc = 0.0
    alt = 0.0

    for i, t in enumerate(tee):
        if pre[i] == 254 or (end_of_time and t > end_of_time):
            break

        if i > 3:
            dalt = simpson(i, vee, dT / 3) - oalt    # differential alt
            alt += dalt

            acc = taylor(i, vee, 12 * dT)           # accel == dv/dt
            gsum += gee[i] - goffset
            oalt = dalt

            if not launch and gsum > LAUNCH_THOLD:
                launch = True

            # TODO: setting atime here clobbers the value derived from the header
            if launch and gsum <= 0.0 and not atime_oride:
                atime = t
                atime_oride = True

        if t <= atime:
            # TODO: setting maxp here clobbers the value derived from the header
            if pre[i] <= maxp:
                maxp = pre[i]
                ptime = t

            if alt > maxialt:
                maxialt = alt
                tmaxialt = t

            if vee[i] > maxvel:
                maxvel = vee[i]
                tmaxvel = t

            if gsum >= 0.0:
                if acc < minacc:
                    minacc = acc
                    tminacc = t

                if acc > maxacc:
                    maxacc = acc
                    tmaxacc = t
        else:
            # (v2) -- Break early if we get back to the ground
            if not args.all and pre[i] >= flight.BasePre and not end_of_time:
                end_of_time = t + 5.0  # Add 5 seconds

    if args.out:
        for i, t in enumerate(tee):
            palt = pressure_alt(pre[i], flight.BasePre, cal) or 0.0

            if args.fmt == 'A':
                print(" %9.4f    %3d    %3d  %5.0f  %9.2f  %9.2f  %9.2f  %8.0f" %
                      (t, gee[i], pre[i], gsum, acc, vee[i], alt, palt), file=outf)
            else:
                print("%.4f,%d,%d,%.0f,",
                      (t, gee[i], pre[i], gsum), end='', file=outf)
                if t <= atime:
                    print("%.2f,%.2f,%.2f,%.0f" % (acc, vee[i], alt, palt), file=outf)
                else:
                    print(",,,%.0f", end='', file=outf)

    maxpalt = pressure_alt(maxp, flight.BasePre, cal)
    msl_alt = pressure_alt(maxp, palt_0, cal) - alt_0

    def report2(fp, com='# '):
        print("%s" % com, file=fp)
        if not args.nomsl:
            print("%sMSL Pressure Altitude:    %6.0f    %s         ( %9.5f sec )" %
                  (com, msl_alt, UNITS[U['alt']], ptime), file=fp)
        print("%sAGL Pressure Altitude:    %6.0f    %s         ( %9.5f sec )" %
              (com, maxpalt, UNITS[U['alt']], ptime), file=fp)
        print("%sMax Inertial Altitude:    %6.0f    %s         ( %9.5f sec )" %
              (com, maxialt, UNITS[U['alt']], tmaxialt), file=fp)
        print("%sMaximum Velocity:         %8.1f  %s / %s   ( %9.5f sec )" %
              (com, maxvel, UNITS[U['alt']], UNITS[U['time']], tmaxvel), file=fp)
        print("%sMaximum Acceleration:     %9.2f %s / %s^2 ( %9.5f sec, %5.1f G's )" %
              (com, maxacc, UNITS[U['alt']], UNITS[U['time']], tmaxacc, maxacc/GEE), file=fp)
        print("%sMinimum Acceleration:     %9.2f %s / %s^2 ( %9.5f sec, %5.1f G's )" %
              (com, minacc, UNITS[U['alt']], UNITS[U['time']], tminacc, minacc/GEE), file=fp)

    if args.out:
        if args.fmt == 'A':
            report2(outf)
        outf.close()

    report2(sys.stdout, com='')


main()
