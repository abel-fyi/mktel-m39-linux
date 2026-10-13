#!/usr/bin/env python3
"""Package encrypted-root bootstrap around the verified source storage kernel."""
import argparse, gzip, hashlib, json, struct, subprocess
from pathlib import Path
from bootramdisk import entries, replace_file, append_files

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-name', default='alpine-m39-storage-tools')
args = parser.parse_args()
assert Path(args.source_name).name == args.source_name
root = Path(__file__).resolve().parent.parent
metadata = json.loads((root/'artifacts/encrypted-internal-root.json').read_text())
base_meta = json.loads((root/'artifacts'/f'{args.source_name}.json').read_text())
base = (root/'artifacts'/f'{args.source_name}.partition.img').read_bytes()
assert hashlib.sha256(base).hexdigest() == base_meta['partition_sha256']
script = (root/'tools/encrypted-unlock-template.sh').read_text().replace('@LUKS_UUID@', metadata['luks_uuid'])
script = script.replace('LUKS2 microSD unlock', 'LUKS2 internal root unlock').replace('Waiting for the encrypted microSD', 'Waiting for encrypted internal root')
(root/'artifacts/m39-unlock').write_text(script)
subprocess.run(['clang','--target=aarch64-linux-gnu','-O2','-Wall','-Wextra',
 '-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-vectorize',
 '-fno-slp-vectorize','-nostdlib','-static','-fuse-ld=lld','-Wl,-e,_start',
 '-DM39_STARTUP_COMMAND="/sbin/m39-unlock"','tools/m39-terminal.c',
 '-o','artifacts/m39-unlock-terminal'],cwd=root,check=True)
words = struct.unpack_from('<10I', base, 8)
page = words[7]
assert page == 2048 and words[4] == 0 and words[8] == 0
align = lambda n: (n+page-1)//page*page
kernel = base[page:page+words[0]]
start = page+align(words[0])
archive = gzip.decompress(base[start:start+words[2]])
init = (root/'tools/encrypted-ram-init.sh').read_bytes()
terminal = (root/'artifacts/m39-unlock-terminal').read_bytes()
archive = replace_file(archive, 'init', init)
archive = replace_file(archive, 'usr/local/bin/m39-terminal', terminal)
archive = append_files(archive, {'sbin/m39-unlock':script.encode()})
original = {n:(v,p) for n,v,p,*_ in entries(gzip.decompress(base[start:start+words[2]]))}
current = {n:(v,p) for n,v,p,*_ in entries(archive)}
for n,value in original.items():
    if n not in ('init','usr/local/bin/m39-terminal','TRAILER!!!'):
        assert current[n] == value, n
for name in ('alpine-sd-temporary-passphrase','microsd-home-key'):
    assert (root/'secrets'/name).read_bytes() not in archive
ramdisk = gzip.compress(archive,mtime=0)
header = bytearray(base[:page])
struct.pack_into('<I',header,16,len(ramdisk))
digest = hashlib.sha1()
for payload in (kernel,ramdisk,b''):
    digest.update(payload);digest.update(struct.pack('<I',len(payload)))
header[576:608] = digest.digest()+bytes(12)
boot = bytes(header)+kernel.ljust(align(len(kernel)),b'\0')+ramdisk.ljust(align(len(ramdisk)),b'\0')
assert len(boot)<=len(base)
partition = boot.ljust(len(base),b'\0')
name = 'alpine-m39-encrypted-source'
(root/'artifacts'/f'{name}.img').write_bytes(boot)
(root/'artifacts'/f'{name}.partition.img').write_bytes(partition)
result = dict(source_image=f'{args.source_name}.partition.img',
 source_partition_sha256=base_meta['partition_sha256'],
 partition_sha256=hashlib.sha256(partition).hexdigest(),
 kernel_payload_sha256=hashlib.sha256(kernel).hexdigest(),kernel_unchanged=True,
 ramdisk_sha256=hashlib.sha256(ramdisk).hexdigest(),boot_bytes=len(boot),
 luks_uuid=metadata['luks_uuid'],credentials_embedded=False,
 modified_entries=['init','usr/local/bin/m39-terminal'],added_entries=['sbin/m39-unlock'],
 charging='Bounded automatic charging before unlock and after switch_root.',
 boot_tested=False)
(root/'artifacts'/f'{name}.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
