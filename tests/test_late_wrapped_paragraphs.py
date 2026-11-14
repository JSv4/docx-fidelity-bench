import importlib.util
import sys
import unittest

from bench.common import ROOT, validate_registry


class LateWrappedParagraphContract(unittest.TestCase):
    def test_destination_wrapping_includes_text_before_the_anchor(self):
        cases = [c for c in validate_registry()['cases'] if c['id'].startswith('late-wrapped-paragraph-')]
        self.assertEqual(len(cases), 9)
        for case in cases:
            self.assertEqual(sum(n for text, n in case['tokens'].items()
                                 if text.startswith('Chive') and text[5:].isdigit()), 78)
        case = next(c for c in cases if c['id'].endswith('square-after-30'))
        labels = {a['marker']: a for a in case['assertions'] if a['type'] == 'marker-region'}
        # The picture follows line30, but line30 already shares its destination-page exclusion.
        self.assertEqual((labels['Chive030']['page'], labels['Chive030']['rect'][0]), (2, 84))
        self.assertEqual(labels['Chive033']['rect'][2], 83)

    def test_offset_picture_differs_from_its_control_only_in_horizontal_placement(self):
        # Docxodus #1736: a column offset that puts the tile's right edge on the column's right
        # edge, beside the right-aligned control, so both expect the same lines and picture.
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile
        records = {c['id']: c for c in validate_registry()['cases']}
        control, offset = (records['late-wrapped-paragraph-square-' + kind + '-after-30'] for kind in ('right', 'offset'))
        wp = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
        with ZipFile(ROOT / control['input']) as aligned, ZipFile(ROOT / offset['input']) as placed:
            self.assertEqual(aligned.namelist(), placed.namelist())
            for name in aligned.namelist():
                if name != 'word/document.xml':
                    self.assertEqual(aligned.read(name), placed.read(name))
            documents = [ET.fromstring(archive.read('word/document.xml')) for archive in (aligned, placed)]
            horizontal = [document.find('.//' + wp + 'positionH') for document in documents]
            self.assertEqual([h.attrib for h in horizontal], [{'relativeFrom': 'column'}] * 2)
            self.assertEqual([child.tag for child in horizontal[0]], [wp + 'align'])
            self.assertEqual(horizontal[0][0].text, 'right')
            self.assertEqual([(child.tag, child.text) for child in horizontal[1]], [(wp + 'posOffset', str(312 * 12700))])
            extent = documents[1].find('.//' + wp + 'extent')
            self.assertEqual(312 * 12700 + int(extent.get('cx')), 360 * 12700)
            for h in horizontal: h.clear(); h.set('relativeFrom', 'column')
            self.assertEqual(ET.tostring(documents[0]), ET.tostring(documents[1]))
        self.assertEqual(control['tokens'], offset['tokens'])
        self.assertEqual(control['assertions'], offset['assertions'])
        self.assertEqual(control['pdfCompanion'], offset['pdfCompanion'])

    def test_frozen_evidence_rejects_missing_or_misplaced_content(self):
        folder = ROOT / 'docs/results/late-wrapped-paragraphs'
        sys.path.insert(0, str(folder))
        try:
            spec = importlib.util.spec_from_file_location('late_picture_mutations', folder / 'Mutations.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            records = module.verify()
            self.assertTrue(all(record['rejected'] for record in records))
            self.assertTrue(any(record['case'].endswith('square-after-30')
                                and record['mutation'] == 'removed-wrap-exclusion' for record in records))
            self.assertTrue(any(record['case'].endswith('square-right-after-30')
                                and record['mutation'] == 'shifted-picture' for record in records))
        finally:
            sys.path.remove(str(folder))
