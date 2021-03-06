""" produce

This Is a Python Program For Converting binary data from the BSR AltAcc
to ASCII Data with nice little Headers.
"""

import sys
import argparse
import logging
from math import log, exp
import prodata

VERSION = "1.25c"

flight_modes = (
    "Main Only Mode",
    "Drogue to Main Mode",
    "Drogue to Main Mode -- !! No Drogue Fire !!"
)

UNITS = {
    "sec", ('press', 1.0),
    "in", ('alt', 1.0),
    "ft", ('alt', 0.3048),
    "cm", ('alt', 0.01),
    "m", ('alt', 1.0),
    "km", ('alt', 1.0),
    "oz", ('acc', 1.0),
    "lb", ('acc', 1.0),
    "gm", ('acc', 1.0),
    "kg", ('acc', 1.0),
    "GHarrys", ('acc', 1.0),
    "inhg", ('press', 0.295),
    "mmhg", ('press', 1.0),
    "torr", ('press', 1.0),
    "kpa", ('press', 1.0),
    "Orvilles", ('press', 1.0),
    "ft/sec", ('vel', 1.0),
}

# default units
U = {
    "alt": "ft",
    "acc": "lb",
    "vel": "ft/sec",
    "time": "sec",
    "pressure": "inhg",
}

PALT_IDEAL_5100 = 210    # what _my_ test unit sez
LAUNCH_THOLD = 16.0      # about 1/4 sec of 1.33 G
DROGUE_TO_MAIN = 1
DEFAULT_GAIN = 2.5500    # +/- 50 G over 255 units
GEE = 32.17              # ft/sec^2
dT = 0.0625              # AltAcc dt 1/16sec


def parse_commandline():
    global args, parser

    parser = argparse.ArgumentParser(prog='produce', description=f'AltAcc data reduction program (v{VERSION})')
    parser.add_argument('-c', '--cal', default=prodata.CAL_NAME, help='calibration (probate) filename')
    parser.add_argument('-n', '--nit', default=prodata.NIT_NAME, help='override init filename')
    parser.add_argument('-f', '--data', help='AltAcc data (proread) filename')
    parser.add_argument('-o', '--out', help='output results filename')

    parser.add_argument('-z', '--oneg', action='store', help='one gee override value (overrides data file one gee)')
    parser.add_argument('-g', '--gain', action='store', help='gain override (overrides cal file gain value)')
    parser.add_argument('-F', '--fmt', action='store', default='A', help='output file format (C)SV (A)SCII')
    parser.add_argument('-m', '--nomsl', action='store_true', help='do not show MSL pressure alt along with AGL')
    parser.add_argument('-a', '--all', action='store_true', help='force all the data out, even after touchdown')
    parser.add_argument('-q', '--quiet', action='store_true', help="be quiet about it")
    parser.add_argument('--version', action='version', version=f'v{VERSION}')
    parser.add_argument('datafile', default=None, nargs='?', action='store', help='data filename')

    args = parser.parse_args()


def trapezoid(ptr, data, dt):
    """I tried Simpson's rule but the noise in the accelerometer output made
    the output less accurate than a simple trapezoid integral.  This also
    made the 3-element array for Altitude ( s[] ) moot but it is easier
    """

    return (data[ptr - 1] + data[ptr]) / 2.0 * dt


def simpson(ptr, data, dt):
    return (data[ptr - 1] + 4 * data[ptr] + data[ptr + 1]) * dt / 3


def taylor(ptr, data, dt):
    # dt is actually dt * 12 here !!!
    return (data[ptr - 2] - 8 * data[ptr - 1] + 8 * data[ptr + 1] - data[ptr + 2]) / dt


def pressure_alt(press, press_0, cal):
    """The Motorola data sheet sez 4.5 V / 14.5 PSI which implies 4.56 V
    at 14.7 PSI.  The unit output is 209 / 14.7 while the ideal is
    229.5 at 14.5 ( assume 255 / 5 Unit / volt ).  This means the
    readings are offset low 23.3 units.  PALT_OFFSET is hardcoded
    for now to +23.3 and all readings are adjusted up by this value.
    """

    if press <= 0:
        return None

    p0 = press_0 * cal['GainBP'] + cal['OffBP']
    p1 = press * cal['GainBP'] + cal['OffBP']
    ln_dp = log(p1 / p0)

    alt = (1 - exp(ln_dp / 5.2556)) / 0.00000688

    return alt


def main():

    parse_commandline()

    # go read the .nit file -- (v2) -- Moved here so CalFile, et al are set
    nit = prodata.read_nitfile(args.nit)
    print(nit)

    cal_filename = args.cal or nit['cal'] or prodata.CAL_NAME
    cal = prodata.read_calfile(cal_filename)
    print()
    prodata.dump_calfile(None, cal)

    data_filename = args.datafile or args.data
    if not data_filename:
        parser.print_help()
        sys.exit(1)
    flight = prodata.read_datafile(data_filename)
    print()
    prodata.dump_datafile(flight)

    # TODO: Version 1.25 -- use the offset from the .cal file so actbp is on
    xducer_type = 'MPX4100'
    if 'xDucer' in cal:
        if cal['XDucer'] == '5100':
            xducer_type = 'MPX5100'
        elif cal['XDucer'] == '4100':
            xducer_type = 'MPX4100'

    # Version 1.25b -- moved from Calibrate ()
    if cal['OffBP'] == 0.00:
        logging.info(f"Calibration file {args.cal} did not have OffBP value!")
        cal['GainBP'] = prodata.xducer_info[xducer_type].gain
        logging.info(f"assuming GainBP = {cal['GainBP']} based on {xducer_type}")

        cal['OffBp'] = cal['ActBP'] - cal['GainBP'] * cal['AvgBP']
        logging.info(f"assuming OffBP = {cal['OffBP']} based on ActBP: {cal['ActBP']}")

    if 'Slope' not in cal or cal['Slope'] == 0.0:
        logging.error(f"Calibration file {args.cal} did not have Slope value!")

    if flight.Version != 0xfe:
        ver = "AltAcc II - v2.%03d" % flight.Version
    else:
        ver = "AltAcc II"

    slope = DEFAULT_GAIN            # aka slope of curve */
    if args.gain:
        slope = float(args.gain)
    elif cal['Slope']:
        slope = cal['Slope']

    onegee = 0.0                    # AltAcc output @ +1 */
    if args.oneg:
        onegee = float(args.oneg)
    else:
        onegee = sum(flight.Window) / 4.0
           
    zerogee = onegee - slope        # AltAcc output @ 0G */
    neggee = zerogee - slope        # AltAcc output @ -1 */
    goffset = onegee                # experimental ...   */

    # pre = ( byte ) floor ( CaliData [ AvgBP ].Val ) ;
    # /*
    # if ( CaliData [ AvgBP ].Val != 0.0 )
    #   palt_0 = CaliData [ AvgBP ].Val ;
    # else
    #   palt_0 = PALT_IDEAL_5100 ;
    # */

    # gather event data from flight data
    flight_mode = flight.BSFlags & 0x01

    def convert_time(sec, sec_16):
        return sec + (sec_16 & 0xE0) * 8.0 + (sec_16 & 0x0F) / 16.0

    main_time = convert_time(flight.MainSec, flight.Main16s)
    if flight_mode == DROGUE_TO_MAIN:
        drogue_time = convert_time(flight.DrogueSec, flight.Drogue16s)
        apogee_time = drogue_time
        apogee_pre = flight.DroguePre
    else:
        drogue_time = None
        apogee_time = main_time
        apogee_pre = flight.MainPre

    # Fill the time, velocity array ...
    oacc = 0.0                           # last accel reading for Trapezoid ()
    vel = 0.0                            # Sum of Accel == Velocity == vel
    multiplier = dT * GEE / slope / 2    # replace slow Trap () w/ inline

    tee, vee, gee, pre = [], [], [], []

    # 1/4 second before launch
    for i in range(4):
        tee.append((i - 3) * dT)
        vee.append(0.0)
        pre.append(flight.BasePre)

        win_ptr = (flight.WinPtr + i + 1) % 4
        gee.append(flight.Window[win_ptr])

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
    for i in range(len(flight.Data) // 2):
        cacc = flight.Data[i * 2] - onegee
        vel += (oacc + cacc) * multiplier

        # 0.25 sec lost when firing pyros
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

    # I want to use Simpson's rule for altitude and Taylor's 2nd order
    # 2-step derivative to back acceleration from velocity.  The simple
    # way is to precalc the velocity into an array then work with that.
    # Velocity is computed using the trapezoidal rule cause the data is
    # noisy anyway. Here we go ...

    oalt = 0.0  # Simpson() does 2dT
    launch = False  # set when gsum>thold
    atime = None  # set when gsum = 0
    end_of_time = None  # All the data (v2)

    maxialt, tmaxialt = 0.0, 0.0                 # max inertial alt   */
    maxvel, tmaxvel = 0.0, 0.0
    minacc, tminacc = 0.0, -1.0                  # tminacc controls derivative mode
    maxacc, tmaxacc = 0.0, 0.0
    minpre, tminpre = 255, 0.0
    maxpre, tmaxpre = 0, 0.0
    
    acc, ialt, palt, gsum = [], [], [], []

    for i, t in enumerate(tee):
        if pre[i] == 254 or (end_of_time and t > end_of_time):
            break

        if i > 3:
            # TODO: this seems to come out too low
            dalt = simpson(i, vee, dT) - oalt       # differential alt
            oalt = dalt
            
            ialt.append(ialt[-1] + dalt)
            palt.append(prodata.palt3(pre[i], flight.BasePre) or 0.0)
            acc.append(taylor(i, vee, 12 * dT))         # accel == dv/dt
            gsum.append(gsum[-1] + gee[i] - goffset)    # goffset = onegee

            if not launch and gsum[i] > LAUNCH_THOLD:
                launch = True

            if launch and gsum[i] <= 0.0 and not atime:
                atime = t
        else:
            acc.append(0.0)
            ialt.append(0.0)
            palt.append(0.0)
            gsum.append(0.0)

        if pre[i] > maxpre:
            maxpre = pre[i]
            tmaxpre = t

        if pre[i] <= minpre:
            minpre = pre[i]
            tminpre = t

        if not atime or t <= atime:
            if ialt[i] > maxialt:
                maxialt = ialt[i]
                tmaxialt = t

            if vee[i] > maxvel:
                maxvel = vee[i]
                tmaxvel = t

            if gsum[i] >= 0.0:
                if acc[i] < minacc:
                    minacc = acc[i]
                    tminacc = t

                if acc[i] > maxacc:
                    maxacc = acc[i]
                    tmaxacc = t
        else:
            # (v2) -- Break early if we get back to the ground
            if not args.all and pre[i] >= flight.BasePre and not end_of_time:
                end_of_time = t + 5.0  # Add 5 seconds

    # v1.25 */
    # compute pressure for ideal sea level 29.921 inHg TODO: cal is in kPa!
    palt_0 = (29.921 - cal['OffBP']) / cal['GainBP']
    # launch site alt
    alt_0 = pressure_alt(flight.BasePre, palt_0, cal)

    agl_alt = pressure_alt(apogee_pre, flight.BasePre, cal)
    msl_alt = pressure_alt(apogee_pre, palt_0, cal) - alt_0
    main_alt = pressure_alt(flight.MainPre, flight.BasePre, cal)
    drogue_alt = pressure_alt(flight.DroguePre, flight.BasePre, cal)
    maxpalt = pressure_alt(minpre, flight.BasePre, cal)
    biba_alt = prodata.palt3(apogee_pre, flight.BasePre)
    
    def report1(fp, com=''):
        print("%s" % com, file=fp)
        print("%sAltAcc Firmware:          %s" % (com, ver), file=fp)
        print("%sXDucer Type:              %s" % (com, prodata.xducer_info[xducer_type].desc), file=fp)
        print("%sFlight Mode:              %s" % (com, flight_modes[flight_mode]), file=fp)
        print("%sAltAcc Data file:         %s" % (com, data_filename), file=fp)
        print("%sCalibration file:         %s" % (com, cal_filename), file=fp)
        print("%s" % com, file=fp)
        print("%sPressure Offset:       %11.4f " % (com, cal['OffBP']), file=fp)
        print("%sPressure Gain/Slope:   %11.4f " % (com, cal['GainBP']), file=fp)
        print("%sAltAcc Gain Factor:    %11.4f GHarrys/G" % (com, slope), file=fp)
        print("%sAltAcc Minus One Gee:  %11.4f GHarrys" % (com, neggee), file=fp)
        print("%sAltAcc Zero Gee:       %11.4f GHarrys" % (com, zerogee), file=fp)
        print("%sAltAcc Plus One Gee:   %11.4f GHarrys" % (com, onegee), file=fp)
        print("%sLaunch Site Pressure:  %6d      Orvilles" % (com, flight.BasePre), file=fp, end='')
        if cal['OffBP'] != 0.00:
            print("   ( %.2f in Hg )" % (flight.BasePre * cal['GainBP'] + cal['OffBP']), file=fp)
        else:
            print(file=fp)
        print("%sDrogue Fire Pressure:  %6d      Orvilles" % (com, flight.DroguePre), file=fp)
        print("%sMain Fire Pressure:    %6d      Orvilles" % (com, flight.MainPre), file=fp)

        print("%sLaunch Site Altitude:  %6.0f      %s MSL" % (com, alt_0, U['alt']), file=fp)

        if cal['ActAlt'] >= 0.0:
            print("%sActual Altitude:       %6.0f      %s MSL     ( Cal: ActAlt )" % (com, cal['ActAlt'],
                                                                                      U['alt']), file=fp)
            
        # alt_0 + CaliData [ ActAlt ].Val, Units [ U[0]] ) ;

        print("%s" % com, file=fp)

        if flight_mode == DROGUE_TO_MAIN:
            print("%sDrogue Fired at Time:  %11.4f %s      ( %6.0f %s AGL )" %
                  (com, drogue_time, U['time'], drogue_alt, U['alt']), file=fp)
        print("%sMain Fired at Time:    %11.4f %s        ( %6.0f %s AGL )" %
              (com, main_time, U['time'], main_alt, U['alt']), file=fp)

        print("%s" % com, file=fp)
        print("%s" % com, file=fp)

    if args.out:
        outf = open(args.out, 'w')
        if args.fmt == 'A':
            report1(outf, "# ")
            
    if not args.quiet:
        report1(sys.stdout)

    def report2(fp):
        if args.fmt == 'A':
            print(
                "      Time  Accel  Press    Sum  Accelerat   Velocity   Altitude  PressAlt\n"
                "       sec  units  units  units   ft/sec^2     ft/sec       feet      feet\n"
                " =========  =====  =====  =====  =========  =========  =========  ========\n",
                file=fp)
        else:
            print(
                '''"Time","Accel","Press","Vel","Accel","Velocity","IAlt","PAlt",'''
                '''"sec","GHarrys","Orvilles","Verns","ft/sec^2","ft/sec","feet","feet"''',
                file=fp)

        for i, t in enumerate(tee):
            if t > end_of_time:
                break

            if args.fmt == 'A':
                print(" %9.4f    %3d    %3d  %5.0f  %9.2f  %9.2f  %9.2f  %8.0f" %
                      (t, gee[i], pre[i], gsum[i], acc[i], vee[i], ialt[i], palt[i]), file=fp)
            elif args.fmt == 'X':
                print(f'{t}\t{gee[i]}\t{vee[i]}')
            else:
                print("%.4f,%d,%d,%.0f," %
                      (t, gee[i], pre[i], gsum[i]), end='', file=fp)
                if t <= atime:
                    print("%.2f,%.2f,%.2f,%.0f" % (acc[i], vee[i], ialt[i], palt[i]), file=fp)
                else:
                    print(",,,%.0f" % palt[i], file=fp)

    if args.out:
        report2(outf)
    report2(sys.stdout)
    
    def report3(fp, com='# '):
        desc = 'Drogue' if flight_mode == DROGUE_TO_MAIN else 'Main'
        
        print("%s" % com, file=fp)
        if not args.nomsl:
            print("%sMSL Pressure Altitude:    %6.0f    %s         ( %9.5f sec  %s )" %
                  (com, msl_alt, U['alt'], apogee_time, desc), file=fp)
        print("%sAGL Pressure Altitude:    %6.0f    %s         ( %9.5f sec )" %
              (com, agl_alt, U['alt'], apogee_time), file=fp)
        print("%sbiba Pressure Altitude:    %6.0f    %s         ( %9.5f sec )" %
              (com, biba_alt, U['alt'], apogee_time), file=fp)
        print("%sMax Pressure Altitude:    %6.0f    %s         ( %9.5f sec )" %
              (com, maxpalt, U['alt'], tminpre), file=fp)
        print("%sMax Inertial Altitude:    %6.0f    %s         ( %9.5f sec )" %
              (com, maxialt, U['alt'], tmaxialt), file=fp)
        print("%sMaximum Velocity:         %8.1f  %s / %s   ( %9.5f sec )" %
              (com, maxvel, U['alt'], U['time'], tmaxvel), file=fp)
        print("%sMaximum Acceleration:     %9.2f %s / %s^2 ( %9.5f sec, %5.1f G's )" %
              (com, maxacc, U['alt'], U['time'], tmaxacc, maxacc / GEE), file=fp)
        print("%sMinimum Acceleration:     %9.2f %s / %s^2 ( %9.5f sec, %5.1f G's )" %
              (com, minacc, U['alt'], U['time'], tminacc, minacc / GEE), file=fp)

    def graph():
        import matplotlib.pyplot as plt

        # x = np.arange(0, DAYS)
        points = int(atime * 16)

        t = tee[:points]
        g = [(x - onegee) / slope for x in gee[:points]]
        # smooth the pressure data
        p = [sum(palt[i: i + 4]) / 4 for i in range(len(palt))]
        
        plt.suptitle(data_filename)

        plt.subplot(221)
        plt.plot(t, g)
        plt.legend(['acc G'], loc='upper right')
        plt.xlabel('sec')
        plt.ylabel('G')
        
        plt.subplot(223)
        plt.plot(t, vee[:points], color='g')
        plt.plot(t, ialt[:points], color='r')
        plt.plot(t, palt[:points], color='r')
        plt.legend(['vel ft/sec', 'alt ft'], loc='upper left')
        plt.xlabel('sec')
        
        plt.subplot(222)
        plt.title('Pressure Altitude')
        plt.plot(tee[:len(p)], p, color='r')
        plt.ylim(ymin=-5)
        # plt.legend(['alt'], loc='upper right')
        plt.xlabel('sec')
        plt.xlim(xmin=-0.25)
        
        plt.show()

    if args.out:
        if args.fmt == 'A':
            report3(outf)
        outf.close()
    report3(sys.stdout, com='')

    graph()

main()
