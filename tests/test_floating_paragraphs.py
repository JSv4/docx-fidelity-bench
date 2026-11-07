import importlib.util
import sys
import unittest
from pathlib import Path
from bench.common import ROOT, validate_registry


class FloatingParagraphContract(unittest.TestCase):
    def test_native_calibrated_line_and_picture_boundaries_remain_explicit(self):
        cases = [c for c in validate_registry()['cases'] if c['id'].startswith('floating-paragraph-')]
        self.assertEqual(len(cases), 12)
        for case in cases:
            self.assertEqual(sum(n for text, n in case['tokens'].items() if text.startswith('Chive') and not text.startswith(('ChiveLead', 'ChiveComplete'))), 78)
            self.assertEqual(case['tokens']['recorded.'], 78)
            labels = [a for a in case['assertions'] if a['type'] == 'marker-region']
            self.assertTrue(all(isinstance(a['page'], int) and a['tolerancePt'] == .0001 for a in labels))
            if 'square' in case['id'] or 'tight' in case['id']:
                self.assertEqual(next(a for a in labels if a['marker'] == 'Chive001')['rect'][0], 84)
                self.assertEqual(next(a for a in labels if a['marker'] == 'Chive004')['rect'][2], 83)

    def test_retained_observations_reject_ownership_loss_and_missing_exclusions(self):
        folder = ROOT / 'docs/results/floating-paragraphs'
        sys.path.insert(0, str(folder))
        try:
            spec = importlib.util.spec_from_file_location('floating_mutations', folder / 'Mutations.py')
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            records = module.verify()
            self.assertTrue(all(r['rejected'] for r in records))
            self.assertTrue(any(r['mutation'] == 'one-of-two-same-page-pictures-lost' for r in records))
        finally:
            sys.path.remove(str(folder))
