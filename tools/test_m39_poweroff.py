"""Exercise shutdown ordering and refusal paths without USB or reboot syscalls."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest


class ShutdownTests(unittest.TestCase):
    def run_shutdown(self, scenario):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            (p / 'owner').write_text('0\n')
            (p / 'gates').write_text('123\n' if scenario == 'active' else '99\n')
            (p / 'mounts').write_text('/dev/mapper/m39_home /home ext4 rw 0 0\n')
            source = Path(__file__).with_name('m39-poweroff.sh').read_text()
            source = source.replace('/run/', directory + '/')
            source = source.replace('/sys/module/charging_hw_pmic/parameters/m39_owner_seconds', str(p / 'owner'))
            source = source.replace('/sys/devices/platform/mt-pmic/pmic_access', str(p / 'access'))
            source = source.replace('/proc/mounts', str(p / 'mounts'))
            source = source.replace('/dev/kmsg', str(p / 'kmsg'))
            source = source.replace('/bin/busybox poweroff -f', 'poweroff_mock')
            mocks = r'''
id() { echo 0; }
m39-charge() { echo stop >> "$MOCK/events"; [ "$SCENARIO" != stop_failure ]; }
cat() {
 if [ "$1" = "$MOCK/access" ]; then
  [ "$SCENARIO" != read_failure ] || return 1
  command cat "$MOCK/gates"
 else command cat "$@"; fi
}
sync() { echo sync >> "$MOCK/events"; }
mount() {
 echo "mount $*" >> "$MOCK/events"
 [ "$SCENARIO" != remount_failure ]
}
poweroff_mock() { echo poweroff >> "$MOCK/events"; }
'''
            result = subprocess.run(['sh', '-c', mocks + source],
                                    env=dict(os.environ, MOCK=directory, SCENARIO=scenario),
                                    capture_output=True, text=True)
            events = (p / 'events').read_text().splitlines()
            self.assertNotEqual(result.returncode, 0)  # A returned poweroff is failure.
            self.assertFalse((p / 'm39-poweroff.lock').exists())
            return events

    def test_sync_and_readonly_mounts_precede_poweroff(self):
        self.assertEqual(self.run_shutdown('valid'), [
            'stop', 'sync', 'mount -o remount,ro /home',
            'mount -o remount,ro /', 'sync', 'poweroff'])

    def test_stop_failure_refuses_poweroff(self):
        self.assertEqual(self.run_shutdown('stop_failure'), ['stop'])

    def test_active_gates_and_failed_read_refuse_poweroff(self):
        for scenario in ['active', 'read_failure']:
            with self.subTest(scenario=scenario):
                self.assertEqual(self.run_shutdown(scenario), ['stop'])

    def test_failed_readonly_remount_refuses_poweroff(self):
        self.assertEqual(self.run_shutdown('remount_failure'),
                         ['stop', 'sync', 'mount -o remount,ro /home'])


if __name__ == '__main__':
    unittest.main()
