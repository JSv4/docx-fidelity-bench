"""Original geometric Liatris fonts for collection discovery, using only the stdlib.

Every visible glyph is an authored chevron; Unicode and metrics remain real so
PDF text, font identity and line placement can be measured independently.
No installed font, renderer fixture or third-party outline is imported.
"""
from pathlib import Path
import struct
import tempfile
from .common import ROOT, digest


def u16(*values):
    return struct.pack('>' + 'H' * len(values), *values)


def s16(*values):
    return struct.pack('>' + 'h' * len(values), *values)


def u32(*values):
    return struct.pack('>' + 'I' * len(values), *values)


def padded(data, size=4):
    return data + bytes(-len(data) % size)


def checksum(data):
    value = padded(data)
    return sum(struct.unpack('>' + 'I' * (len(value) // 4), value)) & 0xffffffff


def font(family):
    # A compact original four-point chevron, repeated for A-Z. Advances vary by
    # character to make an ordinary fallback distinguishable in geometry.
    glyphs, locations, metrics = bytearray(), [], bytearray()
    for index in range(28):
        locations.append(len(glyphs) // 2)
        width = 300 if index == 1 else 540 + (index % 3) * 50
        metrics.extend(u16(width) + s16(0 if index == 1 else 40))
        if index == 1:
            continue
        points = [(40, 0), (width - 40, 320), (40, 640), (150, 320)]
        previous_x = previous_y = 0
        xs, ys = [], []
        for x, y in points:
            xs.append(x - previous_x); ys.append(y - previous_y)
            previous_x, previous_y = x, y
        shape = s16(1, 40, 0, width - 40, 640) + u16(3, 0) + bytes([1] * 4) + s16(*xs, *ys)
        glyphs.extend(padded(shape, 2))
    locations.append(len(glyphs) // 2)
    postscript = family.replace(' ', '') + '-Regular'
    names = {1: family, 2: 'Regular', 3: 'Liatris original benchmark ' + family,
             4: family + ' Regular', 5: 'Version 1.000', 6: postscript,
             13: 'MIT; original geometric outlines by John Scrudato IV'}
    records, strings = bytearray(), bytearray()
    for number, text in names.items():
        encoded = text.encode('utf-16-be')
        records.extend(u16(3, 1, 0x409, number, len(encoded), len(strings)))
        strings.extend(encoded)
    cmap4 = (u16(4, 40, 0, 6, 4, 1, 2) + u16(32, 90, 0xffff, 0, 32, 65, 0xffff)
             + s16(-31, -63, 1) + u16(0, 0, 0))
    tables = {
        'head': u32(0x10000, 0x10000, 0, 0x5f0f3cf5) + u16(3, 1000)
                + struct.pack('>QQ', 2082844800, 2082844800) + s16(0, 0, 600, 640)
                + u16(0, 8) + s16(2, 0, 0),
        'hhea': u32(0x10000) + s16(800, -200, 0) + u16(640)
                + s16(40, 40, 600, 1, 0, 0, 0, 0, 0, 0, 0) + u16(28),
        'maxp': u32(0x10000) + u16(28, 4, 1, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0),
        'OS/2': u16(0) + s16(590) + u16(400, 5, 0)
                + s16(650, 600, 0, 75, 650, 600, 0, 350, 50, 300, 0)
                + bytes([2, 0, 5, 3, 0, 0, 0, 0, 0, 0]) + u32(1, 0, 0, 0)
                + b'LIAT' + u16(0x40, 32, 90) + s16(800, -200, 0) + u16(800, 200),
        'cmap': u16(0, 1, 3, 1) + u32(12) + cmap4,
        'glyf': bytes(glyphs), 'loca': u16(*locations), 'hmtx': bytes(metrics),
        'name': u16(0, len(names), 6 + len(records)) + records + strings,
        'post': u32(0x30000, 0) + s16(-100, 50) + u32(0, 0, 0, 0, 0),
    }
    count = len(tables)
    power = 2 ** (count.bit_length() - 1)
    header = u32(0x10000) + u16(count, power * 16, power.bit_length() - 1, count * 16 - power * 16)
    directory, payload = bytearray(), bytearray()
    offsets = {}
    for tag, data in sorted(tables.items()):
        offsets[tag] = len(header) + count * 16 + len(payload)
        directory.extend(tag.encode() + u32(checksum(data), offsets[tag], len(data)))
        payload.extend(padded(data))
    result = bytearray(header + directory + payload)
    struct.pack_into('>I', result, offsets['head'] + 8, (0xb1b0afba - checksum(result)) & 0xffffffff)
    return bytes(result)


def collection(families):
    header_size = 12 + 4 * len(families)
    offsets, faces = [], bytearray()
    for family in families:
        offset = header_size + len(faces)
        offsets.append(offset)
        face = bytearray(font(family))
        count = struct.unpack_from('>H', face, 4)[0]
        for index in range(count):
            record = 12 + index * 16 + 8
            original = struct.unpack_from('>I', face, record)[0]
            struct.pack_into('>I', face, record, original + offset)
        faces.extend(padded(face))
    return b'ttcf' + u32(0x10000, len(families), *offsets) + faces


def generate(root=ROOT):
    folder = Path(root) / 'fixtures/collection-fonts'
    folder.mkdir(parents=True, exist_ok=True)
    programs = {'liatris-plain.ttf': font('Liatris Plain'),
                'liatris-ttc.ttc': collection(['Liatris TTC', 'Liatris TTC Spare']),
                'liatris-otc.otc': collection(['Liatris OTC', 'Liatris OTC Spare'])}
    for name, data in programs.items():
        (folder / name).write_bytes(data)
    return {name: digest(folder / name) for name in programs}


def validate(root=ROOT):
    with tempfile.TemporaryDirectory() as temporary:
        expected = generate(temporary)
    actual = {path.name: digest(path) for path in (Path(root) / 'fixtures/collection-fonts').iterdir() if path.is_file()}
    if actual != expected:
        raise ValueError('Original collection font programs differ from their generator')
    return expected


if __name__ == '__main__':
    generate()
