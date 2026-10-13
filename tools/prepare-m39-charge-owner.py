#!/usr/bin/env python3
"""Install exclusive, expiring diagnostic charger ownership in source driver."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parent.parent
folder=root/'tools/mt6735-kernel/drivers/misc/mediatek/power/mt6735'
shutil.copyfile(root/'tools/m39-charge-owner.h',folder/'m39_charge_owner.h')
p=folder/'charging_hw_pmic.c'; s=p.read_text()
include='#include "m39_charge_owner.h"'
if include not in s:
    needle='kal_bool charging_type_det_done = KAL_TRUE;'
    assert s.count(needle)==1
    s=s.replace(needle,needle+'\n\n'+include)
    needle='\tif (init == -1) {'
    assert s.count(needle)==1
    s=s.replace(needle,'\tmutex_lock(&m39_owner_lock);\n'+needle)
    needle='\tif (cmd < CHARGING_CMD_NUMBER)\n\t\tstatus = charging_func[cmd] (data);\n\telse\n\t\treturn STATUS_UNSUPPORTED;\n\n\treturn status;'
    assert s.count(needle)==1
    s=s.replace(needle,'''\tif (m39_owner_active && m39_owner_mutating(cmd))
        status = STATUS_OK;
    else if (cmd < CHARGING_CMD_NUMBER)
        status = charging_func[cmd](data);
    else
        status = STATUS_UNSUPPORTED;
    mutex_unlock(&m39_owner_lock);
    return status;''')
    p.write_text(s)
print('Prepared exclusive ownership, <=1800s expiry, root-only control; charge inhibit retained.')
