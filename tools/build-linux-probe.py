#!/usr/bin/env python3
"""Build a RAM-only Linux boot experiment from the backed-up vendor kernel."""
import gzip
import hashlib
import json
import stat
import struct
import argparse
import zlib
import tarfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
out = root / 'artifacts'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--dtb', type=Path, help='Replace appended DTB, preserving the compressed kernel stream.')
parser.add_argument('--name', default='linux-probe', help='Output boot-image basename.')
parser.add_argument('--disable-framebuffer', action='store_true',
                    help='Skip the mtkfb_init function identified in this exact kernel crash trace.')
parser.add_argument('--fix-charger-detection', action='store_true',
                    help='Legacy boot workaround selecting the donor BQ24157 driver despite failed detection; charging is unverified.')
parser.add_argument('--usb-serial', action='store_true', help='Use the built-in ACM serial console instead of ADB.')
parser.add_argument('--charging-usb-console', action='store_true',
                    help='Honor userspace USB function/descriptors in charging boot; leave charging policy unchanged.')
parser.add_argument('--rootfs', type=Path, help='Use an Alpine minirootfs tarball for the userspace.')
parser.add_argument('--map-display-buffer', action='store_true',
                    help='Restrict disp_mgr mmap to the verified M39 reserved scanout buffer.')
parser.add_argument('--display-terminal', type=Path, help='Include and start the userspace display terminal.')
parser.add_argument('--package', type=Path, action='append', default=[], help='Install a signed local APK at boot.')
parser.add_argument('--init-file', type=Path, help='Use this explicitly reviewed custom /init script.')
parser.add_argument('--extra-file', action='append', default=[], metavar='SOURCE:DESTINATION', help='Add a program/script to the ramdisk.')
args = parser.parse_args()
assert Path(args.name).name == args.name
boot = (root / 'backups/initial/boot.img').read_bytes()
assert boot[:8] == b'ANDROID!'
header = bytearray(boot[:2048])
words = struct.unpack_from('<10I', boot, 8)
kernel_size, page = words[0], words[7]
assert page == 2048 and words[4] == 0 and words[8] == 0
kernel = boot[page:page + kernel_size]
kernel_patches = []
if args.dtb or args.disable_framebuffer or args.fix_charger_detection or args.map_display_buffer or args.charging_usb_console:
    stream = zlib.decompressobj(31)
    executable = stream.decompress(kernel)
    assert stream.eof and stream.unused_data[:4] == b'\xd0\x0d\xfe\xed'
    dtb = args.dtb.read_bytes() if args.dtb else stream.unused_data
    assert dtb[:4] == b'\xd0\x0d\xfe\xed'
    compressed = kernel[:len(kernel) - len(stream.unused_data)]
    changed = bytearray(executable)
    if args.disable_framebuffer:
        # Crash trace: mtkfb_init+0x20 at ffffffc000cfcdf0.
        # Image text starts at ffffffc000080000. Disassembly independently
        # confirmed this prologue and call to __platform_driver_register.
        address, offset = 0xffffffc000cfcdd0, 0xc7cdd0
        before = bytes.fromhex('fd7bbea9400700d0')
        after = bytes.fromhex('00008052c0035fd6')  # mov w0, #0; ret
        assert executable[offset:offset + 8] == before
        changed[offset:offset + 8] = after
        kernel_patches.append(dict(address=hex(address), offset=offset,
                                   before=before.hex(), after=after.hex(),
                                   reason='Return success from mtkfb_init without registering the incompatible framebuffer driver.'))
    if args.fix_charger_detection:
        # CORRECTION 2026-10-12: component detection sets flag1 on FAILED
        # reads; zero means matched ID0x51/0x41. This legacy inversion selected
        # an unresponsive donor driver to avoid a NULL-callback boot panic.
        # Retained only to reproduce the working diagnostic boot image.
        # It does NOT prove charger presence or correct charging. See FINDINGS.
        address, offset = 0xffffffc0003dc3e8, 0x35c3e8
        before = bytes.fromhex('fd7bbea9a05200d0fd030091f30b00f9d34f0090')
        # adrp x0, dd4000; ldr w0,[x0,#ec8]; cmp w0,#0; cset w0,eq; ret
        after = bytes.fromhex('c04f009000c84eb91f000071e0179f1ac0035fd6')
        assert executable[offset:offset + len(before)] == before
        changed[offset:offset + len(after)] = after
        kernel_patches.append(dict(address=hex(address), offset=offset,
                                   before=before.hex(), after=after.hex(),
                                   hardware_flag_address='0xffffffc000dd4ec8',
                                   reason='Legacy NULL-callback boot workaround; donor charger detection failed and charging is unverified.'))
    if args.map_display_buffer:
        # Live overlay: 240x320 ARGB8888, stride 1024, base 0xbfea0000.
        # Chosen atag,videolfb reserves 0x120000 bytes. Replace the existing
        # register-only mmap bounds with ONLY this reserved buffer, retaining
        # the overflow/end checks and noncached mapping attributes.
        for offset, before_hex, after_hex in [
            (0x3e4c48, '9f4640f1', '9f8244f1'),
            (0x3e4c5c, 'e0ff8dd2', 'e0ff9fd2'),
            (0x3e4c60, '0080a2f2', '20fdb7f2'),
            (0x3e4c68, '000090d2', '000080d2'),
            (0x3e4c6c, '2080a2f2', '80ffb7f2'),
        ]:
            before, after = bytes.fromhex(before_hex), bytes.fromhex(after_hex)
            assert executable[offset:offset + 4] == before
            changed[offset:offset + 4] = after
            kernel_patches.append(dict(address=hex(0xffffffc000080000 + offset),
                offset=offset, before=before_hex, after=after_hex,
                reason='Permit mmap only within the verified reserved M39 display buffer.'))
    if args.charging_usb_console:
        # Exact-kernel disassembly: these four get_boot_mode calls are only
        # within Android USB enable_store/functions_store. Modes 8/9 override
        # userspace descriptors and force MTP. Return normal mode locally;
        # do NOT change get_boot_mode or battery/charger callers globally.
        for offset, before_hex in [
            (0x5c018c, '2f23f897'),
            (0x5c0288, 'f022f897'),
            (0x5c0410, '8e22f897'),
            (0x5c0468, '7822f897'),
        ]:
            before = bytes.fromhex(before_hex)
            after = bytes.fromhex('00008052')  # mov w0,#0
            assert executable[offset:offset + 4] == before
            changed[offset:offset + 4] = after
            kernel_patches.append(dict(address=hex(0xffffffc000080000 + offset),
                offset=offset, before=before.hex(), after=after.hex(),
                reason='Honor configured ACM USB function/descriptors in charging boot; charger policy unchanged.'))
    if args.disable_framebuffer or args.fix_charger_detection or args.map_display_buffer or args.charging_usb_console:
        compressed = gzip.compress(bytes(changed), mtime=0)
    kernel = compressed + dtb
    struct.pack_into('<I', header, 8, len(kernel))
adbd = bytearray((root / 'analysis/recovery-files/sbin/adbd').read_bytes())
assert adbd[:6] == b'\x7fELF\x02\x01'
phoff = struct.unpack_from('<Q', adbd, 32)[0]
phsize, phnum = struct.unpack_from('<HH', adbd, 54)

def file_offset(address):
    for i in range(phnum):
        kind, flags, offset, virtual, physical, filesz, memsz, align = struct.unpack_from(
            '<II6Q', adbd, phoff + i * phsize)
        if kind == 1 and virtual <= address < virtual + filesz:
            return offset + address - virtual
    raise ValueError(f'Address {address:#x} is not file-backed')

# Adapt this saved, statically linked recovery daemon for our property-service-free
# diagnostic userspace. Preserve root and allow this laptop's USB connection.
patches = []
for address, before, after, reason in [
    (0x404EFC, bytes.fromhex('68100037'), struct.pack('<I', 0x14000083),
     'Skip property-controlled privilege drop; retain root in the diagnostic ramdisk.'),
    (0x5461F4, b'\x01', b'\x00',
     'Disable ADB authentication for the temporary USB diagnostic image.'),
]:
    offset = file_offset(address)
    assert adbd[offset:offset + len(before)] == before, f'Unexpected bytes at {address:#x}'
    adbd[offset:offset + len(after)] = after
    patches.append(dict(address=hex(address), offset=offset, before=before.hex(),
                        after=after.hex(), reason=reason))
(out / 'adbd-linux-probe').write_bytes(adbd)
(out / 'adbd-patches.json').write_text(json.dumps(patches, indent=2) + '\n')

init = b'''#!/bin/sh
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/system/bin
export HOME=/root
export SHELL=/system/bin/sh
export TERM=xterm
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t tmpfs -o mode=0755 tmpfs /dev
mknod /dev/console c 5 1
mknod /dev/null c 1 3
mknod /dev/kmsg c 1 11
chmod 666 /dev/null
mkdir -p /dev/pts /dev/socket /dev/usb-ffs/adb /run
mount -t devpts devpts /dev/pts
ln -s /proc/self/fd /dev/fd
ln -s /proc/self/fd/0 /dev/stdin
ln -s /proc/self/fd/1 /dev/stdout
ln -s /proc/self/fd/2 /dev/stderr
echo /bin/mdev > /proc/sys/kernel/hotplug
mdev -s
echo 'MKTEL Linux RAM probe: init reached' > /dev/kmsg
echo 'Native Linux userspace: BusyBox on the saved MediaTek kernel.' > /etc/motd
echo 'No Android framework; no eMMC filesystems are mounted.' >> /etc/motd
echo MKTEL-Linux-probe > /proc/sys/kernel/hostname
g=/sys/class/android_usb/android0
echo 0 > $g/enable
echo 18d1 > $g/idVendor
echo 4ee7 > $g/idProduct
echo MKTEL > $g/iManufacturer
echo Linux-RAM-probe > $g/iProduct
echo m39-linux-probe > $g/iSerial
echo adb > $g/functions
mount -t functionfs adb /dev/usb-ffs/adb
/sbin/adbd > /run/adbd.log 2>&1 &
daemon=$!
count=0
while [ ! -e /dev/usb-ffs/adb/ep1 ] && [ $count -lt 15 ]; do
    sleep 1
    count=$((count + 1))
done
echo 1 > $g/enable
echo 'MKTEL Linux RAM probe: USB configured' > /dev/kmsg
while :; do
    sleep 10
    if ! kill -0 $daemon 2>/dev/null; then
        /sbin/adbd >> /run/adbd.log 2>&1 &
        daemon=$!
    fi
done
'''
if args.usb_serial:
    prefix = init[:init.index(b'g=/sys/class/android_usb/android0')]
    init = prefix + b'''g=/sys/class/android_usb/android0
echo 0 > $g/enable
echo 18d1 > $g/idVendor
echo 4ee7 > $g/idProduct
echo MKTEL > $g/iManufacturer
echo Native-Linux-serial > $g/iProduct
echo m39-linux-serial > $g/iSerial
if [ -e $g/f_acm/instances ]; then echo 1 > $g/f_acm/instances; fi
echo acm > $g/functions
echo 1 > $g/enable
mdev -s
echo 'MKTEL native Linux: ACM console configured' > /dev/kmsg
while :; do
    if [ ! -e /dev/ttyGS0 ]; then mdev -s; sleep 1; continue; fi
    /bin/busybox stty -F /dev/ttyGS0 raw -echo
    printf '\\nM39_NATIVE_LINUX_CONSOLE\\n' > /dev/ttyGS0
    /bin/sh -i < /dev/ttyGS0 > /dev/ttyGS0 2>&1
    sleep 1
done
'''
if args.package or args.display_terminal:
    assert args.rootfs and args.usb_serial
    startup = b'echo m39 > /proc/sys/kernel/hostname\n'
    if args.package:
        startup += b'apk add --no-network /opt/packages/*.apk > /run/packages.log 2>&1\n'
    if args.display_terminal:
        startup += b'/usr/local/bin/m39-terminal > /run/display-terminal.log 2>&1 &\n'
    init = init.replace(b'while :; do\n', startup + b'while :; do\n', 1)
if args.init_file:
    init = args.init_file.read_bytes()
(out / 'linux-probe-init').write_bytes(init)
archive = bytearray()
inode = 1
root_entries = {}
if args.rootfs:
    assert args.usb_serial, 'The Alpine rootfs experiment uses the serial transport.'
    with tarfile.open(args.rootfs, 'r:gz') as source:
        for member in source.getmembers():
            name = member.name
            while name.startswith('./'):
                name = name[2:]
            name = name.rstrip('/')
            if not name or name == '.':
                continue
            assert not name.startswith('/') and '..' not in Path(name).parts
            if member.isdir():
                value = (stat.S_IFDIR | member.mode, b'', 0, 0)
            elif member.issym():
                value = (stat.S_IFLNK | member.mode, member.linkname.encode(), 0, 0)
            elif member.isfile() or member.islnk():
                value = (stat.S_IFREG | member.mode, source.extractfile(member).read(), 0, 0)
            elif member.ischr() or member.isblk():
                value = ((stat.S_IFCHR if member.ischr() else stat.S_IFBLK) | member.mode,
                         b'', member.devmajor, member.devminor)
            else:
                continue
            root_entries[name] = value

def entry(name, mode, payload=b'', major=0, minor=0):
    global inode
    encoded = name.encode() + b'\0'
    values = [inode, mode, 0, 0, 2 if stat.S_ISDIR(mode) else 1, 0, len(payload),
              0, 0, major, minor, len(encoded), 0]
    archive.extend(b'070701' + ''.join(f'{v:08x}' for v in values).encode())
    archive.extend(encoded)
    archive.extend(b'\0' * (-len(archive) % 4))
    archive.extend(payload)
    archive.extend(b'\0' * (-len(archive) % 4))
    inode += 1

for package in args.package:
    root_entries['opt/packages/' + package.name] = (stat.S_IFREG | 0o644, package.read_bytes(), 0, 0)
if args.package:
    root_entries.setdefault('opt', (stat.S_IFDIR | 0o755, b'', 0, 0))
    root_entries['opt/packages'] = (stat.S_IFDIR | 0o755, b'', 0, 0)
if args.display_terminal:
    root_entries.setdefault('usr/local', (stat.S_IFDIR | 0o755, b'', 0, 0))
    root_entries.setdefault('usr/local/bin', (stat.S_IFDIR | 0o755, b'', 0, 0))
    root_entries['usr/local/bin/m39-terminal'] = (stat.S_IFREG | 0o755, args.display_terminal.read_bytes(), 0, 0)
for specification in args.extra_file:
    source, destination = specification.rsplit(':', 1)
    name = destination.lstrip('/')
    assert name and '..' not in Path(name).parts
    for parent in Path(name).parents:
        if str(parent) != '.':
            root_entries.setdefault(str(parent), (stat.S_IFDIR | 0o755, b'', 0, 0))
    root_entries[name] = (stat.S_IFREG | 0o755, Path(source).read_bytes(), 0, 0)

for name in sorted(root_entries):
    if name not in ['init', 'dev/console', 'dev/null', 'etc/profile']:
        entry(name, *root_entries[name])

for name in ['bin', 'sbin', 'etc', 'proc', 'sys', 'dev', 'run', 'tmp', 'root',
             'system', 'system/bin']:
    if name not in root_entries:
        entry(name, stat.S_IFDIR | (0o1777 if name == 'tmp' else 0o755))
entry('dev/console', stat.S_IFCHR | 0o600, major=5, minor=1)
entry('dev/null', stat.S_IFCHR | 0o666, major=1, minor=3)
if not args.rootfs:
    entry('bin/busybox', stat.S_IFREG | 0o755, (out / 'busybox-aarch64').read_bytes())
for name in ['bin/sh', 'bin/mount', 'bin/mknod', 'bin/chmod', 'bin/mkdir',
             'bin/ln', 'bin/sleep', 'bin/mdev', 'bin/cat', 'bin/id', 'bin/uname',
             'bin/readlink', 'bin/stty', 'bin/ls', 'bin/ps', 'bin/dmesg', 'bin/grep',
             'bin/sed', 'bin/head', 'bin/date', 'bin/reboot', 'system/bin/sh']:
    if name not in root_entries:
        entry(name, stat.S_IFLNK | 0o777, b'/bin/busybox')
if not args.usb_serial:
    entry('sbin/adbd', stat.S_IFREG | 0o755, bytes(adbd))
entry('init', stat.S_IFREG | 0o755, init)
if 'etc/passwd' not in root_entries:
    entry('etc/passwd', stat.S_IFREG | 0o644, b'root:x:0:0:root:/root:/bin/sh\nshell:x:2000:2000:shell:/:/bin/sh\n')
if 'etc/group' not in root_entries:
    entry('etc/group', stat.S_IFREG | 0o644, b'root:x:0:\nshell:x:2000:\n')
profile = root_entries.get('etc/profile', (0, b'', 0, 0))[1]
entry('etc/profile', stat.S_IFREG | 0o644, profile + b'\nexport HOME=/root\ncat /etc/motd\n')
entry('TRAILER!!!', 0)
archive.extend(b'\0' * (-len(archive) % 512))
(out / 'linux-probe.cpio').write_bytes(archive)
ramdisk = gzip.compress(bytes(archive), mtime=0)
(out / 'linux-probe.cpio.gz').write_bytes(ramdisk)
struct.pack_into('<I', header, 16, len(ramdisk))
command = b'bootopt=64S3,32N2,64N2 buildvariant=user selinux=0 enforcing=0 rdinit=/init panic=10'
header[64:576] = command.ljust(512, b'\0')
header[608:1632] = b'\0' * 1024
digest = hashlib.sha1()
for payload in [kernel, ramdisk, b'']:
    digest.update(payload)
    digest.update(struct.pack('<I', len(payload)))
header[576:608] = digest.digest().ljust(32, b'\0')
image = bytes(header) + kernel + b'\0' * (-len(kernel) % page)
image += ramdisk + b'\0' * (-len(ramdisk) % page)
assert len(image) < 0x1000000
(out / (args.name + '.img')).write_bytes(image)
partition_image = image + boot[len(image):]
assert len(partition_image) == len(boot)
(out / (args.name + '.partition.img')).write_bytes(partition_image)
manifest = dict(image_bytes=len(image), image_sha256=hashlib.sha256(image).hexdigest(),
                partition_image_sha256=hashlib.sha256(partition_image).hexdigest(),
                kernel_sha256=hashlib.sha256(kernel).hexdigest(),
                ramdisk_bytes=len(ramdisk), cmdline=command.decode(),
                dtb_override=str(args.dtb) if args.dtb else None,
                kernel_patches=kernel_patches,
                usb_transport='acm' if args.usb_serial else 'adb',
                rootfs_source=str(args.rootfs) if args.rootfs else None,
                packages=[str(p) for p in args.package],
                display_terminal=str(args.display_terminal) if args.display_terminal else None,
                custom_init=str(args.init_file) if args.init_file else None,
                extra_files=args.extra_file,
                purpose=('Native Alpine with an experimental userspace display terminal.'
                         if args.display_terminal else 'Native headless Linux boot experiment.'))
(out / (args.name + '.json')).write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(manifest, indent=2))
