import unittest
from zipfile import ZipFile

from bench.common import ROOT, read_json

FLAGS = ' w:beforeAutospacing="1" w:afterAutospacing="1"'
CONTEXTUAL = '<w:contextualSpacing/>'


class AutomaticSpacingInputs(unittest.TestCase):
    def setUp(self):
        self.cases = {c['id']: c for c in read_json(ROOT / 'fixtures/manifest.json')['cases']}

    def body(self, case_id):
        with ZipFile(ROOT / self.cases[case_id]['input']) as package:
            return package.read('word/document.xml').decode()

    def test_each_automatic_input_differs_from_its_control_only_in_the_flags(self):
        for kind in ('first-paragraph', 'table-cell', 'beside-table'):
            case = 'automatic-spacing-' + kind
            automatic, control = self.body(case), self.body(case + '-control')
            self.assertIn(FLAGS, automatic, kind)
            self.assertNotIn('Autospacing', control, kind)
            self.assertEqual(automatic.replace(FLAGS, ''), control, kind)
            self.assertEqual(self.cases[case]['tokens'], self.cases[case + '-control']['tokens'])

    def test_contextual_pair_moves_only_the_setting(self):
        first, second = self.body('contextual-spacing-absorbs-before'), self.body('contextual-spacing-absorbs-before-control')
        self.assertEqual(first.count(CONTEXTUAL), 1)
        self.assertEqual(second.count(CONTEXTUAL), 1)
        self.assertNotEqual(first, second)
        self.assertEqual(first.replace(CONTEXTUAL, ''), second.replace(CONTEXTUAL, ''))


if __name__ == '__main__':
    unittest.main()
