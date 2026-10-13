// SPDX-License-Identifier: GPL-2.0
/* Optional bounded backlight prototype. Reads keypad without grabbing input;
 * writes only the verified lcd-backlight brightness interface. No PMIC I/O. */
struct screen { long last; int dark; };
static int settings(const char *text, unsigned size, long *idle, long *lifetime) {
    long values[2]={0,0}; unsigned position=0;
    for(unsigned field=0;field<2;field++) {
        unsigned digits=0;
        while(position<size&&text[position]>='0'&&text[position]<='9') {
            values[field]=values[field]*10+text[position++]-'0'; digits++;
            if(values[field]>86400)return -1;
        }
        if(!digits)return -1;
        if(field==0) {
            if(position>=size||text[position++]!=' ')return -1;
        }
    }
    if(position<size&&text[position]=='\n')position++;
    if(position!=size||values[0]<5||values[0]>600)return -1;
    *idle=values[0];*lifetime=values[1];return 0;
}
static int transition(struct screen *state, long now, int activity, long idle) {
    if (activity) {
        state->last=now;
        if (state->dark) { state->dark=0; return 255; }
    } else if (!state->dark && now-state->last>=idle) {
        state->dark=1; return 0;
    }
    return -1;
}
#ifdef M39_SCREEN_HOST_TEST
#include <assert.h>
#include <stdio.h>
int main(void) {
    long idle=0,lifetime=0;
    assert(!settings("60 0\n",5,&idle,&lifetime)&&idle==60&&lifetime==0);
    assert(!settings("10 120\n",7,&idle,&lifetime)&&idle==10&&lifetime==120);
    assert(settings("0 0\n",4,&idle,&lifetime));
    assert(settings("601 0\n",6,&idle,&lifetime));
    assert(settings("60 99999999999999999\n",21,&idle,&lifetime));
    assert(settings("60 0 junk",9,&idle,&lifetime));
    struct screen s={100,0};
    assert(transition(&s,109,0,10)==-1);
    assert(transition(&s,110,0,10)==0);
    assert(transition(&s,111,0,10)==-1);
    assert(transition(&s,112,1,10)==255);
    assert(transition(&s,120,1,10)==-1);
    assert(transition(&s,129,0,10)==-1);
    assert(transition(&s,130,0,10)==0);
    assert(transition(&s,130,1,10)==255);
    puts("PASS: idle threshold, single dark transition, keypad wake and activity reset.");
}
#else
static long sc(long n,long a,long b,long c,long d,long e,long f) {
    register long x0 __asm__("x0")=a,x1 __asm__("x1")=b,x2 __asm__("x2")=c;
    register long x3 __asm__("x3")=d,x4 __asm__("x4")=e,x5 __asm__("x5")=f;
    register long x8 __asm__("x8")=n;
    __asm__ volatile("svc 0":"+r"(x0):"r"(x1),"r"(x2),"r"(x3),"r"(x4),"r"(x5),"r"(x8):"memory","cc");
    return x0;
}
static unsigned length(const char *s) { unsigned n=0;while(s[n])n++;return n; }
static void logline(const char *s) { sc(64,1,(long)s,length(s),0,0,0); }
static int brightness(int value) {
    const char *text=value?"255\n":"0\n";
    long fd=sc(56,-100,(long)"/sys/class/leds/lcd-backlight/brightness",1,0,0,0);
    if(fd<0)return -1;
    long size=length(text),result=sc(64,fd,(long)text,size,0,0,0);
    sc(57,fd,0,0,0,0,0);
    return result==size?0:-1;
}
static long now(void) {
    struct {long sec,nsec;} time;
    if(sc(113,1,(long)&time,0,0,0,0)<0)return -1;
    return time.sec;
}
__attribute__((noreturn)) void _start(void) {
    long idle=10,lifetime=120;
    char config[64];
    long config_fd=sc(56,-100,(long)"/run/m39-screen-idle-config",0,0,0,0);
    int config_error=0;
    if(config_fd>=0) {
        long count=sc(63,config_fd,(long)config,sizeof(config),0,0,0);
        sc(57,config_fd,0,0,0,0,0);
        config_error=count<=0||count==(long)sizeof(config)||settings(config,(unsigned)count,&idle,&lifetime);
    } else if(config_fd!=-2)config_error=1;
    char name[16];
    long fd=sc(56,-100,(long)"/sys/class/input/event1/device/name",0,0,0,0);
    long n=fd<0?-1:sc(63,fd,(long)name,sizeof(name),0,0,0);
    if(fd>=0)sc(57,fd,0,0,0,0,0);
    const char *expected="mtk-kpd\n";
    int correct=n==8;
    for(int i=0;correct&&i<8;i++)correct=name[i]==expected[i];
    long keypad=correct?sc(56,-100,(long)"/dev/input/event1",0x800,0,0,0):-1;
    long started=now();
    long parent=sc(173,0,0,0,0,0,0);
    int error=keypad<0||started<0||config_error||parent<=1;
    struct screen state={started,0};
    if(!error&&brightness(255))error=1;
    if(!error)logline("READY: configured idle; keypad wake; backlight only\n");
    while(!error) {
        struct {int fd;short events,revents;} pollfd={(int)keypad,1,0};
        struct {long sec,nsec;} delay={1,0};
        long polled=sc(73,(long)&pollfd,1,(long)&delay,0,0,0);
        if(polled==-4)continue;
        if(polled<0||(pollfd.revents&56)) {error=1;break;}
        int activity=0;
        if(pollfd.revents&1) {
            struct {long sec,usec;unsigned short type,code;int value;} events[16];
            n=sc(63,keypad,(long)events,sizeof(events),0,0,0);
            if(n==-11||n==-4)continue;
            if(n<=0||n%(long)sizeof(events[0])) {error=1;break;}
            for(long i=0;i<n/(long)sizeof(events[0]);i++)
                if(events[i].type==1&&events[i].value>0)activity=1;
        }
        long current=now();
        if(current<started||sc(173,0,0,0,0,0,0)!=parent) {error=1;break;}
        if(lifetime&&current-started>=lifetime)break;
        int value=transition(&state,current,activity,idle);
        if(value>=0) {
            if(brightness(value)) {error=1;break;}
            logline(value?"WAKE: keypad activity\n":"DARK: idle timeout\n");
        }
    }
    if(keypad>=0)sc(57,keypad,0,0,0,0,0);
    if(brightness(255))error=1;
    logline(error?"ERROR: stopped; restore255 attempted\n":"DONE: restored255\n");
    sc(93,error,0,0,0,0,0);
    for(;;){}
}
#endif
