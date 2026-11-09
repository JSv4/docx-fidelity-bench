"""Frozen independent EMF observations must detect lost, clipped or displaced paint."""
import copy
import gzip
import json
import unittest
from bench import common, pdf


class EmfImageContract(unittest.TestCase):
    def test_retained_geometry_rejects_content_loss_and_clipping(self):
        folder = common.ROOT / 'docs/results/emf-images'
        evidence = json.loads((folder / 'evidence.json').read_text())
        cases = [c for c in common.validate_registry()['cases'] if c['id'].startswith('images-emf-')]
        self.assertEqual(len(cases), 8)
        for case in cases:
            cid = case['id']
            with gzip.open(folder / (cid + '.json.gz'), 'rt') as stream:
                facts = json.load(stream)
            ref, candidate = facts['reference'], facts['candidate']
            self.assertTrue(all(c['passed'] for c in pdf.correctness(case, ref, candidate)), cid)
            self.assertEqual(facts['direct']['words'], ref['words'])
            self.assertEqual(facts['production']['source']['rawPackageBytesDigest'], case['sha256'])
            self.assertEqual(facts['nativeMain']['emfPlaceholders'], 0 if cid.endswith('png-control') else 1)
            for mutation in ('removed', 'shifted', 'coverage'):
                changed = copy.deepcopy(candidate)
                if mutation == 'removed': changed['colorRegions'] = []
                elif mutation == 'shifted': changed['colorRegions'][0]['boundsPt'][0] += 3
                else: changed['colorRegions'][0]['coverage'] *= .8
                self.assertIn('assertion-color-reference-geometry',
                    [c['name'] for c in pdf.correctness(case, ref, changed) if not c['passed']])
            if cid in ('images-emf-stock', 'images-emf-wide-stock'):
                self.assertIn('assertion-color-reference-geometry',
                    [c['name'] for c in pdf.correctness(case, ref, facts['direct']) if not c['passed']])
            for panel in next(c for c in evidence['cases'] if c['id'] == cid)['panels']:
                self.assertEqual(common.digest(folder / panel['pdf']), panel['sha256'])
