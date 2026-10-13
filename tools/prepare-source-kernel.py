#!/usr/bin/env python3
"""Prepare a reproducible, charging-disabled MT6328 diagnostic source kernel."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent.parent
source = root / 'tools/mt6735-kernel'
output = root / 'build/mt6735-source'
output.mkdir(parents=True, exist_ok=True)

def replace(path, old, new, count=1):
    p = source / path
    text = p.read_text()
    if new in text:
        return
    assert text.count(old) == count, path
    p.write_text(text.replace(old, new))

replace('drivers/misc/mediatek/video/common/mtkfb.c',
        'int __init mtkfb_init(void)\n{\n\tint r = 0;',
        'int __init mtkfb_init(void)\n{\n\t/* M39: retain bootloader scanout; incompatible donor panel driver. */\n\treturn 0;\n#if 0\n\tint r = 0;')
replace('drivers/misc/mediatek/video/common/mtkfb.c',
        '\treturn r;\n}\n\n\nstatic void __exit mtkfb_cleanup',
        '\treturn r;\n#endif\n}\n\n\nstatic void __exit mtkfb_cleanup')
replace('drivers/misc/mediatek/video/mt6735/videox/mtk_disp_mgr.c',
        'static const unsigned long addr_min = 0x14007000;\n\tstatic const unsigned long addr_max = 0x14018000;',
        'static const unsigned long addr_min = 0xbfea0000;\n\tstatic const unsigned long addr_max = 0xbffc0000;')
replace('drivers/usb/gadget/android.c',
        'if (get_boot_mode() == KERNEL_POWER_OFF_CHARGING_BOOT || get_boot_mode() == LOW_POWER_OFF_CHARGING_BOOT) {',
        'if (0) { /* M39: honor userspace ACM configuration during charging boot. */', count=2)
replace('drivers/misc/mediatek/power/mt6735/charging_hw_pmic.c',
        'unsigned int enable = *(unsigned int *) (data);',
        'unsigned int enable = KAL_FALSE; /* M39 DIAGNOSTIC: charging disabled until board safety validation. */')
replace('drivers/misc/mediatek/aee/mrdump/mrdump_mini.c',
        'prot = pgprot_noncached(PAGE_KERNEL);',
        '/* Reserved RAM contains strings: device memory rejects unaligned loads. */\n\tprot = pgprot_writecombine(PAGE_KERNEL);')
replace('drivers/misc/mediatek/aee/mrdump/mrdump_mini.c',
        '\tmrdump_mini_elf_header_init();\n\n\tfill_psinfo',
        '\tmrdump_mini_elf_header_init();\n\tif (!mrdump_mini_ehdr)\n\t\treturn -ENOMEM;\n\n\tfill_psinfo')
for path in ['scripts/dtc/dtc-lexer.l', 'scripts/dtc/dtc-lexer.lex.c_shipped']:
    replace(path, '\nYYLTYPE yylloc;\n', '\nextern YYLTYPE yylloc;\n')
replace('mm/ksm.c',
        'static struct notifier_block ksm_fb_notifier = {\n\t.notifier_call = ksm_fb_notifier_callback,\n}',
        'static struct notifier_block ksm_fb_notifier = {\n\t.notifier_call = ksm_fb_notifier_callback,\n};')
replace('drivers/misc/mediatek/connectivity/common/common_detect/drv_init/fm_drv_init.c',
        '#ifdef CONFIG_MTK_FMRADIO',
        '#if defined(CONFIG_MTK_FMRADIO) && defined(CONFIG_MTK_FM_SUPPORT) && defined(CONFIG_MTK_FM)')

config = (root / 'analysis/boot-kernel.config').read_text()
disabled = {'MTK_GPU_SUPPORT', 'MTK_IMGSENSOR', 'MTK_CCCI_DEVICES',
            'MTK_DYNAMIC_BOOST', 'TOUCH_BOOST',
            'MTK_MLOG',
            'MTK_ECCCI_DRIVER', 'MTK_C2K_SUPPORT', 'MTK_CCCI_EXT',
            'ANDROID_BINDER_IPC', 'ANDROID_LOW_MEMORY_KILLER',
            'SECURITY_SELINUX', 'DEFAULT_SECURITY_SELINUX',
            'ANDROID_PARANOID_NETWORK'}
disabled.update(line.split('=')[0][7:] for line in config.splitlines()
                if line.startswith('CONFIG_MTK_') and
                any(x in line for x in ['_BQ24', '_BQ25', '_FAN54', '_NCP18', '_RT95', '_SWCHR']))
values = {'CUSTOM_KERNEL_LCM': '"otm1287a_hd720_dsi_vdo_e539_l521_ld"',
          'CUSTOM_KERNEL_IMGSENSOR': '""',
          'LOCALVERSION': '"-m39-diagnostic"',
          'DEFAULT_SECURITY_DAC': 'y', 'DEFAULT_SECURITY': '""',
          'LOCALVERSION_AUTO': 'n'}
seen = set()
lines = []
for line in config.splitlines():
    if line.startswith('CONFIG_'):
        name = line.split('=')[0][7:]
    elif line.startswith('# CONFIG_') and line.endswith(' is not set'):
        name = line.split()[1][7:]
    else:
        lines.append(line)
        continue
    seen.add(name)
    if name in disabled or values.get(name) == 'n':
        line = f'# CONFIG_{name} is not set'
    elif name in values:
        line = f'CONFIG_{name}={values[name]}'
    lines.append(line)
for name in values.keys() - seen:
    lines.append(f'CONFIG_{name}={values[name]}')
(output / '.config').write_text('\n'.join(lines) + '\n')
patch = subprocess.check_output(['git', '-C', str(source), 'diff'])
(root / 'artifacts/m39-source-kernel.patch').write_bytes(patch)
print(f'Prepared source patches and config: {output}')
