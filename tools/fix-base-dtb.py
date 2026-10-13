#!/usr/bin/env python3
"""Supply missing overlay targets in the experimental base DTB, then test merge."""
from pathlib import Path
import re
import shutil
import subprocess

root = Path(__file__).resolve().parent.parent
analysis = root / 'analysis'
base = analysis / 'boot-appended-0.dtb'
patched = analysis / 'boot-base-overlay-compatible.dtb'
overlay = analysis / 'original-odmdtbo.img-400.dtb'
shutil.copyfile(base, patched)
source = (analysis / 'boot-appended-0.dts').read_text()
phandles = [int(v, 16) for v in re.findall(r'\bphandle = <0x([0-9a-f]+)>', source)]
next_phandle = max(phandles) + 1
labels = ['cdfinger', 'ma_finger', 'quiet_key']
subprocess.run(['fdtput', '-c', str(patched), '/bus/m39-overlay-targets'], check=True)
for i, label in enumerate(labels):
    node = '/bus/m39-overlay-targets/' + label.replace('_', '-')
    subprocess.run(['fdtput', '-c', str(patched), node], check=True)
    subprocess.run(['fdtput', '-t', 'x', str(patched), node, 'phandle', hex(next_phandle + i)], check=True)
    subprocess.run(['fdtput', '-t', 's', str(patched), node, 'status', 'disabled'], check=True)
    subprocess.run(['fdtput', '-t', 's', str(patched), '/__symbols__', label, node], check=True)
merged = analysis / 'merged-original-board.dtb'
subprocess.run(['fdtoverlay', '-i', str(patched), '-o', str(merged), str(overlay)], check=True)
subprocess.run(['dtc', '-I', 'dtb', '-O', 'dts', '-o', str(analysis / 'merged-original-board.dts'),
                str(merged)], check=True, stderr=subprocess.DEVNULL)
print('Original M39 overlay now applies successfully to the experimental base.')
print('Added placeholder targets for:', ', '.join(labels))
print('These satisfy overlay references; they do not implement new hardware drivers.')
