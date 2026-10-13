"""Exercise bounded startup with fake supply files and fake arming; no hardware."""
from pathlib import Path
import json, os, subprocess, tempfile
script = Path(__file__).with_name('m39-charge-startup.sh')
with tempfile.TemporaryDirectory() as directory:
    root=Path(directory)
    for voltage, success, expected in [(3500000,True,'armed'),(3500000,True,'disabled'),(3900000,True,'voltage_limit'),
                                      (3100000,True,'voltage_too_low'),(3500000,False,'arm_failed')]:
        for name,value in [('usb','1'),('ac','0'),('voltage',str(voltage)),('boot','test-boot')]:
            (root/name).write_text(value+'\n')
        arm=root/'arm'
        arm.write_text('#!/bin/sh\necho "$1" >> "'+str(root/'calls')+'"\nexit '+('0' if success else '1')+'\n')
        arm.chmod(0o755)
        (root/'calls').unlink(missing_ok=True)
        (root/'m39-charge-startup.disabled').unlink(missing_ok=True)
        if expected == 'disabled': (root/'m39-charge-startup.disabled').touch()
        env=dict(os.environ,M39_START_RUNTIME=directory,M39_START_USB=str(root/'usb'),
                 M39_START_AC=str(root/'ac'),M39_START_VOLTAGE=str(root/'voltage'),
                 M39_START_BOOT=str(root/'boot'),M39_START_COMMAND=str(arm))
        result=subprocess.run(['sh',str(script)],env=env,capture_output=True,text=True,timeout=5)
        state=json.loads((root/'m39-charge-startup.json').read_text())
        assert state['phase']==expected, (state,result.stderr)
        assert not (root/'m39-charge-startup.lock').exists()
        calls=(root/'calls').read_text() if (root/'calls').exists() else ''
        assert calls==('arm\n' if 3200000<=voltage<3900000 and expected != 'disabled' else '')
        assert result.returncode==(0 if expected in ('armed','voltage_limit','disabled') else 1)
print('PASS: startup arms once, rejects low voltage, skips ceiling and reports failure without retry.')
