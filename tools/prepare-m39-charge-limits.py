#!/usr/bin/env python3
"""Set diagnostic MT6328 limits; keep charging inhibited and stop faking TBAT."""
from pathlib import Path
root = Path(__file__).resolve().parent.parent
src = root / 'tools/mt6735-kernel'
def replace(path, before, after, count=1):
    p = src / path
    text = p.read_text()
    if after in text:
        return
    assert text.count(before) == count, path
    p.write_text(text.replace(before, after))
base = 'drivers/misc/mediatek/power/mt6735/charging_hw_pmic.c'
replace(base, '*(unsigned int *) (data));', 'BATTERY_VOLT_03_900000_V); /* M39 diagnostic hardware CV ceiling. */')
replace(base, 'set_chr_current = bmt_find_closest_level(CS_VTH, array_size, *(unsigned int *) data);',
        'set_chr_current = bmt_find_closest_level(CS_VTH, array_size,\n\t\tmin(*(unsigned int *) data, (unsigned int)CHARGE_CURRENT_300_00_MA)); /* M39 nominal limit. */')
replace('drivers/misc/mediatek/include/mt-plat/mt6735/include/mach/mt_charging.h',
        '#define HIGH_BATTERY_VOLTAGE_SUPPORT', '/* M39: labelled 4.2V cell; high-voltage battery support disabled. */')
replace('drivers/power/mediatek/battery_meter.c', '#include <mach/mt_battery_meter_table.h>',
        '#include <mach/mt_battery_meter_table.h>\n/* M39: report contact conversion, never a fabricated 25 C. Still unvalidated. */\n#undef FIXED_TBAT_25')
assert 'unsigned int enable = KAL_FALSE;' in (src / base).read_text()
print('Prepared 3.9V CV, nominal current <=300mA, high-voltage support off, fixed-TBAT off; charging remains inhibited.')
