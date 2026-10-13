"""Checked MT6328 measurement transport through an already connected M39 DA."""
import json
import os
import struct
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
READABLE = {0x0004, 0x0200, 0x0248, 0x0298, 0x029e, 0x02a6,
            0x028a, 0x0e94, 0x0eb0, 0x0e8a,
            0x0e2e, 0x0e32, 0x0e04, 0x0e06, 0x0e08,
            0x0f48, 0x0f4c, 0x0f4e, 0x0f50, 0x0f54,
            0x0f60, 0x0f62, 0x0f66, 0x0f68, 0x0f70, 0x0f74, 0x0f76, 0x0f7a}
CHARGER_MASKS = {0x0f48: 0x18, 0x0f4c: 0x0a, 0x0f4e: 0x1f,
                 0x0f50: 0x0f, 0x0f62: 0x11f, 0x0f66: 0x03,
                 0x0f74: 0x77, 0x0f76: 0x77, 0x0f7a: 0x46}

class Pmic:
    def __init__(self):
        checkout = ROOT / 'tools/mtkclient'
        os.chdir(checkout)
        sys.path.insert(0, str(checkout))
        from mtkclient.config.mtk_config import MtkConfig
        from mtkclient.Library.mtk_class import Mtk
        from mtkclient.Library.DA.mtk_da_handler import DaHandler
        import usb.core
        state = json.loads((checkout / '.state').read_text())
        if state['flashmode'] != 'LEGACY' or state['hwcode'] != 0x335:
            raise RuntimeError('Not the expected saved M39 legacy DA')
        devices = [d for d in usb.core.find(find_all=True) if
                   (d.idVendor, d.idProduct) in [(0x0e8d, 0x2000), (0x0e8d, 0x2001)]]
        if len(devices) != 1:
            raise RuntimeError('Expected one download-agent USB interface')
        target = Mtk(MtkConfig())
        self.target = DaHandler(target).connect(target)
        if self.target is None or not self.target.reinited:
            raise RuntimeError('Existing DA reconnect failed')
        self.loader = self.target.daloader
        self.base = 0x10001000
        self.writes = []
        self.allow_charger_controls = False
        if self.read(0x0200) >> 8 != 0x28:
            raise RuntimeError('PMIC identity does not match MT6328')

    def close(self):
        self.target.port.close()

    def status(self):
        raw = self.loader.peek(self.base + 0xa4, 4, registers=True)
        if raw is None or len(raw) != 4:
            raise RuntimeError('Wrapper read failed')
        value = struct.unpack('<I', raw)[0]
        if not value & (1 << 21):
            raise RuntimeError('Wrapper is not initialized')
        return value

    def mmio(self, offset, value):
        if offset not in [0xa0, 0xa8] or (offset == 0xa8 and value != 1):
            raise RuntimeError('Unexpected wrapper operation')
        if not self.loader.da.write_reg32(self.base + offset, value):
            raise RuntimeError('Wrapper command failed')

    def wait(self, expected):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            value = self.status()
            if (value >> 16) & 7 == expected:
                return value
            time.sleep(.002)
        raise TimeoutError(f'Wrapper FSM {expected} timeout')

    def idle(self):
        if (self.status() >> 16) & 7 == 6:
            self.mmio(0xa8, 1)
        self.wait(0)

    def read(self, address):
        if address not in READABLE:
            raise RuntimeError('Read address outside reviewed register set')
        self.idle()
        self.mmio(0xa0, (address >> 1) << 16)
        value = self.wait(6) & 0xffff
        self.mmio(0xa8, 1)
        self.wait(0)
        return value

    def adc_write(self, address, value):
        # Only ADC configuration/measurement requests, never charger registers.
        masks = {0x028a: 0x100, 0x0e94: 0x8000, 0x0eb0: 0x80}
        if address == 0x0e8a:
            if value & ~0x1f:
                raise RuntimeError('Unexpected ADC conversion channel')
        elif address in masks:
            current = self.read(address)
            if (current ^ value) & ~masks[address]:
                raise RuntimeError('Write changes unreviewed ADC configuration')
        else:
            raise RuntimeError('PMIC write outside ADC measurement registers')
        self.idle()
        self.mmio(0xa0, 0x80000000 | ((address >> 1) << 16) | value)
        self.wait(0)
        self.writes.append({'address': hex(address), 'value': value, 'purpose': 'ADC measurement'})

    def charger_field(self, address, mask, bits, action=False):
        if not self.allow_charger_controls:
            raise RuntimeError('Charger control is not enabled for this session')
        if address not in CHARGER_MASKS or mask & ~CHARGER_MASKS[address] or bits & ~mask:
            raise RuntimeError('Change outside reviewed charger-control fields')
        current = self.read(address)
        value = (current & ~mask) | bits
        if address == 0x0f48 and value & 0x18:
            # Enabling is allowed only with the conservative diagnostic profile.
            required = [(0x0f4e, 0x1f, 0),
                        (0x0f4c, 0x0a, 0x0a), (0x0f7a, 0x02, 0),
                        (0x0f62, 0x1f, 0x10), (0x0f54, 1, 1)]
            if value & 0x08:
                # The current DAC may only be enabled once HWCV is verified.
                required.append((0x0f7a, 0x40, 0x40))
            elif value & 0x10 and value & 0x04:
                raise RuntimeError('Automatic charging must be off during main-gate staging')
            for reg, wanted_mask, wanted in required:
                if self.read(reg) & wanted_mask != wanted:
                    raise RuntimeError('Conservative profile missing before enable')
            if self.read(0x0f50) & 0x0f not in [14, 15]:
                raise RuntimeError('Current ceiling exceeds diagnostic 200mA maximum')
        if address in [0x0f4e, 0x0f50] and self.read(0x0f48) & 0x18:
            raise RuntimeError('Cannot change voltage/current limits while charging')
        self.idle()
        self.mmio(0xa0, 0x80000000 | ((address >> 1) << 16) | value)
        self.wait(0)
        self.writes.append({'address': hex(address), 'value': value,
                            'purpose': 'bounded charger diagnostic',
                            'monotonic_seconds': time.monotonic()})
        if not action and self.read(address) & mask != bits:
            actual = self.read(address)
            raise RuntimeError(f'Charger-field readback failed at {address:#x}: '
                               f'mask={mask:#x}, wanted={bits:#x}, actual={actual:#x}')

    def sample(self):
        clocks = {0x028a: 0x100, 0x0e94: 0x8000, 0x0eb0: 0x80}
        saved = {a: self.read(a) for a in clocks}
        try:
            for address, mask in clocks.items():
                if not saved[address] & mask:
                    self.adc_write(address, saved[address] | mask)
            # Vendor PMIC_IMM_GetOneChannelValue: CH0/1 battery/sense,
            # CH2 charger divider, CH3 BATON, CH4 PMIC diode temperature.
            self.adc_write(0x0e8a, 0x1f)
            raw = {}
            for address in [0x0e2e, 0x0e32, 0x0e04, 0x0e06, 0x0e08]:
                deadline = time.monotonic() + 1
                while True:
                    value = self.read(address)
                    if value & 0x8000:
                        raw[f'{address:04x}'] = value
                        break
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f'ADC channel {address:#x} not ready')
                    time.sleep(.005)
            result = {
                'raw': raw,
                'battery_mv': (raw['0e2e'] & 0x7fff) * 5400 // 32768,
                'sense_mv': (raw['0e32'] & 0x7fff) * 5400 // 32768,
                'charger_divider_mv': (raw['0e04'] & 0x0fff) * 1800 // 4096,
                'baton_mv': (raw['0e06'] & 0x0fff) * 1800 // 4096,
                'pmic_temp_diode_mv': (raw['0e08'] & 0x0fff) * 1800 // 4096,
            }
            return result
        finally:
            for address, mask in clocks.items():
                current = self.read(address)
                restore = (current & ~mask) | (saved[address] & mask)
                if current != restore:
                    self.adc_write(address, restore)
                if (self.read(address) ^ saved[address]) & mask:
                    raise RuntimeError('ADC clock restoration failed')
