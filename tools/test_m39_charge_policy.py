"""Verify actual pure policy without hardware writes or voltage-limit changes."""
from pathlib import Path
import subprocess
source=Path(__file__).with_name('m39-charge-policy.sh').read_text()
cases=[
(('idle',1,3500,0,'none',1),'start_bounded'),
(('charging',1,3500,0,'none',0),'charging'),
(('charging',1,3900,0,'none',0),'target_hold'),
(('target_hold',1,3890,0,'none',1),'target_hold'),
(('target_hold',1,3751,0,'none',1),'target_hold'),
(('target_hold',1,3750,0,'none',1),'start_bounded'),
(('target_hold',1,3750,0,'none',0),'fault'),
(('charging',1,3500,0,'time_limit',1),'start_bounded'),
(('charging',1,3500,0,'time_limit',0),'fault'),
(('charging',1,3900,0,'voltage_limit',1),'target_hold'),
(('charging',1,3890,0,'voltage_limit',1),'fault'),
(('charging',1,3500,0,'net_discharge',1),'fault'),
(('fault',1,3500,0,'none',1),'fault'),
(('charging',0,3500,0,'unplugged',1),'idle'),
(('charging',0,3500,0,'unplugged',0),'fault'),
(('charging',1,3500,0,'stop_requested',1),'idle'),
(('idle',1,3199,0,'none',1),'low_voltage'),
(('low_voltage',1,3300,0,'none',1),'start_bounded'),
(('idle',1,3500,6,'none',1),'fault'),
(('idle',1,'invalid',0,'none',1),'fault'),
(('idle',1,4400,0,'none',1),'fault'),
]
for args,expected in cases:
 r=subprocess.run(['sh','-c',source+'\nm39_policy_decide "$@"','test',*map(str,args)],capture_output=True,text=True,check=True)
 assert r.stdout.strip()==expected,(args,r.stdout,r.stderr)
print(f'PASS: {len(cases)} policy cases: target hysteresis, verified timed restart, stale/invalid data, low voltage and latched faults.')
