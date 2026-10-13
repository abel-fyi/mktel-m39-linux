"""Fault-inject the actual premeasurement watchdog checks; no hardware access."""
from pathlib import Path
import os
import subprocess
import tempfile

source = Path(__file__).with_name('m39-pmic-pulse.sh').read_text()
start = source.index('    if [ "$supervised_run" -eq 1 ]; then', source.index('    sleep 1\n', source.index('watchdog_observed=0')))
body = source[start:source.index('\n    guard', start)]
fixture = '''set -eu
supervised_run=1
requires_owner=1
owner_path=mock
cv_code=3
current_code=13
stop_file=$STOP
fail() { echo "$*" >&2; exit 1; }
number() { if [ "$FAULT" = lease ]; then echo 0; else echo 100; fi; }
readreg() {
 case "$1" in
  0f48) value=24; bad=0;;
  0f66) value=1; bad=5;;
  0f62) value=16; bad=17;;
  0f4e) value=3; bad=13;;
  0f50) value=13; bad=0;;
  0f7a) value=68; bad=0;;
  *) exit 2;;
 esac
 if [ "$FAULT" = "$1" ]; then echo "$bad"; else echo "$value"; fi
}
writereg() { echo "$*" >> "$LOG"; }
for iteration in 1; do
''' + body + '\ndone\n'

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    for fault in ['none', 'lease', '0f48', '0f66', '0f62', '0f4e', '0f50', '0f7a', 'stop']:
        log = root / (fault + '.log')
        stop = root / (fault + '.stop')
        if fault == 'stop':
            stop.touch()
        result = subprocess.run(['sh', '-c', fixture], capture_output=True, text=True,
                                env=dict(os.environ, FAULT=fault, LOG=str(log), STOP=str(stop)))
        writes = log.read_text() if log.exists() else ''
        if fault == 'none':
            assert result.returncode == 0, result.stderr
            assert writes == '0f62 272\n', writes
        else:
            assert not writes, (fault, writes)
            assert result.returncode == (0 if fault == 'stop' else 1), (fault, result.stderr)
print('PASS: refresh requires active lease, enabled charger, unexpired four-second watchdog, reviewed limits/mode and no stop request.')
