import importlib.util
import sys
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from bench.common import ROOT, validate_registry


class MinimumStoryContract(unittest.TestCase):
    def test_pairs_differ_only_in_story_line_spacing(self):
        cases = [c for c in validate_registry()['cases'] if c['id'].startswith('minimum-story-')]
        self.assertEqual(len(cases), 16)
        w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        for owner in ('header', 'footer', 'footnote', 'endnote'):
            for length in ('short', 'continued'):
                prefix = f'minimum-story-{owner}-{length}'
                part = f'word/{owner}{"1" if owner in ("header", "footer") else "s"}.xml'
                with ZipFile(ROOT / f'fixtures/{prefix}-natural.docx') as natural, ZipFile(ROOT / f'fixtures/{prefix}-minimum.docx') as minimum:
                    self.assertEqual(set(natural.namelist()), set(minimum.namelist()))
                    for path in natural.namelist():
                        if path != part:
                            self.assertEqual(natural.read(path), minimum.read(path))
                    story = ET.fromstring(minimum.read(part))
                    paragraphs = [p for p in story.iter(w + 'p') if any('Poppy' in (t.text or '') for t in p.iter(w + 't'))]
                    self.assertEqual(len(paragraphs), 1)
                    spacing = paragraphs[0].find(f'{w}pPr/{w}spacing')
                    self.assertEqual((spacing.get(w + 'lineRule'), spacing.get(w + 'line')), ('atLeast', '320'))
                    spacing.set(w + 'lineRule', 'auto'); spacing.set(w + 'line', '240')
                    self.assertEqual(ET.tostring(story), ET.tostring(ET.fromstring(natural.read(part))))
                    if owner in ('footnote', 'endnote'):
                        self.assertIsNone(paragraphs[0].find('.//' + w + owner + 'Ref'))

    def test_retained_observations_reject_story_and_control_damage(self):
        folder = ROOT / 'docs/results/minimum-stories'
        sys.path.insert(0, str(folder))
        previous = sys.modules.pop('Checks', None)
        try:
            spec = importlib.util.spec_from_file_location('minimum_story_mutations', folder / 'Mutations.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            records = module.verify()
            self.assertEqual(len(records), 240)
            self.assertTrue(all(r['rejected'] for r in records))
        finally:
            sys.path.remove(str(folder))
            sys.modules.pop('Checks', None)
            if previous is not None:
                sys.modules['Checks'] = previous
