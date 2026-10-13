"""Exercise connect/disconnect and no-repeat behavior with fake sysfs only."""
import os, json, pathlib, subprocess, tempfile, time
root=pathlib.Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory() as name:
 p=pathlib.Path(name)
 for f,v in [('usb','0'),('ac','0'),('owner','0'),('boot','test-boot'),('m39-plug-charge-armed','test-boot')]: (p/f).write_text(v)
 controller=p/'controller'
 controller.write_text('#!/bin/sh\nsleep 1\n')
 controller.chmod(0o755)
 env=dict(os.environ,M39_SERVICE_RUNTIME=str(p),M39_SERVICE_USB=str(p/'usb'),M39_SERVICE_AC=str(p/'ac'),M39_SERVICE_OWNER=str(p/'owner'),M39_SERVICE_BOOT=str(p/'boot'),M39_SERVICE_CONTROLLER=str(controller))
 proc=subprocess.Popen(['sh',str(root/'tools/m39-plug-charge.sh')],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 def await_state(phase,session=None):
  until=time.monotonic()+7
  while time.monotonic()<until:
   try: state=json.loads((p/'m39-plug-status.json').read_text())
   except (FileNotFoundError,json.JSONDecodeError): time.sleep(.05);continue
   if state['phase']==phase and (session is None or state['session']==session):return state
   time.sleep(.05)
  raise AssertionError((phase,state))
 try:
  await_state('waiting_for_power')
  (p/'usb').write_text('1');await_state('session_stopped',1)
  time.sleep(2);assert json.loads((p/'m39-plug-status.json').read_text())['session']==1
  assert (p/'owner').read_text().strip()=='0'
  (p/'usb').write_text('0');await_state('waiting_for_power')
  controller.write_text('#!/bin/sh\ntrap \'echo terminated > "$M39_SERVICE_RUNTIME/result"; exit 1\' TERM\nwhile [ ! -e "$M39_STOP_FILE" ]; do sleep .1; done\necho cooperative > "$M39_SERVICE_RUNTIME/result"\n')
  (p/'usb').write_text('1');await_state('charging',2)
  (p/'usb').write_text('0');await_state('waiting_for_power',2)
  assert (p/'owner').read_text().strip()=='0'
  assert (p/'result').read_text().strip()=='cooperative'
 finally:
  proc.terminate();proc.communicate(timeout=5)
 assert proc.returncode==143 and not (p/'m39-plug-service.lock').exists()
 print('PASS: connection start, no automatic replay, reconnect, unplug cleanup, service shutdown; no hardware accessed.')
