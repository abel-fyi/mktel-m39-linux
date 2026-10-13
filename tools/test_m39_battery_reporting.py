"""Compile actual board detector and property getter against fault fixtures."""
from pathlib import Path
import re
import subprocess
import tempfile

source = (Path(__file__).resolve().parent / 'mt6735-kernel/drivers/power/mediatek/battery_common.c').read_text()
def extract(signature):
    start = source.index(signature)
    index = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[index] == '{') - (source[index] == '}')
        index += 1
    return source[start:index]
detector = extract('static bool m39_battery_estimates_unvalidated(void)')
getter = extract('static int battery_get_property(struct power_supply *psy,')
properties = sorted(set(re.findall(r'POWER_SUPPLY_PROP_\w+', getter)))
fields = sorted(set(re.findall(r'data->(\w+)', getter)))
fixture = '''#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#include <errno.h>
#include <stdio.h>
#define CONFIG_OF 1
#define POWER_SUPPLY_STATUS_UNKNOWN 0
#define POWER_SUPPLY_HEALTH_UNKNOWN 0
#define container_of(ptr,type,member) ((type *)((char *)(ptr)-offsetof(type,member)))
typedef unsigned int u32;
struct power_supply { int unused; };
union power_supply_propval { int intval; };
struct device_node { int unused; };
static struct device_node node;
static int exists=1, missing=0, references=0;
static u32 injected_gpio=69;
static struct device_node *of_find_node_by_path(const char *path) {
 assert(!strcmp(path,"/odm/led@6"));
 if(!exists)return NULL;
 references++;return &node;
}
static int of_property_read_u32(struct device_node *n,const char *name,u32 *value) {
 assert(n==&node && !strcmp(name,"m39,verified-lk-gpio"));
 if(missing)return -EINVAL;
 *value=injected_gpio;return 0;
}
static void of_node_put(struct device_node *n) { if(n)references--; }
''' + 'enum power_supply_property {' + ','.join(properties) + '};\n' + \
    'struct battery_data {struct power_supply psy; ' + ''.join('int '+field+';' for field in fields) + '};\n' + \
    detector + '\n' + getter + '''
int main(void) {
 struct battery_data data={0}; union power_supply_propval value;
 data.BAT_STATUS=1; data.BAT_HEALTH=1; data.BAT_CAPACITY=85;
 data.BAT_batt_temp=470; data.BAT_InstatVolt=3437; data.BAT_TECHNOLOGY=2;
 assert(!battery_get_property(&data.psy,POWER_SUPPLY_PROP_STATUS,&value)&&value.intval==0);
 assert(!battery_get_property(&data.psy,POWER_SUPPLY_PROP_HEALTH,&value)&&value.intval==0);
 enum power_supply_property unavailable[]={POWER_SUPPLY_PROP_PRESENT,POWER_SUPPLY_PROP_CAPACITY,
 POWER_SUPPLY_PROP_batt_temp,POWER_SUPPLY_PROP_TemperatureR,POWER_SUPPLY_PROP_BatteryAverageCurrent,
 POWER_SUPPLY_PROP_status_smb,POWER_SUPPLY_PROP_capacity_smb,POWER_SUPPLY_PROP_present_smb};
 for(unsigned i=0;i<sizeof(unavailable)/sizeof(unavailable[0]);i++)
  assert(battery_get_property(&data.psy,unavailable[i],&value)==-ENODATA);
 assert(!battery_get_property(&data.psy,POWER_SUPPLY_PROP_InstatVolt,&value)&&value.intval==3437);
 assert(!battery_get_property(&data.psy,POWER_SUPPLY_PROP_TECHNOLOGY,&value)&&value.intval==2);
 assert(battery_get_property(&data.psy,(enum power_supply_property)999,&value)==-EINVAL);
 for(int scenario=0;scenario<3;scenario++) {
  exists=scenario!=0;missing=scenario==1;injected_gpio=scenario==2?70:69;
  assert(!battery_get_property(&data.psy,POWER_SUPPLY_PROP_CAPACITY,&value)&&value.intval==85);
  assert(!battery_get_property(&data.psy,POWER_SUPPLY_PROP_batt_temp,&value)&&value.intval==470);
 }
 assert(references==0);
 assert(data.BAT_STATUS==1&&data.BAT_HEALTH==1&&data.BAT_CAPACITY==85&&data.BAT_batt_temp==470);
 puts("PASS: M39 estimates withheld, voltage preserved, other boards unchanged, reference balance and internal data unchanged.");
}
'''
with tempfile.TemporaryDirectory() as directory:
    src = Path(directory)/'check.c'
    binary = Path(directory)/'check'
    src.write_text(fixture)
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(src),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
