"""Exercise actual transient debounce; sustained discharge must still abort."""
from pathlib import Path
import subprocess
s=Path(__file__).with_name('m39-pmic-pulse.sh').read_text()
a=s.index('        if [ "$fg_direction" -gt 0 ]; then')
b=s.index('\n        fi',a)+len('\n        fi')
body=s[a:b]
for values,ok in [('1 -1 1',True),('0 0 1',True),('-1 -1 -1',False),('0 0 0',False),('-1 1 -1 1',True)]:
    script='set -eu\nnonpositive_samples=0\nstop_reason=running\nfail(){ exit 1; }\nfor fg_direction in '+values+'; do\n'+body+'\ndone\n'
    r=subprocess.run(['sh','-c',script],capture_output=True,text=True)
    assert (r.returncode==0)==ok,(values,r.stdout,r.stderr)
print('PASS: isolated current dips recover; three consecutive nonpositive samples stop charging.')
