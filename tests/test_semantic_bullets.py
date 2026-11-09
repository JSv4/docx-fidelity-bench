import copy
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from bench import pdf, runner
from bench.common import ROOT, read_json
from bench.fixtures import W


class SemanticBullets(unittest.TestCase):
    def setUp(self):
        self.folder = ROOT / 'docs/results/semantic-bullets'
        self.bundle = read_json(self.folder / 'reference-bundle.json')
        self.manifest = read_json(self.folder / 'capture-manifest.json')
        self.records = {c['id']: c for c in read_json(ROOT / 'fixtures/manifest.json')['cases']}

    def test_native_evidence_is_bound_to_manifest_and_inputs(self):
        runner.validate_bundle(self.bundle, self.folder, self.manifest, {'contract': self.bundle['environment']})
        self.assertEqual(4, len(self.manifest['cases']))
        for case in self.manifest['cases']:
            self.assertEqual(self.records[case['id']]['sha256'], case['sha256'])

    def test_controls_change_only_the_first_numbering_glyph_and_font(self):
        for kind in ('symbol', 'courier'):
            records = [self.records['semantic-bullet-' + kind + suffix] for suffix in ('-font-glyph', '-unicode-control')]
            with ZipFile(ROOT / records[0]['input']) as a, ZipFile(ROOT / records[1]['input']) as b:
                self.assertEqual(a.namelist(), b.namelist())
                for name in a.namelist():
                    first, second = a.read(name), b.read(name)
                    if name == 'word/numbering.xml':
                        x, y = ET.fromstring(first), ET.fromstring(second)
                        for tag in ('lvlText', 'rFonts'):
                            before, after = x[0].find(f'.//{{{W}}}{tag}'), y[0].find(f'.//{{{W}}}{tag}')
                            before.attrib.clear()
                            before.attrib.update(after.attrib)
                        first, second = ET.tostring(x), ET.tostring(y)
                    self.assertEqual(first, second, (kind, name))
            self.assertEqual(records[0]['assertions'], records[1]['assertions'])
            self.assertEqual(1, records[0]['tokens']['☐'])
            self.assertEqual(1, records[1]['tokens']['☐'])

    def test_marker_and_checkbox_loss_fail_eligible_references(self):
        for cid, capture in self.bundle['cases'].items():
            case, inspection = self.records[cid], capture['inspection']
            failures = pdf.reference_failures(case, inspection, 'libreoffice')
            if cid == 'semantic-bullet-symbol-font-glyph':
                self.assertFalse(capture['eligible'])
                self.assertEqual({'expected-visible-tokens', 'declared-font-families'}, set(failures))
                self.assertEqual(2, inspection['tokens']['\uf0b7'])
                continue
            self.assertTrue(capture['eligible'])
            self.assertEqual([], failures)
            for token in ('☐', next(t for t in case['tokens'] if t in {'•', '◦', 'o'})):
                changed = copy.deepcopy(inspection)
                changed['tokens'][token] -= 1
                self.assertIn('expected-visible-tokens', pdf.reference_failures(case, changed, 'libreoffice'))


if __name__ == '__main__':
    unittest.main()
