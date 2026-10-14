"""Verify supported kernels never fall back after a failed gauge read."""
from pathlib import Path
import subprocess
import tempfile
import unittest

class BackendTests(unittest.TestCase):
    def test_backend_selection(self):
        source=Path(__file__).with_name('m39-pmic-pulse.sh').read_text()
        function=source[source.index('fuel_current()'):source.index('verify_charge_profile()')]
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)
            helper=p/'native'
            helper.write_text('#!/bin/sh\necho fallback\n')
            helper.chmod(0o755)
            endpoint=p/'kernel'
            function=function.replace('/sys/module/battery_meter_hal/parameters/m39_fg_raw',str(endpoint))
            function=function.replace('/run/m39-fg-sample',str(helper))
            script='fail() { exit 1; };\n'+function+'fuel_current\n'
            result=subprocess.run(['sh','-c',script],capture_output=True,text=True)
            self.assertEqual(result.stdout,'fallback\n')
            endpoint.write_text('222 222\n')
            result=subprocess.run(['sh','-c',script],capture_output=True,text=True)
            self.assertEqual(result.stdout,'222 222\n')
            self.assertEqual(result.returncode,0)
            endpoint.unlink()
            endpoint.mkdir()  # Exists, but cannot be read as a gauge record.
            result=subprocess.run(['sh','-c',script],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertNotIn('fallback',result.stdout)

if __name__=='__main__':
    unittest.main()
