#!/usr/bin/env python3
"""Propagate parse/PMIC transport errors rather than acknowledge failed debug I/O."""
from pathlib import Path
root=Path(__file__).resolve().parent.parent
p=root/'tools/mt6735-kernel/drivers/misc/mediatek/power/mt6735/pmic.c'
s=p.read_text();start=s.index('static ssize_t store_pmic_access(');end=s.index('\n}',start)+2
f=s[start:end]
if 'M39: never acknowledge failed PMIC' not in f:
 a='\t\tif (size > 5) {\n\t\t\t/*reg_value'
 assert f.count(a)==1
 f=f.replace(a,'\t\tif (ret)\n\t\t\treturn ret; /* M39: reject invalid addresses before hardware access. */\n\n'+a)
 a='\t\t\tret = kstrtou32(val, 16, (unsigned int *)&reg_value);'
 assert f.count(a)==1
 f=f.replace(a,a+'\n\t\t\tif (ret)\n\t\t\t\treturn ret;')
 a='ret = pmic_read_interface(reg_address, &g_reg_value, 0xFFFF, 0x0);'
 assert f.count(a)==1
 f=f.replace(a,'ret = pmic_read_interface(reg_address, &reg_value, 0xFFFF, 0x0);\n\t\t\tif (!ret)\n\t\t\t\tg_reg_value = reg_value;')
 a='\treturn size;'
 assert f.count(a)==1
 f=f.replace(a,'\t/* M39: never acknowledge failed PMIC transport as successful sysfs I/O. */\n\tif (ret)\n\t\treturn ret < 0 ? ret : -EIO;\n'+a)
 p.write_text(s[:start]+f+s[end:])
print('PMIC access now reports parse/transport errors and publishes only successful reads.')
