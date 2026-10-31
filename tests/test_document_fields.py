import copy
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from bench import common, fixtures, pdf


class DocumentFieldFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {case['id']: case for case in common.validate_registry()['cases']}
        cls.w = '{' + fixtures.W + '}'

    def test_property_pair_changes_only_six_field_caches(self):
        cases = [self.cases['fields-property-' + suffix] for suffix in ('uncached', 'cached-control')]
        self.assertEqual(cases[0]['tokens'], cases[1]['tokens'])
        self.assertEqual(cases[0]['assertions'], cases[1]['assertions'])
        title = 'Juniper equipment register'
        with ZipFile(common.ROOT / cases[0]['input']) as empty, ZipFile(common.ROOT / cases[1]['input']) as cached:
            self.assertEqual(empty.namelist(), cached.namelist())
            self.assertEqual(ET.fromstring(empty.read('docProps/core.xml')).find(
                '{http://purl.org/dc/elements/1.1/}title').text, title)
            changed = 0
            for name in empty.namelist():
                if name not in ('word/document.xml', 'word/header1.xml', 'word/footer1.xml'):
                    self.assertEqual(empty.read(name), cached.read(name))
                    continue
                first, second = [ET.fromstring(package.read(name)) for package in (empty, cached)]
                self.assertEqual(len(first.findall('.//' + self.w + 'fldSimple')), 1)
                self.assertEqual(len(first.findall('.//' + self.w + 'instrText')), 1)
                for text in second.findall('.//' + self.w + 't'):
                    if text.text == title:
                        text.text = None
                        changed += 1
                self.assertEqual(ET.tostring(first), ET.tostring(second))
            self.assertEqual(changed, 6)

    def test_running_pair_keeps_body_and_style_identity_and_control_stays_constant(self):
        ids = ['fields-styleref-' + suffix for suffix in ('uncached', 'stale-cache', 'constant-control')]
        with ZipFile(common.ROOT / self.cases[ids[0]]['input']) as empty, ZipFile(common.ROOT / self.cases[ids[1]]['input']) as stale:
            for name in empty.namelist():
                if name not in ('word/header1.xml', 'word/footer1.xml'):
                    self.assertEqual(empty.read(name), stale.read(name))
            for name in ('word/header1.xml', 'word/footer1.xml'):
                root = ET.fromstring(stale.read(name))
                for text in root.findall('.//' + self.w + 't'):
                    if text.text == 'ALDER SECTION':
                        text.text = None
                self.assertEqual(ET.tostring(root), ET.tostring(ET.fromstring(empty.read(name))))
        for case_id in ids:
            case = self.cases[case_id]
            constant = case_id.endswith('constant-control')
            self.assertEqual(case['tokens']['ALDER'], 2 if constant else 1)
            self.assertEqual(case['tokens'].get('BIRCH', 0), 0 if constant else 1)
            self.assertEqual(case['tokens']['SECTION'], 6)
            self.assertEqual(len(case['assertions']), 6)
            self.assertEqual({a['page'] for a in case['assertions']}, {1, 2})
            with ZipFile(common.ROOT / case['input']) as package:
                body = ET.fromstring(package.read('word/document.xml'))
                headings = [p.find(self.w + 'r/' + self.w + 't').text for p in body.findall('.//' + self.w + 'p')
                            if p.find(self.w + 'pPr/' + self.w + 'pStyle') is not None]
                self.assertEqual(headings, ['ALDER SECTION', 'ALDER SECTION' if constant else 'BIRCH SECTION'])

    def test_running_contract_rejects_wrong_page_copies_even_when_total_tokens_match(self):
        case = self.cases['fields-styleref-stale-cache']
        geometry = {'rotation': 0, 'media': [0, 0, 612, 792], 'crop': [0, 0, 612, 792]}
        words = [{'text': text, 'page': page, 'rect': [100, y, 200, y + 11]}
                 for page, text, y in [(1, 'Running1:ALDER', 36), (1, 'JuniperFirstBody', 86), (1, 'Closing1:ALDER', 742),
                                       (2, 'Running2:BIRCH', 36), (2, 'JuniperSecondBody', 86), (2, 'Closing2:BIRCH', 742)]]
        info = {'geometry': [geometry, geometry], 'tokens': case['tokens'],
                'fonts': ['LiberationSerif'], 'words': words}
        self.assertTrue(all(c['passed'] for c in pdf.correctness(case, info, info)))
        swapped = copy.deepcopy(info)
        swapped['words'][0]['page'], swapped['words'][3]['page'] = 2, 1
        checks = pdf.correctness(case, info, swapped)
        self.assertTrue(next(c for c in checks if c['name'] == 'expected-visible-tokens')['passed'])
        self.assertTrue(any(not c['passed'] for c in checks if c['name'] == 'assertion-marker-region'))

    def test_wrapping_pair_requires_the_body_tail_on_page_three(self):
        pair = [self.cases['fields-styleref-wrapping' + suffix] for suffix in ('', '-control')]
        self.assertEqual(pair[0]['assertions'], pair[1]['assertions'])
        with ZipFile(common.ROOT / pair[0]['input']) as short, ZipFile(common.ROOT / pair[1]['input']) as long:
            for name in short.namelist():
                if name not in ('word/document.xml', 'word/header1.xml'):
                    self.assertEqual(short.read(name), long.read(name))
            first, control = [ET.fromstring(package.read('word/document.xml')) for package in (short, long)]
            first.find('.//' + self.w + 'p/' + self.w + 'r/' + self.w + 't').text = control.find(
                './/' + self.w + 'p/' + self.w + 'r/' + self.w + 't').text
            self.assertEqual(ET.tostring(first), ET.tostring(control))
        case = pair[0]
        geometry = {'rotation': 0, 'media': [0, 0, 228, 240], 'crop': [0, 0, 228, 240]}
        info = {'geometry': [geometry] * 3, 'tokens': case['tokens'], 'fonts': ['LiberationSerif'], 'words': [
            {'text': 'Running2:JUNIPER', 'page': 2, 'rect': [24, 7, 120, 19]},
            {'text': 'Running3:JUNIPER', 'page': 3, 'rect': [24, 7, 120, 19]},
            {'text': 'JuniperWrapTail', 'page': 3, 'rect': [24, 80, 120, 92]},
        ]}
        self.assertTrue(all(c['passed'] for c in pdf.correctness(case, info, info)))
        late = copy.deepcopy(info)
        late['words'][-1]['page'] = 2
        self.assertTrue(any(not c['passed'] for c in pdf.correctness(case, info, late)))


if __name__ == '__main__':
    unittest.main()
