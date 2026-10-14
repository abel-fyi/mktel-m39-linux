"""Exercise actual CV preparation with fake PMIC I/O; no hardware writes."""
from pathlib import Path
import os,subprocess,tempfile
source=Path(__file__).with_name('m39-charge.sh').read_text()
helper=source[source.index('prepare_reconnect_cv()'):source.index('owner_diagnostics()')]
with tempfile.TemporaryDirectory() as d:
 p=Path(d)
 fake=r'''
cat() {
 if [ "$1" = "$MOCK/access" ]; then
  read reg < "$MOCK/reg"
  case "$reg" in 0200) command cat "$MOCK/chip";;0f48) command cat "$MOCK/gates";;0f4e) command cat "$MOCK/cv";;*) return 1;;esac
 elif [ "$1" = "$MOCK/request" ]; then
  read reg value < "$1";printf '%s\n' "$reg" > "$MOCK/reg"
  if [ -n "$value" ]; then
   test "$reg" = 0f4e || return 1
   echo write >> "$MOCK/writes"
   test "$MOCK_FAIL_WRITE" = 1 || printf '%s\n' "$((0x$value))" > "$MOCK/cv"
  fi
 else command cat "$@";fi
}
'''
 script='set -eu\nowner='+str(p/'owner')+'\n'+fake+helper.replace('/sys/devices/platform/mt-pmic/pmic_access',str(p/'access')).replace('/run/m39-cv-prepare.$$',str(p/'request'))+'prepare_reconnect_cv\n'
 for chip,gates,cv,lease,fail,success,writes,final in [(10288,99,205,0,0,True,1,195),(10288,99,195,0,0,True,0,195),(10288,99,194,0,0,False,0,194),(10288,99,223,0,0,False,0,223),(10288,123,205,0,0,False,0,205),(0,99,205,0,0,False,0,205),(10288,99,205,60,0,False,0,205),(10288,99,205,0,1,False,1,205)]:
  for name,value in [('chip',chip),('gates',gates),('cv',cv),('owner',lease)]: (p/name).write_text(str(value)+'\n')
  (p/'writes').unlink(missing_ok=True)
  result=subprocess.run(['sh','-c',script],env=dict(os.environ,MOCK=d,MOCK_FAIL_WRITE=str(fail)),capture_output=True,text=True)
  assert (result.returncode==0)==success,(cv,result.stderr)
  assert int((p/'cv').read_text())==final
  assert ((p/'writes').read_text().count('write') if (p/'writes').exists() else 0)==writes
print('PASS: only known 4.2V standby lowered to 3.9V; unknown/lower CV, active gates, owner, chip and failed readback rejected.')
