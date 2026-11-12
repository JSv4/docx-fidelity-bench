import copy
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from bench import common, fixtures, pdf


class VmlGroupTextboxes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = [c for c in common.validate_registry()['cases'] if c['id'].startswith('textboxes-vml-')]

    def test_every_source_contains_both_independent_stories_and_the_control_contract(self):
        self.assertEqual(len(self.cases), 6)
        for case in self.cases:
            with self.subTest(case=case['id']), ZipFile(common.ROOT / case['input']) as package:
                part = 'word/header1.xml' if '-header-' in case['id'] else 'word/document.xml'
                root = ET.fromstring(package.read(part))
                contents = root.findall('.//{' + fixtures.W + '}txbxContent')
                self.assertEqual([''.join(c.itertext()) for c in contents], ['MapleNorthLabel', 'MapleSouthLabel'])
                groups = root.findall('.//{urn:schemas-microsoft-com:vml}group')
                self.assertEqual(len(groups), 0 if case['id'].endswith('control') else 2 if case['id'].endswith('nested') else 1)
                self.assertEqual(case['tokens'], self.cases[0]['tokens'])
                self.assertEqual(case['assertions'][:2], self.cases[0]['assertions'][:2])
                self.assertEqual(len(case['assertions']), 2 if not groups else 4)

    def test_contract_rejects_omitted_or_misplaced_second_story(self):
        case = self.cases[0]
        geometry = {'rotation': 0, 'media': [0, 0, 612, 792], 'crop': [0, 0, 612, 792]}
        good = {'geometry': [geometry], 'tokens': case['tokens'], 'fonts': ['LiberationSerif'], 'words': [
            {'text': 'MapleRegisterReceipt', 'page': 1, 'rect': [72, 72, 180, 85]},
            {'text': 'MapleNorthLabel', 'page': 1, 'rect': [84, 132, 170, 145]},
            {'text': 'MapleSouthLabel', 'page': 1, 'rect': [228, 180, 314, 193]},
        ]}
        self.assertTrue(all(c['passed'] for c in pdf.correctness(case, good, good)))
        missing = copy.deepcopy(good)
        del missing['tokens']['MapleSouthLabel']
        missing['words'].pop()
        self.assertTrue(any(not c['passed'] for c in pdf.correctness(case, good, missing)))
        misplaced = copy.deepcopy(good)
        misplaced['words'][-1]['rect'] = [84, 132, 170, 145]
        checks = pdf.correctness(case, good, misplaced)
        self.assertTrue(next(c for c in checks if c['name'] == 'expected-visible-tokens')['passed'])
        self.assertTrue(any(not c['passed'] for c in checks if c['name'] == 'assertion-marker-region'))
        # Ignoring the nested origin (10,20) shifts the second label by (4.8,9.6) pt.
        # Either axis alone must fail despite preserving tokens and the broad page region.
        for candidate in (c for c in self.cases if not c['id'].endswith('control')):
            for dx, dy in [(4.8, 0), (0, 9.6)]:
                shifted = copy.deepcopy(good)
                shifted['words'][-1]['rect'] = [228 + dx, 180 + dy, 314 + dx, 193 + dy]
                checks = pdf.correctness(candidate, good, shifted)
                self.assertTrue(any(not c['passed'] for c in checks if c['name'] == 'assertion-marker-reference-position'))


if __name__ == '__main__':
    unittest.main()
