#!/usr/bin/env python3
"""Upload a file to the running Alpine phone through its serial shell."""
import argparse, base64, hashlib, re, shlex, struct, time
from pathlib import Path
import usb.core, usb.util

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('local',type=Path)
p.add_argument('remote')
p.add_argument('--execute',action='store_true')
p.add_argument('--recover',action='store_true',help='Finish an upload whose receiver is already waiting for input.')
a=p.parse_args()
data=a.local.read_bytes(); digest=hashlib.sha256(data).hexdigest()
device=None
for vid,pid in [(0x18d1,0x4ee7),(0x0e8d,0x2008),(0x0e8d,0x2009)]:
    device=usb.core.find(idVendor=vid,idProduct=pid)
    if device is not None: break
if device is None: raise SystemExit('Phone USB interface not found.')
try:
    cfg=device.get_active_configuration()
    control=next((i for i in cfg if i.bInterfaceClass==2),None)
    interface=next((i for i in cfg if i.bInterfaceClass==0x0a),None)
    if interface is None:
        interface=next(i for i in cfg if i.bInterfaceClass==0xff and sum(usb.util.endpoint_type(e.bmAttributes)==2 for e in i)==2)
    for i in [i for i in [control,interface] if i is not None]:
        if device.is_kernel_driver_active(i.bInterfaceNumber): device.detach_kernel_driver(i.bInterfaceNumber)
        usb.util.claim_interface(device,i.bInterfaceNumber)
    ep_in=next(e for e in interface if usb.util.endpoint_direction(e.bEndpointAddress)==usb.util.ENDPOINT_IN)
    ep_out=next(e for e in interface if usb.util.endpoint_direction(e.bEndpointAddress)==usb.util.ENDPOINT_OUT)
    if control is not None:
        device.ctrl_transfer(0x21,0x20,0,control.bInterfaceNumber,struct.pack('<IBBB',115200,0,0,8),timeout=1000)
        device.ctrl_transfer(0x21,0x22,3,control.bInterfaceNumber,b'',timeout=1000)
    def read_until(marker,seconds=30):
        result=bytearray();end=time.monotonic()+seconds
        pattern=rb'(?:^|[\r\n])'+marker.encode()+rb'[\r\n]'
        while time.monotonic()<end:
            try: result.extend(bytes(ep_in.read(512,timeout=200)))
            except usb.core.USBTimeoutError: continue
            if re.search(pattern,result):return bytes(result)
        raise RuntimeError('Missing transfer marker '+marker+': '+result[-1500:].decode(errors='replace'))
    time.sleep(.3)
    if a.recover:
        ep_out.write(b'\x04',timeout=3000)
        read_until('__UPLOAD_DONE__')
    target=shlex.quote(a.remote)
    command=f"stty icanon -echo; printf '\\n__UPLOAD_READY__\\n'; base64 -d > {target}; chmod 755 {target}; stty sane; stty -echo; sha256sum {target}; printf '\\n__UPLOAD_DONE__\\n'\n"
    ep_out.write(command.encode(),timeout=3000)
    read_until('__UPLOAD_READY__')
    encoded=base64.b64encode(data)
    payload=b'\n'.join(encoded[i:i+76] for i in range(0,len(encoded),76))+b'\n'
    for i in range(0,len(payload),1024):
        ep_out.write(payload[i:i+1024],timeout=5000)
        time.sleep(.002)
    ep_out.write(b'\x04',timeout=3000)
    result=read_until('__UPLOAD_DONE__',max(30,len(data)/100000))
    if digest.encode() not in result:raise RuntimeError('Uploaded file checksum mismatch: '+result.decode(errors='replace'))
    print(f'Uploaded and verified {len(data)} bytes to {a.remote}',flush=True)
    if a.execute:
        ep_out.write((target+"; printf '\\n__EXEC_DONE__\\n'\n").encode(),timeout=3000)
        print(read_until('__EXEC_DONE__').decode(errors='replace'),flush=True)
finally:
    usb.util.dispose_resources(device)
