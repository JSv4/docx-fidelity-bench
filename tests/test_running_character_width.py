import importlib.util
import sys
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from bench.common import ROOT, validate_registry


class RunningCharacterWidthContract(unittest.TestCase):
    def test_stories_wrap_unchanged_body_paragraphs(self):
        cases = [c for c in validate_registry()['cases'] if c['id'].startswith('running-character-width-')]
        self.assertEqual(len(cases), 6)
        w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        for case in cases:
            owner, percent = case['id'].split('-')[-2:]
            with ZipFile(ROOT / case['input']) as story, ZipFile(ROOT / f'fixtures/character-width-12-{percent}.docx') as control:
                self.assertEqual(story.read('word/styles.xml'), control.read('word/styles.xml'))
                original = ET.fromstring(control.read('word/document.xml')).find(w + 'body/' + w + 'p')
                paragraph = ET.fromstring(story.read(f'word/{owner}1.xml')).find(w + 'p')
                self.assertEqual(ET.tostring(paragraph), ET.tostring(original))
            with ZipFile(ROOT / case['input']) as changed, ZipFile(ROOT / f'fixtures/running-character-width-{owner}-100.docx') as natural:
                self.assertEqual(set(changed.namelist()), set(natural.namelist()))
                for path in changed.namelist():
                    if path == f'word/{owner}1.xml':
                        actual = ET.fromstring(changed.read(path))
                        actual.find(f'{w}p/{w}r/{w}rPr/{w}w').set(w + 'val','100')
                        self.assertEqual(ET.tostring(actual), ET.tostring(ET.fromstring(natural.read(path))))
                    else:
                        self.assertEqual(changed.read(path), natural.read(path))

    def test_retained_observations_reject_scale_position_and_ownership_damage(self):
        folder = ROOT / 'docs/results/running-character-width'
        sys.path.insert(0, str(folder))
        previous = sys.modules.pop('WidthChecks', None)
        try:
            spec = importlib.util.spec_from_file_location('running_width_mutations', folder / 'Mutations.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            records = module.verify()
            self.assertEqual(len(records), 96)
            self.assertTrue(all(r['rejected'] for r in records))
        finally:
            sys.path.remove(str(folder))
            sys.modules.pop('WidthChecks', None)
            if previous is not None:
                sys.modules['WidthChecks'] = previous
