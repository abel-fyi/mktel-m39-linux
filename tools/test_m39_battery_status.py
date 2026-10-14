"""Run actual status tool against fresh/stale/foreign controller records."""
import json,os,subprocess,tempfile
from pathlib import Path
script=Path(__file__).with_name('m39-battery-status.sh')
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'boot').write_text('boot-a\n');(p/'uptime').write_text('100.00 1.00\n');(p/'proc/123').mkdir(parents=True)
 (p/'proc/123/stat').write_text('alive')
 (p/'proc/123/cmdline').write_bytes(b'/bin/sh\0/run/m39-pmic-pulse.sh\0')
 env=dict(os.environ,M39_STATUS_RUNTIME=d,M39_STATUS_BOOT=str(p/'boot'),M39_STATUS_UPTIME=str(p/'uptime'),M39_STATUS_PROC=str(p/'proc'))
 base=dict(phase='charging',pid=123,boot_id='boot-a',uptime_seconds=99,battery_mv=3600,fg_signed_raw=450,charging_off_verified=False,stop_reason='running')
 cases=[({},'charging'),({'uptime_seconds':90},'unknown'),({'boot_id':'other'},'unknown'),({'fg_signed_raw':-20},'unknown'),({'battery_mv':5000},'unknown'),({'phase':'preparing'},'unknown'),({'fg_signed_raw':'1-2'},'unknown'),({'battery_mv':'03600'},'unknown'),({'uptime_seconds':'099'},'unknown'),({'pid':'0123'},'unknown'),({'fg_signed_raw':'0450'},'unknown')]
 for changes,expected in cases:
  (p/'m39-charge-status.json').write_text(json.dumps(base|changes))
  value=json.loads(subprocess.check_output(['sh',str(script)],env=env))
  assert value['status']==expected,(changes,value)
  assert all(value[k] is None for k in ('percentage','full','cell_temperature'))
  if changes.get('uptime_seconds')==90 or changes.get('boot_id')=='other':assert value['voltage_mv'] is None
 (p/'proc/123/stat').write_text('alive')
 value=json.loads(subprocess.check_output(['sh',str(script)],env=env));assert value['status']=='unknown'
 (p/'proc/123/stat').unlink()
 (p/'m39-charge-status.json').write_text(json.dumps(base|dict(phase='stopped',charging_off_verified=True,uptime_seconds=50,stop_reason='voltage_limit')))
 value=json.loads(subprocess.check_output(['sh',str(script)],env=env));assert value['status']=='not_charging' and value['full'] is None
 (p/'m39-charge-status.json').unlink()
 assert json.loads(subprocess.check_output(['sh',str(script)],env=env))['status']=='unknown'
 # Broker measurements must be fresh and tied to the same process lifetime.
 (p/'proc/456').mkdir()
 (p/'proc/456/stat').write_text('456 (sh) S '+' '.join(['0']*18)+' 777\n')
 (p/'proc/456/cmdline').write_bytes(b'/bin/sh\0/usr/local/libexec/m39/m39-charge-broker.sh\0')
 broker=dict(phase='target_hold',pid=456,pid_start_ticks=777,boot_id='boot-a',
             uptime_seconds=100,sample_uptime_seconds=99,battery_mv=3850,usb_mv=5000)
 for changes,valid in [({},True),({'usb_mv':0},True),
                       ({'sample_uptime_seconds':90},False),
                       ({'sample_uptime_seconds':101},False),
                       ({'boot_id':'foreign'},False),({'pid_start_ticks':778},False),
                       ({'battery_mv':'03850'},False),({'usb_mv':3000},True)]:
  (p/'m39-broker.json').write_text(json.dumps(broker|changes))
  value=json.loads(subprocess.check_output(['sh',str(script)],env=env))
  assert value['voltage_mv']==(3850 if valid else None),(changes,value)
  expected_input=(False if changes.get('usb_mv')==0 else
                  None if not valid or changes.get('usb_mv')==3000 else True)
  assert value['input_present']==expected_input,(changes,value)
  assert value['status']=='unknown' # Policy state alone does not prove charging.
 (p/'proc/456/stat').unlink()
 value=json.loads(subprocess.check_output(['sh',str(script)],env=env))
 assert value['voltage_mv'] is None and value['policy_phase'] is None
print('PASS: freshness, boot/PID, net-current direction, verified OFF, no invented full/SOC/temperature.')
