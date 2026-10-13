#!/bin/sh
# Enable the encryption mode required by the project's LUKS2 volumes.
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
"$root/tools/mt6735-kernel/scripts/config" --file "$root/build/mt6735-source/.config" \
    --enable CRYPTO_XTS --enable CRYPTO_GF128MUL
make -C "$root/tools/mt6735-kernel" O="$root/build/mt6735-source" ARCH=arm64 \
    CROSS_COMPILE="$root/tools/aarch64-gcc49/bin/aarch64-linux-android-" \
    KBUILD_NOCMDDEP=1 olddefconfig
