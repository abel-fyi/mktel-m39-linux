"""Execute the actual provisioning write loop against a recording fake dd."""
from pathlib import Path
import os, subprocess, tempfile
source=Path(__file__).with_name('provision-encrypted-root.sh').read_text()
body=source[source.index('total=$(( (30108672'):source.index('header_after=')]
with tempfile.TemporaryDirectory() as directory:
    root=Path(directory)
    prefix='''set -eu
device=mock
written=0
status() { :; }
dd() {
 echo "$*" >> "$LOG"
 [ "$FAIL" != 1 ] || return 1
}
'''
    for fail in (0,1):
        log=root/str(fail)
        result=subprocess.run(['sh','-c',prefix+body],env=dict(os.environ,LOG=str(log),FAIL=str(fail)),capture_output=True,text=True)
        rows=log.read_text().splitlines()
        if fail:
            assert result.returncode!=0 and len(rows)==1
            continue
        assert result.returncode==0,result.stderr
        end=16777216
        for row in rows:
            args=dict(arg.split('=',1) for arg in row.split())
            assert args['if']=='/dev/zero' and args['of']=='mock'
            assert args['conv']=='notrunc,fsync'
            bs=int(args['bs']);start=int(args['seek'])*bs
            assert start==end
            end=start+int(args['count'])*bs
            assert end<=30108672*512
        assert end==30108672*512
print('PASS: actual write loop preserves the 16MiB header, covers exactly the data area, stays within root and stops on write failure.')
