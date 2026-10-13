"""Ceiling reached during charging is a clean stop; initial checks still reject it."""
from pathlib import Path
import subprocess
s=Path(__file__).with_name('m39-pmic-pulse.sh').read_text()
a=s.index('    if [ "$voltage" -ge "$maximum_mv" ]; then')
b=s.index('\n    fi',a)+len('\n    fi')
body=s[a:b]
for active,voltage,expected in [(1,3900,0),(1,3910,0),(0,3900,1),(1,3899,0)]:
    code=f'set -eu\nstatus_active={active}\nvoltage={voltage}\nmaximum_mv=3900\nfail(){{ exit 1; }}\n'+body
    r=subprocess.run(['sh','-c',code],capture_output=True,text=True)
    assert r.returncode==expected,(active,voltage,r.stdout,r.stderr)
print('PASS: active voltage ceiling stops cleanly; initial high voltage refuses enable.')
