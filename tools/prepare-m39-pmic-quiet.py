#!/usr/bin/env python3
"""Avoid unconditional printk traffic in the PMIC debug sysfs hot path."""
from pathlib import Path
p=Path(__file__).resolve().parent/'mt6735-kernel/drivers/misc/mediatek/power/mt6735/pmic.c'
s=p.read_text();a=s.index('static ssize_t show_pmic_access(');b=s.index('\nstatic DEVICE_ATTR(pmic_access',a)
f=s[a:b]
assert 'M39: never acknowledge failed PMIC' in f
if 'pr_err' in f:
 f=f.replace('pr_err','pr_debug')
 p.write_text(s[:a]+f+s[b:])
print('PMIC successful-access logging is debug-only; parse/transport error returns unchanged.')
