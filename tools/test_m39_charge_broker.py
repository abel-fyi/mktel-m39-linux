"""Run the actual broker against simulated ADC, controller and ownership."""
import json,os,subprocess,tempfile,time
from pathlib import Path
root=Path(__file__).parent.resolve()
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'boot').write_text('test-boot\n');(p/'uptime').write_text('100.00 0.00\n');(p/'owner').write_text('0\n');(p/'adc').write_text('4000 4000 5000 695 410\n');(p/'proc').mkdir()
 worker=subprocess.Popen(['/bin/sleep','120']);(p/f'proc/{worker.pid}').mkdir();(p/f'proc/{worker.pid}/stat').write_text(Path(f'/proc/{worker.pid}/stat').read_text())
 mock=r'''#!/usr/bin/python3
import json,os,sys
from pathlib import Path
p=Path(os.environ['M39_MOCK_RUNTIME']);pid=int(os.environ['M39_MOCK_PID'])
with (p/'calls').open('a') as f:f.write(sys.argv[1]+'\n')
if sys.argv[1]=='stop':
 (p/'owner').write_text('0\n')
 if os.environ.get('M39_STOP_INTERNAL')!='1':(p/'m39-charge-startup.disabled').touch()
else:
 assert not (p/'m39-charge-startup.disabled').exists()
 (p/'owner').write_text('1800\n')
 (p/'m39-plug-status.json').write_text(json.dumps(dict(phase='charging',boot_id='test-boot',controller_pid=str(pid))))
 (p/'m39-charge-status.json').write_text(json.dumps(dict(phase='charging',pid=pid,boot_id='test-boot',uptime_seconds=100,battery_mv=3700,charging_off_verified=False,voltage_limit_mv=3900,stop_reason='running')))
'''
 (p/'command').write_text(mock);(p/'command').chmod(0o755)
 (p/'sampler').write_text(f'#!/bin/sh\necho sample >> "{p}/samples"\ncat "{p}/adc"\n');(p/'sampler').chmod(0o755)
 (p/'pause').write_text('#!/bin/sh\nexec /bin/sleep .02\n');(p/'pause').chmod(0o755)
 env=dict(os.environ,M39_MOCK_RUNTIME=d,M39_MOCK_PID=str(worker.pid),M39_BROKER_RUNTIME=d,M39_BROKER_COMMAND=str(p/'command'),M39_BROKER_ADC=str(p/'sampler'),M39_BROKER_POLICY=str(root/'m39-charge-policy.sh'),M39_BROKER_BOOT=str(p/'boot'),M39_BROKER_UPTIME=str(p/'uptime'),M39_BROKER_OWNER=str(p/'owner'),M39_BROKER_PROC=str(p/'proc'),M39_BROKER_SLEEP=str(p/'pause'))
 def await_phase(phase):
  end=time.monotonic()+5
  while time.monotonic()<end:
   try:v=json.loads((p/'m39-broker.json').read_text())
   except (FileNotFoundError,json.JSONDecodeError):time.sleep(.01);continue
   if v['phase']==phase:return v
   time.sleep(.01)
  raise AssertionError((phase,v,proc.poll()))
 def publish(**values):
  base=dict(phase='stopped',pid=worker.pid,boot_id='test-boot',uptime_seconds=100,battery_mv=3900,charging_off_verified=True,voltage_limit_mv=3900,stop_reason='voltage_limit')
  (p/'next').write_text(json.dumps(base|values));(p/'next').replace(p/'m39-charge-status.json');(p/'owner').write_text('0\n')
 proc=subprocess.Popen(['sh',str(root/'m39-charge-broker.sh'),'--run'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 try:
  await_phase('target_hold');assert 'arm' not in (p/'calls').read_text()
  (p/'adc').write_text('3750 3750 5000 695 410\n');await_phase('charging')
  samples=(p/'samples').read_text();time.sleep(.1);assert (p/'samples').read_text()==samples,'Concurrent ADC reader during charging'
  (p/'adc').write_text('3850 3850 5000 695 410\n');publish();await_phase('target_hold')
  count=(p/'calls').read_text().count('arm');time.sleep(.1);assert (p/'calls').read_text().count('arm')==count
  (p/'adc').write_text('3750 3750 5000 695 410\n');await_phase('charging');assert (p/'calls').read_text().count('arm')==count+1
  (p/'adc').write_text('3700 3700 0 695 410\n');publish(stop_reason='unplugged',battery_mv=3700);await_phase('idle')
  assert proc.poll() is None,'Unplug must not terminate automatic broker'
  (p/'adc').write_text('3700 3700 5000 695 410\n');await_phase('charging')
  count=(p/'calls').read_text().count('arm')
  publish(phase='aborted',stop_reason='fault',battery_mv=3700);out,err=proc.communicate(timeout=5)
  assert proc.returncode!=0,(out,err)
  assert json.loads((p/'m39-broker.json').read_text())['phase']=='fault'
  assert (p/'owner').read_text().strip()=='0'
  assert (p/'calls').read_text().count('arm')==count,'Fault was retried'
  # A clean timed segment gets fresh validation, rather than extending a lease.
  (p/'m39-broker.json').unlink()
  proc=subprocess.Popen(['sh',str(root/'m39-charge-broker.sh'),'--run'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  await_phase('charging');count=(p/'calls').read_text().count('arm')
  publish(stop_reason='time_limit',battery_mv=3700)
  end=time.monotonic()+5
  while (p/'calls').read_text().count('arm')==count and time.monotonic()<end:time.sleep(.01)
  await_phase('charging');assert (p/'calls').read_text().count('arm')==count+1
  (p/'m39-charge-startup.disabled').touch()
  out,err=proc.communicate(timeout=5)
  assert proc.returncode==0,(out,err)
  assert json.loads((p/'m39-broker.json').read_text())['phase']=='cancelled'
  assert (p/'owner').read_text().strip()=='0'
  # Terminal records must be fresh, from the correct boot/controller, and OFF.
  for changes in [dict(uptime_seconds=94),dict(uptime_seconds=101),
                  dict(phase='charging',uptime_seconds=94),
                  dict(boot_id='another-boot'),dict(pid=worker.pid+1),
                  dict(charging_off_verified=False),dict(voltage_limit_mv=4200)]:
   (p/'m39-broker.json').unlink()
   proc=subprocess.Popen(['sh',str(root/'m39-charge-broker.sh'),'--run'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
   await_phase('charging');count=(p/'calls').read_text().count('arm')
   publish(stop_reason='time_limit',battery_mv=3700,**changes)
   try:out,err=proc.communicate(timeout=5)
   except subprocess.TimeoutExpired:
    raise AssertionError(('Broker did not reject completion',changes,(p/'m39-charge-status.json').read_text(),(p/'m39-broker.json').read_text()))
   assert proc.returncode!=0,(changes,out,err)
   assert (p/'owner').read_text().strip()=='0'
   assert (p/'calls').read_text().count('arm')==count,('Invalid completion retried',changes)
  (p/'m39-broker.json').unlink()
  proc=subprocess.Popen(['sh',str(root/'m39-charge-broker.sh'),'--run'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  await_phase('charging');count=(p/'calls').read_text().count('arm')
  stat=p/f'proc/{worker.pid}/stat';words=stat.read_text().split();words[21]=str(int(words[21])+1)
  stat.write_text(' '.join(words)+'\n')
  out,err=proc.communicate(timeout=5)
  assert proc.returncode!=0,(out,err)
  assert (p/'owner').read_text().strip()=='0'
  assert (p/'calls').read_text().count('arm')==count,'Reused controller PID retried'
 finally:
  if proc.poll() is None:proc.terminate();proc.communicate(timeout=5)
  worker.terminate();worker.wait()
print('PASS: hold/recharge, exclusive ADC, unplug/reconnect, timed restart, operator cancellation, stale/foreign/unverified completion and fault shutdown.')
