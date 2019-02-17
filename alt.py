from math import log, exp, pow


cali_data = {}
cali_data['OffBP'] = 23.3
cali_data['GainBP'] = 1.0


def palt(press, press_0):
    """The Motorolla data sheet sez 4.5 V / 14.5 PSI which implies 4.56 V
    at 14.7 PSI.  The unit output is 209 / 14.7 while the ideal is
    229.5 at 14.5 ( assume 255 / 5 Unit / volt ).  This means the
    readings are offset low 23.3 units.  PALT_OFFSET is hardcoded
    for now to +23.3 and all readings are adjusted up by this value.
    """

    if press <= 0:
        return None

    if cali_data["OffBP"] != 1.00:
        p0 = press_0 * cali_data['GainBP'] + cali_data['OffBP']
        p1 = press   * cali_data['GainBP'] + cali_data['OffBP']
        dp = p1 / p0
    else:
        dp = (press + cali_data['OffBP']) / (press_0 + cali_data['OffBP'])

    ln_dp = log(dp)

    alt = (1 - exp(ln_dp / 5.2556)) / 0.00000688

    return alt


def palt2(press, press_0):
    """The Motorolla data sheet sez 4.5 V / 14.5 PSI which implies 4.56 V
    at 14.7 PSI.  The unit output is 209 / 14.7 while the ideal is
    229.5 at 14.5 ( assume 255 / 5 Unit / volt ).  This means the
    readings are offset low 23.3 units.  PALT_OFFSET is hardcoded
    for now to +23.3 and all readings are adjusted up by this value.
    """

    if press <= 0:
        return None

    p0 = press_0 * cali_data['GainBP'] + cali_data ['OffBP']
    p1 = press   * cali_data['GainBP'] + cali_data ['OffBP']

    alt = (1 - (p1 / p0) ** (1 / 5.256)) / 0.00000688

    return alt


def palt3(press, press_0):
    """The Motorolla data sheet sez 4.5 V / 14.5 PSI which implies 4.56 V
    at 14.7 PSI.  The unit output is 209 / 14.7 while the ideal is
    229.5 at 14.5 ( assume 255 / 5 Unit / volt ).  This means the
    readings are offset low 23.3 units.  PALT_OFFSET is hardcoded
    for now to +23.3 and all readings are adjusted up by this value.
    
    http://home.earthlink.net/~schultdw/altacc/altacc.html
    """

    if press <= 0:
        return None

    p0 = press_0 * 0.37037 + 13.6
    p1 = press * 0.37037 + 13.6
    
    alt0 = (288.14 - 288.08 * (p0 / 101.29) ** (1/5.256)) / 0.00649
    alt1 = (288.14 - 288.08 * (p1 / 101.29) ** (1/5.256)) / 0.00649

    return (alt1 - alt0) * 3.2808
    

print(palt(189, 209))
print(palt2(189, 209))
print(palt3(189, 209))
