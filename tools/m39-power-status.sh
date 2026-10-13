#!/bin/sh
# Engineering status: PMIC register reads and the reviewed gauge latch only.
# Never enables charging or changes charger configuration.
set -eu
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
access=/sys/devices/platform/mt-pmic/pmic_access
[ -x /run/m39-fg-sample ] || { echo 'Upload /run/m39-fg-sample first' >&2; exit 1; }
selector=$(mktemp /run/m39-power-read.XXXXXX)
trap 'rm -f "$selector"' EXIT HUP INT TERM
readreg() {
    printf '%s\n' "$1" > "$selector"
    cat "$selector" > "$access"
    value=$(cat "$access")
    case "$value" in ''|*[!0-9]*) echo 'Invalid PMIC response' >&2; exit 1;; esac
    echo "$value"
}
chip=$(readreg 0200)
[ "$((chip >> 8))" -eq 40 ] || { echo 'Unexpected PMIC' >&2; exit 1; }
control=$(readreg 0f48)
watchdog=$(readreg 0f66)
# Capture helper exit status before parsing; never reuse a failed sample.
fg=$(/run/m39-fg-sample)
set -- $fg
[ "$#" -eq 2 ] || exit 1
printf 'Charger gates: main=%s current_DAC=%s; watchdog_expired=%s\n' \
    "$(((control >> 4) & 1))" "$(((control >> 3) & 1))" "$(((watchdog >> 2) & 1))"
printf 'Fresh gauge signed raw: %s (positive=net charge, negative=net discharge)\n' "$2"
printf 'Kernel cached battery voltage (mV): '
cat /sys/class/power_supply/battery/InstatVolt
printf 'Battery temperature and percentage: UNVALIDATED\n'
printf 'Kernel status/health labels are not verified hardware evidence.\n'
