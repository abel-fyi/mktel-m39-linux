#!/usr/bin/env python3
"""Read known MT6328 PMIC registers through an existing M39 download agent.

Only AP wrapper READ commands/acknowledgements are issued. No PMIC register
writes, charger enable operations, or flash operations are implemented here.
"""
import json
import os
import struct
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parent.parent
checkout = root / 'tools/mtkclient'
os.chdir(checkout)
sys.path.insert(0, str(checkout))
from mtkclient.config.mtk_config import MtkConfig
from mtkclient.Library.mtk_class import Mtk
from mtkclient.Library.DA.mtk_da_handler import DaHandler
import usb.core

state = json.loads((checkout / '.state').read_text())
if state['flashmode'] != 'LEGACY' or state['hwcode'] != 0x335:
    raise SystemExit('Not the expected existing M39 DA session')
devices = [d for d in usb.core.find(find_all=True)
           if (d.idVendor, d.idProduct) in [(0x0e8d, 0x2000), (0x0e8d, 0x2001)]]
if len(devices) != 1:
    raise SystemExit('Expected exactly one connected M39 download-agent interface')
mtk = Mtk(MtkConfig())
handler = DaHandler(mtk)
mtk = handler.connect(mtk)
if mtk is None or not mtk.reinited:
    raise SystemExit('Existing DA reconnect failed')
loader = mtk.daloader
base = 0x10001000  # Verified M39 PWRAP device-tree reg, not generic header comment.

def status():
    data = loader.peek(base + 0xa4, 4, registers=True)
    if data is None or len(data) != 4:
        raise RuntimeError('Wrapper status read failed')
    value = struct.unpack('<I', data)[0]
    if not (value & (1 << 21)):
        raise RuntimeError('Wrapper initialization bit is clear')
    return value

def transport_write(offset, value):
    assert ((offset == 0xa0 and not value & 0x80000000)
            or (offset == 0xa8 and value == 1))
    # Legacy loader exposes the checked 32-bit MMIO primitive directly;
    # its generic poke(registers=True) dispatch references a missing method.
    if not loader.da.write_reg32(base + offset, value):
        raise RuntimeError('AP wrapper read-command/acknowledgement failed')

def wait_fsm(expected):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        value = status()
        if (value >> 16) & 7 == expected:
            return value
        time.sleep(0.005)
    raise RuntimeError(f'Wrapper did not reach FSM {expected}')

def read_pmic(address):
    assert address in [0x0200, 0x0248, 0x0298, 0x029e, 0x02a6,
                       0x0f48, 0x0f4c, 0x0f4e, 0x0f50,
                       0x0f54, 0x0f62, 0x0f66, 0x0f7a,
                       0x028a, 0x0e94, 0x0eb0, 0x0e2e, 0x0e32,
                       0x0e04, 0x0e06, 0x0e08]
    if (status() >> 16) & 7 == 6:
        transport_write(0xa8, 1)  # Release a prior completed read, as vendor HAL does.
    wait_fsm(0)
    transport_write(0xa0, (address >> 1) << 16)
    value = wait_fsm(6) & 0xffff
    transport_write(0xa8, 1)
    wait_fsm(0)
    return value

try:
    identity = read_pmic(0x0200)
    if identity >> 8 != 0x28:
        raise RuntimeError(f'Unexpected PMIC hardware identity {identity:#x}')
    registers = {'0200': identity}
    for address in [0x0248, 0x0298, 0x029e, 0x02a6,
                    0x0f48, 0x0f4c, 0x0f4e, 0x0f50, 0x0f54,
                    0x0f62, 0x0f66, 0x0f7a, 0x028a, 0x0e94, 0x0eb0,
                    0x0e2e, 0x0e32, 0x0e04, 0x0e06, 0x0e08]:
        registers[f'{address:04x}'] = read_pmic(address)
    result = {'wrapper_base': hex(base), 'pmic_registers': registers,
              'charger_enable': bool(registers['0f48'] & 16),
              'csdac_enable': bool(registers['0f48'] & 8),
              'pmic_register_writes': False, 'flash_writes': False}
    (root / 'analysis/da-pmic-read.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)
finally:
    mtk.port.close()
