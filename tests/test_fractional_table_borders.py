import copy
import unittest
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from bench import common, fixtures, pdf


class FractionalTableBorders(unittest.TestCase):
    def test_size_series_changes_only_the_declared_border_sizes(self):
        records = {c['id'].removeprefix('tables-fractional-border-'): c
                   for c in common.validate_registry()['cases']
                   if c['id'].startswith('tables-fractional-border-')}
        self.assertEqual(len(records), 9)
        w = '{' + fixtures.W + '}'
        baseline = records['quarter']
        for name, size in [('half', '4'), ('one', '8'), ('three-point-control', '24')]:
            case = records[name]
            with ZipFile(common.ROOT / baseline['input']) as left, ZipFile(common.ROOT / case['input']) as right:
                self.assertEqual(left.namelist(), right.namelist())
                for part in left.namelist():
                    if part != 'word/document.xml':
                        self.assertEqual(left.read(part), right.read(part))
                expected, actual = [ET.fromstring(z.read('word/document.xml')) for z in (left, right)]
                borders = actual.findall('.//' + w + 'tcBorders')
                self.assertEqual(len(borders), 2)
                for border in borders:
                    for side in border:
                        self.assertEqual(side.get(w + 'sz'), size)
                        side.set(w + 'sz', '2')
                self.assertEqual(ET.tostring(expected), ET.tostring(actual))
            self.assertEqual(baseline['tokens'], case['tokens'])
            declarations = copy.deepcopy(case['assertions'])
            widths = next(a for a in declarations if a['type'] == 'colored-rule-widths')
            self.assertEqual(widths['widthsPt'], [int(size)/8])
            widths['widthsPt'] = [.25]
            self.assertEqual(baseline['assertions'], declarations)

    def test_paint_contract_rejects_quantization_even_when_text_and_bounds_match(self):
        for case in common.validate_registry()['cases']:
            if not case['id'].startswith('tables-fractional-border-') or case['id'].endswith('no-border-control'):
                continue
            declaration = case['assertions'][0]
            self.assertEqual(declaration['type'], 'color-reference-geometry')
            reference = {'colorRegions': [{'page': 1, 'rgb': [32, 80, 128],
                                           'boundsPt': [72, 72, 313, 98], 'coverage': 100}]}
            self.assertTrue(pdf.color_geometry_pass(declaration, reference, reference))
            for ratio in (0, .75, 1.5, 3):
                candidate = copy.deepcopy(reference)
                candidate['colorRegions'][0]['coverage'] *= ratio
                self.assertFalse(pdf.color_geometry_pass(declaration, reference, candidate), (case['id'], ratio))


if __name__ == '__main__':
    unittest.main()
