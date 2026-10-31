import copy
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from bench import common, fixtures, pdf


class RubyGuides(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = [c for c in common.validate_registry()['cases'] if c['id'].startswith('ruby-')]

    def test_original_pairs_keep_complete_token_inventories(self):
        self.assertEqual(len(self.cases), 5)
        cases = {c['id']: c for c in self.cases}
        for name in ('center', 'multiple-base', 'long'):
            case = cases['ruby-' + name]
            with ZipFile(common.ROOT / case['input']) as package:
                root = ET.fromstring(package.read('word/document.xml'))
                guide = root.find('.//{' + fixtures.W + '}rt')
                base = root.find('.//{' + fixtures.W + '}rubyBase')
                self.assertEqual(''.join(guide.itertext()), 'needle')
                self.assertEqual(''.join(base.itertext()), 'LARCH')
            control = cases['ruby-long-plain-control' if name == 'long' else 'ruby-plain-control']
            self.assertEqual(case['tokens'], control['tokens'])

    def test_contract_rejects_lost_reading_duplicate_base_and_wrong_raise(self):
        case = next(c for c in self.cases if c['id'] == 'ruby-center')
        good = {'geometry': [{'rotation': 0, 'media': [0, 0, 300, 240], 'crop': [0, 0, 300, 240]}],
                'tokens': case['tokens'], 'fonts': ['LiberationSerif'], 'words': [
                    {'text': 'LARCH', 'page': 1, 'rect': [96, 37, 134, 50]},
                    {'text': 'needle', 'page': 1, 'rect': [107, 30, 123, 37]}]}
        self.assertTrue(all(c['passed'] for c in pdf.correctness(case, good, good)))
        for defect in ('missing', 'duplicate', 'raise'):
            changed = copy.deepcopy(good)
            if defect == 'missing':
                del changed['tokens']['needle']
                changed['words'].pop()
            elif defect == 'duplicate':
                changed['tokens']['LARCH'] += 1
            else:
                changed['words'][1]['rect'] = [107, 34, 123, 41]
            self.assertTrue(any(not c['passed'] for c in pdf.correctness(case, good, changed)), defect)

        for guarded in (c for c in self.cases if not c['id'].endswith('control')):
            reference = copy.deepcopy(good)
            reference['tokens'] = guarded['tokens']
            self.assertTrue(all(c['passed'] for c in pdf.correctness(guarded, reference, reference)))
            shifted = copy.deepcopy(reference)
            shifted['words'][1]['rect'] = [107, 54, 123, 61]
            self.assertTrue(any(not c['passed'] for c in pdf.correctness(guarded, reference, shifted)), guarded['id'])


if __name__ == '__main__':
    unittest.main()
