import importlib.util
import sys
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from bench.common import ROOT, validate_registry


class FootnoteCharacterWidthContract(unittest.TestCase):
    def test_percentage_is_the_only_note_input_difference(self):
        w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        def normalize(data):
            source = ET.fromstring(data)
            width = source.find(f'{w}footnote[@{w}id="1"]/{w}p/{w}r/{w}rPr/{w}w')
            del width.attrib[w + 'val']
            return ET.tostring(source)
        for count in (12,400):
            with ZipFile(ROOT / f'fixtures/footnote-character-width-{count}-100.docx') as control:
                for percent in (80,150):
                    with ZipFile(ROOT / f'fixtures/footnote-character-width-{count}-{percent}.docx') as changed:
                        self.assertEqual(set(control.namelist()),set(changed.namelist()))
                        for path in control.namelist():
                            if path == 'word/footnotes.xml':
                                self.assertEqual(normalize(control.read(path)),normalize(changed.read(path)))
                            else: self.assertEqual(control.read(path),changed.read(path))

    def test_footer_control_changes_only_preceding_body_paragraphs(self):
        w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        with ZipFile(ROOT / 'fixtures/story-drift-footer-0.docx') as control, ZipFile(ROOT / 'fixtures/story-drift-footer-40.docx') as changed:
            self.assertEqual(set(control.namelist()),set(changed.namelist()))
            for path in control.namelist():
                if path != 'word/document.xml': self.assertEqual(control.read(path),changed.read(path))
            original = ET.fromstring(control.read('word/document.xml')).find(w + 'body')
            expanded = ET.fromstring(changed.read('word/document.xml')).find(w + 'body')
            self.assertEqual(len(original),2);self.assertEqual(len(expanded),42)
            self.assertEqual(ET.tostring(original[0]),ET.tostring(expanded[0]))
            self.assertEqual(ET.tostring(original[-1]),ET.tostring(expanded[-1]))

    def test_retained_contract_and_damage_probes(self):
        folder = ROOT / 'docs/results/footnote-character-width'
        sys.path.insert(0,str(folder));previous = sys.modules.pop('WidthChecks',None)
        try:
            spec = importlib.util.spec_from_file_location('footnote_width_mutations',folder / 'Mutations.py')
            module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            records = module.verify()
            self.assertEqual(len(records),124)
            self.assertTrue(all(r['rejected'] and r['newFailures'] for r in records))
            self.assertEqual(sum(r['mutation'] == 'note-above-body-band' for r in records),1)
            self.assertEqual(sum(r['mutation'] == 'independent-story-drift' for r in records),2)
            cases = [c for c in validate_registry()['cases'] if c['id'].startswith(('footnote-character-width-','story-drift-footer-'))]
            self.assertEqual(len(cases),8)
            for case in cases: module.source(case)
        finally:
            sys.path.remove(str(folder));sys.modules.pop('WidthChecks',None)
            if previous is not None: sys.modules['WidthChecks'] = previous
