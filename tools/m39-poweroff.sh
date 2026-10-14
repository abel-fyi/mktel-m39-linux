#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Custom PID 1 does not implement BusyBox init's shutdown signals. Prepare
# persistent filesystems before asking the kernel directly to power down.
set -eu
umask 077
[ "$(id -u)" = 0 ]
lock=/run/m39-poweroff.lock
mkdir "$lock" || { echo 'Shutdown already in progress.' >&2; exit 1; }
trap 'rmdir "$lock"' EXIT
trap 'exit 1' HUP INT TERM
m39-charge stop
count=0
while [ -d /run/m39-broker.lock ] || [ -d /run/m39-plug-service.lock ] ||
      [ -d /run/m39-pmic-pulse.lock ] || [ -d /run/m39-charge-startup.lock ]; do
    count=$((count + 1))
    [ "$count" -lt 150 ] || { echo 'Charging cleanup still active; shutdown refused.' >&2; exit 1; }
    sleep .1
done
owner=/sys/module/charging_hw_pmic/parameters/m39_owner_seconds
[ "$(cat "$owner")" = 0 ]
# A zero lease alone is insufficient. Confirm both charger enable gates OFF.
request=/run/m39-poweroff-pmic.$$
trap 'rm -f "$request"; rmdir "$lock"' EXIT
printf '0f48\n' > "$request"
cat "$request" > /sys/devices/platform/mt-pmic/pmic_access
gates=$(cat /sys/devices/platform/mt-pmic/pmic_access)
case "$gates" in ''|*[!0-9]*|0[0-9]*) exit 1;; esac
[ "$gates" -le 65535 ] && [ "$((gates & 24))" = 0 ]
sync
if grep -q ' /home ' /proc/mounts; then mount -o remount,ro /home; fi
mount -o remount,ro /
sync
echo 'M39: filesystems read-only; requesting kernel poweroff.' > /dev/kmsg
/bin/busybox poweroff -f
echo 'Kernel poweroff returned unexpectedly; charging remains stopped.' >&2
exit 1
