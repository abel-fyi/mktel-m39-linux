// SPDX-License-Identifier: GPL-2.0
/* Bounded MT6328 current snapshot. No charger controls, counter resets or
 * calibration writes. Kernel users share the gauge: no exclusive lock is
 * claimed. Reject a lost latch, release it, and retry within 30 ms. */
typedef unsigned long long u64;
struct io {
    int (*read)(unsigned, unsigned *);
    int (*write_control)(unsigned);
    u64 (*now)(void);
    void (*pause)(void);
};
struct result { unsigned raw, attempts, stage; };

static int release(const struct io *p, u64 deadline) {
    unsigned control;
    if (p->read(0xca4, &control)) return -1;
    if (p->write_control((control & 255) | 0x800)) return -1;
    do {
        if (p->read(0xca4, &control)) return -1;
        if (!(control & 0x400))
            return p->write_control(control & 255);
        p->pause();
    } while (p->now() < deadline);
    return -1;
}

/* Every acquired request is released before success or retry. A failed
 * release is fatal, never treated as a valid or merely stale measurement. */
static int snapshot(const struct io *p, struct result *out) {
    unsigned identity, control, raw;
    u64 finish = p->now() + 30000000ULL;
    out->stage=1;
    if (p->read(0x200, &identity)) return -1;
    out->stage=2;
    if ((identity >> 8) != 0x28) return -1;
    for (unsigned attempt = 1; attempt <= 3; attempt++) {
        out->attempts=attempt;
        do {
            out->stage=3;
            if (p->read(0xca4, &control)) return -1;
            if (!(control & 0xff00)) break;
            out->stage=4;
            if (p->now() >= finish) return -1;
            p->pause();
        } while (1);
        out->stage=9;
        if (p->now() >= finish) return -1;
        if (p->write_control((control & 255) | 0x200)) {
            out->stage=release(p, p->now() + 5000000ULL)?10:5;
            return -1;
        }
        int complete = 0, io_failed = 0;
        u64 ready_deadline = p->now() + 5000000ULL;
        do {
            out->stage=6;
            if (p->read(0xca4, &control)) { io_failed = 1; break; }
            if (control & 0x400) {
                out->stage=7;
                if (p->read(0xcb2, &raw) || p->read(0xca4, &control)) {
                    io_failed = 1;
                } else {
                    complete = !!(control & 0x400);
                }
                break;
            }
            p->pause();
        } while (p->now() < ready_deadline && p->now() < finish);
        if (release(p, p->now() + 5000000ULL)) { out->stage=10; return -1; }
        if (io_failed) return -1;
        if (complete && p->now() < finish) {
            out->raw = raw;
            out->attempts = attempt;
            out->stage=0;
            return 0;
        }
        out->stage=complete?9:8;
    }
    return -1;
}

#ifdef M39_FG_HOST_TEST
#include <stdio.h>
#include <string.h>
static unsigned ctrl = 0x29, requests, clears, changes, failed_reads;
static u64 ticks;
static const char *scenario;
static u64 now(void) { return ticks; }
static void pause_io(void) { ticks += 100000ULL; }
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
        ctrl = value & 255;
    } else ctrl = value;
    return 0;
}
int main(int argc, char **argv) {
    if (argc != 2) return 2;
    scenario = argv[1];
    if (!strcmp(scenario, "busy")) ctrl |= 0x600;
    struct io p = {read_reg, write_control, now, pause_io};
    struct result r = {0};
    int rc = snapshot(&p, &r);
    printf("rc=%d raw=%u requests=%u clears=%u low_changes=%u ctrl=%u ticks=%llu failed_reads=%u stage=%u\n",
           rc, r.raw, requests, clears, changes, ctrl, ticks, failed_reads,r.stage);
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
    static const struct io p = {read_reg,write_control,now,pause_io};
    struct result r={0};
    int rc=snapshot(&p,&r);
    if (!rc) {
        char output[32]; unsigned n=decimal(output,r.raw); output[n++]=' ';
        if (r.raw>32767) {output[n++]='-'; n+=decimal(output+n,65535-r.raw);}
        else n+=decimal(output+n,r.raw);
        output[n++]='\n';
        if (sc(64,1,(long)output,n,0)!=n) { rc=-1;r.stage=11; }
    }
    if (rc) {
        char error[64]="FG_ERROR stage=";unsigned n=15;
        n+=decimal(error+n,r.stage);error[n++]='\n';
        sc(64,2,(long)error,n,0);
    }
    sc(93,rc ? 1 : 0,0,0,0);
    for (;;) {}
}
#endif
