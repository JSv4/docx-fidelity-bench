import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from bench import common, fixtures, pdf


class InlineFrames(unittest.TestCase):
    def test_positions_reject_packed_frames_and_lost_table_clearance(self):
        cases = {c['id']: c for c in common.validate_registry()['cases']}
        geometry = {'rotation': 0, 'media': [0, 0, 612, 792], 'crop': [0, 0, 612, 792]}
        for cid, label, valid, invalid in [
            ('body-separated', 'AsterAfter', [270, 96, 319, 108.2], [468, 96, 517, 108.2]),
            ('body-separated', 'AsterFrame2', [90, 96, 150, 108.2], [270, 84, 330, 96.2]),
            ('header-table-clearance', 'AsterBody0', [24, 88.5, 80, 100.7], [24, 28.5, 80, 40.7]),
            ('header-table-clearance', 'AsterBody1', [24, 112.5, 80, 124.7], [24, 52.5, 80, 64.7]),
        ]:
            case = dict(cases['frames-inline-' + cid])
            case['assertions'] = [a for a in case['assertions'] if a['type'] == 'marker-region' and a['marker'] == label]
            self.assertEqual(len(case['assertions']), 1)
            reference = {'geometry': [geometry], 'fonts': ['LiberationSerif'], 'tokens': case['tokens'],
                         'words': [{'text': label, 'page': 1, 'rect': valid}]}
            for rect, expected in [(valid, True), (invalid, False)]:
                with self.subTest(case=cid, label=label, rect=rect):
                    candidate = {**reference, 'words': [{'text': label, 'page': 1, 'rect': rect}]}
                    self.assertEqual(pdf.correctness(case, reference, candidate)[-1]['passed'], expected)

    def test_grouped_and_separated_sources_retain_every_original_label(self):
        cases = [c for c in common.validate_registry()['cases'] if c['id'].startswith('frames-inline-')]
        self.assertEqual(len(cases), 30)
        w = '{' + fixtures.W + '}'
        for case in cases:
            with self.subTest(case=case['id']), ZipFile(common.ROOT / case['input']) as package:
                normal = 'normal-control' in case['id']
                part = 'word/header1.xml' if '-header-' in case['id'] else 'word/footer1.xml' if '-footer-' in case['id'] else 'word/document.xml'
                source = ET.fromstring(package.read(part))
                properties = source.findall('.//' + w + 'framePr')
                self.assertEqual(len(properties), 0 if normal else 6 if 'overhang' in case['id'] or 'table-clearance' in case['id'] else 2)
                if properties:
                    self.assertTrue(all(p.attrib == properties[0].attrib for p in properties))
                if '-separated' in case['id']:
                    paragraphs = source.findall('.//' + w + 'p')
                    labels = [''.join(t.text or '' for t in p.iter(w + 't')) for p in paragraphs]
                    self.assertLess(labels.index('AsterFrame1'), labels.index('AsterBetween'))
                    self.assertLess(labels.index('AsterBetween'), labels.index('AsterFrame2'))
                self.assertNotIn('clippedTokens', case)
                self.assertNotIn('pdfTextNormalization', case)

    def test_both_frame_lines_have_independent_overlap_and_page_bounds(self):
        for case in common.validate_registry()['cases']:
            if not case['id'].startswith('frames-inline-') or 'table-clearance' in case['id']:
                continue
            with self.subTest(case=case['id']):
                assertions = case['assertions']
                pairs = [a['markers'] for a in assertions if a['type'] == 'non-overlapping-markers']
                if 'floating-control' in case['id']:
                    self.assertEqual(pairs, [])
                    continue
                for label in ['AsterFrame1', 'AsterFrame2']:
                    self.assertIn([label, 'AsterAfter'], pairs)
                bounded = {a['marker']: a for a in assertions if a['type'] == 'marker-region'}
                for pair in pairs:
                    for label in pair:
                        self.assertIn(label, bounded)
                        self.assertIn(bounded[label]['page'], [1, 2])
                if 'page-end' in case['id']:
                    self.assertEqual([bounded[label]['page'] for label in ['AsterFrame1', 'AsterFrame2', 'AsterAfter']], [1, 1, 2])
                if 'header-overhang' in case['id']:
                    for i in range(1, 7):
                        self.assertIn([f'AsterFrame{i}', 'AsterBody'], pairs)


if __name__ == '__main__':
    unittest.main()
