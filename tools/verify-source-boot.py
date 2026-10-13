#!/usr/bin/env python3
"""Verify packaged kernel, DTB, header lengths/ID and unchanged rescue entries."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import stat
import struct
import zlib
from bootramdisk import entries

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('metadata', type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
metadata = json.loads(args.metadata.read_text())
partition_path = args.metadata.with_suffix('.partition.img')
partition = partition_path.read_bytes()
assert len(partition) == 16777216
assert hashlib.sha256(partition).hexdigest() == metadata['partition_sha256']
assert partition[:8] == b'ANDROID!'
words = struct.unpack_from('<10I', partition, 8)
page = words[7]
assert page == 2048 and words[4] == 0 and words[8] == 0
align = lambda size: (size + page - 1) // page * page
kernel = partition[page:page+words[0]]
start = page + align(words[0])
ramdisk = partition[start:start+words[2]]
digest = hashlib.sha1()
for payload in (kernel, ramdisk, b''):
    digest.update(payload)
    digest.update(struct.pack('<I', len(payload)))
assert partition[576:596] == digest.digest()
decoder = zlib.decompressobj(31)
raw_kernel = decoder.decompress(kernel)
assert decoder.eof and raw_kernel[0x38:0x3c] == b'ARMd'
assert hashlib.sha256(raw_kernel).hexdigest() == metadata['raw_kernel_sha256']
assert decoder.unused_data[:4] == bytes.fromhex('d00dfeed')
assert hashlib.sha256(decoder.unused_data).hexdigest() == metadata['dtb_sha256']
assert hashlib.sha256(ramdisk).hexdigest() == metadata['ramdisk_sha256']
current = {name: (values, payload) for name, values, payload, _, _
           in entries(gzip.decompress(ramdisk))}
template = (root / metadata['ramdisk_template']).read_bytes()
old_words = struct.unpack_from('<10I', template, 8)
assert old_words[7] == page
old_start = page + align(old_words[0])
old_ramdisk = template[old_start:old_start+old_words[2]]
original = {name: (values, payload) for name, values, payload, _, _
            in entries(gzip.decompress(old_ramdisk)) if name != 'TRAILER!!!'}
for name, value in original.items():
    if name == 'init' and metadata.get('bounded_charge_startup'):
        hook = b'/usr/local/libexec/m39/m39-charge-startup > /run/m39-charge-startup.log 2>&1 &\n'
        expected = value[1].replace(b'while :; do\n', hook + b'while :; do\n')
        assert current[name][1] == expected
        for index in range(13):
            if index != 6:
                assert current[name][0][index] == value[0][index]
    else:
        assert current[name] == value, name
for name, checksum in {**metadata.get('bundled_charge_files', {}), **metadata.get('bundled_extra_files', {})}.items():
    values, payload = current[name]
    assert hashlib.sha256(payload).hexdigest() == checksum
    assert stat.S_ISREG(values[1]) and values[1] & 0o777 == 0o755
if not metadata.get('bounded_charge_startup'):
    assert current['init'] == original['init']
assert all(name not in current for name in
           ('run/m39-plug-charge-armed', 'run/m39-watchdog-validated'))
assert partition[metadata['boot_bytes']:] == bytes(len(partition)-metadata['boot_bytes'])
assert args.metadata.with_suffix('.img').read_bytes() == partition[:metadata['boot_bytes']]
print(json.dumps(dict(validated=True, partition_sha256=metadata['partition_sha256'],
                     original_entries_unchanged=len(original) - int(bool(metadata.get('bounded_charge_startup'))),
                     init_startup_hook_added=bool(metadata.get('bounded_charge_startup')),
                     added_files=list({**metadata.get('bundled_charge_files', {}), **metadata.get('bundled_extra_files', {})}),
                     header_lengths_and_boot_id_verified=True,
                     auto_armed=metadata.get('bounded_charge_startup', False)), indent=2))
