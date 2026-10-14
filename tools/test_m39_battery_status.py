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
 cases=[({},'charging'),({'uptime_seconds':90},'unknown'),({'boot_id':'other'},'unknown'),({'fg_signed_raw':-20},'unknown'),({'battery_mv':5000},'unknown'),({'phase':'preparing'},'unknown'),({'fg_signed_raw':'1-2'},'unknown')]
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
print('PASS: freshness, boot/PID, net-current direction, verified OFF, no invented full/SOC/temperature.')
