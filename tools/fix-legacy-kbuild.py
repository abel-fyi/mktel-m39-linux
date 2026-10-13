#!/usr/bin/env python3
"""Fix legacy Kbuild hash escaping and repair cached commands while make is stopped."""
from pathlib import Path
import re
root = Path(__file__).resolve().parent.parent
p = root / 'tools/mt6735-kernel/scripts/Kbuild.include'
s = p.read_text()
new = 'pound := \\#\n' + r'make-cmd = $(call escsq,$(subst $(pound),\$(pound),$(subst $$,$$$$,$(cmd_$(1)))))'
if new not in s:
    old = next(line for line in s.splitlines() if line.startswith('make-cmd = '))
    assert r'$(subst \#,\\\#,' in old
    p.write_text(s.replace(old, new, 1))
count = 0
for p in (root / 'build/mt6735-source').rglob('*.cmd'):
    text = p.read_text()
    lines = text.splitlines(keepends=True)
    if lines and lines[0].startswith('cmd_'):
        repaired = re.sub(r'(?<!\\)#', r'\\#', lines[0])
        if repaired != lines[0]:
            lines[0] = repaired
            p.write_text(''.join(lines))
            count += 1
print(f'Fixed Kbuild hash escaping; repaired {count} saved compiler commands.')
