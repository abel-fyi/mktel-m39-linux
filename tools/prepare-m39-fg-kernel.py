#!/usr/bin/env python3
"""Serialize vendor gauge transactions and expose a bounded raw snapshot."""
from pathlib import Path
import shutil

root = Path(__file__).resolve().parent.parent
folder = root / 'tools/mt6735-kernel/drivers/misc/mediatek/power/mt6735'
for name in ['m39-fg-core.h', 'm39-fg-kernel.h']:
    shutil.copyfile(root / 'tools' / name, folder / name)
path = folder / 'battery_meter_hal.c'
source = path.read_text()
include = '#include "m39-fg-kernel.h"'
if include not in source:
    needle = 'signed int bm_ctrl_cmd(BATTERY_METER_CTRL_CMD cmd, void *data)'
    assert source.count(needle) == 1
    source = source.replace(needle, include + '\n\n' + needle)
    begin = source.index(needle)
    prefix, function = source[:begin], source[begin:]
    needle = '\tif (init == -1) {'
    assert function.count(needle) == 1
    function = function.replace(needle, '\tmutex_lock(&m39_fg_lock);\n'+needle)
    needle = '\t} else\n\t\treturn STATUS_UNSUPPORTED;\n\n\treturn status;'
    assert function.count(needle) == 1
    function = function.replace(needle, '\t} else\n\t\tstatus = STATUS_UNSUPPORTED;\n\n\tmutex_unlock(&m39_fg_lock);\n\treturn status;')
    path.write_text(prefix + function)
source = path.read_text()
if 'WRITE_ONCE(m39_fg_vendor_cmd, cmd)' not in source:
    needle = '\tmutex_lock(&m39_fg_lock);'
    assert source.count(needle) == 1
    source = source.replace(needle, needle + '\n\tWRITE_ONCE(m39_fg_vendor_started, m39_fg_now());\n\tWRITE_ONCE(m39_fg_vendor_cmd, cmd);')
    needle = '\tmutex_unlock(&m39_fg_lock);'
    assert source.count(needle) == 1
    source = source.replace(needle, '\tWRITE_ONCE(m39_fg_vendor_cmd, -1);\n' + needle)
    path.write_text(source)
print('Prepared serialized bounded raw gauge endpoint; no charger limits changed.')
