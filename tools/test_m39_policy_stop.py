"""Test the actual CLI stop path: internal stops cannot erase operator cancel."""
import os,subprocess,tempfile
from pathlib import Path
source=Path(__file__).with_name('m39-charge.sh').read_text()
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'owner').write_text('0\n');(p/'boot').write_text('test\n')
 script=source.replace('/run/',d+'/').replace('/proc/sys/kernel/random/boot_id',str(p/'boot')).replace('/sys/module/charging_hw_pmic/parameters/m39_owner_seconds',str(p/'owner'))
 script=script.replace('case "${1:-status}" in','id() { echo 0; }\ncase "${1:-status}" in')
 for internal,existing,expected in [('1',False,False),('0',False,True),('1',True,True)]:
  flag=p/'m39-charge-startup.disabled';flag.unlink(missing_ok=True)
  if existing:flag.touch()
  r=subprocess.run(['sh','-c',script,'test','stop'],capture_output=True,text=True,env=dict(os.environ,M39_STOP_INTERNAL=internal))
  assert r.returncode==0,r.stderr
  assert flag.exists()==expected,(internal,existing)
print('PASS: manual stop cancels startup; internal stop preserves existing cancellation without creating one.')
