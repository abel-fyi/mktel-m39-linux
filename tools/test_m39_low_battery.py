"""Test actual observer with fake readings; it cannot invoke poweroff."""
import json,os,subprocess,tempfile
from pathlib import Path
root=Path(__file__).parent
source=(root/'m39-low-battery-policy.sh').read_text()
cases=[((3500,'false',0,0),'healthy'),((3400,'false',0,0),'low_pending'),
       ((3390,'false',0,3),'shutdown_recommended'),((3300,'true',0,3),'powered'),
       ((3300,'null',0,3),'unavailable'),((3300,'false',6,3),'unavailable'),
       (('null','false',0,3),'unavailable'),(('03300','false',0,3),'unavailable'),
       ((2600,'false',0,3),'unavailable')]
for args,expected in cases:
    result=subprocess.check_output(['sh','-c',source+'\nm39_low_battery_decide "$@"','test',*map(str,args)],text=True)
    assert result.strip()==expected,(args,result)
with tempfile.TemporaryDirectory() as directory:
    p=Path(directory);(p/'boot').write_text('test-boot\n');(p/'uptime').write_text('100 0\n')
    (p/'reader').write_text('#!/bin/sh\ncat "$MOCK/reading"\n');(p/'reader').chmod(0o755)
    # Drive five distinct observations, then interrupt normally.
    (p/'pause').write_text('''#!/usr/bin/python3
import os,json,signal
from pathlib import Path
p=Path(os.environ['MOCK']);state=json.loads((p/'m39-low-battery.json').read_text())
with (p/'events').open('a') as f:f.write(json.dumps(state)+'\\n')
n=len((p/'events').read_text().splitlines())
if n==7:os.kill(os.getppid(),signal.SIGTERM)
else:
 (p/'uptime').write_text(str(100+5*n)+' 0\\n')
 sample=dict(voltage_mv=3300,input_present=False,sample_age_seconds=0)
 if n==2:sample['sample_age_seconds']=5
 if n==4:sample['input_present']=True
 if n==5:sample['sample_age_seconds']=6
 (p/'reading').write_text(json.dumps(sample))
''');(p/'pause').chmod(0o755)
    (p/'reading').write_text(json.dumps(dict(voltage_mv=3300,input_present=False,sample_age_seconds=0)))
    env=dict(os.environ,MOCK=directory,M39_LOW_RUNTIME=directory,M39_LOW_BOOT=str(p/'boot'),
             M39_LOW_UPTIME=str(p/'uptime'),M39_LOW_POLICY=str(root/'m39-low-battery-policy.sh'),
             M39_LOW_REPORT=str(p/'reader'),M39_LOW_SLEEP=str(p/'pause'))
    subprocess.run(['sh',str(root/'m39-low-battery-monitor.sh'),'--observe'],env=env,check=True,timeout=10)
    events=[json.loads(line) for line in (p/'events').read_text().splitlines()]
    assert [e['phase'] for e in events]==['low_pending','low_pending','low_pending','shutdown_recommended','powered','unavailable','low_pending']
    assert all(e['shutdown_enabled'] is False for e in events)
    assert not (p/'m39-low-battery.lock').exists()
print('PASS: fresh/valid readings, sustained low-voltage debounce, USB reset, observation-only shutdown gate.')
