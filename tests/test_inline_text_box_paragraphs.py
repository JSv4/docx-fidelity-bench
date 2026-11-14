import copy
import re
import unittest
from zipfile import ZipFile

from bench import pdf
from bench.common import ROOT, validate_registry


class InlineTextBoxParagraphContract(unittest.TestCase):
    """Docxodus #1735: a paragraph longer than a page around an inline legacy text box."""

    @classmethod
    def setUpClass(cls):
        records = {c['id']: c for c in validate_registry()['cases']}
        cls.case, cls.control = records['inline-text-box-paragraph'], records['inline-text-box-paragraph-control']

    def test_pair_differs_only_by_the_box_run(self):
        with ZipFile(ROOT / self.case['input']) as boxed, ZipFile(ROOT / self.control['input']) as plain:
            self.assertEqual(boxed.namelist(), plain.namelist())
            for name in boxed.namelist():
                if name != 'word/document.xml':
                    self.assertEqual(boxed.read(name), plain.read(name))
            document = boxed.read('word/document.xml').decode()
            box = re.findall(r'<w:r><w:pict>.*?</w:pict></w:r>', document)
            self.assertEqual(len(box), 1)
            self.assertIn('type="#_x0000_t202" style="width:150pt;height:60pt"', box[0])
            self.assertNotIn('position:absolute', box[0])
            self.assertIn('Bryony055 recorded.</w:t></w:r>' + box[0], document)
            self.assertEqual(document.replace(box[0], ''), plain.read('word/document.xml').decode())
        tokens = dict(self.case['tokens'])
        self.assertEqual(tokens.pop('BryonyGauge'), 1)
        self.assertEqual(tokens, self.control['tokens'])

    def test_box_line_ends_page_two_for_any_line_over_54_and_up_to_72pt(self):
        regions = {a['marker']: a for a in self.case['assertions'] if a['type'] == 'marker-region'}
        pages = [sum(1 for a in regions.values() if a['page'] == n and a['marker'] != 'BryonyGauge') for n in (1, 2, 3)]
        self.assertEqual(pages, [29, 26, 24])
        control = [sum(1 for a in self.control['assertions'] if a['page'] == n) for n in (1, 2, 3)]
        self.assertEqual(control, [29, 29, 21])
        top, body_bottom = 36 + 25 * 18, 558
        self.assertEqual(regions['Bryony055']['rect'][1:4:2], [top - 1, body_bottom + 1])
        # A box line of h points fits below line 25 while h <= 72, and leaves no room for another
        # 18pt line once h > 54, so the reference's and a top-aligned box's line break alike.
        self.assertEqual((body_bottom - top - 18, body_bottom - top), (54, 72))
        self.assertEqual((regions['Bryony056']['page'], regions['Bryony056']['rect'][1]), (3, 35))
        fill = next(a for a in self.case['assertions'] if a['type'] == 'color-geometry')
        self.assertEqual((fill['page'], fill['boundsPt'][1::2]), (2, [top, top + 60]))

    def test_split_box_and_unsplit_paragraph_observations_fail(self):
        def observation():
            words = []
            for a in self.case['assertions']:
                if a['type'] != 'marker-region': continue
                l, t, r, b = a['rect']
                # Text at the bottom of each line, as the reference sets it; the box text near its top.
                y = t + {'Bryony055': 51, 'BryonyGauge': 11}.get(a['marker'], 7)
                words.append({'text': a['marker'], 'page': a['page'], 'rect': [l + 1, y, l + 44, y + 12.2]})
            fill = next(a for a in self.case['assertions'] if a['type'] == 'color-geometry')
            return {'geometry': [], 'words': words, 'tokens': {}, 'fonts': [],
                    'colorRegions': [{'page': 2, 'rgb': fill['rgb'], 'boundsPt': list(fill['boundsPt']), 'coverage': fill['coverage'] * .97}]}

        def failed(info):
            return [c['declaration'].get('marker', c['declaration']['type'])
                    for c in pdf.correctness(self.case, info, info) if c['name'].startswith('assertion-') and not c['passed']]

        self.assertEqual(failed(observation()), [])
        unsplit = observation()
        for word in unsplit['words']:
            if word['page'] == 3: word['page'] = 1
        self.assertIn('Bryony056', failed(unsplit))
        pushed = observation()
        next(w for w in pushed['words'] if w['text'] == 'Bryony055')['page'] = 3
        self.assertEqual(failed(pushed), ['Bryony055'])
        split = observation()
        split['colorRegions'][0]['boundsPt'][3] = 522
        split['colorRegions'][0]['coverage'] *= 36 / 60
        self.assertEqual(failed(split), ['color-geometry'])
        shifted = observation()
        next(w for w in shifted['words'] if w['text'] == 'Bryony030')['rect'][1::2] = [61, 73.2]
        self.assertEqual(failed(shifted), ['Bryony030'])


if __name__ == '__main__':
    unittest.main()
