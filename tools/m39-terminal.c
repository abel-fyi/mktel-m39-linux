// SPDX-License-Identifier: GPL-2.0
/* M39 prototype userspace terminal. No libc, GPU or LCD register writes.
 * Uses the bootloader's verified reserved ARGB8888 scanout allocation.
 * Input: real PTY, keypad evdev, and /run/m39-terminal.in control FIFO.
 * This is not a replacement for a general-purpose framebuffer/VT driver.
 */
#include "font-6x10.h"
#ifndef M39_STARTUP_COMMAND
#define M39_STARTUP_COMMAND "printf '\033[2J\033[HMKTEL M39 - native Alpine Linux\n\n'; fastfetch --logo small --logo-position top --structure OS:Host:Kernel:CPU:Memory:Packages:Uptime --key-width 10; printf '\nUSB input: /run/m39-terminal.in\n'; exec /bin/sh -i"
#endif
typedef unsigned int u32;
static long sc(long n,long a,long b,long c,long d,long e,long f) {
 register long x0 __asm__("x0")=a,x1 __asm__("x1")=b,x2 __asm__("x2")=c;
 register long x3 __asm__("x3")=d,x4 __asm__("x4")=e,x5 __asm__("x5")=f;
 register long x8 __asm__("x8")=n;
 __asm__ volatile("svc 0":"+r"(x0):"r"(x1),"r"(x2),"r"(x3),"r"(x4),"r"(x5),"r"(x8):"memory","cc");return x0;
}
static unsigned len(const char*s){unsigned n=0;while(s[n])n++;return n;}
static void writefd(long fd,const char*s){sc(64,fd,(long)s,len(s),0,0,0);}
static void die(const char*s){writefd(2,s);sc(93,1,0,0,0,0,0);for(;;){}}
static int bad(long x){return x<0&&x>=-4095;}
#define COLS 40
#define ROWS 32
static volatile u32 *fb;
static struct cell {unsigned char ch,fg,bg;} cells[ROWS][COLS];
static unsigned row,col,fg=7,bg=0,savedrow,savedcol,state,params[16],np,utf8;
static long master;
static const u32 colors[16]={0xff101820,0xffd54e53,0xff81b88b,0xffe8c882,0xff80b8eb,0xffb88ee8,0xff81d5d5,0xffeeeeee,0xff65717e,0xffff7777,0xffa6e6a6,0xffffffaa,0xffaacfff,0xffd8b5ff,0xffb5ffff,0xffffffff};
static void paint(unsigned y,unsigned x){
#ifdef M39_HEADLESS_TEST
 (void)y;(void)x;return;
#endif
 struct cell c=cells[y][x];
 for(unsigned dy=0;dy<10;dy++)for(unsigned dx=0;dx<6;dx++)
  fb[(y*10+dy)*256+x*6+dx]=(font[c.ch*10+dy]&(0x80>>dx))?colors[c.fg]:colors[c.bg];
}
static void blank(unsigned y,unsigned x){cells[y][x]=(struct cell){' ',fg,bg};paint(y,x);}
static void clear(void){for(unsigned y=0;y<ROWS;y++)for(unsigned x=0;x<COLS;x++)blank(y,x);row=col=0;}
static void newline(void){
 if(++row<ROWS)return;row=ROWS-1;
 for(unsigned y=0;y<ROWS-1;y++)for(unsigned x=0;x<COLS;x++){cells[y][x]=cells[y+1][x];paint(y,x);}
 for(unsigned x=0;x<COLS;x++)blank(ROWS-1,x);
}
static unsigned arg(unsigned i,unsigned fallback){return i<=np&&params[i]?params[i]:fallback;}
static void decimal(char*b,unsigned v){unsigned n=0;char t[12];do{t[n++]='0'+v%10;v/=10;}while(v);for(unsigned i=0;i<n;i++)b[i]=t[n-i-1];b[n]=0;}
static void csi(unsigned c){
 unsigned n=arg(0,1);
 if(c=='A')row=n>row?0:row-n;
 if(c=='B')row=row+n<ROWS?row+n:ROWS-1;
 if(c=='C')col=col+n<COLS?col+n:COLS-1;
 if(c=='D')col=n>col?0:col-n;
 if(c=='G')col=n<=COLS?n-1:COLS-1;
 if(c=='H'||c=='f'){row=arg(0,1)-1;col=arg(1,1)-1;if(row>=ROWS)row=ROWS-1;if(col>=COLS)col=COLS-1;}
 if(c=='J'){
  if(params[0]==2||params[0]==3)clear();
  else if(params[0]==0)for(unsigned y=row;y<ROWS;y++)for(unsigned x=y==row?col:0;x<COLS;x++)blank(y,x);
 }
 if(c=='K'){unsigned start=params[0]==0?col:0,end=params[0]==1?col+1:COLS;for(unsigned x=start;x<end;x++)blank(row,x);}
 if(c=='s'){savedrow=row;savedcol=col;}
 if(c=='u'){row=savedrow;col=savedcol;}
 if(c=='m')for(unsigned i=0;i<=np;i++){
  unsigned p=params[i];if(p==0){fg=7;bg=0;}else if(p==1&&fg<8)fg+=8;else if(p==22&&fg>=8)fg-=8;
  else if(p>=30&&p<=37)fg=p-30;else if(p>=40&&p<=47)bg=p-40;
  else if(p>=90&&p<=97)fg=p-90+8;else if(p>=100&&p<=107)bg=p-100+8;
  else if(p==39)fg=7;else if(p==49)bg=0;
  else if((p==38||p==48)&&i+2<=np&&params[i+1]==5){unsigned v=params[i+2];if(v<16){if(p==38)fg=v;else bg=v;}i+=2;}
 }
 if(c=='n'&&params[0]==6){char b[12];writefd(master,"\033[");decimal(b,row+1);writefd(master,b);writefd(master,";");decimal(b,col+1);writefd(master,b);writefd(master,"R");}
}
static void feed(unsigned char c){
 if(state==3){if(c==7)state=0;else if(c==27)state=4;return;}
 if(state==4){state=c=='\\'?0:3;return;}
 if(state==1){state=0;if(c=='['){state=2;np=0;for(unsigned i=0;i<16;i++)params[i]=0;}else if(c==']')state=3;else if(c=='7'){savedrow=row;savedcol=col;}else if(c=='8'){row=savedrow;col=savedcol;}return;}
 if(state==2){if(c>='0'&&c<='9')params[np]=params[np]*10+c-'0';else if(c==';'){if(np<15)np++;}else if(c>=0x40&&c<=0x7e){csi(c);state=0;}return;}
 if(c==27){state=1;return;}if(c=='\r'){col=0;return;}if(c=='\n'){newline();return;}
 if(c==8){if(col)col--;return;}if(c=='\t'){unsigned next=(col+8)&~7;col=next<COLS?next:COLS;return;}
 if(c<32)return;
 if(utf8){if((c&0xc0)==0x80){utf8--;return;}utf8=0;}
 if(c>=0xc0){utf8=c<0xe0?1:c<0xf0?2:3;c='?';}else if(c>=0x80)c='?';
 if(col>=COLS){col=0;newline();}cells[row][col]=(struct cell){c,fg,bg};paint(row,col++);
}
static void key(unsigned code){
 const char*s=0;char b[2]={0,0};
 if(code>=2&&code<=10)b[0]='1'+code-2;else if(code==11)b[0]='0';
 else if(code==28||code==352||code==232)s="\r";else if(code==14||code==158)s="\177";
 else if(code==103)s="\033[A";else if(code==108)s="\033[B";else if(code==105)s="\033[D";else if(code==106)s="\033[C";
 if(!s&&b[0])s=b;if(s)writefd(master,s);
}
__attribute__((noreturn)) void _start(void){
#ifdef M39_HEADLESS_TEST
 long fd=-1;clear();
#else
 long fd=sc(56,-100,(long)"/dev/mtk_disp_mgr",2,0,0,0);if(fd<0)die("display open failed\n");
 long p=sc(222,0,0x120000,3,1,fd,0xbfea0000);if(bad(p))die("display mmap failed\n");fb=(volatile u32*)p;clear();
#endif
 master=sc(56,-100,(long)"/dev/ptmx",2|0x100,0,0,0);if(master<0)die("ptmx open failed\n");
 int zero=0,number=0;if(sc(29,master,0x40045431,(long)&zero,0,0,0)<0)die("pty unlock failed\n");
 if(sc(29,master,0x80045430,(long)&number,0,0,0)<0)die("pty number failed\n");
 char slave[40]="/dev/pts/";decimal(slave+9,number);
 struct {unsigned short rows,cols,x,y;} size={ROWS,COLS,240,320};sc(29,master,0x5414,(long)&size,0,0,0);
 long child=sc(220,17,0,0,0,0,0);if(child<0)die("fork failed\n");
 if(child==0){
  sc(157,0,0,0,0,0,0);long tty=sc(56,-100,(long)slave,2,0,0,0);if(tty<0)die("slave open failed\n");
  sc(29,tty,0x540e,0,0,0,0);for(long i=0;i<3;i++)if(tty!=i)sc(24,tty,i,0,0,0,0);
  sc(57,master,0,0,0,0,0);if(tty>2)sc(57,tty,0,0,0,0,0);sc(57,fd,0,0,0,0,0);
  char *argv[]={"/bin/sh","-c",M39_STARTUP_COMMAND,0};
  char *env[]={"PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin","HOME=/root","TERM=linux","SHELL=/bin/sh","LANG=C","PS1=m39:~# ",0};
  sc(221,(long)argv[0],(long)argv,(long)env,0,0,0);die("shell exec failed\n");
 }
 sc(57,fd,0,0,0,0,0);
 sc(33,-100,(long)"/run/m39-terminal.in",0010600,0,0,0);
 long input=sc(56,-100,(long)"/run/m39-terminal.in",2|0x800,0,0,0);
 long keypad=sc(56,-100,(long)"/dev/input/event1",0x800,0,0,0);
 writefd(1,"display mapped; PTY shell running; input FIFO ready\n");
 struct pollfd {int fd;short events,revents;} fds[3]={{master,1,0},{input,1,0},{keypad,1,0}};
 char buf[2048];
 for(;;){
  long ready=sc(73,(long)fds,3,0,0,0,0);if(ready<0)continue;
  if(fds[0].revents&1){long n=sc(63,master,(long)buf,sizeof(buf),0,0,0);if(n<=0)die("PTY closed\n");
#ifdef M39_HEADLESS_TEST
   sc(64,1,(long)buf,n,0,0,0);
#endif
   for(long i=0;i<n;i++)feed(buf[i]);}
  if(fds[0].revents&16)die("PTY hangup\n");
  if(fds[1].revents&1){long n=sc(63,input,(long)buf,sizeof(buf),0,0,0);if(n>0)sc(64,master,(long)buf,n,0,0,0);}
  if(fds[2].revents&1){struct event {long sec,usec;unsigned short type,code;int value;} ev[16];long n=sc(63,keypad,(long)ev,sizeof(ev),0,0,0);for(long i=0;i<n/(long)sizeof(ev[0]);i++)if(ev[i].type==1&&ev[i].value)key(ev[i].code);}
 }
}
