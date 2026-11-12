"""Original font/line boundary probes. Outputs are diagnostics, never fidelity scores."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from bench.fixtures import FONT, W, package, para, run


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate(folder):
    folder.mkdir(parents=True, exist_ok=False)
    cases = []
    for font_size, line_size, face in [(10, 12, 'regular'), (12, 12, 'regular'), (12, 14, 'regular'),
                                       (14, 14, 'bold-italic'), (10, 12, 'italic'), (16, 16, 'regular')]:
        identifier = f'clip-boundary-{font_size}-{line_size}-{face}'
        height = line_size * 3
        labels = ['QuartzEdgeOne', 'QuartzEdgeTwo', 'QuartzEdgeThree', 'QuartzEdgeTail']
        paragraphs = ''
        for index, label in enumerate(labels):
            properties = (f'<w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}"/><w:sz w:val="{font_size * 2}"/>'
                          + ('<w:b/>' if 'bold' in face else '') + ('<w:i/>' if 'italic' in face else '')
                          + ('<w:color w:val="FF0000"/>' if index == 3 else ''))
            paragraphs += para(props=f'<w:spacing w:before="0" w:after="0" w:line="{line_size * 20}" w:lineRule="exact"/>',
                               runs=run(label, properties))
        box = ('<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
               f'<wp:extent cx="2159000" cy="{height * 12700}"/><wp:docPr id="91" name="Quartz boundary probe"/>'
               '<a:graphic><a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
               '<wps:wsp><wps:cNvSpPr txBox="1"/><wps:spPr><a:xfrm><a:off x="0" y="0"/>'
               f'<a:ext cx="2159000" cy="{height * 12700}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
               '<a:noFill/><a:ln><a:noFill/></a:ln></wps:spPr><wps:txbx><w:txbxContent>' + paragraphs
               + '</w:txbxContent></wps:txbx><wps:bodyPr lIns="0" tIns="0" rIns="0" bIns="0">'
               '<a:noAutofit/></wps:bodyPr></wps:wsp></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>')
        paper = ('<w:sectPr><w:pgSz w:w="9200" w:h="9600"/><w:pgMar w:top="800" w:right="1000" '
                 'w:bottom="800" w:left="1000" w:header="200" w:footer="200"/></w:sectPr>')
        styles = (f'<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="{FONT}" '
                  f'w:hAnsi="{FONT}"/><w:sz w:val="24"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>'
                  '<w:spacing w:before="0" w:after="0"/></w:pPr></w:pPrDefault></w:docDefaults></w:styles>')
        path = folder / (identifier + '.docx')
        package(path, para(runs=box) + para('QuartzEdgeReceipt'), final_section=paper, styles_xml=styles,
                namespaces_extra=' xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"')
        cases.append({'id': identifier, 'version': 1, 'category': 'paragraphs',
                      'description': 'Original colored boundary-ink probe; full source inventory deliberately retains the clipped tail',
                      'input': str(path.relative_to(ROOT)), 'sha256': digest(path),
                      'generator': {'path': str(Path(__file__).resolve().relative_to(ROOT)), 'sha256': digest(Path(__file__))},
                      'rights': {'author': 'John Scrudato IV', 'license': 'MIT', 'origin': 'Original probe script',
                                 'assets': 'Literal OOXML and text only; no embedded font program'},
                      'profile': {'review': 'final', 'comments': 'hidden'}, 'fonts': [FONT],
                      'tokens': dict(Counter(labels + ['QuartzEdgeReceipt'])), 'assertions': []})
    manifest = {'schema': 1, 'suite': {'id': 'clip-boundary-probes-v1', 'version': 1, 'cases': [case['id'] for case in cases]}, 'cases': cases}
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(folder / 'manifest.json')


def font_bounds(environment):
    result = []
    for name, declaration in environment['contract']['fonts'].items():
        paths = [Path(folder) / name for folder in environment['fontDirectories'] if (Path(folder) / name).is_file()]
        if len(paths) != 1 or digest(paths[0]) != declaration['sha256']:
            raise ValueError('Changed or ambiguous font: ' + name)
        data = paths[0].read_bytes()
        table_count = struct.unpack_from('>H', data, 4)[0]
        tables = {}
        for index in range(table_count):
            tag, checksum, offset, length = struct.unpack_from('>4sIII', data, 12 + index * 16)
            if offset + length > len(data):
                raise ValueError('Invalid font table bounds')
            tables[tag] = data[offset:offset + length]
        head, hhea = tables[b'head'], tables[b'hhea']
        if struct.unpack_from('>I', head, 12)[0] != 0x5F0F3CF5:
            raise ValueError('Unknown TrueType head table')
        units = struct.unpack_from('>H', head, 18)[0]
        x_min, y_min, x_max, y_max = struct.unpack_from('>hhhh', head, 36)
        ascent, descent, gap = struct.unpack_from('>hhh', hhea, 4)
        result.append({'file': name, **declaration, 'unitsPerEm': units,
                       'globalGlyphBounds': [x_min, y_min, x_max, y_max],
                       'globalTopEm': y_max / units, 'hheaAscent': ascent, 'hheaDescent': descent,
                       'hheaLineGap': gap, 'belowTwoEmTopBound': y_max < 2 * units})
    return result


def inspect(reference, environment, destination):
    from PIL import Image
    bundle = json.loads((reference / 'bundle.json').read_text())
    record = {'schema': 1, 'status': 'unscored-boundary-ink-probes', 'probeToolSha256': digest(Path(__file__)),
              'referenceBundleSha256': digest(reference / 'bundle.json'), 'fontBounds': font_bounds(environment), 'cases': [],
              'note': 'Only the fourth line is red. Any PNG pixel with red greater than both green and blue is counted. Full source inventories remain unchanged; these intentionally clipped probes are not fidelity references.'}
    for identifier, item in bundle['cases'].items():
        pdf = reference / item['pdf']
        prefix = reference / identifier / 'boundary-600dpi'
        subprocess.run(['pdftoppm', '-f', '1', '-singlefile', '-r', '600', '-png', str(pdf), str(prefix)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        raster = prefix.with_suffix('.png')
        with Image.open(raster) as image:
            colors = image.convert('RGB').getcolors(maxcolors=1_000_000)
            if colors is None:
                raise ValueError('Unexpectedly complex probe raster')
            red_pixels = sum(count for count, (red, green, blue) in colors if red > green and red > blue)
        record['cases'].append({'id': identifier, 'inputSha256': item['inputSha256'], 'pdfSha256': digest(pdf),
                                'referenceEligible': item['eligible'], 'referenceFailures': item['ineligibleChecks'],
                                'rasterSha256': digest(raster), 'rasterDpi': 600, 'redPixelCount': red_pixels})
    destination.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    if sys.argv[1] == 'generate':
        generate((ROOT / sys.argv[2]).resolve())
    elif sys.argv[1] == 'inspect':
        inspect(Path(sys.argv[2]), json.loads(Path(sys.argv[3]).read_text()), Path(sys.argv[4]))
    else:
        raise SystemExit('Usage: ProbeClipBoundary.py generate OUTPUT | inspect REFERENCES ENVIRONMENT OUTPUT_JSON')
