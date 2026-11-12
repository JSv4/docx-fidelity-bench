import importlib.util
import sys
import unittest

from bench.common import ROOT, validate_registry


class LateWrappedParagraphContract(unittest.TestCase):
    def test_destination_wrapping_includes_text_before_the_anchor(self):
        cases = [c for c in validate_registry()['cases'] if c['id'].startswith('late-wrapped-paragraph-')]
        self.assertEqual(len(cases), 8)
        for case in cases:
            self.assertEqual(sum(n for text, n in case['tokens'].items()
                                 if text.startswith('Chive') and text[5:].isdigit()), 78)
        case = next(c for c in cases if c['id'].endswith('square-after-30'))
        labels = {a['marker']: a for a in case['assertions'] if a['type'] == 'marker-region'}
        # The picture follows line30, but line30 already shares its destination-page exclusion.
        self.assertEqual((labels['Chive030']['page'], labels['Chive030']['rect'][0]), (2, 84))
        self.assertEqual(labels['Chive033']['rect'][2], 83)

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
