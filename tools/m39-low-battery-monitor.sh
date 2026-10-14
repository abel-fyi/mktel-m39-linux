#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Observation only until the discharge threshold is validated. No PMIC writes,
# extra hardware reads, charging changes or poweroff calls.
set -eu
umask 077
[ "${1:-}" = --observe ] || { echo 'Only --observe is enabled; cutoff calibration is pending.' >&2; exit 2; }
runtime=${M39_LOW_RUNTIME:-/run}
report=${M39_LOW_REPORT:-/usr/local/sbin/m39-battery-status}
policy=${M39_LOW_POLICY:-/usr/local/libexec/m39/m39-low-battery-policy.sh}
boot_file=${M39_LOW_BOOT:-/proc/sys/kernel/random/boot_id}
uptime_file=${M39_LOW_UPTIME:-/proc/uptime}
pause=${M39_LOW_SLEEP:-sleep}
. "$policy"
boot=$(cat "$boot_file")
mkdir "$runtime/m39-low-battery.lock" || exit 1
snapshot="$runtime/m39-low-battery-snapshot.$$"
trap 'rm -f "$snapshot"; rmdir "$runtime/m39-low-battery.lock"' EXIT
trap 'exit 0' HUP INT TERM
field() { sed -n "s/.*\"$1\":[[:space:]]*\"\{0,1\}\([^\",}]*\).*/\1/p" "$snapshot"; }
samples=0
last_stamp=-1
last_low=-1
while :; do
    [ "$(cat "$boot_file")" = "$boot" ]
    read up rest < "$uptime_file"
    now=${up%%.*}
    if "$report" > "$snapshot"; then
        voltage=$(field voltage_mv); input=$(field input_present); age=$(field sample_age_seconds)
    else voltage=null; input=null; age=null; fi
    preliminary=$(m39_low_battery_decide "$voltage" "$input" "$age" 0)
    if [ "$preliminary" = low_pending ]; then
        stamp=$((now-age))
        # Count only distinct readings separated by at least five seconds.
        # A missing observation or a long gap resets the debounce window.
        if [ "$last_low" -ge 0 ] && [ "$((now-last_low))" -gt 15 ]; then samples=0; last_stamp=-1; fi
        if [ "$last_stamp" -lt 0 ] || [ "$((stamp-last_stamp))" -ge 5 ]; then
            samples=$((samples+1)); last_stamp=$stamp
        fi
        last_low=$now
    else samples=0; last_stamp=-1; last_low=-1; fi
    state=$(m39_low_battery_decide "$voltage" "$input" "$age" "$samples")
    case "$voltage" in ''|*[!0-9]*|0[0-9]*) voltage=null;; esac
    printf '{"phase":"%s","mode":"observe","pid":%s,"boot_id":"%s","uptime_seconds":%s,"voltage_mv":%s,"low_samples":%s,"candidate_cutoff_mv":3400,"shutdown_enabled":false}\n' \
        "$state" "$$" "$boot" "$now" "$voltage" "$samples" > "$runtime/m39-low-battery.json.tmp"
    mv "$runtime/m39-low-battery.json.tmp" "$runtime/m39-low-battery.json"
    "$pause" 5
done
