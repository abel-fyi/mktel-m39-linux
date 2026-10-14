"""Compile the actual kernel adapter with mocked PMIC/locking primitives."""
from pathlib import Path
import subprocess
import tempfile
import unittest

class KernelGaugeTests(unittest.TestCase):
    def test_serialized_adapter_and_failure_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            (p / 'linux').mkdir()
            for name in ['mutex.h', 'moduleparam.h', 'ktime.h']:
                (p / 'linux' / name).write_text('')
            source = r'''
#include <stdio.h>
#include <string.h>
#include <errno.h>
#define __KERNEL__
#define BATTERY_METER_CMD_GET_ADC_V_BAT_SENSE 5
#define BATTERY_METER_CMD_GET_ADC_V_I_SENSE 6
#define BATTERY_METER_CMD_GET_ADC_V_BAT_TEMP 7
#define BATTERY_METER_CMD_GET_ADC_V_CHARGER 8
typedef unsigned long long u64;
struct kernel_param { int unused; };
struct kernel_param_ops { int (*get)(char *, const struct kernel_param *); };
#define DEFINE_MUTEX(name) int name
#define PAGE_SIZE 4096
#define pr_err(...) fprintf(stderr, __VA_ARGS__)
#define READ_ONCE(value) (value)
#define WRITE_ONCE(value, new_value) ((value) = (new_value))
#define scnprintf snprintf
#define module_param_cb(name, ops, arg, mode) \
    static const struct kernel_param_ops *registered_ops = ops
static unsigned ctrl=0x29, writes, locks, unlocks, m39_unlock_pending;
static u64 ticks;
static const char *scenario;
static int mutex_trylock(int *lock) {
 if (*lock && !m39_unlock_pending) return 0; m39_unlock_pending=0; *lock=1; locks++; return 1;
}
static void mutex_unlock(int *lock) { *lock=0; unlocks++; }
static u64 ktime_get(void) { return ticks; }
static u64 ktime_to_ns(u64 time) { return time; }
static void usleep_range(unsigned a,unsigned b) {
 ticks+=a*1000; (void)b;
 if((!strcmp(scenario,"contended") && ticks>=500000) ||
    (!strcmp(scenario,"late") && ticks>=30000000)) m39_unlock_pending=1;
}
static int pmic_read_interface(unsigned reg,unsigned *value,unsigned mask,unsigned shift) {
 (void)mask; (void)shift; ticks+=1000;
 if(reg==0x200) *value=0x2830;
 else if(reg==0xca4) *value=ctrl;
 else if(reg==0xcb2) { if(!strcmp(scenario,"read-error")) return -EIO; *value=64833; }
 else return -EINVAL;
 return 0;
}
static int pmic_config_interface(unsigned reg,unsigned value,unsigned mask,unsigned shift) {
 if(reg!=0xca4 || mask!=0xff00 || shift) return -EINVAL;
 writes++;
 if(value==0x200) ctrl=(ctrl&255)|0x600;
 else if(value==0x800) {
  if(!strcmp(scenario,"release-error")) return -EIO;
  ctrl&=255;
 } else ctrl=(ctrl&~mask)|(value&mask);
 return 0;
}
#include "m39-fg-kernel.h"
int main(int argc,char **argv) {
 char buffer[4096]={0}; if(argc!=2) return 2; scenario=argv[1];
 for(unsigned command=0;command<100;command++)
  if(m39_fg_needs_lock(command)!=(command<5 || command>8)) return 3;
 if(m39_meter_command_lock) return 4;
 if(!strcmp(scenario,"adc-held")) m39_meter_command_lock=1;
 if(!strcmp(scenario,"busy") || !strcmp(scenario,"contended") || !strcmp(scenario,"late")) m39_fg_lock=1;
 m39_fg_vendor_cmd=1;
 int rc=registered_ops->get(buffer,0);
 printf("rc=%d writes=%u locks=%u unlocks=%u ctrl=%u ticks=%llu command_lock=%d\n%s",rc,writes,locks,unlocks,ctrl,ticks,m39_meter_command_lock,buffer);
 return 0;
}
'''
            (p / 'test.c').write_text(source)
            subprocess.run(['cc', '-std=gnu99', '-Wall', '-Wextra', '-Werror',
                            '-Wno-misleading-indentation', '-I'+str(p),
                            '-I'+str(Path(__file__).parent), str(p/'test.c'),
                            '-o', str(p/'test')], check=True)
            for scenario in ['valid', 'adc-held', 'contended', 'busy', 'late', 'read-error', 'release-error']:
                with self.subTest(scenario=scenario):
                    result = subprocess.run([str(p/'test'), scenario], capture_output=True,
                                            text=True, check=True)
                    lines=result.stdout.splitlines()
                    values=dict(item.split('=') for item in lines[0].split())
                    self.assertEqual(values['command_lock'], '1' if scenario=='adc-held' else '0')
                    if scenario in ['busy','late']:
                        self.assertEqual(values['rc'], str(-16))
                        self.assertEqual(values['writes'], '0')
                        self.assertEqual(values['locks'], '0' if scenario=='busy' else '1')
                        self.assertLessEqual(int(values['ticks']), 30000000)
                        self.assertEqual(values['unlocks'], '0' if scenario=='busy' else '1')
                        if scenario=='busy':
                            self.assertIn('vendor_cmd=1 held_us=30000',result.stderr)
                    else:
                        self.assertEqual(values['locks'], '1')
                        self.assertEqual(values['unlocks'], '1')
                        if scenario in ['valid','adc-held','contended']:
                            self.assertEqual(lines[1], '64833 -702')
                            self.assertEqual(values['ctrl'], '41')
                        else:
                            self.assertEqual(values['rc'], str(-5))
                            self.assertEqual(len(lines), 1)

if __name__ == '__main__':
    unittest.main()
