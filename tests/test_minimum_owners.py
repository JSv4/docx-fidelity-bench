import importlib.util
import sys
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from bench.common import ROOT, validate_registry


class MinimumOwnerContract(unittest.TestCase):
    def test_pairs_differ_only_in_the_declared_line_spacing(self):
        cases = [c for c in validate_registry()['cases'] if c['id'].startswith('minimum-owner-')]
        self.assertEqual(len(cases), 12)
        w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        for owner in ('cell', 'list-tab', 'list-nothing'):
            for count in (18, 64):
                prefix = f'minimum-owner-{owner}-{count}'
                with ZipFile(ROOT / f'fixtures/{prefix}-natural.docx') as natural, ZipFile(ROOT / f'fixtures/{prefix}-minimum.docx') as minimum:
                    self.assertEqual(set(natural.namelist()), set(minimum.namelist()))
                    for path in natural.namelist():
                        if path != 'word/document.xml':
                            self.assertEqual(natural.read(path), minimum.read(path))
                    document = ET.fromstring(minimum.read('word/document.xml'))
                    paragraphs = document.findall('.//' + w + 'p')
                    self.assertEqual(len(paragraphs), 1)
                    paragraph = paragraphs[0]
                    self.assertEqual(''.join(t.text or '' for t in paragraph.iter(w + 't')).split(),
                                     [f'Rue{i:03d}' for i in range(1, count + 1)])
                    spacing = paragraph.find(f'{w}pPr/{w}spacing')
                    self.assertEqual((spacing.get(w + 'lineRule'), spacing.get(w + 'line')), ('atLeast', '320'))
                    spacing.set(w + 'lineRule', 'auto'); spacing.set(w + 'line', '240')
                    self.assertEqual(ET.tostring(document), ET.tostring(ET.fromstring(natural.read('word/document.xml'))))
                    if owner == 'cell':
                        self.assertIsNotNone(document.find(f'{w}body/{w}tbl/{w}tr/{w}tc/{w}p'))
                    else:
                        self.assertIsNotNone(paragraph.find(f'{w}pPr/{w}numPr'))
                        numbering = ET.fromstring(natural.read('word/numbering.xml'))
                        self.assertEqual(numbering.find(f'{w}abstractNum/{w}lvl/{w}suff').get(w + 'val'), owner.removeprefix('list-'))

    def test_retained_observations_reject_spacing_geometry_number_and_inventory_damage(self):
        folder = ROOT / 'docs/results/minimum-owners'
        sys.path.insert(0, str(folder))
        previous = sys.modules.pop('Checks', None)
        try:
            spec = importlib.util.spec_from_file_location('minimum_owner_mutations', folder / 'Mutations.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            records = module.verify()
            self.assertEqual(len(records), 186)
            self.assertTrue(all(r['rejected'] for r in records))
        finally:
            sys.path.remove(str(folder))
            sys.modules.pop('Checks', None)
            if previous is not None:
                sys.modules['Checks'] = previous
