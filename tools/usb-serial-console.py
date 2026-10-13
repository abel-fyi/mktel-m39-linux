#!/usr/bin/env python3
"""Run a diagnostic command over the phone's CDC ACM console using libusb."""
import argparse
import struct
import time
import re
import sys
import os
import select
import termios
import tty
import uuid
import usb.core
import usb.util

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--timeout', type=int, default=90)
parser.add_argument('--command-timeout', type=int, default=20, help='Seconds to wait for command output/completion.')
parser.add_argument('--interactive', action='store_true', help='Open an interactive shell; Ctrl+] exits.')
parser.add_argument('--command', default='id; uname -a; cat /proc/1/cmdline; echo; readlink /proc/1/exe; cat /etc/motd; cat /proc/mounts')
args = parser.parse_args()
if args.interactive and not sys.stdin.isatty():
    raise SystemExit('Interactive mode requires running this command in your terminal.')
deadline = time.monotonic() + args.timeout
device = None
while time.monotonic() < deadline:
    candidate = usb.core.find(idVendor=0x18d1, idProduct=0x4ee7)
    if candidate is None:
        candidate = usb.core.find(idVendor=0x0e8d, idProduct=0x2008)
    if candidate is None:
        candidate = usb.core.find(idVendor=0x0e8d, idProduct=0x2009)
    if candidate is not None:
        try:
            cfg = candidate.get_active_configuration()
            control = next((i for i in cfg if i.bInterfaceClass == 2), None)
            interface = next((i for i in cfg if i.bInterfaceClass == 0x0a), None)
            if interface is None:
                interface = next(i for i in cfg if i.bInterfaceClass == 0xff and
                                 sum(usb.util.endpoint_type(e.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK for e in i) == 2)
            device = candidate
            break
        except (usb.core.USBError, StopIteration):
            usb.util.dispose_resources(candidate)
    time.sleep(0.1)
if device is None:
    raise SystemExit('No diagnostic ACM device before timeout.')
try:
    for i in [i for i in [control, interface] if i is not None]:
        if device.is_kernel_driver_active(i.bInterfaceNumber):
            device.detach_kernel_driver(i.bInterfaceNumber)
        usb.util.claim_interface(device, i.bInterfaceNumber)
    ep_in = next(e for e in interface if usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN)
    ep_out = next(e for e in interface if usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT)
    if control is not None:
        device.ctrl_transfer(0x21, 0x20, 0, control.bInterfaceNumber,
                             struct.pack('<IBBB', 115200, 0, 0, 8), timeout=1000)
        device.ctrl_transfer(0x21, 0x22, 3, control.bInterfaceNumber, b'', timeout=1000)
    print('Connected to diagnostic ACM console.', flush=True)
    # Allow init's tty setup and shell startup after DTR establishes the carrier.
    time.sleep(2)
    if args.interactive:
        print('Interactive Linux console. Press Ctrl+] to exit.', flush=True)
        # The bootstrap shell starts without a controlling terminal. Acquire it
        # once using Alpine's setsid, preserving future sessions and Ctrl+C.
        ep_out.write(b'stty sane; stty -echo; if [ -x /usr/bin/setsid ] && ! ( : < /dev/tty ) 2>/dev/null; then exec /usr/bin/setsid -c /bin/sh -i; fi\n', timeout=3000)
        fd = sys.stdin.fileno()
        previous = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ep_out.write(b'\n', timeout=3000)
            display_buffer = b''
            cursor_query = b'\x1b[6n'
            while True:
                if select.select([fd], [], [], 0)[0]:
                    incoming = os.read(fd, 4096)
                    if not incoming or b'\x1d' in incoming:
                        break
                    # Late local cursor-position replies can become shell input
                    # over a serial link. Do not forward these terminal reports.
                    incoming = re.sub(rb'\x1b\[[0-9]+;[0-9]+R', b'', incoming)
                    if incoming:
                        ep_out.write(incoming, timeout=3000)
                try:
                    chunk = bytes(ep_in.read(512, timeout=50))
                except usb.core.USBTimeoutError:
                    continue
                display_buffer += chunk
                end = len(display_buffer)
                for length in range(len(cursor_query) - 1, 0, -1):
                    if display_buffer.endswith(cursor_query[:length]):
                        end -= length
                        break
                visible = display_buffer[:end].replace(cursor_query, b'')
                display_buffer = display_buffer[end:]
                sys.stdout.buffer.write(visible)
                sys.stdout.buffer.flush()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, previous)
            print('\nDisconnected from console.', flush=True)
        raise SystemExit(0)
    marker = '__M39_DONE_' + uuid.uuid4().hex + '__'
    ep_out.write((args.command + "; printf '\\n" + marker + "\\n'\n").encode(), timeout=3000)
    response = bytearray()
    read_deadline = time.monotonic() + args.command_timeout
    while time.monotonic() < read_deadline:
        try:
            chunk = bytes(ep_in.read(512, timeout=500))
        except usb.core.USBTimeoutError:
            continue
        except usb.core.USBError as error:
            raise SystemExit(f'USB monitoring interrupted: {error}. Remote command completion and cleanup were not verified; no command was replayed.') from None
        response.extend(chunk)
        print(chunk.decode(errors='replace'), end='', flush=True)
        if re.search(rb'(?:^|[\r\n])' + re.escape(marker.encode()) + rb'[\r\n]', response):
            break
    else:
        raise SystemExit('Console connected but command completion was not received.')
finally:
    usb.util.dispose_resources(device)
