/* Read-only inspection of the bootloader's display overlay registers. */
typedef unsigned long u64;
typedef unsigned int u32;
static long sc(long n, long a, long b, long c, long d, long e, long f) {
    register long x0 __asm__("x0")=a, x1 __asm__("x1")=b, x2 __asm__("x2")=c;
    register long x3 __asm__("x3")=d, x4 __asm__("x4")=e, x5 __asm__("x5")=f;
    register long x8 __asm__("x8")=n;
    __asm__ volatile("svc 0" : "+r"(x0) : "r"(x1),"r"(x2),"r"(x3),"r"(x4),"r"(x5),"r"(x8) : "memory","cc");
    return x0;
}
static void text(const char *s) { unsigned n=0; while(s[n]) n++; sc(64,1,(long)s,n,0,0,0); }
static void hex(u64 v) { char b[19]="0x0000000000000000"; const char *h="0123456789abcdef"; for(int i=0;i<16;i++) b[17-i]=h[(v>>(4*i))&15]; sc(64,1,(long)b,18,0,0,0); }
__attribute__((noreturn)) void _start(void) {
    long fd=sc(56,-100,(long)"/dev/mtk_disp_mgr",0,0,0,0);
    if(fd<0) { text("open failed ");hex(-fd);text("\n");sc(93,1,0,0,0,0,0); }
    long p=sc(222,0,4096,1,1,fd,0x14007000);
    if(p<0 && p>=-4095) {text("mmap failed ");hex(-p);text("\n");sc(93,2,0,0,0,0,0);}
    volatile u32 *r=(volatile u32*)p;
    const unsigned offsets[]={0x000,0x020,0x02c,0x030,0x034,0x038,0x03c,0x040,0x044,0x050,0x058,0x064,0xf40,0xf44,0xf48,0xf4c};
    for(unsigned i=0;i<sizeof(offsets)/sizeof(offsets[0]);i++){hex(offsets[i]);text(" = ");hex(r[offsets[i]/4]);text("\n");}
    sc(215,p,4096,0,0,0,0);sc(57,fd,0,0,0,0,0);sc(93,0,0,0,0,0,0);for(;;){}
}
