"""Compile the actual sysfs handler with fake PMIC I/O; no hardware access."""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parent.parent
s=(root/'tools/mt6735-kernel/drivers/misc/mediatek/power/mt6735/pmic.c').read_text()
a=s.index('static ssize_t store_pmic_access(');b=s.index('\n}',a)+2
fixture=r'''
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <limits.h>
#include <unistd.h>
#include <assert.h>
struct device {int unused;}; struct device_attribute {int unused;};
#define pr_err(...) ((void)0)
unsigned int g_reg_value=0xaabb;
static int hardware_error,reads,writes;
static unsigned int last_address,last_value;
static int kstrtou32(const char *s,unsigned int base,unsigned int *out) {
 char *end;unsigned long value;if(!s)return -EINVAL;errno=0;
 value=strtoul(s,&end,base);
 if(end==s||(*end&&strcmp(end,"\n")))return -EINVAL;
 if(errno||value>UINT_MAX)return -ERANGE;
 *out=value;return 0;
}
static unsigned int pmic_read_interface(unsigned int a,unsigned int *v,unsigned int m,unsigned int z) {
 reads++;last_address=a;if(hardware_error)return hardware_error;*v=0xbeef;return 0;
}
static unsigned int pmic_config_interface(unsigned int a,unsigned int v,unsigned int m,unsigned int z) {
 writes++;last_address=a;last_value=v;return hardware_error;
}
'''
main=r'''
static ssize_t request(const char *text) {
 char *buffer=strdup(text);ssize_t result=store_pmic_access(NULL,NULL,buffer,strlen(buffer));free(buffer);return result;
}
int main(void) {
 assert(request("0f4e\n")==5&&g_reg_value==0xbeef&&last_address==0xf4e);
 hardware_error=7;assert(request("0f4e\n")==-EIO&&g_reg_value==0xbeef);
 hardware_error=-ETIMEDOUT;assert(request("0f4e\n")==-ETIMEDOUT);
 hardware_error=0;assert(request("0f4e 0003\n")==10&&last_value==3);
 hardware_error=7;assert(request("0f4e 0003\n")==-EIO);
 int old_reads=reads,old_writes=writes;
 assert(request("nope\n")==-EINVAL);
 assert(request("0f4e nope\n")==-EINVAL);
 assert(reads==old_reads&&writes==old_writes);
 puts("PASS: actual handler rejects malformed input, propagates read/write errors, and preserves cache on failed reads.");
}
'''
with tempfile.TemporaryDirectory() as directory:
 p=Path(directory);(p/'test.c').write_text(fixture+s[a:b]+main)
 subprocess.run(['cc',str(p/'test.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
