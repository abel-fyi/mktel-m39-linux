"""Compile actual driver/caller functions with an injected completion backend."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parent / 'mt6735-kernel'
def extract(path, signature):
    text = (root / path).read_text()
    start = text.index(signature)
    opening = text.index('{', start)
    depth = 1
    index = opening + 1
    while depth:
        depth += (text[index] == '{') - (text[index] == '}')
        index += 1
    return text[start:index]

getter = extract('drivers/misc/mediatek/power/mt6735/charging_hw_pmic.c',
                 'static unsigned int charging_get_charging_status(void *data)')
policy = extract('drivers/power/mediatek/switch_charging.c',
                 'static unsigned int charging_full_check(void)')
fixture = '''#include <assert.h>
#include <stdio.h>
typedef unsigned int kal_bool;
#define KAL_FALSE 0
#define KAL_TRUE 1
#define STATUS_UNSUPPORTED ((unsigned int)-1)
#define CHARGING_CMD_GET_CHARGING_STATUS 1
#define FULL_CHECK_TIMES 10
#define printk(...) ((void)0)
unsigned int g_full_check_count;
struct { int bat_vol; } BMT_status;
static unsigned int injected_value;
static int injected_error;
static int battery_charging_control(int command, void *data) {
 assert(command == CHARGING_CMD_GET_CHARGING_STATUS);
 *(unsigned int *)data = injected_value;
 return injected_error;
}
''' + getter + '\n' + policy + '''
int main(void) {
 unsigned int value = 99;
 assert(charging_get_charging_status(&value) == STATUS_UNSUPPORTED);
 assert(value == KAL_FALSE);
 BMT_status.bat_vol=4200;
 injected_value=1; injected_error=0;
 for (int i=0;i<9;i++) assert(charging_full_check()==KAL_FALSE);
 assert(charging_full_check()==KAL_TRUE);
 injected_error=-1;
 assert(charging_full_check()==KAL_FALSE && g_full_check_count==0);
 for (int i=0;i<20;i++) assert(charging_full_check()==KAL_FALSE);
 injected_error=0; injected_value=0;
 assert(charging_full_check()==KAL_FALSE && g_full_check_count==0);
 injected_value=1; BMT_status.bat_vol=3900;
 for (int i=0;i<20;i++) assert(charging_full_check()==KAL_FALSE);
 puts("PASS: unsupported/failed/negative queries never report full; valid repeated completion remains supported for other backends.");
}
'''
with tempfile.TemporaryDirectory() as directory:
    source = Path(directory) / 'check.c'
    binary = Path(directory) / 'check'
    source.write_text(fixture)
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
