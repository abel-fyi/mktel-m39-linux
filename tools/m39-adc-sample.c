// SPDX-License-Identifier: GPL-2.0
/* Bounded fresh ADC snapshot; never writes charger controls. */
typedef unsigned long long u64;
struct adc_io {
 int (*read)(unsigned, unsigned *);
 int (*write)(unsigned, unsigned);
 u64 (*now)(void);
 void (*pause)(void);
};
static int field(const struct adc_io *p,unsigned a,unsigned mask,unsigned bits) {
 unsigned v,actual;
 if(p->read(a,&v)||p->write(a,(v&~mask)|(bits&mask))||p->read(a,&actual))return -1;
 return (actual&mask)==(bits&mask)?0:-1;
}
static int adc_snapshot(const struct adc_io *p,unsigned out[5]) {
 static const unsigned clocks[3]={0x28a,0xe94,0xeb0};
 static const unsigned masks[3]={256,32768,128};
 static const unsigned channels[5]={0xe2e,0xe32,0xe04,0xe06,0xe08};
 unsigned saved[3],raw[5],chip;
 int rc=0;
 /* Positive stage codes are reported on stderr, never as valid samples. */
 if(p->read(0x200,&chip))return 1;
 if((chip>>8)!=0x28)return 2;
 for(unsigned i=0;i<3;i++)if(p->read(clocks[i],saved+i))return 10+i;
 for(unsigned i=0;i<3;i++)if(field(p,clocks[i],masks[i],masks[i])){rc=20+i;break;}
 if(!rc && p->write(0xe8a,31))rc=30;
 u64 end=p->now()+30000000ULL;
 for(unsigned i=0;!rc && i<5;i++) {
  for(;;) {
   if(p->read(channels[i],raw+i)){rc=40+i;break;}
   if(raw[i]&32768)break;
   if(p->now()>=end){rc=50+i;break;}
   p->pause();
  }
 }
 if(!rc && p->now()>=end)rc=60;
 /* Restore only changed clock bits, even after acquisition failure. */
 for(unsigned i=0;i<3;i++)if(field(p,clocks[i],masks[i],saved[i]))rc=70+i;
 if(rc)return rc;
 out[0]=(raw[0]&32767)*5400/32768;
 out[1]=(raw[1]&32767)*5400/32768;
 out[2]=(raw[2]&4095)*1800/4096*369/39;
 out[3]=(raw[4]&4095)*1800/4096;
 out[4]=(raw[3]&4095)*1800/4096;
 return 0;
}
#ifndef M39_ADC_HOST_TEST
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
    if (address != 0x200 && address != 0x28a && address != 0xe94 && address != 0xeb0 && address != 0xe8a && address != 0xe2e && address != 0xe32 && address != 0xe04 && address != 0xe06 && address != 0xe08) return -1;
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
static int write_reg(unsigned a,unsigned v) {
 char request[10];
 if(a!=0x28a && a!=0xe94 && a!=0xeb0 && a!=0xe8a)return -1;
 hex4(request,a);request[4]=' ';hex4(request+5,v);request[9]='\n';
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
 static const struct adc_io p={read_reg,write_reg,now,pause_io};
 unsigned values[5];int rc=adc_snapshot(&p,values);
 if(!rc) {
  char out[64];unsigned n=0;
  for(unsigned i=0;i<5;i++){n+=decimal(out+n,values[i]);out[n++]=i==4?'\n':' ';}
  if(sc(64,1,(long)out,n,0)!=n)rc=80;
 }
 if(rc) {
  char error[32]="ADC_ERROR stage=";
  unsigned n=16;n+=decimal(error+n,(unsigned)rc);error[n++]='\n';
  sc(64,2,(long)error,n,0);
 }
 sc(93,rc,0,0,0);for(;;){}
}
#endif
