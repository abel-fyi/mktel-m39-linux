#!/usr/bin/env python3
"""Build the small freestanding gauge helper with the existing AOSP toolchain."""
from pathlib import Path
import hashlib
import json
import subprocess

root = Path(__file__).resolve().parent.parent
source = root / 'tools/m39-fg-sample.c'
output = root / 'artifacts/m39-fg-sample'
compiler = root / 'tools/aarch64-gcc49/bin/aarch64-linux-android-gcc'
flags = ['-std=gnu99', '-Os', '-Wall', '-Wextra', '-Werror', '-ffreestanding',
         '-fno-builtin', '-fno-stack-protector', '-nostdlib', '-static', '-Wl,-e,_start']
subprocess.run([str(compiler), *flags, '-o', str(output), str(source)], check=True)
metadata = {
    'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'binary_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
    'compiler': str(compiler.relative_to(root)), 'flags': flags,
    'charger_control_writes': False, 'kernel_or_storage_writes': False,
}
(root / 'artifacts/m39-fg-sample.json').write_text(json.dumps(metadata, indent=2) + '\n')
print(json.dumps(metadata, indent=2))
