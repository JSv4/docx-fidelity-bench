import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from bench.common import ROOT, read_json
from bench.fixtures import W


class TextSpanInputs(unittest.TestCase):
    def test_fragmented_and_whole_inputs_have_identical_text_and_distinct_run_shapes(self):
        cases = {c['id']: c for c in read_json(ROOT / 'fixtures/manifest.json')['cases']}
        shapes = []
        for name in ('text-span-fragmented', 'text-span-whole-control'):
            case = cases[name]
            with ZipFile(ROOT / case['input']) as package:
                doc = ET.fromstring(package.read('word/document.xml'))
            paragraphs = doc.findall(f'.//{{{W}}}body/{{{W}}}p')
            self.assertEqual(['CelandineHarbor', 'CelandineLedger', 'CelandineBold CelandineItalic'],
                [''.join(p.itertext()) for p in paragraphs])
            self.assertEqual(dict.fromkeys('CelandineHarbor CelandineLedger CelandineBold CelandineItalic'.split(), 1), case['tokens'])
            shapes.append([len(p.findall(f'{{{W}}}r')) for p in paragraphs])
        self.assertEqual([[2, 2, 2], [1, 1, 2]], shapes)


if __name__ == '__main__':
    unittest.main()
