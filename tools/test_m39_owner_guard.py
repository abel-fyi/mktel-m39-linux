"""Verify the actual lease rejection mask preserves every hardware limit."""
from pathlib import Path
import subprocess,tempfile
source=r'''
#define M39_OWNER_GUARD_TEST
#include "m39-charge-owner.h"
#include <assert.h>
#include <stdio.h>
int main(void) {
 struct m39_owner_profile p={0x2830,99,195,13,5};
 assert(m39_owner_reject_mask(&p)==0);
 for(unsigned chip=0;chip<65536;chip++) {
  p.chip=chip;assert(m39_owner_reject_mask(&p)==((chip>>8)==40?0:1));
 }
 p.chip=0x2830;
 for(unsigned c=0;c<256;c++)for(unsigned v=0;v<32;v++)
 for(unsigned i=0;i<16;i++)for(unsigned o=0;o<8;o++) {
  p.control=c;p.cv=v;p.current_reg=i;p.ov=o;
  unsigned mask=m39_owner_reject_mask(&p);
  int allowed=!(c&24)&&v==3&&i>=13&&o==5;
  assert((mask==0)==allowed);
  assert(!!(mask&2)==!!(c&24));assert(!!(mask&4)==(v!=3));
  assert(!!(mask&8)==(i<13));assert(!!(mask&16)==(o!=5));
 }
 puts("PASS: chip family, off gates, exact CV, current cap and OV guards unchanged across all tested combinations.");
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'test.c').write_text(source)
 subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror','-I',str(Path(__file__).parent.resolve()),str(p/'test.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
