// SPDX-License-Identifier: GPL-2.0
/* Read the verified M39 scanout buffer into a portable RGB PPM screenshot. */
typedef unsigned int u32;
static long sc(long n,long a,long b,long c,long d,long e,long f){
 register long x0 __asm__("x0")=a,x1 __asm__("x1")=b,x2 __asm__("x2")=c;
 register long x3 __asm__("x3")=d,x4 __asm__("x4")=e,x5 __asm__("x5")=f,x8 __asm__("x8")=n;
 __asm__ volatile("svc 0":"+r"(x0):"r"(x1),"r"(x2),"r"(x3),"r"(x4),"r"(x5),"r"(x8):"memory","cc");return x0;
}
__attribute__((noreturn)) void _start(void){
 long fd=sc(56,-100,(long)"/dev/mtk_disp_mgr",0,0,0,0);
 long p=fd<0?-1:sc(222,0,0x120000,1,1,fd,0xbfea0000);
 long out=(p<0&&p>=-4095)?-1:sc(56,-100,(long)"/tmp/m39-screen.ppm",1|64|512,0644,0,0);
 int status=1;
 if(out>=0){
  volatile u32 *fb=(volatile u32*)p;char line[720];
  const char header[]="P6\n240 320\n255\n";
  if(sc(64,out,(long)header,sizeof(header)-1,0,0,0)==sizeof(header)-1){
   status=0;
   for(unsigned y=0;y<320;y++){
    for(unsigned x=0;x<240;x++){u32 v=fb[y*256+x];line[x*3]=v>>16;line[x*3+1]=v>>8;line[x*3+2]=v;}
    if(sc(64,out,(long)line,sizeof(line),0,0,0)!=sizeof(line)){status=1;break;}
   }
  }
  sc(57,out,0,0,0,0,0);
 }
 sc(93,status,0,0,0,0,0);for(;;){}
}
