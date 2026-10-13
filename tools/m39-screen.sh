#!/bin/sh
# Optional backlight idle mode, independent of charging and system suspend.
set -eu
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
boot=$(cat /proc/sys/kernel/random/boot_id)
record=/run/m39-screen-idle.pid
case "${1:-status}" in
on)
    idle=${2:-60}
    case "$idle" in ''|*[!0-9]*) exit 2;; esac
    [ "$idle" -ge 5 ] && [ "$idle" -le 600 ]
    [ ! -d /run/m39-screen-idle.lock ]
    nohup sh /usr/local/sbin/m39-screen run "$idle" 0 </dev/null >/run/m39-screen-idle.log 2>&1 &
    sleep 1
    [ -r "$record" ]
    echo "Backlight idle enabled after ${idle}s; any keypad press wakes it."
    ;;
run)
    idle=$2 lifetime=$3
    case "$idle:$lifetime" in *[!0-9:]*|:*) exit 2;; esac
    [ "$idle" -ge 5 ] && [ "$idle" -le 600 ]
    [ "$lifetime" -ge 0 ] && [ "$lifetime" -le 86400 ]
    mkdir /run/m39-screen-idle.lock
    child=''
    cleanup() {
        trap - EXIT HUP INT TERM
        if [ -n "$child" ]; then kill -TERM "$child" 2>/dev/null || :; wait "$child" 2>/dev/null || :; fi
        printf '255\n' > /run/m39-screen-restore.$$
        cat /run/m39-screen-restore.$$ > /sys/class/leds/lcd-backlight/brightness
        rm -f /run/m39-screen-restore.$$ "$record" /run/m39-screen-idle-config
        rmdir /run/m39-screen-idle.lock
    }
    trap cleanup EXIT
    trap 'exit 1' HUP INT TERM
    printf '%s %s\n' "$$" "$boot" > "$record"
    printf '%s %s\n' "$idle" "$lifetime" > /run/m39-screen-idle-config
    /usr/local/libexec/m39/m39-screen-idle &
    child=$!
    wait "$child"
    child=''
    ;;
off)
    if [ -r "$record" ]; then
        read -r pid recorded_boot < "$record"
        [ "$recorded_boot" = "$boot" ]
        case "$pid" in ''|*[!0-9]*) exit 1;; esac
        if kill -0 "$pid" 2>/dev/null; then
            tr '\000' ' ' < "/proc/$pid/cmdline" | grep -Fq 'm39-screen run '
            kill -TERM "$pid"
            count=0
            while kill -0 "$pid" 2>/dev/null; do
                count=$((count+1)); [ "$count" -lt 50 ]; sleep .1
            done
        else
            # A dead supervisor makes the worker restore255 and exit within
            # one poll interval. Do not signal an unrelated/reused process.
            sleep 2
            rm -f "$record" /run/m39-screen-idle-config
            rmdir /run/m39-screen-idle.lock
        fi
    fi
    [ ! -d /run/m39-screen-idle.lock ]
    printf '255\n' > /run/m39-screen-restore.$$
    cat /run/m39-screen-restore.$$ > /sys/class/leds/lcd-backlight/brightness
    rm -f /run/m39-screen-restore.$$
    echo 'Backlight idle disabled; brightness restored to255.'
    ;;
status)
    if [ -r "$record" ]; then
        read -r pid recorded_boot < "$record"
        [ "$recorded_boot" = "$boot" ]
        kill -0 "$pid" 2>/dev/null || { echo 'Stale idle supervisor; use m39-screen off to clean up.'; exit 1; }
        read -r idle lifetime < /run/m39-screen-idle-config
        value=$(cat /sys/class/leds/lcd-backlight/brightness)
        case "$value" in 0) state=off;; 255) state=on;; *) state=unknown;; esac
        echo "Backlight idle: ${idle}s; backlight currently $state."
    else echo 'Backlight idle inactive.'; fi
    ;;
*) echo 'Usage: m39-screen [on [5..600 seconds]|off|status]' >&2; exit 2;;
esac
