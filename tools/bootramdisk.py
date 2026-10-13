"""Parse newc archives and append reviewed files without rewriting old entries."""
import stat

def entries(data):
    offset = 0
    while True:
        start = offset
        if data[offset:offset+6] != b'070701':
            raise ValueError(f'Invalid newc header at {offset}')
        values = [int(data[offset+6+i*8:offset+14+i*8], 16) for i in range(13)]
        offset += 110
        name_length = values[11]
        if name_length < 1 or offset + name_length > len(data):
            raise ValueError('Invalid archive name length')
        encoded = data[offset:offset+name_length]
        if encoded[-1:] != b'\0':
            raise ValueError('Unterminated archive name')
        name = encoded[:-1].decode()
        offset = (offset + name_length + 3) & ~3
        end = offset + values[6]
        if end > len(data):
            raise ValueError('Truncated archive payload')
        payload = data[offset:end]
        offset = (end + 3) & ~3
        yield name, values, payload, start, offset
        if name == 'TRAILER!!!':
            return

def append_files(data, files):
    existing = list(entries(data))
    names = {row[0]: row for row in existing}
    inode = max(row[1][0] for row in existing) + 1
    archive = bytearray(data[:existing[-1][3]])
    def add(name, mode, payload=b''):
        nonlocal inode
        encoded = name.encode() + b'\0'
        values = [inode, mode, 0, 0, 2 if stat.S_ISDIR(mode) else 1, 0,
                  len(payload), 0, 0, 0, 0, len(encoded), 0]
        archive.extend(b'070701' + ''.join(f'{value:08x}' for value in values).encode())
        archive.extend(encoded)
        archive.extend(b'\0' * (-len(archive) % 4))
        archive.extend(payload)
        archive.extend(b'\0' * (-len(archive) % 4))
        inode += 1
    for name, payload in sorted(files.items()):
        parts = name.split('/')
        if any(part in ('', '.', '..') for part in parts) or name in names:
            raise ValueError(f'Unsafe/duplicate destination {name}')
        for depth in range(1, len(parts)):
            parent = '/'.join(parts[:depth])
            if parent in names:
                if not stat.S_ISDIR(names[parent][1][1]):
                    raise ValueError(f'Parent is not a directory: {parent}')
            else:
                add(parent, stat.S_IFDIR | 0o755)
                names[parent] = (parent, [0, stat.S_IFDIR | 0o755])
        add(name, stat.S_IFREG | 0o755, payload)
        names[name] = (name, [0, stat.S_IFREG | 0o755])
    add('TRAILER!!!', 0)
    archive.extend(b'\0' * (-len(archive) % 512))
    result = bytes(archive)
    # The complete original archive prefix (including hardlink metadata,
    # ownership, device nodes and init) must remain byte-identical.
    assert result[:existing[-1][3]] == data[:existing[-1][3]]
    found = {row[0]: row[2] for row in entries(result)}
    assert all(found[name] == payload for name, payload in files.items())
    return result
