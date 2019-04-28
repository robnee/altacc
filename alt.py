from math import log, exp


cali_data = {
   'OffBP': 23.3,
   'GainBP': 1.0
}


def palt(press, press_0):
    """The Motorolla data sheet sez 4.5 V / 14.5 PSI which implies 4.56 V
    at 14.7 PSI.  The unit output is 209 / 14.7 while the ideal is
    229.5 at 14.5 ( assume 255 / 5 Unit / volt ).  This means the
    readings are offset low 23.3 units.  PALT_OFFSET is hardcoded
    for now to +23.3 and all readings are adjusted up by this value.
    """

    if press <= 0:
        return None
    
    p0 = press_0 * cali_data['GainBP'] + cali_data['OffBP']
    p1 = press * cali_data['GainBP'] + cali_data['OffBP']
    
    alt = (1 - exp(log(p1 / p0) / 5.2556)) / 0.00000688

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

    p0 = press_0 * cali_data['GainBP'] + cali_data['OffBP']
    p1 = press * cali_data['GainBP'] + cali_data['OffBP']

    alt = (1 - (p1 / p0) ** (1 / 5.256)) / 0.00000688

    return alt


print(palt(189, 209))
print(palt2(189, 209))

