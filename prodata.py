"""
These are common routines for the BSR AltAcc software

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
"""

import sys
import struct
import logging
import datetime
from collections import namedtuple

NIT_NAME = "prodata.nit"
CAL_NAME = "prodata.cal"
OUT_NAME = "prodata.dat"


nit_info = {
    "port": "where do you plug in the AltAcc ( oride: -p COM# )",
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
    "StDNegG": ("std-1g", "Minus One Gee Std Dev"),
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

data_info = {
    "Version": "Starting at v2-125, we have V!",
    "DrogueSec": "Time of Drogue Deploy, Seconds",
    "Drogue16s": "Time of Drogue Deploy, 1/16sec",
    "DrogueAcc": "Accel at Drogue Deploy",
    "DroguePre": "Pressure at Drogue Deploy",
    "MainSec": "Time of Main Deploy, Seconds",
    "Main16s": "Time of Main Deploy, 1/16sec",
    "MainAcc": "Accel at Main Deploy",
    "MainPre": "Pressure at Main Deploy",
    "BSFlags": "AltAcc Launch Status Flags",
    "BasePre": "Pressure Reading, Win [Ptr]",
    "LastPre": "Pressure Reading, Win [Ptr+3]",
    "WinPtr": "Pointer to Beginning of Win []",
    "Window": "4-byte circular buffer, Accel",
    "AvgAcc": "Average of Window [] Data",
    "NitAcc": "T={1,2,3,4} / 16 (Liftoff Acc)",
    "SumLob": "Lo Byte of Sum of NitAcc []",
    "SumHib": "Hi Byte of Sum of NitAcc []",
    "Data": "This is the 8160 Byte Flight",
    "CkSum": "AltAcc's Version of check sum",
    "OK": "AltAcc sez 'OK'",
}

# flight data header format
altacc_format = struct.Struct("<B3x4B4BBBBB4sB4sBB5x8160sH2s")
AltAccDump = namedtuple('AltAccDump', ' '.join(data_info.keys()))

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

# noinspection PyProtectedMember
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


def dump_calfile(file, data, header=None):
    fp = open(file, "w") if file else sys.stdout

    print("#\n# AltAcc Calibration Data %s\n#\n" % 
          (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")), file=fp)

    for k, v in data.items():
        if v is not None and k != 'Data':
            print(f'{cal_info[k][0]:8}  {v:8}  # {cal_info[k][1]}', file=fp)

    if file:
        fp.close()


def dump_datafile(data):
    for k, v in data._asdict().items():
        if k == 'Data':
            pass
        elif k in ('Window', 'NitAcc'):
            vec = ''.join('%02X ' % x for x in v)
            print(f'{k:10}: {vec:12}  {data_info[k]}')
        elif k in ('OK',):
            print(f'{k:10}: {v.decode():12}  {data_info[k]}')
        elif k in ('BSFlags',):
            b = '{:08b}'.format(v)
            print(f"{k:10}: {b:12}  {data_info[k]}")
        else:
            print(f'{k:10}: {v:12}  {data_info[k]}')

