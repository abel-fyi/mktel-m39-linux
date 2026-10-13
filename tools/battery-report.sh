#!/bin/sh
# Read-only diagnostics: leave charger policy and storage untouched.
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
while :; do
    printf '\033[2J\033[HM39 battery diagnostics\n'
    printf 'Uptime: '; cut -d ' ' -f 1 /proc/uptime
    for supply in /sys/class/power_supply/*; do
        [ -d "$supply" ] || continue
        printf '\n%s\n' "${supply##*/}"
        for name in status present online capacity voltage_now current_now temp batt_vol batt_temp; do
            [ -r "$supply/$name" ] || continue
            printf '%s: %s\n' "$name" "$(cat "$supply/$name")"
        done
    done
    printf '\nVoltage: uV; temp: tenths C\n'
    printf 'Donor charging driver NOT verified\n'
    printf 'Reported current/temp may be wrong\n'
    sleep 10
done
