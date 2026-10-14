"""Check actual profile guard keeps failed I/O distinct from readable mode changes."""
from pathlib import Path
import os,subprocess
s=Path(__file__).with_name('m39-pmic-pulse.sh').read_text()
a=s.index('        regulation_now=$(readreg 0f4c)')
b=s.index('        old=$(readreg 0f62)',a)
block=s[a:b]
script='''set -eu
cv_code=3;current_code=13;stop_reason=running
readreg() {
 test "$1" != "$FAILED_REG" || return 1
 case "$1" in 0f4c) echo 10;;0f4e) echo "$TEST_CV";;0f50) echo 13;;0f7a) echo 68;;esac
}
fail() { echo "$stop_reason"; exit 1; }
'''+block+'echo passed\n'
for reg in ('0f4c','0f4e','0f50','0f7a'):
 r=subprocess.run(['sh','-c',script],env=dict(os.environ,FAILED_REG=reg,TEST_CV='3'),capture_output=True,text=True)
 assert r.returncode!=0 and r.stdout.strip()=='running',(reg,r.stdout,r.stderr)
for cv,expected in [('3','passed'),('13','power_profile_changed')]:
 r=subprocess.run(['sh','-c',script],env=dict(os.environ,FAILED_REG='',TEST_CV=cv),capture_output=True,text=True)
 assert r.stdout.strip()==expected,(cv,r.stdout,r.stderr)
print('PASS: failed PMIC reads cannot masquerade as expected unplug profile changes.')
