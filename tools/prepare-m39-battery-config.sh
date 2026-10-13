#!/bin/sh
# Run Alpine as a normal system even when LK supplies a charger-mode boot tag.
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
# This vendor tree references a charger-only enum outside its config guard.
python3 - "$root" <<'PYFIX'
from pathlib import Path
import sys
p=Path(sys.argv[1])/'tools/mt6735-kernel/drivers/power/mediatek/battery_common.c'
s=p.read_text()
old='                                    || (g_platform_boot_mode == KERNEL_POWER_OFF_CHARGING_BOOT) \n'
new='                                    #ifdef CONFIG_MTK_KERNEL_POWER_OFF_CHARGING\n                                    || (g_platform_boot_mode == KERNEL_POWER_OFF_CHARGING_BOOT)\n                                    #endif\n'
if old in s:
    assert s.count(old)==1
    p.write_text(s.replace(old,new))
else:
    assert new in s, 'Unexpected vendor source; inspect before patching'
PYFIX
"$root/tools/mt6735-kernel/scripts/config" --file "$root/build/mt6735-source/.config" \
    --disable MTK_KERNEL_POWER_OFF_CHARGING
make -C "$root/tools/mt6735-kernel" O="$root/build/mt6735-source" ARCH=arm64 \
    CROSS_COMPILE="$root/tools/aarch64-gcc49/bin/aarch64-linux-android-" \
    KBUILD_NOCMDDEP=1 olddefconfig
