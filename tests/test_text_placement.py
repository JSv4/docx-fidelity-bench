import re
import unittest
from zipfile import ZipFile

from bench.common import ROOT, read_json


def first_line(case):
    return [a['marker'] for a in case['assertions'] if a['rect'][1] == 72]


def text(case):
    with ZipFile(ROOT / case['input']) as package:
        return ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', package.read('word/document.xml').decode()))


class TextPlacementInputs(unittest.TestCase):
    """Each placement holds the Hazel prose of its paragraph-text control in a 501pt or 390pt band;
    only the placement and its Word 2024 line choice differ (Docxodus #1550/#1562)."""

    def setUp(self):
        self.cases = {c['id']: c for c in read_json(ROOT / 'fixtures/manifest.json')['cases']}

    def test_justified_placements_keep_the_condensed_line_and_left_controls_do_not(self):
        control = self.cases['paragraph-text-justify-plain']
        for placement in ('unspaced', 'bold', 'link', 'list', 'cell'):
            case = self.cases['text-placement-justify-both-' + placement]
            self.assertEqual(text(case), text(control), placement)
            self.assertEqual(first_line(case), first_line(control), placement)
            self.assertEqual(first_line(case)[-1], 'landing', placement)
        for placement in ('bold', 'list', 'cell'):
            case = self.cases['text-placement-justify-left-' + placement]
            self.assertEqual(first_line(case), first_line(control)[:-1], placement)

    def test_kerning_follows_only_a_positive_minimum_at_the_text_size(self):
        control = self.cases['paragraph-text-kern-plain']
        for placement, kerned in (('bold', False), ('zero', False), ('at-size', True)):
            case = self.cases['text-placement-kern-left-' + placement]
            self.assertEqual(text(case), text(control), placement)
            self.assertEqual(first_line(case)[-1], 'Water' if kerned else 'Warm', placement)
        with ZipFile(ROOT / self.cases['text-placement-kern-left-zero']['input']) as package:
            self.assertIn('<w:kern w:val="0"/>', package.read('word/document.xml').decode())


if __name__ == '__main__':
    unittest.main()
