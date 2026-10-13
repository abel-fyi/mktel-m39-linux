#!/bin/sh
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export TERM=linux
uuid=@LUKS_UUID@
printf '\033[2J\033[HMKTEL M39 - encrypted Alpine\n\n'
printf 'LUKS2 microSD unlock\n\n'
printf 'Use the number keys.\nCentre OK: submit.\nTop-right key: delete digit.\n\n'
while :; do
    device=
    for candidate in /dev/mmcblk[0-9]p*; do
        [ -b "$candidate" ] || continue
        if [ "$(cryptsetup luksUUID "$candidate" 2>/dev/null)" = "$uuid" ]; then
            device=$candidate
            break
        fi
    done
    if [ -z "$device" ]; then
        printf 'Waiting for the encrypted microSD...\n'
        sleep 5
        continue
    fi
    if [ ! -b /dev/mapper/m39_root ]; then
        if ! cryptsetup open --disable-keyring --tries 1 "$device" m39_root; then
            printf '\nUnlock failed. Try again.\n\n'
            continue
        fi
    fi
    if ! mount -o noatime /dev/mapper/m39_root /newroot; then
        printf '\nUnable to mount encrypted root.\n'
        sleep 5
        continue
    fi
    if [ "$(cat /newroot/etc/m39-rootfs-id 2>/dev/null)" != "$uuid" ]; then
        printf '\nRoot identity check failed.\n'
        umount /newroot
        sleep 5
        continue
    fi
    printf '%s\n' "$uuid" > /run/m39-root.ready
    printf '\nUnlocked. Starting Alpine...\n'
    while :; do sleep 10; done
done
