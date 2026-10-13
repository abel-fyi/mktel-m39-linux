#!/usr/bin/env python3
"""Download a known-length file over the phone's raw USB serial shell."""
import argparse, hashlib, re, shlex, struct, time
from pathlib import Path
import usb.core, usb.util

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('remote');p.add_argument('local',type=Path)
p.add_argument('--size',type=int,required=True);p.add_argument('--sha256',required=True)
a=p.parse_args()
assert a.size>0 and re.fullmatch('[0-9a-f]{64}',a.sha256)
device=usb.core.find(idVendor=0x18d1,idProduct=0x4ee7)
if device is None:raise SystemExit('Normal-mode Linux USB interface missing')
try:
 cfg=device.get_active_configuration()
 control=next(i for i in cfg if i.bInterfaceClass==2)
 interface=next(i for i in cfg if i.bInterfaceClass==0x0a)
 for i in [control,interface]:
  if device.is_kernel_driver_active(i.bInterfaceNumber):device.detach_kernel_driver(i.bInterfaceNumber)
  usb.util.claim_interface(device,i.bInterfaceNumber)
 ep_in=next(e for e in interface if usb.util.endpoint_direction(e.bEndpointAddress)==usb.util.ENDPOINT_IN)
 ep_out=next(e for e in interface if usb.util.endpoint_direction(e.bEndpointAddress)==usb.util.ENDPOINT_OUT)
 device.ctrl_transfer(0x21,0x20,0,control.bInterfaceNumber,struct.pack('<IBBB',115200,0,0,8),timeout=1000)
 device.ctrl_transfer(0x21,0x22,3,control.bInterfaceNumber,b'',timeout=1000)
 time.sleep(.3)
 cmd="stty raw -echo; printf '\\n__M39_BINARY_BEGIN__\\n'; dd if="+shlex.quote(a.remote)+" bs=65536 2>/run/usb-download.log; printf '\\n__M39_BINARY_END__\\n'; stty sane; stty -echo\n"
 ep_out.write(cmd.encode(),timeout=3000)
 prefix=bytearray();end=time.monotonic()+30
 while time.monotonic()<end:
  try:prefix.extend(bytes(ep_in.read(65536,timeout=500)))
  except usb.core.USBTimeoutError:continue
  m=re.search(rb'(?:^|[\r\n])__M39_BINARY_BEGIN__\r?\n',prefix)
  if m:
   pending=bytes(prefix[m.end():]);break
 else:raise RuntimeError('Binary transfer start marker absent')
 digest=hashlib.sha256();received=0;start=time.monotonic();deadline=start+300
 with a.local.open('xb') as target:
  a.local.chmod(0o600)
  while received<a.size:
   if time.monotonic()>deadline:raise RuntimeError('Binary transfer deadline exceeded')
   if not pending:
    try:pending=bytes(ep_in.read(min(65536,a.size-received),timeout=1000))
    except usb.core.USBTimeoutError:continue
   chunk=pending[:a.size-received];pending=pending[len(chunk):]
   target.write(chunk);digest.update(chunk);received+=len(chunk)
 suffix=bytearray(pending);end=time.monotonic()+15
 while b'__M39_BINARY_END__' not in suffix and time.monotonic()<end:
  try:suffix.extend(bytes(ep_in.read(4096,timeout=500)))
  except usb.core.USBTimeoutError:continue
 if b'__M39_BINARY_END__' not in suffix:raise RuntimeError('Binary transfer completion marker absent')
 if digest.hexdigest()!=a.sha256:raise RuntimeError('Downloaded checksum mismatch')
 print(f'Downloaded and verified {received} bytes in {time.monotonic()-start:.1f}s: {a.local}')
finally:
 usb.util.dispose_resources(device)
