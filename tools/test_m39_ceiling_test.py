"""Exercise the real ceiling-test terminal policy and JSON-field reader."""
import subprocess
import tempfile
from pathlib import Path
s=Path(__file__).with_name('m39-charge-ceiling-test.sh').read_text()
a=s.index('active_phase() {');b=s.index('\ncleanup()',a)
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

for phase,expected in [('preparing',0),('charging',0),('stopped',1),('aborted',1),('off_unverified',1)]:
 r=subprocess.run(['sh','-c',functions+'\nactive_phase "$1"','test',phase])
 assert r.returncode==expected,phase

# Run the actual coordinator against fake commands: it must survive preparing,
# observe charging, then finish on a verified voltage cutoff.
import os
import time
import json
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'bin').mkdir();(p/'boot').write_text('integration-boot\n')
 worker=subprocess.Popen(['/bin/sleep','120'])
 mock='''#!/usr/bin/python3
import json,os,sys
from pathlib import Path
p=Path(os.environ['M39_MOCK_RUNTIME'])
pid=int(os.environ['M39_MOCK_PID'])
if sys.argv[1]=='stop':
 (p/'m39-charge-startup.disabled').touch()
else:
 (p/'m39-charge-startup.disabled').unlink(missing_ok=True)
 (p/'m39-plug-status.json').write_text(json.dumps(dict(phase='charging',boot_id='integration-boot',controller_pid=str(pid))))
 (p/'m39-charge-status.json').write_text(json.dumps(dict(phase='preparing',pid=pid,boot_id='integration-boot',charging_off_verified=False)))
'''
 (p/'bin/m39-charge').write_text(mock);(p/'bin/m39-charge').chmod(0o755)
 (p/'bin/sleep').write_text('#!/bin/sh\nexec /bin/sleep .02\n');(p/'bin/sleep').chmod(0o755)
 script=s.replace('/run/',str(p)+'/').replace('/proc/sys/kernel/random/boot_id',str(p/'boot'))
 script=script.replace('export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',f'export PATH={p}/bin:/usr/bin:/bin')
 proc=subprocess.Popen(['sh','-c',script],env=dict(os.environ,M39_MOCK_RUNTIME=str(p),M39_MOCK_PID=str(worker.pid)),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 try:
  end=time.monotonic()+5
  while time.monotonic()<end:
   f=p/'m39-ceiling-test.json'
   if f.exists() and json.loads(f.read_text())['phase']=='charging':break
   time.sleep(.02)
  else:raise AssertionError('Coordinator did not enter charging')
  time.sleep(.15)
  assert proc.poll() is None,'Preparing phase incorrectly treated as terminal'
  state=dict(phase='charging',pid=worker.pid,boot_id='integration-boot',charging_off_verified=False)
  (p/'next').write_text(json.dumps(state));(p/'next').replace(p/'m39-charge-status.json')
  time.sleep(.15)
  state.update(phase='stopped',charging_off_verified=True,stop_reason='voltage_limit',battery_mv=3900,voltage_limit_mv=3900)
  (p/'next').write_text(json.dumps(state));(p/'next').replace(p/'m39-charge-status.json')
  out,err=proc.communicate(timeout=5)
  assert proc.returncode==0,(out,err)
  assert json.loads((p/'m39-ceiling-test.json').read_text())['phase']=='voltage_ceiling_reached'
 finally:
  if proc.poll() is None:proc.terminate();proc.communicate(timeout=5)
  worker.terminate();worker.wait()
print('PASS: actual coordinator survives preparing, observes charging and stops at verified ceiling.')
