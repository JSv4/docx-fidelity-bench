import unittest
from collections import Counter
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
        for key in ('tokens', 'fonts', 'profile'):
            self.assertEqual(self.cases[case_id][key], self.cases[case_id + '-control'][key], key)
        # The pair checks the same things; only the page of a label after a removed page break differs.
        positions = lambda name: [a for a in self.cases[name]['assertions'] if a['type'] != 'marker-region']
        self.assertEqual(positions(case_id), positions(case_id + '-control'))

    def test_each_page_split_differs_from_its_control_only_by_the_page_break(self):
        # The right-to-left control puts a line break in the page break's place, so each label keeps its own line.
        for direction, instead in (('ltr', ''), ('rtl', LINE_BREAK_RUN)):
            case_id = 'direction-mark-page-split-' + direction
            document = self.parts(case_id)['word/document.xml'].decode()
            self.assertEqual(document.count(PAGE_BREAK), 1)
            self.assert_pair(case_id, lambda text: text.replace(PAGE_BREAK, instead))
            pages = lambda name: [a['page'] for a in self.cases[name]['assertions'] if a['type'] == 'marker-region']
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
        self.assertEqual([document.count(part) for part in field], [1, 1])
        self.assertLess(document.index(field[0]), document.index('<w:hyperlink'))
        self.assertLess(document.index('</w:hyperlink>'), document.index(field[1]))
        self.assert_pair('direction-mark-field-link-line-break',
                         lambda text: text.replace(field[0], '').replace(field[1], ''))

    def test_invisible_marks_pass_and_their_names_printed_as_text_fail(self):
        def words(*texts):
            items = ''.join(f'<word xMin="{i}" yMin="1" xMax="{i + 1}" yMax="2">{t}</word>' for i, t in enumerate(texts))
            found = pdf.bbox_words(f'<html xmlns="http://www.w3.org/1999/xhtml"><body><doc><page>{items}'
                                   '</page></doc></body></html>')
            return {'tokens': dict(Counter(w['text'] for w in found if w['text']))}
        ltr = self.cases['direction-mark-page-split-ltr']
        rtl = self.cases['direction-mark-page-split-rtl']
        self.assertTrue(pdf.inventory_check(words('TamariskLanding', '\u200eTamariskBeacon', 'TamariskCove'), ltr))
        self.assertTrue(pdf.inventory_check(words('\u200f\u200fTamariskQuay\u200f', '\u200fTamariskMole\u200f'), rtl))
        self.assertFalse(pdf.inventory_check(words('TamariskLanding', '#x200eTamariskBeacon', 'TamariskCove'), ltr))
        self.assertFalse(pdf.inventory_check(words('TamariskLanding', '#x200e', 'TamariskBeacon', 'TamariskCove'), ltr))
        self.assertFalse(pdf.inventory_check(words('#x200fTamariskQuay#x200f', 'TamariskMole'), rtl))
        # A duplicated label is a wrong inventory too.
        self.assertFalse(pdf.inventory_check(words('TamariskLanding', 'TamariskBeacon', 'TamariskBeacon', 'TamariskCove'), ltr))

    def test_the_word_after_the_line_break_must_start_where_the_reference_starts_it(self):
        geometry = {'media': [0, 0, 612, 792], 'crop': [0, 0, 612, 792], 'rotation': 0, 'userUnit': 1}
        def info(*words):
            found = [{'text': text, 'page': 1, 'rect': [x, y, x + 90, y + 12]} for text, x, y in words]
            return {'geometry': [geometry], 'words': found, 'tokens': dict(Counter(w['text'] for w in found)),
                    'fonts': ['LiberationSerif']}
        def failed(case_id, candidate, reference):
            return [c['name'] for c in pdf.correctness(self.cases[case_id], reference, candidate) if not c['passed']]
        for case_id in ('direction-mark-field-link-line-break', 'direction-mark-field-link-line-break-control'):
            reference = info(('TamariskChart', 72, 72.25), ('TamariskSounding', 72, 84.9))
            self.assertEqual(failed(case_id, reference, reference), [])
            self.assertEqual(failed(case_id, info(('TamariskChart', 71.9, 72.5), ('TamariskSounding', 71.9, 84.9)), reference), [])
            # The line break lost: both words on one line, every word still printed on its page.
            self.assertEqual(failed(case_id, info(('TamariskChart', 72, 72.25), ('TamariskSounding', 165, 72.25)), reference),
                             ['assertion-marker-reference-position'])
            self.assertEqual(failed(case_id, info(('TamariskChart', 72, 72.25), ('TamariskSounding', 72, 85.5)), reference),
                             ['assertion-marker-reference-position'])
        ltr = 'direction-mark-page-split-ltr'
        reference = info(('TamariskLanding', 72, 72.25), ('TamariskBeacon', 72, 84.9))
        reference['geometry'] *= 2
        reference['words'].append({'text': 'TamariskCove', 'page': 2, 'rect': [72, 72, 160, 84]})
        reference['tokens']['TamariskCove'] = 1
        joined = {**reference, 'words': [dict(w) for w in reference['words']]}
        joined['words'][1]['rect'] = [170, 72.25, 260, 84.25]
        self.assertEqual(failed(ltr, reference, reference), [])
        self.assertEqual(failed(ltr, joined, reference), ['assertion-marker-reference-position'])


if __name__ == '__main__':
    unittest.main()
