#!/usr/bin/env python3
"""Verify encrypted bootstrap against its source image and exact public inputs."""
import gzip, hashlib, json, struct
from pathlib import Path
from bootramdisk import entries
root = Path(__file__).resolve().parent.parent
meta = json.loads((root/'artifacts/alpine-m39-encrypted-source.json').read_text())
base = (root/'artifacts'/meta['source_image']).read_bytes()
image = (root/'artifacts/alpine-m39-encrypted-source.partition.img').read_bytes()
assert hashlib.sha256(base).hexdigest() == meta['source_partition_sha256']
assert hashlib.sha256(image).hexdigest() == meta['partition_sha256']
assert len(image) == len(base) == 16777216
words = struct.unpack_from('<10I',image,8);old = struct.unpack_from('<10I',base,8)
assert words[7] == old[7] == 2048
assert all(words[i] == old[i] for i in range(10) if i != 2)
page = words[7];align=lambda n:(n+page-1)//page*page
kernel=image[page:page+words[0]]
assert kernel == base[page:page+old[0]]
start=page+align(words[0]);ramdisk=image[start:start+words[2]]
archive=gzip.decompress(ramdisk)
digest=hashlib.sha1()
for payload in (kernel,ramdisk,b''):
 digest.update(payload);digest.update(struct.pack('<I',len(payload)))
assert image[576:596] == digest.digest()
old_archive=gzip.decompress(base[start:start+old[2]])
original={n:(v,p) for n,v,p,*_ in entries(old_archive)}
current={n:(v,p) for n,v,p,*_ in entries(archive)}
assert current.keys() - original.keys() == {'sbin/m39-unlock'}
assert not (original.keys() - current.keys())
for n,value in original.items():
 if n not in ('init','usr/local/bin/m39-terminal','TRAILER!!!'):
  assert current[n] == value,n
assert current['init'][1] == (root/'tools/encrypted-ram-init.sh').read_bytes()
assert current['usr/local/bin/m39-terminal'][1] == (root/'artifacts/m39-unlock-terminal').read_bytes()
expected=(root/'tools/encrypted-unlock-template.sh').read_text().replace('@LUKS_UUID@',meta['luks_uuid'])
expected=expected.replace('LUKS2 microSD unlock','LUKS2 internal root unlock').replace('Waiting for the encrypted microSD','Waiting for encrypted internal root')
assert current['sbin/m39-unlock'][1] == expected.encode()
for n in ('alpine-sd-temporary-passphrase','microsd-home-key'):
 assert (root/'secrets'/n).read_bytes() not in archive
assert image[meta['boot_bytes']:] == bytes(len(image)-meta['boot_bytes'])
print('Verified unchanged kernel, exact bootstrap scripts, archive preservation, header ID and absence of credentials.')
