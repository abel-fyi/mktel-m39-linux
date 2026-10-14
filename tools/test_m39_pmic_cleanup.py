"""Run the native shell cleanup against fake registers; never access USB."""
import json
import pathlib
import subprocess
import tempfile
import unittest

SOURCE = pathlib.Path(__file__).with_name('m39-pmic-pulse.sh').read_text()
STATUS = SOURCE.split('write_status() {', 1)[1].split('\n}\n', 1)[0]
CLEANUP = SOURCE.split('cleanup() {', 1)[1].split('\n}\n', 1)[0]
OWNER = SOURCE.split('write_owner() (', 1)[1].split('\n)\n', 1)[0]


class CleanupChecks(unittest.TestCase):
    def run_cleanup(self, fail_off=False, exit_code=0, source=False, vbus=5100, sample_failure=False, reason="running"):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / 'm39-pmic-pulse.lock').mkdir()
            (root / 'boot_id').write_text('test-boot\n')
            (root / 'owner').write_text('120\n')
            functions = ('write_owner() (' + OWNER + '\n)\n'
                         'write_status() {' + STATUS + '\n}\n'
                         'cleanup() {' + CLEANUP + '\n}\n')
            functions = functions.replace('/run/', directory + '/')
            functions = functions.replace('/proc/sys/kernel/random/boot_id', str(root / 'boot_id'))
            script = '''set -eu
uptime_seconds() { echo 123; }
sample() {
    [ "$sample_failure" = 0 ] || return 1
    echo "3300 3300 $sample_vbus 700 410"
}
field() {
    echo "$1 $2 $3" >> "$register_log"
    if [ "$fail_off" -eq 1 ] && [ "$1" = 0f48 ]; then return 1; fi
}
status_active=1
current_ma=300
voltage=3300
fg_direction=220
mode=--supervised-recharge
saved_f4c=4
saved_f7a=18
saved_f74=34
saved_f76=36
saved_f4e=205
saved_f50=15
saved_f62=0
saved_f66=0
''' + functions + '\ncleanup\n'
            result = subprocess.run(['sh', '-c', script], env={
                'PATH': '/usr/bin:/bin', 'register_log': str(root / 'registers'),
                'fail_off': str(int(fail_off)), 'test_exit': str(exit_code),
                'requires_owner': str(int(source)), 'owner_path': str(root / 'owner'),
                'sample_failure': str(int(sample_failure)), 'sample_vbus': str(vbus), 'stop_reason': reason,
            }, capture_output=True, text=True)
            return result.returncode, (root / 'registers').read_text().splitlines(), json.loads(
                (root / 'm39-charge-status.json').read_text())

    def test_hardware_stop_with_absent_usb_is_unplug(self):
        _, _, state = self.run_cleanup(source=True, vbus=113, exit_code=1, reason='charger_stopped')
        self.assertEqual(state['phase'], 'stopped')
        self.assertEqual(state['stop_reason'], 'unplugged')

    def test_hardware_stop_with_usb_present_remains_fault(self):
        _, _, state = self.run_cleanup(source=True, vbus=5100, exit_code=1, reason='charger_stopped')
        self.assertEqual(state['phase'], 'aborted')
        self.assertEqual(state['stop_reason'], 'charger_stopped')

    def test_regulation_stop_requires_confirmed_unplug(self):
        for vbus, expected in [(728,'stopped'),(5100,'aborted')]:
            _, _, state = self.run_cleanup(source=True,vbus=vbus,exit_code=1,reason='regulation_disabled')
            self.assertEqual(state['phase'],expected)
            self.assertEqual(state['stop_reason'],'unplugged' if vbus<1000 else 'regulation_disabled')
        _, _, state = self.run_cleanup(source=True,sample_failure=True,exit_code=1,reason='regulation_disabled')
        self.assertEqual(state['phase'],'off_restore_failed')
        _, _, state = self.run_cleanup(source=True,fail_off=True,vbus=728,exit_code=1,reason='regulation_disabled')
        self.assertFalse(state['charging_off_verified'])

    def test_power_profile_change_requires_verified_input_loss(self):
        for vbus,failed_sample,failed_off,phase in [(889,False,False,'stopped'),
            (5100,False,False,'aborted'),(889,True,False,'off_restore_failed'),
            (889,False,True,'off_unverified')]:
            _,_,state=self.run_cleanup(source=True,vbus=vbus,sample_failure=failed_sample,
                fail_off=failed_off,exit_code=1,reason='power_profile_changed')
            self.assertEqual(state['phase'],phase)
            if phase=='stopped':self.assertEqual(state['stop_reason'],'unplugged')

    def test_unplug_does_not_hide_unrelated_fault(self):
        _, _, state = self.run_cleanup(source=True, vbus=113, exit_code=1, reason='fault')
        self.assertEqual(state['phase'], 'aborted')
        self.assertEqual(state['stop_reason'], 'fault')

    def test_off_precedes_restoring_higher_limits(self):
        code, writes, status = self.run_cleanup()
        self.assertEqual(code, 0)
        self.assertEqual(writes[0], '0f48 24 0')
        self.assertIn('0f4e 31 205', writes[1:])
        self.assertTrue(status['charging_off_verified'])
        self.assertEqual(status['phase'], 'stopped')

    def test_failed_off_does_not_restore_higher_limits(self):
        code, writes, status = self.run_cleanup(fail_off=True)
        self.assertNotEqual(code, 0)
        self.assertEqual(writes, ['0f48 24 0'])
        self.assertFalse(status['charging_off_verified'])

    def test_hangup_exit_reports_aborted_but_off(self):
        code, _, status = self.run_cleanup(exit_code=129)
        self.assertEqual(code, 0)
        self.assertEqual(status['phase'], 'aborted')
        self.assertTrue(status['charging_off_verified'])

    def test_disconnected_input_leaves_charger_profile_untouched(self):
        code, writes, status = self.run_cleanup(source=True, vbus=359)
        self.assertEqual(code, 0)
        self.assertEqual(writes, ['0f48 24 0'])
        self.assertTrue(status['charging_off_verified'])
        self.assertEqual(status['phase'], 'stopped')

    def test_powered_input_still_restores_profile_after_off(self):
        code, writes, status = self.run_cleanup(source=True, vbus=5100)
        self.assertEqual(code, 0)
        self.assertEqual(writes[0], '0f48 24 0')
        self.assertIn('0f4e 31 205', writes[1:])

    def test_uncertain_input_reports_error_without_higher_limits(self):
        code, writes, status = self.run_cleanup(source=True, sample_failure=True)
        self.assertNotEqual(code, 0)
        self.assertEqual(writes, ['0f48 24 0'])
        self.assertEqual(status['phase'], 'off_restore_failed')
        self.assertTrue(status['charging_off_verified'])


if __name__ == '__main__':
    unittest.main()
