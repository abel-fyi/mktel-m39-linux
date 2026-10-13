"""Check service completion against current-controller cleanup evidence."""
from pathlib import Path
import json, os, subprocess, tempfile
source = Path(__file__).with_name('m39-plug-charge.sh').read_text()
body = source[source.index('completion_outcome() {'):source.index('connected() {')]
base = dict(boot_id='current', pid=123, phase='stopped', charging_off_verified=True,
            stop_reason='time_limit', battery_mv=3500, voltage_limit_mv=3900)
cases = [({}, 'time_limit'), ({'stop_reason':'voltage_limit','battery_mv':3900,'phase':'aborted'}, 'voltage_limit'),
         ({'stop_reason':'voltage_limit'}, 'fault'), ({'stop_reason':'unplugged'}, 'unplugged'),
         ({'stop_reason':'fault'}, 'fault'), ({'boot_id':'old'}, 'unverified_stop'),
         ({'pid':456}, 'unverified_stop'), ({'charging_off_verified':False}, 'unverified_stop'),
         ({'phase':'off_restore_failed'}, 'cleanup_error'), ({'phase':'aborted'}, 'fault')]
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    for change, expected in cases:
        (root/'m39-charge-status.json').write_text(json.dumps(dict(base, **change), separators=(',', ':')))
        result = subprocess.run(['sh','-c','set -eu\nruntime=$RUNTIME\nboot=current\npid=123\n'+body+'completion_outcome'],
                                env=dict(os.environ,RUNTIME=directory),capture_output=True,text=True)
        assert result.returncode == 0 and result.stdout.strip() == expected, (change, result.stdout, result.stderr)
print('PASS: completion requires matching boot/PID and verified cleanup; voltage limit is not reported as full.')
