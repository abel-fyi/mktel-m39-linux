"""Exercise optional timing without changing register output/error status."""
from pathlib import Path
import tempfile,subprocess,os
s=Path(__file__).with_name('m39-pmic-pulse.sh').read_text()
a=s.index('readreg() {');b=s.index('\n}\n',a)+3
with tempfile.TemporaryDirectory() as d:
 p=Path(d)
 wrapper=s[a:b].replace('/run/m39-charge-last-io',str(p/'stage'))
 fixture='''set -eu
uptime_seconds() { cat "$CLOCK"; }
readreg_raw() {
 echo 12 > "$CLOCK"
 [ "$RESULT" = 0 ] || return "$RESULT"
 echo 123
}
'''+wrapper+'\nreadreg 0f66\n'
 for trace,result in [('1','0'),('1','1'),('0','0'),('0','1')]:
  (p/'clock').write_text('10\n');(p/'stage').unlink(missing_ok=True)
  r=subprocess.run(['sh','-c',fixture],capture_output=True,text=True,env=dict(os.environ,CLOCK=str(p/'clock'),RESULT=result,M39_TRACE_IO=trace))
  assert r.returncode==int(result)
  assert r.stdout==('123\n' if result=='0' else '')
  assert ('SLOW_IO operation=readreg register=0f66' in r.stderr)==(trace=='1')
  assert (p/'stage').exists()==(trace=='1')
print('PASS: tracing preserves numeric output and errors; disabled tracing adds no stage writes.')
