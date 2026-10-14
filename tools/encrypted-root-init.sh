#!/bin/sh
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export HOME=/root SHELL=/bin/sh TERM=linux
echo m39 > /proc/sys/kernel/hostname
echo /bin/mdev > /proc/sys/kernel/hotplug
mdev -s
home_uuid=$(cat /etc/m39-home-uuid 2>/dev/null)
home_mounted=0
if [ -n "$home_uuid" ] && [ -r /etc/keys/microsd-home.key ]; then
    for candidate in /dev/mmcblk[0-9]p*; do
        [ -b "$candidate" ] || continue
        if [ "$(cryptsetup luksUUID "$candidate" 2>/dev/null)" = "$home_uuid" ]; then
            if cryptsetup open --disable-keyring --key-file /etc/keys/microsd-home.key "$candidate" m39_home &&
                mount -o noatime /dev/mapper/m39_home /home; then
                home_mounted=1
            fi
            break
        fi
    done
fi
echo 'Alpine: LUKS2 internal root; encrypted microSD /home.' > /etc/motd
if [ "$home_mounted" != 1 ]; then
    echo 'Encrypted microSD /home unavailable; internal root remains usable.' >> /etc/motd
fi
echo 'M39: switched to encrypted persistent root' > /dev/kmsg
if [ ! -e /run/m39-charge-startup.disabled ]; then
    /usr/local/libexec/m39/m39-charge-startup > /run/m39-charge-startup.log 2>&1 &
fi
/usr/local/bin/m39-terminal > /run/display-terminal.log 2>&1 &
# The validated keypad-wake idle helper reduces backlight load. Failure is
# logged and leaves the terminal usable; it must never prevent root boot.
if [ -x /usr/local/sbin/m39-screen ]; then
    /usr/local/sbin/m39-screen on 30 > /run/m39-screen-startup.log 2>&1 || :
fi
while :; do
    if [ ! -e /dev/ttyGS0 ]; then mdev -s; sleep 1; continue; fi
    stty -F /dev/ttyGS0 raw -echo
    printf '\nM39_ENCRYPTED_PERSISTENT_ALPINE\n' > /dev/ttyGS0
    /bin/sh -i < /dev/ttyGS0 > /dev/ttyGS0 2>&1
    sleep 1
done
