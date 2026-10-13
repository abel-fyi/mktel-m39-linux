"""Host-only checks of charger exclusion and ADC cleanup; no USB access."""
import unittest
from da_pmic import Pmic

class FakePmic(Pmic):
    def __init__(self):
        self.allow_charger_controls = False
        self.writes = []
        self.registers = {0x0f48: 0x63, 0x0f4c: 4, 0x0f4e: 13,
                          0x0f50: 15, 0x0f54: 1, 0x0f62: 0,
                          0x0f66: 0, 0x0f7a: 0x12,
                          0x028a: 0, 0x0e94: 0, 0x0eb0: 0}
        self.fail_adc = False
    def read(self, address):
        if self.fail_adc and address == 0x0e2e:
            raise IOError('Simulated failed ADC transaction')
        return self.registers.get(address, 0x8000 | 20000)
    def idle(self):
        pass
    def wait(self, expected):
        return 0
    def mmio(self, offset, value):
        if offset != 0xa0 or not value & 0x80000000:
            raise AssertionError('Unexpected mock transport operation')
        self.registers[((value >> 16) & 0x7fff) << 1] = value & 0xffff

class GuardChecks(unittest.TestCase):
    def test_read_session_cannot_enable_charging(self):
        p = FakePmic()
        with self.assertRaises(RuntimeError):
            p.charger_field(0x0f48, 0x18, 0x18)
        self.assertEqual(p.registers[0x0f48], 0x63)
    def test_missing_profile_cannot_enable_charging(self):
        p = FakePmic(); p.allow_charger_controls = True
        with self.assertRaises(RuntimeError):
            p.charger_field(0x0f48, 0x18, 0x18)
        self.assertEqual(p.registers[0x0f48], 0x63)
    def test_active_charger_cannot_raise_limits(self):
        p = FakePmic(); p.allow_charger_controls = True
        p.registers[0x0f48] |= 0x18
        with self.assertRaises(RuntimeError):
            p.charger_field(0x0f4e, 0x1f, 13)
        self.assertEqual(p.registers[0x0f4e], 13)
    def test_unreviewed_fields_are_rejected(self):
        p = FakePmic(); p.allow_charger_controls = True
        with self.assertRaises(RuntimeError):
            p.charger_field(0x0f48, 0xffff, 0)
    def test_enable_requires_limits_but_mode_is_set_after_enable(self):
        p = FakePmic(); p.allow_charger_controls = True
        p.registers.update({0x0f4e: 0, 0x0f4c: 0x0a,
                            0x0f7a: 0x40, 0x0f62: 0x10})
        p.charger_field(0x0f48, 0x18, 0x18)
        p.charger_field(0x0f7a, 0x04, 0x04)
        self.assertEqual(p.registers[0x0f7a] & 0x46, 0x44)
    def test_main_gate_can_stage_but_dac_requires_hwcv(self):
        p = FakePmic(); p.allow_charger_controls = True
        p.registers.update({0x0f4e: 0, 0x0f4c: 0x0a,
                            0x0f7a: 0, 0x0f62: 0x10})
        p.charger_field(0x0f48, 0x18, 0x10)
        self.assertFalse(p.registers[0x0f48] & 8)
        with self.assertRaises(RuntimeError):
            p.charger_field(0x0f48, 0x18, 0x18)
        self.assertFalse(p.registers[0x0f48] & 8)
    def test_main_gate_rejects_automatic_mode(self):
        p = FakePmic(); p.allow_charger_controls = True
        p.registers.update({0x0f48: 0x67, 0x0f4e: 0,
                            0x0f4c: 0x0a, 0x0f7a: 0, 0x0f62: 0x10})
        with self.assertRaises(RuntimeError):
            p.charger_field(0x0f48, 0x18, 0x10)
    def test_adc_failure_restores_clocks(self):
        p = FakePmic(); p.fail_adc = True
        with self.assertRaises(IOError):
            p.sample()
        self.assertEqual([p.registers[a] for a in [0x028a, 0x0e94, 0x0eb0]], [0, 0, 0])
        self.assertEqual(p.registers[0x0f48], 0x63)

if __name__ == '__main__':
    unittest.main()
