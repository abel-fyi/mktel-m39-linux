#!/usr/bin/env python3
"""Decode 64 bytes read from physical 0xbffb0000 after source-trace boot."""
import argparse
import json
import struct
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('record', type=Path)
parser.add_argument('--symbols', type=Path, default=Path('build/mt6735-source/System.map'))
args = parser.parse_args()
data = args.record.read_bytes()
if len(data) != 64:
    raise SystemExit('Expected exactly 64 bytes; do not decode a partial RAM read.')
magic, = struct.unpack_from('<Q', data, 0)
version, = struct.unpack_from('<I', data, 40)
if magic != 0x54494e4939334d or version != 1:
    raise SystemExit('No recognized trace: this does not prove the kernel never entered.')
sequence, state, level = struct.unpack_from('<III', data, 8)
address, = struct.unpack_from('<Q', data, 24)
result, = struct.unpack_from('<i', data, 32)
if state not in (0, 1, 2) or (level > 7 and level != 0xffffffff):
    raise SystemExit('Invalid trace state; inspect raw bytes before drawing conclusions.')
symbol = None
for line in args.symbols.read_text().splitlines():
    fields = line.split()
    if len(fields) == 3 and fields[1] in ('t', 'T'):
        value = int(fields[0], 16)
        if value <= address and (symbol is None or value > symbol['address']):
            symbol = {'name': fields[2], 'address': value}
if symbol:
    symbol['offset'] = address - symbol['address']
    symbol['address'] = hex(symbol['address'])
print(json.dumps({'sequence': sequence, 'state': ['initialized', 'entered', 'returned'][state],
                  'level': 'before regular initcalls' if level == 0xffffffff else level,
                  'function_address': hex(address), 'symbol': symbol,
                  'return_value': result if state == 2 else None,
                  'limitations': 'RAM persistence and an untorn record are not guaranteed; absence is inconclusive.'}, indent=2))
