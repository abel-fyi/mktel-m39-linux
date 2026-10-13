#!/bin/sh
# One bounded experimental session per boot, never an unattended full-charge policy.
set -eu
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
runtime=${M39_START_RUNTIME:-/run}
usb=${M39_START_USB:-/sys/class/power_supply/usb/online}
ac=${M39_START_AC:-/sys/class/power_supply/ac/online}
voltage=${M39_START_VOLTAGE:-/sys/class/power_supply/battery/batt_vol}
command=${M39_START_COMMAND:-/usr/local/sbin/m39-charge}
boot_file=${M39_START_BOOT:-/proc/sys/kernel/random/boot_id}
boot=$(cat "$boot_file")
status() {
    printf '{"phase":"%s","boot_id":"%s","temperature_support":"deferred"}\n' "$1" "$boot" > "$runtime/m39-charge-startup.json.tmp"
    mv "$runtime/m39-charge-startup.json.tmp" "$runtime/m39-charge-startup.json"
}
mkdir "$runtime/m39-charge-startup.lock" || exit 1
trap 'rmdir "$runtime/m39-charge-startup.lock"' EXIT
trap 'status interrupted; exit 1' HUP INT TERM
stable=0
status waiting_for_power
while :; do
    if [ -e "$runtime/m39-charge-startup.disabled" ]; then status disabled; exit 0; fi
    if [ "$(cat "$usb" 2>/dev/null || echo 0)" = 1 ] || [ "$(cat "$ac" 2>/dev/null || echo 0)" = 1 ]; then
        stable=$((stable + 1))
    else
        stable=0
    fi
    [ "$stable" -lt 2 ] || break
    sleep 1
done
mv=$(cat "$voltage") || { status voltage_unavailable; exit 1; }
case "$mv" in ''|*[!0-9]*) status voltage_invalid; exit 1;; esac
# batt_vol is in microvolts. Do not run a watchdog pulse at the voltage ceiling.
[ "$mv" -lt 3900000 ] || { status voltage_limit; exit 0; }
[ "$mv" -ge 3200000 ] || { status voltage_too_low; exit 1; }
[ ! -e "$runtime/m39-charge-startup.disabled" ] || { status disabled; exit 0; }
status validating_watchdog
if M39_STARTUP=1 "$command" arm; then
    status armed
else
    status arm_failed
    exit 1
fi
