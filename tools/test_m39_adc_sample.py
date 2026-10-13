"""Fault-inject the actual ADC transaction without accessing hardware."""
from pathlib import Path
import subprocess
import tempfile

source = r'''
#define M39_ADC_HOST_TEST
#include "m39-adc-sample.c"
#include <assert.h>
#include <stdio.h>
static unsigned regs[65536], writes, fault, changed, restored;
static u64 ticks;
static int read_mock(unsigned a,unsigned *v){
 ticks+=1000;
 if(a==0xe32 && fault==2)return -1;
 *v=regs[a];return 0;
}
static int write_mock(unsigned a,unsigned v){
 assert(a==0x28a||a==0xe94||a==0xeb0||a==0xe8a);
 writes++;
 if(a==0xe8a){
  if(fault==3)return -1;
  unsigned channels[5]={0xe2e,0xe32,0xe04,0xe06,0xe08};
  for(unsigned i=0;i<5;i++)regs[channels[i]]=fault==1?0:32768+1000;
 }else{
  unsigned mask=a==0x28a?256:a==0xe94?32768:128;
  if(v&mask)changed++;else {restored++;if(fault==4 && a==0xeb0)return -1;}
 }
 regs[a]=v;return 0;
}
static u64 now_mock(void){return ticks;}
static void pause_mock(void){ticks+=100000;}
int main(void){
 struct adc_io p={read_mock,write_mock,now_mock,pause_mock};
 for(fault=0;fault<=5;fault++){
  for(unsigned i=0;i<65536;i++)regs[i]=0;
  regs[0x200]=fault==5?0x3500:0x2830;
  writes=changed=restored=0;ticks=0;
  unsigned out[5]={99,99,99,99,99};
  int rc=adc_snapshot(&p,out);
  assert((rc==0)==(fault==0));
  if(fault==5)assert(writes==0);
  else {assert(changed==3);assert(restored==3);}
  if(fault)assert(out[0]==99);
  if(fault!=4)assert(regs[0x28a]==0 && regs[0xe94]==0 && regs[0xeb0]==0);
  assert(ticks<40000000);
 }
 puts("PASS: fresh ADC, timeout/read/trigger/restore failures, clock cleanup and wrong-chip rejection.");
}
'''
with tempfile.TemporaryDirectory() as d:
    p=Path(d);(p/'test.c').write_text(source)
    subprocess.run(['cc','-Wall','-Wextra','-Werror','-I',str(Path(__file__).parent.resolve()),str(p/'test.c'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
