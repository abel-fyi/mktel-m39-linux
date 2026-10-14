"""Check actual profile guard keeps failed I/O distinct from readable mode changes."""
from pathlib import Path
import os,subprocess
s=Path(__file__).with_name('m39-pmic-pulse.sh').read_text()
block='verify_charge_profile() {'+s.split('verify_charge_profile() {',1)[1].split('\n}\n',1)[0]+'\n}\nverify_charge_profile\n'
script='''set -eu
cv_code=3;current_code=13;stop_reason=running
readreg() {
 test "$1" != "$FAILED_REG" || return 1
 case "$1" in 0f4c) echo "${TEST_REGULATION:-10}";;0f4e) echo "$TEST_CV";;0f50) echo "${TEST_CURRENT:-13}";;0f7a) echo "${TEST_MODE:-68}";;esac
}
fail() { echo "$stop_reason"; exit 1; }
'''+block+'echo passed\n'
for reg in ('0f4c','0f4e','0f50','0f7a'):
 r=subprocess.run(['sh','-c',script],env=dict(os.environ,FAILED_REG=reg,TEST_CV='3'),capture_output=True,text=True)
 assert r.returncode!=0 and r.stdout.strip()=='running',(reg,r.stdout,r.stderr)
for cv,expected in [('3','passed'),('13','power_profile_changed')]:
 r=subprocess.run(['sh','-c',script],env=dict(os.environ,FAILED_REG='',TEST_CV=cv),capture_output=True,text=True)
 assert r.stdout.strip()==expected,(cv,r.stdout,r.stderr)
for changes,expected in [(dict(TEST_REGULATION='0'),'regulation_disabled'),(dict(TEST_CURRENT='15'),'power_profile_changed'),(dict(TEST_MODE='0'),'power_profile_changed')]:
 r=subprocess.run(['sh','-c',script],env=dict(os.environ,FAILED_REG='',TEST_CV='3',**changes),capture_output=True,text=True)
 assert r.returncode!=0 and r.stdout.strip()==expected,(changes,r.stdout,r.stderr)
print('PASS: failed PMIC reads cannot masquerade as expected unplug profile changes.')
