#!/bin/sh
# Run after encrypted-root handoff. Credentials never enter the boot image.
set -eu
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
config=/etc/wpa_supplicant/wpa_supplicant.conf
test -r "$config"
mkdir /run/m39-wifi.lock 2>/dev/null || exit 0
trap 'rmdir /run/m39-wifi.lock' EXIT
mtinit -safe > /run/m39-mtinit.log 2>&1
if ! pidof mtdaemon >/dev/null; then
    nohup mtdaemon -m 3 -p /etc/firmware </dev/null > /run/m39-mtdaemon.log 2>&1 &
    echo "$!" > /run/m39-mtdaemon.pid
fi
if [ ! -d /sys/class/net/wlan0 ]; then
    echo 1 > /dev/wmtWifi
fi
ip link set wlan0 up
if ! pidof wpa_supplicant >/dev/null; then
    wpa_supplicant -B -D nl80211 -i wlan0 -c "$config" -P /run/m39-wpa.pid
fi
if ! pidof udhcpc >/dev/null; then
    nohup udhcpc -i wlan0 -b -p /run/m39-udhcpc.pid -t 4 -T 3 \
        </dev/null > /run/m39-dhcp.log 2>&1 &
fi
# Bound startup waiting; wpa_supplicant remains available to reconnect later.
attempt=0
until wpa_cli -i wlan0 status | grep -q '^wpa_state=COMPLETED$'; do
    attempt=$((attempt + 1))
    [ "$attempt" -lt 30 ] || exit 1
    sleep 1
done
