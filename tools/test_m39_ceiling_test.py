"""Exercise the real ceiling-test terminal policy and JSON-field reader."""
import subprocess
import tempfile
from pathlib import Path
s=Path(__file__).with_name('m39-charge-ceiling-test.sh').read_text()
a=s.index('terminal_action() {');b=s.index('\ncleanup()',a)
functions=s[a:b]
for phase,reason,mv,limit,expected in [
 ('stopped','time_limit','3500','3900','next'),
 ('stopped','interval_limit','3500','3900','next'),
 ('stopped','voltage_limit','3900','3900','ceiling'),
 ('stopped','voltage_limit','3899','3900','fault'),
 ('stopped','voltage_limit','4200','4200','fault'),
 ('aborted','time_limit','3500','3900','fault'),
 ('aborted','net_discharge','3500','3900','fault'),
 ('stopped','unplugged','3500','3900','cancelled'),
 ('stopped','stop_requested','3500','3900','cancelled'),
 ('off_unverified','time_limit','3500','3900','fault')]:
 r=subprocess.run(['sh','-c',functions+'\nterminal_action "$@"','test',phase,reason,mv,limit],capture_output=True,text=True,check=True)
 assert r.stdout.strip()==expected,(phase,reason,r.stdout)
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'state';p.write_text('{"phase":"stopped","pid":123,"boot_id":"test-boot","charging_off_verified":true,"battery_mv":3900}')
 for k,expected in [('phase','stopped'),('pid','123'),('boot_id','test-boot'),('charging_off_verified','true'),('battery_mv','3900')]:
  r=subprocess.run(['sh','-c',functions+'\nvalue "$1" "$2"','test',str(p),k],capture_output=True,text=True,check=True)
  assert r.stdout.strip()==expected,(k,r.stdout)
print('PASS: only clean timed completion advances; cutoff identity, faults/cancellation and status parsing verified.')
