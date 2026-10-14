#include "m39-fg-core.h"

#ifdef M39_FG_HOST_TEST
#include <stdio.h>
#include <string.h>
static unsigned ctrl = 0x29, requests, clears, changes, failed_reads;
static u64 ticks;
static const char *scenario;
static u64 now(void) { return ticks; }
static void pause_io(void) {
    int delayed = !strcmp(scenario, "release-scheduled-late") ||
        !strcmp(scenario, "release-scheduled-expired");
    if (delayed && (ctrl & 0x800)) {
        ticks += !strcmp(scenario, "release-scheduled-expired") ?
            31000000ULL : 6000000ULL;
        ctrl &= ~0x400;
    } else ticks += 100000ULL;
}
static int read_reg(unsigned address, unsigned *value) {
    ticks += 1000;
    if (address == 0x200) {
        *value = !strcmp(scenario, "wrong-chip") ? 0x3500 : 0x2830;
    } else if (address == 0xca4) {
        *value = ctrl;
    } else if (address == 0xcb2) {
        if (!strcmp(scenario, "read-error")) { failed_reads++; return -1; }
        *value = !strcmp(scenario, "negative") ? 64833 : 222;
        if (!strcmp(scenario, "contended") && requests == 1) ctrl &= ~0xff00;
    } else return -1;
    return 0;
}
static int write_control(unsigned value) {
    if ((value & 255) != (ctrl & 255)) changes++;
    if (value & 0x200) {
        requests++;
        ctrl = (value & 255) | (!strcmp(scenario, "never-ready") ? 0 : 0x600);
    } else if (value & 0x800) {
        clears++;
        if (!strcmp(scenario, "release-error")) return -1;
        if (!strcmp(scenario, "release-timeout")) return 0;
        if (!strcmp(scenario, "release-scheduled-late") ||
            !strcmp(scenario, "release-scheduled-expired")) {
            ctrl = (value & 255) | 0xc00;
            return 0;
        }
        ctrl = value & 255;
    } else ctrl = value;
    return 0;
}
int main(int argc, char **argv) {
    if (argc != 2) return 2;
    scenario = argv[1];
    if (!strcmp(scenario, "busy")) ctrl |= 0x600;
    struct m39_fg_io p = {read_reg, write_control, now, pause_io};
    struct m39_fg_result r = {0};
    int rc = m39_fg_snapshot(&p, &r, now() + 30000000ULL);
    printf("rc=%d raw=%u requests=%u clears=%u low_changes=%u ctrl=%u ticks=%llu failed_reads=%u stage=%u release_stage=%u release_control=%u\n",
           rc, r.raw, requests, clears, changes, ctrl, ticks, failed_reads,r.stage,r.release_stage,r.release_control);
    return 0;
}
#else
static long sc(long n, long a, long b, long c, long d) {
    register long x0 __asm__("x0")=a, x1 __asm__("x1")=b;
    register long x2 __asm__("x2")=c, x3 __asm__("x3")=d;
    register long x8 __asm__("x8")=n;
    __asm__ volatile("svc 0":"+r"(x0):"r"(x1),"r"(x2),"r"(x3),"r"(x8):"memory","cc");
    return x0;
}
static const char path[] = "/sys/devices/platform/mt-pmic/pmic_access";
static void hex4(char *s, unsigned value) {
    static const char digits[] = "0123456789abcdef";
    for (int i=3; i>=0; i--) { s[i]=digits[value & 15]; value >>= 4; }
}
static int send(const char *s, unsigned size) {
    long fd = sc(56, -100, (long)path, 1, 0); // openat, O_WRONLY
    if (fd < 0) return -1;
    long rc = sc(64, fd, (long)s, size, 0);
    sc(57, fd, 0, 0, 0);
    return rc == size ? 0 : -1;
}
static int read_reg(unsigned address, unsigned *value) {
    char request[5], buffer[32];
    if (address != 0x200 && address != 0xca4 && address != 0xcb2) return -1;
    hex4(request, address); request[4]='\n';
    if (send(request, 5)) return -1;
    long fd = sc(56, -100, (long)path, 0, 0);
    if (fd < 0) return -1;
    long size = sc(63, fd, (long)buffer, sizeof(buffer), 0);
    sc(57, fd, 0, 0, 0);
    if (size < 1 || size >= (long)sizeof(buffer)) return -1;
    unsigned v=0, digits=0;
    for (long i=0; i<size; i++) {
        if (buffer[i]=='\n' && i==size-1) break;
        if (buffer[i]<'0' || buffer[i]>'9') return -1;
        v=v*10+(buffer[i]-'0'); digits++;
        if (v>65535 || digits>5) return -1;
    }
    if (!digits) return -1;
    *value=v; return 0;
}
static int write_control(unsigned value) {
    char request[10] = "0ca4 0000\n";
    hex4(request+5,value);
    return send(request,10);
}
static u64 now(void) {
    long time[2];
    if (sc(113, 1, (long)time, 0, 0)<0) return ~0ULL;
    return (u64)time[0]*1000000000ULL+time[1];
}
static void pause_io(void) {
    long time[2]={0,100000};
    sc(101,(long)time,0,0,0);
}
static unsigned decimal(char *buffer, unsigned value) {
    char backwards[10]; unsigned n=0;
    do { backwards[n++]='0'+value%10; value/=10; } while (value);
    for (unsigned i=0;i<n;i++) buffer[i]=backwards[n-i-1];
    return n;
}
void _start(void) {
    static const struct m39_fg_io p = {read_reg,write_control,now,pause_io};
    struct m39_fg_result r={0};
    int rc=m39_fg_snapshot(&p,&r,now() + 30000000ULL);
    if (!rc) {
        char output[32]; unsigned n=decimal(output,r.raw); output[n++]=' ';
        if (r.raw>32767) {output[n++]='-'; n+=decimal(output+n,65535-r.raw);}
        else n+=decimal(output+n,r.raw);
        output[n++]='\n';
        if (sc(64,1,(long)output,n,0)!=n) { rc=-1;r.stage=11; }
    }
    if (rc) {
        char error[64]="FG_ERROR stage=";unsigned n=15;
        n+=decimal(error+n,r.stage);
        if (r.stage==10) {
            const char detail[]=" release_stage=";
            for (unsigned i=0;i<sizeof(detail)-1;i++) error[n++]=detail[i];
            n+=decimal(error+n,r.release_stage);
            const char control[]=" control=";
            for (unsigned i=0;i<sizeof(control)-1;i++) error[n++]=control[i];
            n+=decimal(error+n,r.release_control);
        }
        error[n++]='\n';
        sc(64,2,(long)error,n,0);
    }
    sc(93,rc ? 1 : 0,0,0,0);
    for (;;) {}
}
#endif
