import unittest
from zipfile import ZipFile

from bench import pdf
from bench.common import ROOT, read_json
from bench.fixtures import complex_field

PAGE_BREAK = '<w:r><w:br w:type="page"/></w:r>'
LINE_BREAK_RUN = '<w:r><w:br/></w:r>'


class SplitDirectionMarkInputs(unittest.TestCase):
    def setUp(self):
        self.cases = {c['id']: c for c in read_json(ROOT / 'fixtures/manifest.json')['cases']}

    def parts(self, case_id):
        with ZipFile(ROOT / self.cases[case_id]['input']) as package:
            return {name: package.read(name) for name in package.namelist()}

    def assert_pair(self, case_id, trigger_removed):
        case, control = self.parts(case_id), self.parts(case_id + '-control')
        self.assertEqual(case.keys(), control.keys())
        for name in case:
            if name != 'word/document.xml':
                self.assertEqual(case[name], control[name], name)
        self.assertEqual(trigger_removed(case['word/document.xml'].decode()), control['word/document.xml'].decode())
        self.assertEqual(self.cases[case_id]['tokens'], self.cases[case_id + '-control']['tokens'])

    def test_each_page_split_differs_from_its_control_only_by_the_page_break(self):
        # The right-to-left control puts a line break in the page break's place, so each label keeps its own line.
        for direction, instead in (('ltr', ''), ('rtl', LINE_BREAK_RUN)):
            case_id = 'direction-mark-page-split-' + direction
            document = self.parts(case_id)['word/document.xml'].decode()
            self.assertEqual(document.count(PAGE_BREAK), 1)
            self.assert_pair(case_id, lambda text: text.replace(PAGE_BREAK, instead))
            pages = lambda name: [a['page'] for a in self.cases[name]['assertions']]
            self.assertEqual(pages(case_id)[-1], 2)
            self.assertEqual(set(pages(case_id)[:-1] + pages(case_id + '-control')), {1})

    def test_the_left_to_right_mark_comes_from_a_line_break_before_the_page_break(self):
        document = self.parts('direction-mark-page-split-ltr')['word/document.xml'].decode()
        self.assertNotIn('w:bidi', document)
        self.assertLess(document.index('<w:br/>'), document.index(PAGE_BREAK))

    def test_the_right_to_left_paragraph_holds_only_right_to_left_text_runs(self):
        for case_id, line_breaks in (('direction-mark-page-split-rtl', 0), ('direction-mark-page-split-rtl-control', 1)):
            document = self.parts(case_id)['word/document.xml'].decode()
            self.assertEqual(document.count('<w:pPr><w:bidi/></w:pPr>'), 1)
            self.assertEqual(document.count('<w:t '), 2)
            self.assertEqual(document.count('<w:rPr><w:szCs w:val="22"/><w:rtl/></w:rPr><w:t '), 2)
            self.assertEqual(document.count(LINE_BREAK_RUN), line_breaks)

    def test_the_field_link_differs_from_its_control_only_by_the_field(self):
        field = complex_field(' HYPERLINK "https://example.com/" ', '|').split('|')
        document = self.parts('direction-mark-field-link-line-break')['word/document.xml'].decode()
        self.assertEqual(document.count('<w:hyperlink r:id="rTamariskLink">'), 1)
        self.assertLess(document.index(field[0]), document.index('<w:hyperlink'))
        self.assertLess(document.index('</w:hyperlink>'), document.index(field[1]))
        self.assert_pair('direction-mark-field-link-line-break',
                         lambda text: text.replace(field[0], '').replace(field[1], ''))

    def test_invisible_marks_pass_and_their_names_printed_as_text_fail(self):
        def words(*texts):
            items = ''.join(f'<word xMin="{i}" yMin="1" xMax="{i + 1}" yMax="2">{t}</word>' for i, t in enumerate(texts))
            found = pdf.bbox_words(f'<html xmlns="http://www.w3.org/1999/xhtml"><body><doc><page>{items}'
                                   '</page></doc></body></html>')
            return {'tokens': {w['text']: 1 for w in found if w['text']}}
        ltr = self.cases['direction-mark-page-split-ltr']
        rtl = self.cases['direction-mark-page-split-rtl']
        self.assertTrue(pdf.inventory_check(words('TamariskLanding', '\u200eTamariskBeacon', 'TamariskCove'), ltr))
        self.assertTrue(pdf.inventory_check(words('\u200f\u200fTamariskQuay\u200f', '\u200fTamariskMole\u200f'), rtl))
        self.assertFalse(pdf.inventory_check(words('TamariskLanding', '#x200eTamariskBeacon', 'TamariskCove'), ltr))
        self.assertFalse(pdf.inventory_check(words('TamariskLanding', '#x200e', 'TamariskBeacon', 'TamariskCove'), ltr))
        self.assertFalse(pdf.inventory_check(words('#x200fTamariskQuay#x200f', 'TamariskMole'), rtl))


if __name__ == '__main__':
    unittest.main()
