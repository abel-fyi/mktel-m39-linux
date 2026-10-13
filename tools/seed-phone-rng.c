// SPDX-License-Identifier: GPL-2.0
/* Credit 512 bits from a freshly generated, trusted host CSPRNG seed.
 * No seed is embedded in the binary or boot image. Deletes its input file.
 */
static long sc(long n,long a,long b,long c,long d,long e,long f){
 register long x0 __asm__("x0")=a,x1 __asm__("x1")=b,x2 __asm__("x2")=c;
 register long x3 __asm__("x3")=d,x4 __asm__("x4")=e,x5 __asm__("x5")=f,x8 __asm__("x8")=n;
 __asm__ volatile("svc 0":"+r"(x0):"r"(x1),"r"(x2),"r"(x3),"r"(x4),"r"(x5),"r"(x8):"memory","cc");return x0;
}
__attribute__((noreturn)) void _start(void){
 struct {int bits,size;unsigned char seed[64];} input={512,64,{0}};
 long source=sc(56,-100,(long)"/tmp/m39-entropy.seed",0,0,0,0);int status=1;
 if(source>=0){
  unsigned used=0;while(used<64){long n=sc(63,source,(long)(input.seed+used),64-used,0,0,0);if(n<=0)break;used+=n;}
  unsigned char extra;long rest=sc(63,source,(long)&extra,1,0,0,0);sc(57,source,0,0,0,0,0);
  if(used==64&&rest==0){
   long random=sc(56,-100,(long)"/dev/random",2,0,0,0);
   if(random>=0){if(sc(29,random,0x40085203,(long)&input,0,0,0)==0)status=0;sc(57,random,0,0,0,0,0);}
  }
 }
 sc(35,-100,(long)"/tmp/m39-entropy.seed",0,0,0,0);
 const char *message=status?"RNG seed failed\n":"Fresh host entropy credited; seed file removed\n";
 unsigned length=0;while(message[length])length++;sc(64,1,(long)message,length,0,0,0);
 sc(93,status,0,0,0,0,0);for(;;){}
}
