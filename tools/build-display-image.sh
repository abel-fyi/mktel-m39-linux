#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
for helper in m39-terminal display-dump; do
    clang --target=aarch64-linux-gnu -O2 -Wall -Wextra \
        -ffreestanding -fno-builtin -fno-stack-protector \
        -fno-vectorize -fno-slp-vectorize -nostdlib -static \
        -fuse-ld=lld -Wl,-e,_start "tools/$helper.c" -o "artifacts/$helper"
done
python3 tools/build-linux-probe.py \
    --dtb analysis/boot-base-overlay-compatible.dtb \
    --disable-framebuffer --fix-charger-detection --usb-serial \
    --rootfs artifacts/alpine-minirootfs-aarch64.tar.gz \
    --name alpine-m39-display --map-display-buffer \
    --display-terminal artifacts/m39-terminal \
    --package artifacts/packages/hwdata-pci.apk \
    --package artifacts/packages/fastfetch.apk
