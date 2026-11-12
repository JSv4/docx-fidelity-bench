import unittest
from zipfile import ZipFile

from bench.common import ROOT, read_json


class SectionMarkInputs(unittest.TestCase):
    def setUp(self):
        self.cases = {c['id']: c for c in read_json(ROOT / 'fixtures/manifest.json')['cases']}

    def document(self, case_id):
        with ZipFile(ROOT / self.cases[case_id]['input']) as package:
            return package.read('word/document.xml').decode()

    def test_each_line_case_moves_the_break_from_its_line_to_an_empty_mark(self):
        for name in ('continuous', 'spaced', 'two-column'):
            case, control = self.document('section-mark-' + name), self.document('section-mark-' + name + '-control')
            self.assertEqual(case.count('<w:sectPr>'), control.count('<w:sectPr>'), name)
            self.assertEqual((case.count('</w:sectPr></w:pPr></w:p>'), control.count('</w:sectPr></w:pPr></w:p>')), (1, 0), name)
        for name in ('continuous', 'spaced', 'two-column', 'after-page-break'):
            self.assertEqual(self.cases['section-mark-' + name]['tokens'],
                             self.cases['section-mark-' + name + '-control']['tokens'])

    def test_the_page_break_case_differs_from_its_control_only_by_the_breaks(self):
        brk = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
        case = self.document('section-mark-after-page-break')
        self.assertEqual(case.count(brk), 2)
        self.assertEqual(case.replace(brk, ''), self.document('section-mark-after-page-break-control'))


if __name__ == '__main__':
    unittest.main()
