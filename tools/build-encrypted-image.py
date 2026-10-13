#!/usr/bin/env python3
"""Rebuild the unencrypted bootstrap for the encrypted internal Alpine root.

Reads only public volume metadata, signed APKs, official minirootfs and source
scripts. No credential or home-unlock key is included in the boot ramdisk.
"""
import json
import subprocess
from pathlib import Path

root=Path(__file__).resolve().parent.parent
metadata=json.loads((root/'artifacts/encrypted-internal-root.json').read_text())
script=(root/'tools/encrypted-unlock-template.sh').read_text()
script=script.replace('@LUKS_UUID@',metadata['luks_uuid'])
script=script.replace('LUKS2 microSD unlock','LUKS2 internal root unlock')
script=script.replace('Waiting for the encrypted microSD','Waiting for encrypted internal root')
(root/'artifacts/m39-unlock').write_text(script)
subprocess.run(['clang','--target=aarch64-linux-gnu','-O2','-Wall','-Wextra',
 '-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-vectorize',
 '-fno-slp-vectorize','-nostdlib','-static','-fuse-ld=lld','-Wl,-e,_start',
 '-DM39_STARTUP_COMMAND="/sbin/m39-unlock"','tools/m39-terminal.c',
 '-o','artifacts/m39-unlock-terminal'],cwd=root,check=True)
args=['python3','tools/build-linux-probe.py','--dtb','analysis/boot-base-overlay-compatible.dtb',
 '--disable-framebuffer','--fix-charger-detection','--usb-serial','--rootfs',
 'artifacts/alpine-minirootfs-aarch64.tar.gz','--name','alpine-m39-encrypted',
 '--map-display-buffer','--display-terminal','artifacts/m39-unlock-terminal',
 '--init-file','tools/encrypted-ram-init.sh','--extra-file','artifacts/m39-unlock:/sbin/m39-unlock']
for package in sorted((root/'artifacts/packages').glob('*.apk')):
 args+=['--package',str(package.relative_to(root))]
subprocess.run(args,cwd=root,check=True)
