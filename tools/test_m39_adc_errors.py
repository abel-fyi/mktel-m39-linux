"""Fault-inject the actual ADC helper, including a caller with errexit disabled."""
from pathlib import Path
import subprocess,tempfile,os
source=Path(__file__).with_name('m39-pmic-pulse.sh').read_text()
body=source.split('sample() (',1)[1].split('\n)\n',1)[0]
fixture='''set +e
fail() { exit 1; }
readreg() {
 case "$1" in
  028a|0e94|0eb0) [ "$FAULT:$1" != clock:0e94 ] || return 1; echo 123;;
  *) [ "$FAULT:$1" != read:0e2e ] || return 1; echo 33768;;
 esac
}
field() {
 echo "field $*" >> "$LOG"
 [ "$FAULT:$1:$3" != enable:028a:256 ] || return 1
 [ "$FAULT:$1:$3" != restore:0eb0:123 ] || return 1
}
writereg() {
 echo "request $*" >> "$LOG"
 [ "$FAULT" != request ]
}
sample() (
'''+body+'''
)
if values=$(sample); then echo "PASS_VALUES=$values"; exit 0; else exit 1; fi
'''
with tempfile.TemporaryDirectory() as name:
 p=Path(name)
 for fault in ['none','clock','enable','request','read','restore']:
  log=p/fault
  result=subprocess.run(['sh','-c',fixture],env=dict(os.environ,FAULT=fault,LOG=str(log)),capture_output=True,text=True)
  assert result.returncode==(0 if fault=='none' else 1),(fault,result.stdout,result.stderr)
  writes=log.read_text() if log.exists() else ''
  if fault=='clock':assert not writes
  if fault=='enable':assert 'request ' not in writes and 'field 0eb0 128 123' in writes
  if fault=='read':assert 'field 0eb0 128 123' in writes
print('PASS: original-clock, enable, request, read and restoration errors cannot produce a successful ADC sample.')
