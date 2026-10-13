"""Fault-injection checks of native gauge acquisition; no USB or hardware."""
from pathlib import Path
import subprocess
import tempfile
import unittest


class GaugeChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.binary = Path(cls.directory.name) / 'gauge'
        subprocess.run(['cc', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-DM39_FG_HOST_TEST', str(Path(__file__).with_name('m39-fg-sample.c')),
                        '-o', str(cls.binary)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def sample(self, scenario):
        result = subprocess.run([str(self.binary), scenario], capture_output=True,
                                text=True, check=True)
        return {k: int(v) for k, v in (p.split('=') for p in result.stdout.split())}

    def test_lost_latch_is_rejected_and_next_snapshot_used(self):
        result = self.sample('contended')
        self.assertEqual(result['rc'], 0)
        self.assertEqual(result['requests'], 2)
        self.assertEqual(result['clears'], 2)
        self.assertEqual(result['raw'], 222)
        self.assertEqual(result['ctrl'], 0x29)

    def test_busy_kernel_latch_is_not_modified(self):
        result = self.sample('busy')
        self.assertEqual(result['rc'], -1)
        self.assertEqual(result['requests'], 0)
        self.assertEqual(result['clears'], 0)
        self.assertLess(result['ticks'], 31000000)

    def test_never_ready_fails_with_bounded_retries_and_releases(self):
        result = self.sample('never-ready')
        self.assertEqual(result['rc'], -1)
        self.assertEqual(result['requests'], 3)
        self.assertEqual(result['clears'], 3)
        self.assertEqual(result['ctrl'], 0x29)
        self.assertLess(result['ticks'], 30000000)

    def test_io_and_release_failures_never_return_valid_samples(self):
        for scenario in ['read-error', 'release-error']:
            with self.subTest(scenario=scenario):
                result = self.sample(scenario)
                self.assertEqual(result['rc'], -1)
                self.assertEqual(result['requests'], 1)
                self.assertEqual(result['clears'], 1)

    def test_wrong_chip_causes_no_measurement_writes(self):
        result = self.sample('wrong-chip')
        self.assertEqual(result['rc'], -1)
        self.assertEqual(result['requests'], 0)

    def test_raw_sign_and_low_configuration_are_preserved(self):
        for scenario, raw in [('positive', 222), ('negative', 64833)]:
            with self.subTest(scenario=scenario):
                result = self.sample(scenario)
                self.assertEqual(result['rc'], 0)
                self.assertEqual(result['raw'], raw)
                self.assertEqual(result['low_changes'], 0)
                self.assertEqual(result['ctrl'], 0x29)


if __name__ == '__main__':
    unittest.main()
