#!/usr/bin/env python3
"""Observe an existing bounded charge process. Never starts or restarts charging."""
import argparse
import datetime
import json
from pathlib import Path
import re
import subprocess
import time
from m39_charge_outcome import classify

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--pid', type=int, required=True)
parser.add_argument('--boot-id', required=True)
args = parser.parse_args()
status_path = root / 'logs/charger-recharge-status.json'
deadline = time.monotonic() + 1900
command = [str(root / '.venv/bin/python'), '-u', str(root / 'tools/usb-serial-console.py'),
           '--timeout', '10', '--command-timeout', '15', '--command',
           'cat /run/m39-charge-status.json; tail -n 6 /run/m39-charge.log']

def save(value):
    value['observed_at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    temporary = status_path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(status_path)

last = {}
while time.monotonic() < deadline:
    try:
        response = subprocess.run(command, capture_output=True, text=True, timeout=35)
    except (subprocess.TimeoutExpired, OSError) as error:
        last['monitor_state'] = 'interrupted'
        last['remote_state_is_current'] = False
        last['monitor_error'] = str(error)
        save(last)
        raise SystemExit('Monitoring interrupted; no charge command was replayed.') from None
    print(response.stdout, end='', flush=True)
    match = re.search(r'(\{"phase":[^\r\n]*\})', response.stdout)
    if response.returncode or not match:
        last['monitor_state'] = 'interrupted'
        last['remote_state_is_current'] = False
        last['monitor_error'] = response.stderr.strip() or 'No valid remote status received'
        save(last)
        print('Monitoring interrupted. No charge command was replayed.', flush=True)
        raise SystemExit(1)
    state = json.loads(match[1])
    if state['pid'] != args.pid or state['boot_id'] != args.boot_id:
        save({'monitor_state': 'different_process_or_boot', 'remote_state_is_current': True,
              'remote': state})
        raise SystemExit('Existing charge process or boot changed; no command replayed.')
    state['monitor_state'] = 'observed'
    state['remote_state_is_current'] = True
    last = state
    if state['phase'] not in ['preparing', 'charging']:
        state['outcome'] = classify(state, response.stdout)
        save(state)
        print(json.dumps(state), flush=True)
        raise SystemExit(0 if state['outcome'] != 'stopped_with_error' else 1)
    save(state)
    time.sleep(20)
last['monitor_state'] = 'deadline_reached'
last['remote_state_is_current'] = False
save(last)
raise SystemExit('Watcher deadline reached; no remote stop or cleanup is assumed.')
