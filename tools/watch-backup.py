#!/usr/bin/env python3
"""Validate and hash the full dump after its existing reader exits."""
import argparse
import hashlib
import json
import time
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('pid', type=int)
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
backup = root / 'backups/initial/emmc-user.bin'
status = root / 'logs/backup-status.json'
expected = 0x3A3E00000
process = Path('/proc') / str(args.pid) / 'cmdline'

def save(state, **extra):
    value = dict(state=state, bytes=backup.stat().st_size if backup.exists() else 0,
                 expected_bytes=expected, timestamp=time.time(), **extra)
    temporary = status.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(status)

while True:
    try:
        command = process.read_bytes()
    except FileNotFoundError:
        break
    if b'mtk.py' not in command or b'emmc-user.bin' not in command:
        break
    save('reading')
    time.sleep(5)

if not backup.exists() or backup.stat().st_size != expected:
    save('incomplete', message='Reader stopped before expected full dump size.')
    raise SystemExit(1)

save('hashing')
digest = hashlib.sha256()
with backup.open('rb') as stream:
    while chunk := stream.read(8 * 1024 * 1024):
        digest.update(chunk)
checksum = digest.hexdigest()
backup.with_suffix('.sha256').write_text(checksum + '  ' + backup.name + '\n')
save('complete', sha256=checksum,
     message='Expected file length confirmed and local SHA-256 saved; no second phone read performed.')
print('Full backup complete:', backup, flush=True)
