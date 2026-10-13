#!/bin/sh
# Read boot-mode metadata only; never writes the boot-mode attribute.
set -eu
for path in /sys/class/BOOT/BOOT/boot/boot_mode /sys/devices/virtual/BOOT/BOOT/boot/boot_mode; do
    if [ -r "$path" ]; then
        value=$(cat "$path")
        printf 'boot_mode=%s\n' "$value"
        case "$value" in
            0) echo 'boot_mode_name=normal' ;;
            8) echo 'boot_mode_name=kernel_power_off_charging' ;;
            9) echo 'boot_mode_name=low_power_off_charging' ;;
            *) echo 'boot_mode_name=other' ;;
        esac
        exit 0
    fi
done
for path in /proc/device-tree/chosen/atag,boot /proc/device-tree/chosen@0/atag,boot; do
    if [ -r "$path" ]; then
        echo 'boot_mode_source=atag,boot'
        od -An -tu4 "$path"
        exit 0
    fi
done
echo 'boot_mode_source=unavailable'
exit 1
