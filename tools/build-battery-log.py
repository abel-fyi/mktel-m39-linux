#!/usr/bin/env python3
"""Build a bounded battery-only logger from the reviewed measurement helpers."""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
source = (root / 'tools/m39-pmic-pulse.sh').read_text()
functions = ''
for name in ['fail', 'number', 'readreg', 'field', 'writereg', 'uptime_seconds', 'sample', 'fuel_current']:
    bracket = '(' if name in ('sample', 'fuel_current') else '{'
    ending = ')' if bracket == '(' else '}'
    start = source.index(name + '() ' + bracket)
    finish = source.index('\n' + ending + '\n', start) + 3
    functions += source[start:finish] + '\n'
functions = functions.replace('writereg() {\n', '''writereg() {
    # This logger cannot write any charger-control register.
    case "$1" in 028a|0e94|0eb0|0e8a) ;; *) fail 'Logger write outside ADC controls';; esac
''')
script = '''#!/bin/sh
# Measurement requests/clock restoration only; never enables charging.
set -eu
access=/sys/devices/platform/mt-pmic/pmic_access
owner=/sys/module/charging_hw_pmic/parameters/m39_owner_seconds
boot=$(cat /proc/sys/kernel/random/boot_id)
''' + functions + '''
[ "$(number "$owner")" = 0 ]
[ ! -d /run/m39-plug-service.lock ]
[ -x /run/m39-fg-sample ]
mkdir /run/m39-pmic-pulse.lock
trap 'rmdir /run/m39-pmic-pulse.lock' EXIT
trap 'exit 1' HUP INT TERM
[ "$(( $(readreg 0200) >> 8 ))" = 40 ]
waiting=$(uptime_seconds)
echo 'READY: waiting for USB removal; 90s measurement then automatic exit'
while [ "$(cat /sys/class/power_supply/usb/online)" = 1 ] ||
      [ "$(cat /sys/class/power_supply/ac/online)" = 1 ]; do
    [ "$(( $(uptime_seconds)-waiting ))" -lt 600 ] || fail 'No unplug before deadline'
    sleep 1
done
started=$(uptime_seconds)
echo "START battery-only boot=$boot uptime=$started"
while [ "$(( $(uptime_seconds)-started ))" -lt 90 ]; do
    [ "$(number "$owner")" = 0 ] || fail 'Another charger owner appeared'
    [ "$(( $(readreg 0f48) & 24 ))" = 0 ] || fail 'Charger gates unexpectedly active'
    snapshot=$(sample) || fail 'ADC measurement/restore failed'
    set -- $snapshot
    [ "$#" = 5 ] || fail 'Incomplete ADC snapshot'
    voltage=$1 vbus=$3
    [ "$voltage" -ge 3300 ] && [ "$voltage" -le 4300 ] || fail 'Battery outside test bounds'
    fg=$(fuel_current) || fail 'Gauge measurement/restore failed'
    set -- $fg
    [ "$#" = 2 ] || fail 'Incomplete gauge snapshot'
    brightness=$(number /sys/class/leds/lcd-backlight/brightness)
    printf '{"uptime":%s,"battery_mv":%s,"usb_mv":%s,"fg_signed_raw":%s,"brightness":%s}\n' \
        "$(uptime_seconds)" "$voltage" "$vbus" "$2" "$brightness"
    sleep 2
done
echo 'DONE: 90s measurement complete; no charger configuration changed'
'''
path = root / 'artifacts/m39-battery-log.sh'
path.write_text(script)
print(path)
