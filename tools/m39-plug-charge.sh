#!/bin/sh
# Opt-in, current-boot supervised test service. Not a production charge policy.
set -eu
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
runtime=${M39_SERVICE_RUNTIME:-/run}
usb=${M39_SERVICE_USB:-/sys/class/power_supply/usb/online}
ac=${M39_SERVICE_AC:-/sys/class/power_supply/ac/online}
owner=${M39_SERVICE_OWNER:-/sys/module/charging_hw_pmic/parameters/m39_owner_seconds}
boot_file=${M39_SERVICE_BOOT:-/proc/sys/kernel/random/boot_id}
controller=${M39_SERVICE_CONTROLLER:-/run/m39-pmic-pulse.sh}
boot=$(cat "$boot_file")
write_owner() (
    command_file="$runtime/m39-owner-command.$$"
    trap 'rm -f "$command_file"' EXIT
    trap 'exit 1' HUP INT TERM
    printf '%s\n' "$1" > "$command_file" || exit 1
    cat "$command_file" > "$owner"
)
mkdir "$runtime/m39-plug-service.lock" || { echo 'Plug service already active'; exit 1; }
pid=''
stop_file=''
sequence=0
owns_lease=0
outcome=none
status() {
    printf '{"phase":"%s","service_pid":%s,"controller_pid":"%s","boot_id":"%s","session":%s,"outcome":"%s"}\n' \
        "$1" "$$" "$pid" "$boot" "$sequence" "$outcome" > "$runtime/m39-plug-status.json.tmp"
    mv "$runtime/m39-plug-status.json.tmp" "$runtime/m39-plug-status.json"
}
completion_outcome() {
    state="$runtime/m39-charge-status.json"
    [ -r "$state" ] || { echo unverified_stop; return; }
    grep -Fq "\"boot_id\":\"$boot\"" "$state" &&
    grep -Fq "\"pid\":$pid," "$state" &&
    grep -Fq '"charging_off_verified":true' "$state" || {
        echo unverified_stop; return;
    }
    phase=$(sed -n 's/.*"phase":"\([^" ]*\)".*/\1/p' "$state")
    case "$phase" in stopped|aborted) ;; *) echo cleanup_error; return;; esac
    reason=$(sed -n 's/.*"stop_reason":"\([^" ]*\)".*/\1/p' "$state")
    case "$reason" in
        time_limit|interval_limit) [ "$phase" = stopped ] && echo time_limit || echo fault ;;
        voltage_limit)
            mv=$(sed -n 's/.*"battery_mv":\([0-9][0-9]*\).*/\1/p' "$state")
            limit=$(sed -n 's/.*"voltage_limit_mv":\([0-9][0-9]*\).*/\1/p' "$state")
            case "$mv:$limit" in *[!0-9:]*|:*|*:) echo unverified_stop;;
                *) if [ "$limit" -eq 3900 ] && [ "$mv" -ge "$limit" ]; then echo voltage_limit; else echo fault; fi;;
            esac ;;
        stop_requested|unplugged) [ "$phase" = stopped ] && echo "$reason" || echo fault ;;
        *) echo fault ;;
    esac
}
connected() {
    [ "$(cat "$usb" 2>/dev/null || echo 0)" = 1 ] ||
    [ "$(cat "$ac" 2>/dev/null || echo 0)" = 1 ]
}
stop_child() {
    if [ -n "$pid" ]; then
        if [ -n "$stop_file" ]; then : > "$stop_file"; fi
        grace=0
        while kill -0 "$pid" 2>/dev/null && [ "$grace" -lt 30 ]; do
            sleep .1
            grace=$((grace + 1))
        done
        if kill -0 "$pid" 2>/dev/null; then
            echo 'Controller did not stop cooperatively; sending TERM.' >&2
            kill -TERM "$pid" 2>/dev/null || :
        fi
        wait "$pid" 2>/dev/null || :
        outcome=$(completion_outcome)
        pid=''
    fi
    if [ -n "$stop_file" ]; then rm -f "$stop_file"; stop_file=''; fi
    if [ "$owns_lease" = 1 ]; then
        write_owner 0 || return 1
        owns_lease=0
    fi
}
cleanup() {
    trap - EXIT
    trap '' HUP INT TERM
    stop_child
    status service_stopped
    rmdir "$runtime/m39-plug-service.lock"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
# Arming must be explicit and belongs to this boot, not embedded in firmware.
[ "$(cat "$runtime/m39-plug-charge-armed" 2>/dev/null)" = "$boot" ] || {
    status not_armed; exit 1;
}
[ -x "$controller" ] && [ -r "$owner" ] || { status missing_interface; exit 1; }
previous=0
stable=0
disconnected=0
status waiting_for_power
while :; do
    if connected; then power=1; else power=0; fi
    if [ "$power" = 0 ]; then
        stop_child
        disconnected=$((disconnected + 1))
        stable=0
        if [ "$disconnected" -ge 2 ] || [ "$previous" = 0 ]; then
            previous=0
            status waiting_for_power
        else
            status waiting_for_reconnect
        fi
    elif [ "$previous" = 0 ]; then
        disconnected=0
        stable=$((stable + 1))
        if [ "$stable" -ge 2 ]; then
            previous=1
            if [ "$(cat "$owner")" != 0 ]; then
                status charger_busy
            elif write_owner 1800; then
                owns_lease=1
                outcome=none
                sequence=$((sequence + 1))
                child_log="$runtime/m39-plug-charge-$$-$sequence.log"
                stop_file="$runtime/m39-plug-charge-$$-$sequence.stop"
                rm -f "$stop_file"
                : > "$child_log"
                ln -sf "$child_log" "$runtime/m39-charge.log"
                M39_SUPERVISED=1 M39_STOP_FILE="$stop_file" "$controller" --supervised-recharge-3900 300 \
                    </dev/null > "$child_log" 2>&1 &
                pid=$!
                status charging
            else
                status lease_rejected
            fi
        fi
    elif [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then
        disconnected=0
        wait "$pid" 2>/dev/null || :
        outcome=$(completion_outcome)
        pid=''
        if [ "$owns_lease" = 1 ]; then
            write_owner 0 || { status cleanup_failed; exit 1; }
            owns_lease=0
        fi
        status session_stopped
        # Remain latched until physical power removal; never blindly replay.
    else
        disconnected=0
    fi
    sleep 1
done
