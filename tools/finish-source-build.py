#!/usr/bin/env python3
"""Finish this authorized source-kernel experiment after make exits.

No GPT, preloader, other partitions, charging settings, or startup-service writes.
Stops on failed checks; never boots an unverified image.
"""
import argparse, hashlib, json, re, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path
import usb.core

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--make-pid', type=int, required=True)
args = parser.parse_args()
status_path = root / 'logs/source-build-status.json'
python = root / '.venv/bin/python'
name = 'alpine-m39-source-trace-mrdumpfix'
phase = 'waiting_for_build'
def status(phase, **fields):
    value = dict(phase=phase, updated_at_utc=datetime.now(timezone.utc).isoformat(), **fields)
    temporary = status_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(status_path)
    print(json.dumps(value), flush=True)
def run(command, logfile, timeout=120):
    with (root / 'logs' / logfile).open('w') as output:
        subprocess.run([str(v) for v in command], cwd=root, stdout=output,
                       stderr=subprocess.STDOUT, check=True, timeout=timeout)
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
try:
    status(phase, make_pid=args.make_pid)
    deadline = time.monotonic() + 3600
    while Path(f'/proc/{args.make_pid}/cmdline').exists():
        command = Path(f'/proc/{args.make_pid}/cmdline').read_bytes()
        state = Path(f'/proc/{args.make_pid}/stat').read_text().split()[2]
        if state == 'Z':
            break
        if b'make' not in command or b'mt6735' not in command:
            raise RuntimeError('Build PID changed; refusing to proceed.')
        if time.monotonic() >= deadline:
            raise RuntimeError('Build wait deadline reached.')
        time.sleep(10)
    log = (root / 'logs/source-kernel-mrdump-cached-build.txt').read_text()
    if 'OBJCOPY arch/arm64/boot/Image' not in log or re.search(r'error:|make.*Error [0-9]', log):
        raise RuntimeError('Build completion not verified; inspect build log.')
    image = root / 'build/mt6735-source/arch/arm64/boot/Image'
    for source in ['init/main.c', 'drivers/misc/mediatek/aee/mrdump/mrdump_mini.c']:
        if image.stat().st_mtime < (root / 'tools/mt6735-kernel' / source).stat().st_mtime:
            raise RuntimeError('Kernel image is older than the changed source.')
    source = (root / 'tools/mt6735-kernel/drivers/misc/mediatek/power/mt6735/charging_hw_pmic.c').read_text()
    if 'unsigned int enable = KAL_FALSE;' not in source:
        raise RuntimeError('Charging-disabled diagnostic requirement missing.')
    rollback = root / 'artifacts/alpine-m39-charge-lowpower.partition.img'
    if digest(rollback) != '4a7d0d5b5624817f828e39a9354955195c001a56edae0c6b1b6f2d8d5e38851b':
        raise RuntimeError('Known working rollback hash mismatch.')
    phase = 'packaging'
    status(phase)
    run([python, 'tools/build-source-boot.py', '--name', name, '--initcall-trace'], 'source-mrdumpfix-package.txt')
    target = root / 'artifacts' / (name + '.partition.img')
    metadata = json.loads((root / 'artifacts' / (name + '.json')).read_text())
    if target.stat().st_size != 16777216 or digest(target) != metadata['partition_sha256']:
        raise RuntimeError('Packaged image size/hash mismatch.')
    state = json.loads((root / '.state').read_text())
    if state['hwcode'] != 0x335 or state['flashmode'] != 'LEGACY':
        raise RuntimeError('Saved download-agent state is not the M39.')
    devices = [d for d in usb.core.find(find_all=True)
               if (d.idVendor, d.idProduct) in [(0x0e8d, 0x2000), (0x0e8d, 0x2001)]]
    if len(devices) != 1:
        raise RuntimeError('Expected exactly one connected M39 download agent.')
    phase = 'writing_boot'
    status(phase, partition_sha256=metadata['partition_sha256'])
    run([python, 'tools/mtkclient/mtk.py', 'w', 'boot', target], 'flash-source-mrdumpfix.txt')
    phase = 'verifying_readback'
    status(phase)
    readback = root / 'analysis/source-mrdumpfix-readback.img'
    run([python, 'tools/mtkclient/mtk.py', 'r', 'boot', readback], 'source-mrdumpfix-readback.txt')
    if readback.read_bytes() != target.read_bytes():
        raise RuntimeError('Full boot partition readback mismatch; refusing to boot.')
    run([python, 'tools/da-fastboot.py', '--mode', 'home'], 'source-mrdumpfix-home-finish.txt')
    with (root / 'RECOVERY-CHECKPOINT.md').open('a') as checkpoint:
        checkpoint.write('\nAUTOMATEDSOURCEFIX installed/fullreadbackverified/homeACK. SHA ' +
                         metadata['partition_sha256'] + '\nArtifact ' + name +
                         '.partition.img; phone needs unplug5/reconnect/power3.\n' +
                         'No GPT/preloader/otherpartition/chargingwrites. Source boot not yet validated.\n')
    status('ready_for_boot', partition_sha256=metadata['partition_sha256'],
           instruction='Unplug USB for 5 seconds, reconnect, hold power 3 seconds once, leave connected; report display.')
except Exception as error:
    status('failed', failed_phase=phase, error=str(error),
           instruction='Do not reboot or start another flasher; inspect logs first.')
    sys.exit(1)
