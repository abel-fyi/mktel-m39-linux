#!/usr/bin/env python3
"""Catch READY from preloader and request FASTBOOT, with bounded USB retries."""
import time
import struct
import usb.core
import usb.util

deadline = time.monotonic() + 75
last_error = None
while time.monotonic() < deadline:
    device = usb.core.find(idVendor=0x0e8d, idProduct=0x2000)
    if device is None:
        time.sleep(0.05)
        continue
    try:
        cfg = device.get_active_configuration()
        interface = next(i for i in cfg if i.bInterfaceClass == 0x0a)
        usb.util.claim_interface(device, interface.bInterfaceNumber)
        ep_in = next(e for e in interface if usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN)
        ep_out = next(e for e in interface if usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT)
        print('Connected to preloader; waiting for READY.', flush=True)
        try:
            device.ctrl_transfer(0x21, 0x20, 0, 0, struct.pack('<IBBB', 921600, 0, 0, 8), timeout=200)
            device.ctrl_transfer(0x21, 0x22, 3, 0, b'', timeout=200)
        except usb.core.USBError:
            pass
        ready_deadline = time.monotonic() + 2
        sent = False
        while time.monotonic() < ready_deadline:
            try:
                response = bytes(ep_in.read(512, timeout=150))
            except usb.core.USBTimeoutError:
                continue
            print('RX:', repr(response), flush=True)
            if b'READY' in response and not sent:
                ep_out.write(b'FASTBOOT', timeout=1000)
                print('TX: FASTBOOT', flush=True)
                sent = True
                ready_deadline = time.monotonic() + 2
            if b'TOOBTSAF' in response:
                ep_out.write(b'DISCONNECT', timeout=1000)
                print('Fastboot request acknowledged.', flush=True)
                usb.util.dispose_resources(device)
                raise SystemExit(0)
    except (usb.core.USBError, StopIteration) as error:
        message = str(error)
        if message != last_error:
            print('USB retry:', message, flush=True)
            last_error = message
    finally:
        usb.util.dispose_resources(device)
    time.sleep(0.05)
raise SystemExit('No acknowledged fastboot request within 75 seconds.')
