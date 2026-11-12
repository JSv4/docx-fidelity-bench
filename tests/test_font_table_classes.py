import copy
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from bench import pdf, runner
from bench.common import ROOT, read_json
from bench.fixtures import W


class FontTableClasses(unittest.TestCase):
    def setUp(self):
        self.folder = ROOT / 'docs/results/font-table-classes'
        self.manifest = read_json(self.folder / 'capture-manifest.json')
        self.bundle = read_json(self.folder / 'reference-bundle.json')
        self.records = {c['id']: c for c in read_json(ROOT / 'fixtures/manifest.json')['cases']}

    def test_capture_is_bound_to_exact_manifest_and_current_inputs(self):
        runner.validate_bundle(self.bundle, self.folder, self.manifest, {'contract': self.bundle['environment']})
        self.assertEqual(8, len(self.manifest['cases']))
        for case in self.manifest['cases']:
            self.assertEqual(self.records[case['id']]['sha256'], case['sha256'])

    def test_controls_change_only_the_requested_family(self):
        for kind in ('sans', 'serif', 'mono', 'panose-mono'):
            declared = self.records['font-table-' + kind + '-declared']
            control = self.records['font-table-' + kind + '-named-control']
            with ZipFile(ROOT / declared['input']) as a, ZipFile(ROOT / control['input']) as b:
                self.assertEqual(a.namelist(), b.namelist())
                for name in a.namelist():
                    first, second = a.read(name), b.read(name)
                    if name == 'word/styles.xml':
                        alias = ET.fromstring(a.read('word/fontTable.xml'))[0].get(f'{{{W}}}name')
                        first = first.replace(alias.encode(), declared['fonts'][0].encode())
                    self.assertEqual(first, second, (kind, name))
            self.assertEqual(declared['tokens'], control['tokens'])
            self.assertEqual(declared['assertions'], control['assertions'])

    def test_native_choices_remain_ineligible_and_controls_reject_wrong_fonts(self):
        for cid, capture in self.bundle['cases'].items():
            with self.subTest(case=cid):
                case, inspection = self.records[cid], capture['inspection']
                failures = pdf.reference_failures(case, inspection, 'libreoffice')
                if cid.endswith('-declared'):
                    self.assertFalse(capture['eligible'])
                    self.assertIn('assertion-required-font-family', failures)
                    expected = 'NotoSans-Regular' if cid == 'font-table-sans-declared' else 'NotoSerif-Regular'
                    self.assertEqual([expected], inspection['fonts'])
                else:
                    self.assertTrue(capture['eligible'])
                    self.assertEqual([], failures)
                    changed = copy.deepcopy(inspection)
                    changed['fonts'] = ['NotoSerif-Regular']
                    self.assertIn('assertion-required-font-family', pdf.reference_failures(case, changed, 'libreoffice'))


if __name__ == '__main__':
    unittest.main()
