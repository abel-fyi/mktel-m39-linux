#!/usr/bin/env python3
"""Package the charging-disabled source kernel with the verified RAM-only rescue."""
from pathlib import Path
import argparse, gzip, hashlib, json, struct, subprocess
from bootramdisk import append_files

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--name', default='alpine-m39-source-diagnostic')
parser.add_argument('--dtb', type=Path, help='Use an explicitly reviewed replacement base DTB.')
parser.add_argument('--charge-tools', action='store_true',
                    help='Include diagnostic helpers; startup remains off unless separately enabled.')
parser.add_argument('--initcall-trace', action='store_true',
                    help='Require source markers and enable verbose boot logs without automatic panic reboot.')
parser.add_argument('--bounded-charge-startup', action='store_true',
                    help='Start explicitly experimental bounded charging at boot; requires --charge-tools.')
parser.add_argument('--package', type=Path, action='append', default=[],
                    help='Include a signed offline APK in the rescue image.')
args = parser.parse_args()
assert not args.bounded_charge_startup or args.charge_tools
assert Path(args.name).name == args.name

root = Path(__file__).resolve().parent.parent
template_path = root / 'artifacts/alpine-m39-charge-lowpower.partition.img'
image_path = root / 'build/mt6735-source/arch/arm64/boot/Image'
dtb_path = args.dtb or root / 'analysis/boot-base-overlay-compatible.dtb'
template = template_path.read_bytes()
assert template[:8] == b'ANDROID!' and len(template) == 16 * 1024 * 1024
words = struct.unpack_from('<10I', template, 8)
page = words[7]
assert page == 2048 and words[4] == 0 and words[8] == 0
align = lambda n: (n + page - 1) // page * page
ramdisk_offset = page + align(words[0])
ramdisk = template[ramdisk_offset:ramdisk_offset + words[2]]
assert gzip.decompress(ramdisk).startswith(b'070701')
charge_files = {}
package_files = {}
for package in args.package:
    assert package.suffix == '.apk' and package.is_file()
    destination = 'opt/packages/' + package.name
    assert destination not in package_files
    package_files[destination] = package.read_bytes()
if args.charge_tools:
    charge_files = {
        'usr/local/sbin/m39-charge': (root / 'tools/m39-charge.sh').read_bytes(),
        'usr/local/sbin/m39-battery-status': (root / 'tools/m39-battery-status.sh').read_bytes(),
        'usr/local/libexec/m39/m39-low-battery-policy.sh': (root / 'tools/m39-low-battery-policy.sh').read_bytes(),
        'usr/local/libexec/m39/m39-low-battery-monitor.sh': (root / 'tools/m39-low-battery-monitor.sh').read_bytes(),
        'usr/local/sbin/m39-poweroff': (root / 'tools/m39-poweroff.sh').read_bytes(),
        'usr/local/sbin/poweroff': (root / 'tools/m39-poweroff.sh').read_bytes(),
        'usr/local/libexec/m39/m39-charge-policy.sh': (root / 'tools/m39-charge-policy.sh').read_bytes(),
        'usr/local/libexec/m39/m39-charge-broker.sh': (root / 'tools/m39-charge-broker.sh').read_bytes(),
        'usr/local/libexec/m39/m39-pmic-pulse.sh': (root / 'tools/m39-pmic-pulse.sh').read_bytes(),
        'usr/local/libexec/m39/m39-plug-charge.sh': (root / 'tools/m39-plug-charge.sh').read_bytes(),
        'usr/local/libexec/m39/m39-fg-sample': (root / 'artifacts/m39-fg-sample').read_bytes(),
        'usr/local/libexec/m39/m39-adc-sample': (root / 'artifacts/m39-adc-sample').read_bytes(),
        'usr/local/sbin/m39-screen': (root / 'tools/m39-screen.sh').read_bytes(),
        'usr/local/libexec/m39/m39-screen-idle': (root / 'artifacts/m39-screen-idle').read_bytes(),
    }
    if args.bounded_charge_startup:
        charge_files['usr/local/libexec/m39/m39-charge-startup'] = (root / 'tools/m39-charge-startup.sh').read_bytes()
        # Keep the rescue init identical except for this explicit background hook.
        from bootramdisk import entries
        archive = gzip.decompress(ramdisk)
        rows = list(entries(archive))
        init_row = next(row for row in rows if row[0] == 'init')
        hook = b'/usr/local/libexec/m39/m39-charge-startup > /run/m39-charge-startup.log 2>&1 &\n'
        marker = b'while :; do\n'
        assert init_row[2].count(marker) == 1
        revised = init_row[2].replace(marker, hook + marker)
        # Rebuild only this entry; preserve all other newc entries byte-for-byte.
        from bootramdisk import replace_file
        ramdisk = gzip.compress(replace_file(archive, 'init', revised), mtime=0)
    assert charge_files['usr/local/libexec/m39/m39-fg-sample'][:4] == b'\x7fELF'
if charge_files or package_files:
    ramdisk = gzip.compress(append_files(gzip.decompress(ramdisk), {**charge_files, **package_files}), mtime=0)
image = image_path.read_bytes()
assert image[0x38:0x3c] == b'ARMd'
dtb = dtb_path.read_bytes()
assert dtb[:4] == bytes.fromhex('d00dfeed')
kernel = gzip.compress(image, mtime=0) + dtb
header = bytearray(template[:page])
if args.initcall_trace:
    assert 'M39 source bring-up: reserved scanout breadcrumbs' in (root / 'tools/mt6735-kernel/init/main.c').read_text()
    command_line = (bytes(header[64:576]).split(b'\0')[0] +
                    bytes(header[608:1632]).split(b'\0')[0]).decode()
    command_line = command_line.replace('panic=10', 'panic=0')
    command_line += ' initcall_debug ignore_loglevel'
    encoded = command_line.encode()
    assert len(encoded) < 512
    header[64:576] = encoded.ljust(512, b'\0')
    header[608:1632] = bytes(1024)
struct.pack_into('<I', header, 8, len(kernel))
struct.pack_into('<I', header, 16, len(ramdisk))
digest = hashlib.sha1()
for payload in [kernel, ramdisk, b'']:
    digest.update(payload)
    digest.update(struct.pack('<I', len(payload)))
header[576:608] = digest.digest() + bytes(12)
boot = bytes(header) + kernel.ljust(align(len(kernel)), b'\0') + ramdisk.ljust(align(len(ramdisk)), b'\0')
assert len(boot) <= len(template)
partition = boot.ljust(len(template), b'\0')
name = args.name
out = root / 'artifacts'
(out / (name + '.img')).write_bytes(boot)
(out / (name + '.partition.img')).write_bytes(partition)
metadata = {
    'source_commit': subprocess.check_output(['git', '-C', str(root / 'tools/mt6735-kernel'), 'rev-parse', 'HEAD'], text=True).strip(),
    'kernel_release': (root / 'build/mt6735-source/include/config/kernel.release').read_text().strip(),
    'raw_kernel_sha256': hashlib.sha256(image).hexdigest(),
    'ramdisk_sha256': hashlib.sha256(ramdisk).hexdigest(),
    'ramdisk_identical_to': None if (args.charge_tools or package_files) else str(template_path.relative_to(root)),
    'ramdisk_template': str(template_path.relative_to(root)),
    'bundled_charge_files': {name: hashlib.sha256(payload).hexdigest() for name, payload in charge_files.items()},
    'bundled_extra_files': {name: hashlib.sha256(payload).hexdigest() for name, payload in package_files.items()},
    'charging_auto_armed': args.bounded_charge_startup,
    'bounded_charge_startup': args.bounded_charge_startup,
    'dtb_sha256': hashlib.sha256(dtb).hexdigest(),
    'boot_bytes': len(boot),
    'partition_sha256': hashlib.sha256(partition).hexdigest(),
    'charging': 'disabled unconditionally in PMIC charging_enable; diagnostic only',
    'section_mismatch_warnings': 61,
    'limitations': 'Revised source image not yet boot-tested; Linux 3.18.19; legacy init-memory references; battery-temperature input unvalidated',
    'initcall_trace': args.initcall_trace,
    'initcall_trace_address': '0xbffb0000' if args.initcall_trace else None,
}
(out / (name + '.json')).write_text(json.dumps(metadata, indent=2) + '\n')
print(json.dumps(metadata, indent=2))
