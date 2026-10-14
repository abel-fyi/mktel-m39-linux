#!/bin/sh
# OpenMTTools remains MIT licensed; see its upstream LICENSE.
set -eu
cd "$(dirname "$0")/.."
source_dir=tools/openmttools
revision=ef35f769d211a2942a6783410b58bd824dd363f9
test "$(git -C "$source_dir" rev-parse HEAD)" = "$revision"
# Refuse an unexpected local source modification.
git -C "$source_dir" diff -- mtdaemon.c | cmp - tools/openmttools-m39.patch
compiler=tools/aarch64-gcc49/bin/aarch64-linux-android-gcc
headers=$($compiler -print-file-name=include)
libgcc=$($compiler -print-libgcc-file-name)
lib=build/wifi-musl/usr/lib
python3 - <<'PY'
import hashlib, json
for item in json.load(open('tools/openmttools-build-inputs.json')):
    assert hashlib.sha256(open(item['path'], 'rb').read()).hexdigest() == item['sha256']
PY
for name in mtinit mtdaemon; do
    "$compiler" -std=gnu99 -Os -fno-stack-protector -nostdinc \
        -isystem build/wifi-musl/usr/include -isystem "$headers" \
        -nostdlib -static "$lib/crt1.o" "$lib/crti.o" "$source_dir/$name.c" \
        -Wl,--start-group "$lib/libc.a" "$libgcc" -Wl,--end-group "$lib/crtn.o" \
        -o "artifacts/$name"
done
