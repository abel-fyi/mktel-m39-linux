#!/usr/bin/env python3
"""Read storage preparation progress without starting or resuming work."""
import json
from pathlib import Path
import re
import subprocess
import sys

root = Path(__file__).resolve().parent.parent
result = subprocess.run([
    str(root / '.venv/bin/python'), str(root / 'tools/usb-serial-console.py'),
    '--timeout', '10', '--command-timeout', '15', '--command',
    'cat /run/m39-root-provision.json; cat /run/m39-storage-power-pause.txt 2>/dev/null'
], capture_output=True, text=True)
match = re.search(r'\{"phase"[^\r\n]*\}', result.stdout)
if result.returncode or not match:
    print('Could not read progress. Stop any other USB console/watcher and retry.')
    print(result.stderr.strip() or result.stdout.strip())
    sys.exit(1)
state = json.loads(match.group())
written, total = state['written_bytes'], state['total_bytes']
print('Phase:', state['phase'])
if total:
    print(f'{100 * written / total:.1f}% cleared — {written / 1e9:.2f} / {total / 1e9:.2f} GB')
for line in result.stdout.splitlines():
    if line.startswith('Storage paused:'):
        print(line)
if state['phase'] == 'complete':
    print('Root preparation complete; encrypted boot still needs verification.')
