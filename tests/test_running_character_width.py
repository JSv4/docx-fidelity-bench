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

    def test_unrelated_body_picture_is_the_only_control_difference(self):
        w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        cases = [c for c in validate_registry()['cases'] if c['id'].startswith('running-story-picture-')]
        self.assertEqual(len(cases), 4)
        for owner in ('header', 'footer'):
            with ZipFile(ROOT / f'fixtures/running-story-picture-{owner}-image.docx') as image, ZipFile(ROOT / f'fixtures/running-story-picture-{owner}-control.docx') as control:
                self.assertEqual(image.read(f'word/{owner}1.xml'), control.read(f'word/{owner}1.xml'))
                self.assertEqual(image.read('word/styles.xml'), control.read('word/styles.xml'))
                paragraph = ET.fromstring(image.read(f'word/{owner}1.xml')).find(w + 'p')
                self.assertEqual(paragraph.find(f'{w}pPr/{w}jc').get(w + 'val'), 'both')
                body = ET.fromstring(image.read('word/document.xml'))
                children = body.find(w + 'body')
                self.assertIsNotNone(children[-2].find(f'{w}r/{w}drawing'))
                children.remove(children[-2])
                self.assertEqual(ET.tostring(body), ET.tostring(ET.fromstring(control.read('word/document.xml'))))

    def test_retained_observations_reject_scale_position_and_ownership_damage(self):
        self.verify_mutations('running-character-width', 96)
        self.verify_mutations('running-story-picture', 68)

    def verify_mutations(self, name, count):
        folder = ROOT / 'docs/results' / name
        sys.path.insert(0, str(folder))
        previous = sys.modules.pop('WidthChecks', None)
        try:
            spec = importlib.util.spec_from_file_location('running_width_mutations', folder / 'Mutations.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            records = module.verify()
            self.assertEqual(len(records), count)
            self.assertTrue(all(r['rejected'] for r in records))
        finally:
            sys.path.remove(str(folder))
            sys.modules.pop('WidthChecks', None)
            if previous is not None:
                sys.modules['WidthChecks'] = previous
