import unittest
from zipfile import ZipFile

from bench.common import ROOT, read_json


class FractionalMeasureInputs(unittest.TestCase):
    def test_each_input_differs_from_its_control_only_in_the_fractional_value(self):
        cases = {c['id']: c for c in read_json(ROOT / 'fixtures/manifest.json')['cases']}
        pairs = {'paragraph-border': ('w:sz="4.5"', 'w:sz="4"'), 'table-border': ('w:sz="4.5"', 'w:sz="4"'),
                 'cell-border': ('w:sz="4.5"', 'w:sz="4"'), 'grid-column': ('w:w="4000.5"', 'w:w="4000"')}
        for kind, (fractional, whole) in pairs.items():
            documents = []
            for suffix in ('', '-control'):
                case = cases['fractional-measure-' + kind + suffix]
                with ZipFile(ROOT / case['input']) as package:
                    documents.append(package.read('word/document.xml').decode())
            self.assertIn(fractional, documents[0], kind)
            self.assertNotIn(fractional, documents[1], kind)
            self.assertEqual(documents[0].replace(fractional, whole), documents[1], kind)
            self.assertEqual(cases['fractional-measure-' + kind]['tokens'],
                             cases['fractional-measure-' + kind + '-control']['tokens'])


if __name__ == '__main__':
    unittest.main()
