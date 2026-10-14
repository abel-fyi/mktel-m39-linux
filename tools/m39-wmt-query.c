// SPDX-License-Identifier: GPL-2.0-only
/* Read-only WMT identity query. No module-init, power, calibration or SET ioctls.
 * The reviewed vendor driver returns chip IDs as ioctl's return value. */
static long syscall4(long n, long a, long b, long c, long d) {
    register long x0 __asm__("x0")=a, x1 __asm__("x1")=b;
    register long x2 __asm__("x2")=c, x3 __asm__("x3")=d;
    register long x8 __asm__("x8")=n;
    __asm__ volatile("svc 0":"+r"(x0):"r"(x1),"r"(x2),"r"(x3),"r"(x8):"memory","cc");
    return x0;
}
static int print_id(const char *label, unsigned size, long value) {
    static const char digits[]="0123456789abcdef";
    char line[32]; unsigned n=0, i;
    for(i=0;i<size;i++) line[n++]=label[i];
    if(value<0 || value>65535) {
        static const char unknown[]="unavailable";
        for(i=0;i<sizeof(unknown)-1;i++) line[n++]=unknown[i];
    } else {
        line[n++]='0';line[n++]='x';
        for(i=0;i<4;i++) line[n++]=digits[(value>>(12-4*i))&15];
    }
    line[n++]='\n';
    return syscall4(64,1,(long)line,n,0)==n ? 0 : 1;
}
void _start(void) {
    static const char path[]="/dev/wmtdetect";
    long fd=syscall4(56,-100,(long)path,0,0); /* openat O_RDONLY */
    int failed=fd<0;
    if(!failed) {
        long soc=syscall4(29,fd,0x80047703UL,0,0);
        long combo=syscall4(29,fd,0x80047700UL,0,0);
        failed=print_id("soc_chip=",9,soc) | print_id("combo_chip=",11,combo);
        syscall4(57,fd,0,0,0);
    }
    syscall4(93,failed,0,0,0);
    for(;;) {}
}
