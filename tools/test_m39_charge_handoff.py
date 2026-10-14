"""Exercise the real encrypted-init stop barrier against delayed broker cleanup."""
from pathlib import Path
import os, subprocess, tempfile
source=Path(__file__).with_name('encrypted-ram-init.sh').read_text()
barrier=source[source.index('stopped=0\n'):source.index('if [ "$stopped" != 1 ]')]
with tempfile.TemporaryDirectory() as d:
    root=Path(d)
    (root/'m39-broker.lock').mkdir();(root/'m39-charge-startup.lock').mkdir()
    stopper=root/'stop'
    stopper.write_text('''#!/bin/sh
n=$(cat "$M39_TEST_RUNTIME/count" 2>/dev/null || echo 0)
n=$((n+1)); echo "$n" > "$M39_TEST_RUNTIME/count"
touch "$M39_TEST_RUNTIME/m39-charge-startup.disabled"
if [ "$n" -ge 2 ]; then
 rmdir "$M39_TEST_RUNTIME/m39-broker.lock" "$M39_TEST_RUNTIME/m39-charge-startup.lock" 2>/dev/null || :
fi
''')
    stopper.chmod(0o755)
    script='set -eu\n'+barrier.replace('/usr/local/sbin/m39-charge stop',str(stopper)).replace('/run/',d+'/')+'test "$stopped" = 1\ntest "$(cat '+d+'/count)" = 2\n'
    subprocess.run(['sh','-c',script],env=dict(os.environ,M39_TEST_RUNTIME=d),check=True,timeout=5)
print('PASS: encrypted-root handoff waits for both startup and broker to release old-root locks.')
