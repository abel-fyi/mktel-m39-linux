"""Exercise actual shell guard stop classification without device access."""
from pathlib import Path
import os
import subprocess
import tempfile

source = Path(__file__).with_name('m39-pmic-pulse.sh').read_text()
def function(name):
    return name + '() {' + source.split(name + '() {', 1)[1].split('\n}\n', 1)[0] + '\n}\n'

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / 'type').write_text('mtktspmic\n')
    stop = root / 'stop'
    fixture = '''set -eu
stop_reason=running
stop_file=$STOP
requires_owner=0
maximum_mv=3900
pmic_thermal=$THERMAL
uptime_decimal() { echo 10; }
number() { echo "$TEMP"; }
sample() { [ "$CASE" != adc ] || return 1; echo "$VOLT 3500 5000 700 410"; }
readreg() { echo 1; }
fuel_current() { echo '220 220'; }
trap 'printf "REASON=%s\\n" "$stop_reason"' EXIT
''' + function('fail') + function('guard') + '\nguard\n'
    cases = [('normal', 3500, 30000, 'running', 0),
             ('ceiling', 3900, 30000, 'voltage_limit', 1),
             ('over', 3950, 30000, 'voltage_limit', 1),
             ('low', 3100, 30000, 'fault', 1),
             ('hot', 3500, 41000, 'fault', 1),
             ('adc', 3500, 30000, 'fault', 1),
             ('stop', 3500, 30000, 'stop_requested', 0)]
    for case, voltage, temperature, reason, code in cases:
        if case == 'stop':
            stop.touch()
        result = subprocess.run(['sh', '-c', fixture], capture_output=True, text=True,
                                env=dict(os.environ, CASE=case, VOLT=str(voltage),
                                         TEMP=str(temperature), STOP=str(stop), THERMAL=str(root)))
        assert result.returncode == code, (case, result.stderr)
        assert f'REASON={reason}\n' in result.stdout, (case, result.stdout, result.stderr)
print('PASS: normal, ceiling, over-ceiling, low-voltage, thermal, ADC failure and cooperative-stop classification.')
