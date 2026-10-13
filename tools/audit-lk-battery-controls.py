#!/usr/bin/env python3
"""Recover battery-input flag descriptors from the saved M39 LK, offline only."""
import hashlib
import json
import struct
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

root = Path(__file__).resolve().parent.parent
data = (root / 'analysis/m39-lk-code.bin').read_bytes()
u32 = lambda offset: struct.unpack_from('<I', data, offset)[0]
# Verified Thumb setter at b5bc: PC-relative pointer, 12-byte descriptors.
pointer_cell = (0xb5cc + u32(0xb60c)) & 0xffffffff
table = u32(pointer_cell) - 0x41e00000
assert 0 <= table < len(data)
rows = []
for index in range(4096):
    offset = table + index * 12
    if offset + 12 > len(data):
        break
    flag, address, mask, shift = struct.unpack_from('<IHHB', data, offset)
    if flag != index:
        break
    assert shift < 16 and mask
    if address in (0xa44, 0xf56, 0xf9e):
        rows.append(dict(flag=hex(flag), address=hex(address), mask=hex(mask), shift=shift))
assert rows, 'No validated battery-input descriptors'
# A candidate search, not a control-flow proof: decode at every halfword to
# avoid losing Thumb alignment in the mixed ARM/Thumb/data binary.
flags = {int(row['flag'], 16) for row in rows}
decoder = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
candidates = []
for offset in range(0, 0x35000, 2):
    instruction = next(decoder.disasm(data[offset:offset+4], offset, count=1), None)
    if instruction is None or instruction.mnemonic not in ('movw', 'movs'):
        continue
    if not instruction.op_str.startswith('r0, #'):
        continue
    if int(instruction.op_str.split('#')[1], 0) in flags:
        candidates.append(dict(offset=hex(offset), instruction=instruction.op_str,
                               following=[f'{i.address:x}: {i.mnemonic} {i.op_str}'
                                          for i in decoder.disasm(data[offset:offset+20], offset)]))
report = dict(code_sha256=hashlib.sha256(data).hexdigest(), table_offset=hex(table),
              validated_descriptor_count=index, battery_input_descriptors=rows,
              direct_immediate_candidates=candidates,
              limitations='Candidate scan does not cover computed IDs, indirect calls, ARM code, preloader configuration or hardware thermal behavior. No sensor identity or thermal safety follows from absent references.')
output = root / 'analysis/lk-battery-control-audit.json'
output.write_text(json.dumps(report, indent=2) + '\n')
print(f'Saved {len(rows)} battery-input descriptors and {len(candidates)} direct candidates to {output}')
