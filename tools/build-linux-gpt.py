from pathlib import Path
import struct,zlib,hashlib,json
src=Path('/home/a/mktel/backups/initial/emmc-user.bin');out=Path('/home/a/mktel/artifacts');sectors=src.stat().st_size//512
with src.open('rb') as f:
 f.seek(512);primary=bytearray(f.read(512));f.seek((sectors-1)*512);backup=bytearray(f.read(512))
 for hdr in [primary,backup]:
  assert hdr[:8]==b'EFI PART';size=struct.unpack_from('<I',hdr,12)[0];saved=struct.unpack_from('<I',hdr,16)[0];t=bytearray(hdr[:size]);struct.pack_into('<I',t,16,0);assert zlib.crc32(t)==saved
 plba,n,esize=struct.unpack_from('<QII',primary,72);blba,bn,besize=struct.unpack_from('<QII',backup,72);assert n==bn and esize==besize and plba==2
 f.seek(plba*512);table=bytearray(f.read(n*esize));f.seek(blba*512);assert f.read(n*esize)==table
 assert zlib.crc32(table)==struct.unpack_from('<I',primary,88)[0]
 entry=lambda i:table[(i-1)*esize:i*esize]
 assert entry(23)[56:128].decode('utf-16le').rstrip('\0')=='vendor'
 assert entry(26)[56:128].decode('utf-16le').rstrip('\0')=='userdata'
 start=struct.unpack_from('<Q',entry(23),32)[0];end=struct.unpack_from('<Q',entry(26),40)[0]
 count=(n*esize+511)//512;primary_count=1+count;backup_count=sectors-blba
 f.seek(512);oldp=f.read(primary_count*512);f.seek(blba*512);oldb=f.read(backup_count*512)
 newp=bytearray(oldp);newb=bytearray(oldb)
 for i in [23,24,25]:table[(i-1)*esize:i*esize]=b'\0'*esize
 struct.pack_into('<Q',table,(26-1)*esize+32,start)
 for hdr in [primary,backup]:
  struct.pack_into('<I',hdr,88,zlib.crc32(table));struct.pack_into('<I',hdr,16,0);size=struct.unpack_from('<I',hdr,12)[0];struct.pack_into('<I',hdr,16,zlib.crc32(hdr[:size]))
 newp[:512]=primary;newp[512:512+len(table)]=table;newb[:len(table)]=table;newb[-512:]=backup
 # All untouched entry records are byte-identical; partition 26 only changes start.
 original=oldp[512:512+n*esize]
 for i in range(1,n+1):
  if i not in [23,24,25,26]:assert entry(i)==original[(i-1)*esize:i*esize]
 original26=bytearray(original[25*esize:26*esize]);struct.pack_into('<Q',original26,32,start);assert entry(26)==original26
 paths={'gpt-original-primary.bin':oldp,'gpt-original-backup.bin':oldb,'gpt-linux-primary.bin':newp,'gpt-linux-backup.bin':newb}
 for name,payload in paths.items():(out/name).write_bytes(payload)
 meta={'disk_sectors':sectors,'primary_start_sector':1,'backup_start_sector':blba,'primary_span_sectors':primary_count,'backup_span_sectors':backup_count,'root_partition_number':26,'root_start_sector':start,'root_end_sector':end,'root_sectors':end-start+1,'removed_partition_numbers':[23,24,25],'sha256':{name:hashlib.sha256(payload).hexdigest() for name,payload in paths.items()}}
 (out/'linux-gpt.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta,indent=2))
