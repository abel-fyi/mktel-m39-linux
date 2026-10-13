#!/bin/sh
# A two-minute optional test, never started automatically on boot.
set -eu
mkdir /run/m39-screen-idle.lock
child=''
cleanup() {
    trap - EXIT HUP INT TERM
    if [ -n "$child" ]; then kill -TERM "$child" 2>/dev/null || :; wait "$child" 2>/dev/null || :; fi
    # Buffered sysfs write; keypad processing remains owned by the terminal.
    printf '255\n' > /run/m39-screen-restore.$$
    cat /run/m39-screen-restore.$$ > /sys/class/leds/lcd-backlight/brightness
    rm -f /run/m39-screen-restore.$$
    rmdir /run/m39-screen-idle.lock
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
/run/m39-screen-idle &
child=$!
wait "$child"
child=''
