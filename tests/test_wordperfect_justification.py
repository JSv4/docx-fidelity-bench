import copy
import importlib.util
import sys
import unittest
from collections import Counter
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from bench.common import ROOT, validate_registry
from bench.pdf import reference_failures


class WordPerfectJustificationContract(unittest.TestCase):
    def test_retained_checks_reject_corrupted_captures(self):
        folder = ROOT / 'docs/results/wordperfect-justification'
        sys.path.insert(0, str(folder)); previous = sys.modules.pop('WidthChecks', None)
        try:
            spec = importlib.util.spec_from_file_location('wordperfect_mutations', folder / 'Mutations.py')
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            records = module.verify()
            self.assertEqual(len(records), 43)
            self.assertTrue(all(r['rejected'] and r['failures'] for r in records))
            self.assertEqual(sum(r['mutation'] == 'shrunken-glyphs' for r in records), 4)
        finally:
            sys.path.remove(str(folder)); sys.modules.pop('WidthChecks', None)
            if previous is not None: sys.modules['WidthChecks'] = previous

    def test_explicit_policy_and_every_source_token_are_pinned(self):
        w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        cases = [c for c in validate_registry()['cases'] if c['id'].startswith('wordperfect-justification-')]
        self.assertEqual(len(cases), 4)
        for case in cases:
            with ZipFile(ROOT / case['input']) as package:
                source = ET.fromstring(package.read('word/document.xml'))
                settings = ET.fromstring(package.read('word/settings.xml'))
            control = case['id'].endswith('control')
            self.assertEqual(settings.find('.//' + w + 'wpJustification').get(w + 'val'), '0' if control else None)
            self.assertEqual(Counter(' '.join(e.text or '' for e in source.iter(w + 't')).split()), Counter(case['tokens']))
            self.assertTrue(case['pdfCompanion']['exactInventory'])
            self.assertEqual(case['pdfCompanion']['requiredTokens'], case['tokens'])
            self.assertEqual(len(case['assertions']), sum(case['tokens'].values()))
            first_sixth = next(a for a in case['assertions'] if a['marker'].endswith('0006X'))
            self.assertEqual(first_sixth['rect'][1], 72 + (2320 / 2048 * 12 if control else 0))

    def test_glyph_shrink_cannot_pass_by_retaining_the_correct_line_and_left_edge(self):
        spec = importlib.util.spec_from_file_location('wordperfect_widths',
            ROOT / 'docs/results/wordperfect-justification/WidthChecks.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for case in validate_registry()['cases']:
            if not case['id'].startswith('wordperfect-justification-'):
                continue
            ideal = dict(geometry=[dict(media=[0, 0, 612, 792], crop=[0, 0, 612, 792], rotation=0)]
                         * max(a['page'] for a in case['assertions']), fonts=['LiberationMono'], tokens=case['tokens'],
                rawTokens=[a['marker'] for a in case['assertions']],
                words=[dict(text=a['marker'], page=a['page'], rect=a['rect'][:]) for a in case['assertions']])
            self.assertFalse(reference_failures(case, ideal))
            self.assertTrue(all(c['passed'] for c in module.checks(case, ideal)))
            for dimension in (2, 3):
                damaged = copy.deepcopy(ideal)
                for word in damaged['words']:
                    rect = word['rect']
                    rect[dimension] = rect[dimension - 2] + (rect[dimension] - rect[dimension - 2]) * .95
                # Existing containment checks alone accept this incorrect print.
                self.assertFalse(reference_failures(case, damaged))
                self.assertFalse(all(c['passed'] for c in module.checks(case, damaged)))
            damaged = copy.deepcopy(ideal)
            damaged['rawTokens'][0], damaged['rawTokens'][1] = damaged['rawTokens'][1], damaged['rawTokens'][0]
            self.assertFalse(all(c['passed'] for c in module.checks(case, damaged)))
