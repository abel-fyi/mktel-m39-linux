#!/usr/bin/env python3
"""Ask the already-running legacy download agent to finish in a chosen boot mode."""
import json
import os
import sys
import argparse
from struct import pack
from pathlib import Path

checkout = Path(__file__).resolve().parent / 'mtkclient'
invocation_directory = Path.cwd()
sys.path.insert(0, str(checkout))
from mtkclient.config.mtk_config import MtkConfig
from mtkclient.Library.mtk_class import Mtk
from mtkclient.Library.DA.mtk_da_handler import DaHandler
import usb.core

state_path = invocation_directory / '.state'
if not state_path.exists():
    state_path = checkout / '.state'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--mode', choices=['normal', 'home', 'fastboot'], default='fastboot')
parser.add_argument('--continue-finish', action='store_true',
                    help='Resume after the upstream finish method consumed the first ACK but returned early.')
args = parser.parse_args()
if not state_path.exists():
    raise SystemExit('No saved DA session. Refusing to initialize a new session here.')
os.chdir(state_path.parent)
state = json.loads(state_path.read_text())
if state['flashmode'] != 'LEGACY' or state['hwcode'] != 0x335:
    raise SystemExit('Saved state is not the expected M39 legacy DA session.')
config = MtkConfig()
device = usb.core.find(idVendor=0x0e8d, idProduct=0x2001)
if device is None:
    # This loader can retain the preloader USB ID after entering stage 2.
    device = usb.core.find(idVendor=0x0e8d, idProduct=0x2000)
if device is None:
    raise SystemExit('The existing download-agent USB interface is absent.')
try:
    device.get_active_configuration()
except usb.core.USBError as error:
    raise SystemExit(f'Download-agent USB access failed: {error}')
mtk = Mtk(config)
handler = DaHandler(mtk)
mtk = handler.connect(mtk)
if mtk is None or not mtk.reinited:
    raise SystemExit('Could not reconnect to the existing DA.')
da = mtk.daloader.da
mode = {'normal': 0, 'home': 1, 'fastboot': 2}[args.mode]
print(f'Sending legacy DA finish mode {mode} ({args.mode}); no flash write/erase.', flush=True)
# Upstream finish() compares an integer to bytes with `is`, so its ACK check
# always fails. Keep responses as bytes and compare by value.
if not args.continue_finish:
    if not da.usbwrite(da.Cmd.FINISH_CMD):
        raise SystemExit('Could not send finish command.')
    ack = da.usbread(1)
    if ack != da.Rsp.ACK:
        raise SystemExit(f'Unexpected initial ACK: {ack.hex()}')
if not da.usbwrite(pack('>I', mode)):
    raise SystemExit('Could not send boot mode.')
ack = da.usbread(1)
if ack != da.Rsp.ACK:
    raise SystemExit(f'Unexpected mode ACK: {ack.hex()}')
print('DA acknowledged. Closing USB session.', flush=True)
mtk.port.close()
state_path.rename(state_path.with_name('.state.before-' + args.mode))
