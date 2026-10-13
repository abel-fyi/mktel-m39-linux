#!/bin/sh
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export HOME=/root SHELL=/bin/sh TERM=linux
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t tmpfs -o mode=0755 tmpfs /dev
mknod /dev/console c 5 1
mknod /dev/null c 1 3
mknod /dev/kmsg c 1 11
chmod 666 /dev/null
mkdir -p /dev/pts /run /newroot
mount -t devpts devpts /dev/pts
mount -t tmpfs tmpfs /run
ln -s /proc/self/fd /dev/fd
ln -s /proc/self/fd/0 /dev/stdin
ln -s /proc/self/fd/1 /dev/stdout
ln -s /proc/self/fd/2 /dev/stderr
echo /bin/mdev > /proc/sys/kernel/hotplug
mdev -s
echo m39-unlock > /proc/sys/kernel/hostname
if [ -w /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq ]; then
    echo 221000 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq
fi
apk add --no-network /opt/packages/*.apk > /run/packages.log 2>&1
g=/sys/class/android_usb/android0
echo 0 > "$g/enable"
echo 18d1 > "$g/idVendor"
echo 4ee7 > "$g/idProduct"
echo MKTEL > "$g/iManufacturer"
echo Native-Linux-serial > "$g/iProduct"
echo m39-linux-serial > "$g/iSerial"
if [ -e "$g/f_acm/instances" ]; then echo 1 > "$g/f_acm/instances"; fi
echo acm > "$g/functions"
echo 1 > "$g/enable"
mdev -s
# Charging does not depend on unlocking encrypted storage. The helper remains
# bounded and is stopped before switching roots below.
/usr/local/libexec/m39/m39-charge-startup > /run/m39-charge-startup.log 2>&1 &
/usr/local/bin/m39-terminal > /run/display-terminal.log 2>&1 &
display_pid=$!
serial_loop() {
    while :; do
        if [ ! -e /dev/ttyGS0 ]; then mdev -s; sleep 1; continue; fi
        stty -F /dev/ttyGS0 raw -echo
        printf '\nM39_LUKS2_RECOVERY_CONSOLE\n' > /dev/ttyGS0
        /bin/sh -i < /dev/ttyGS0 > /dev/ttyGS0 2>&1 &
        echo "$!" > /run/m39-serial-child.pid
        wait "$!"
        sleep 1
    done
}
serial_loop &
serial_pid=$!
while [ ! -e /run/m39-root.ready ]; do sleep 1; done
if [ ! -x /newroot/sbin/m39-init ]; then
    echo 'Encrypted root lacks m39-init; remaining in recovery.' > /dev/kmsg
    while :; do sleep 10; done
fi
# No charge controller may retain paths into the old initramfs across switch_root.
user_stopped=0
[ ! -e /run/m39-charge-startup.disabled ] || user_stopped=1
# An unlock can finish while startup is still validating watchdog expiry.
# stop cancels startup immediately; give that bounded test time to release its lease.
stopped=0
for attempt in 1 2 3 4 5 6 7 8 9 10 11 12; do
    if /usr/local/sbin/m39-charge stop >> /run/m39-unlock-charge-stop.log 2>&1; then
        stopped=1
        break
    fi
    sleep 1
done
if [ "$stopped" != 1 ]; then
    echo 'Unable to stop charging for root transition; remaining in recovery.' > /dev/kmsg
    while :; do sleep 10; done
fi
[ "$user_stopped" = 1 ] || rm -f /run/m39-charge-startup.disabled
# Interactive ash ignores TERM; stop the respawner first, then its shell.
# Otherwise the old-root shell survives switch_root and competes for ttyGS0.
kill -KILL "$serial_pid" 2>/dev/null
kill "$display_pid" 2>/dev/null
if [ -f /run/m39-serial-child.pid ]; then
    kill -KILL "$(cat /run/m39-serial-child.pid)" 2>/dev/null
fi
sleep 1
for directory in proc sys dev run; do
    mkdir -p "/newroot/$directory"
    mount --move "/$directory" "/newroot/$directory" || {
        echo "Unable to move /$directory" > /dev/kmsg
        while :; do sleep 10; done
    }
done
exec /bin/busybox switch_root /newroot /sbin/m39-init
