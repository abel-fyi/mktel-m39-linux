#!/bin/sh
# Explicit opt-in diagnostic charging. No automatic arming at startup.
set -eu
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
bundle=/usr/local/libexec/m39
owner=/sys/module/charging_hw_pmic/parameters/m39_owner_seconds
boot=$(cat /proc/sys/kernel/random/boot_id)
write_owner() (
    command_file=/run/m39-owner-command.$$
    trap 'rm -f "$command_file"' EXIT
    trap 'exit 1' HUP INT TERM
    printf '%s\n' "$1" > "$command_file" || exit 1
    cat "$command_file" > "$owner"
)
case "${1:-status}" in
status)
    echo 'Policy: supervised; <=300mA nominal, 3.9V ceiling, <=1770s per connection.'
    echo 'Cell temperature, charge percentage and capacity remain unvalidated.'
    for file in /run/m39-charge-startup.json /run/m39-plug-status.json /run/m39-charge-status.json; do
        if [ -r "$file" ]; then cat "$file"; else echo "$file: inactive"; fi
    done
    ;;
arm)
    [ "$(id -u)" = 0 ]
    [ ! -d /run/m39-stop.lock ]
    if [ "${M39_STARTUP:-0}" = 1 ]; then
        [ ! -e /run/m39-charge-startup.disabled ] || exit 1
    else
        rm -f /run/m39-charge-startup.disabled
    fi
    [ -r "$owner" ] && [ "$(cat "$owner")" = 0 ]
    [ ! -d /run/m39-plug-service.lock ]
    [ ! -d /run/m39-pmic-pulse.lock ]
    # Refuse to replace helpers while any controller/service is active.
    for name in m39-pmic-pulse.sh m39-plug-charge.sh m39-fg-sample; do
        cp "$bundle/$name" "/run/$name"
        chmod 755 "/run/$name"
    done
    # A fresh hardware-cutoff test is required after every boot. The test
    # intentionally lets the unchanged four-second watchdog expire.
    # Ownership being zero does not prove the hardware gates stayed off during
    # a reconnect. Establish and verify OFF through the kernel before claiming.
    write_owner 0
    write_owner 60
    if ! M39_SUPERVISED=1 /run/m39-pmic-pulse.sh --watchdog-test-3900 200 \
            > /run/m39-arm-watchdog.log 2>&1; then
        write_owner 0
        echo 'Arming failed; no charging service started. See /run/m39-arm-watchdog.log.' >&2
        exit 1
    fi
    [ "$(cat "$owner")" = 0 ]
    [ "$(cat /run/m39-watchdog-validated)" = "$(uname -r)" ]
    [ ! -e /run/m39-charge-startup.disabled ] || { write_owner 0; exit 1; }
    printf '%s\n' "$boot" > /run/m39-plug-charge-armed
    nohup sh /run/m39-plug-charge.sh </dev/null >/run/m39-plug-service.log 2>&1 &
    echo 'Bounded diagnostic charging armed for this boot; not unattended/full charging.'
    ;;
stop)
    [ "$(id -u)" = 0 ]
    # Internal policy stops preserve an operator's cancellation flag.
    if [ "${M39_STOP_INTERNAL:-0}" != 1 ]; then
        : > /run/m39-charge-startup.disabled
    fi
    # Manual stop and broker cleanup may arrive together. Serialize signaling
    # so a second TERM cannot interrupt the service's existing cleanup.
    attempts=0
    until mkdir /run/m39-stop.lock 2>/dev/null; do
        attempts=$((attempts + 1))
        [ "$attempts" -lt 150 ] || exit 1
        sleep .1
    done
    trap 'rmdir /run/m39-stop.lock' EXIT
    trap 'exit 1' HUP INT TERM
    rm -f /run/m39-plug-charge-armed
    if [ -d /run/m39-plug-service.lock ]; then
        grep -Fq "\"boot_id\":\"$boot\"" /run/m39-plug-status.json
        pid=$(sed -n 's/.*"service_pid":\([0-9][0-9]*\).*/\1/p' /run/m39-plug-status.json)
        case "$pid" in ''|*[!0-9]*) exit 1;; esac
        tr '\000' ' ' < "/proc/$pid/cmdline" | grep -Fq m39-plug-charge.sh
        kill -TERM "$pid"
        count=0
        while kill -0 "$pid" 2>/dev/null; do
            count=$((count + 1))
            [ "$count" -lt 100 ] || { echo 'Stop did not finish; inspect runtime status.' >&2; exit 1; }
            sleep .1
        done
    fi
    [ "$(cat "$owner")" = 0 ]
    echo 'Diagnostic service stopped and charger lease released.'
    ;;
*) echo 'Usage: m39-charge [status|arm|stop]' >&2; exit 2;;
esac
