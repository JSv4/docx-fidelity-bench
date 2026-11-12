import copy
from pathlib import Path
import struct
import tempfile
import unittest
from zipfile import ZipFile
from bench import collection_fonts, pdf, runner
from bench.common import ROOT, digest, identity, read_json


class CollectionFontTests(unittest.TestCase):
    def test_production_evidence_binds_outputs_and_preserves_controls(self):
        folder = ROOT / 'docs/results/font-collections'
        evidence = read_json(folder / 'production-evidence.json')
        for name, expected in evidence['files'].items():
            self.assertEqual(digest(folder / name), expected, name)
        original_bundle = read_json(folder / 'reference-bundle.json')
        # Retained PDFs are flattened into this directory; run identities bind
        # the original capture layout without changing any PDF or inspection.
        for cid, capture in original_bundle['cases'].items():
            capture['pdf'] = f'{cid}/reference.pdf'
        manifest = read_json(folder / 'capture-manifest.json')
        results = {kind: read_json(folder / f'{kind}-result.json') for kind in ('main', 'fixed', 'calibration')}
        for kind, result in results.items():
            runner.validate_result(result)
            self.assertEqual(result['contract']['referenceDigest'], identity(original_bundle))
            self.assertEqual(result['contract']['suiteDigest'], identity(manifest))
            self.assertEqual(evidence['runs'][kind]['summary'], result['summary'])
            if kind != 'calibration':
                self.assertEqual(read_json(folder / f'{kind}-build.json')['commit'], result['candidate'])
                for case in result['cases']:
                    if case['adapter']['status'] == 'ok':
                        self.assertEqual(case['adapter']['pdfSha256'], digest(folder / f"{case['id']}-{kind}-candidate.pdf"))
        self.assertEqual(results['main']['contractDigest'], results['fixed']['contractDigest'])
        self.assertEqual(results['main']['summary']['mandatoryPassRate'], 0.5)
        self.assertEqual(results['fixed']['summary']['mandatoryPassRate'], 1)
        self.assertEqual(results['calibration']['summary']['score'], 100)
        for kind in ('ttc', 'otc'):
            prefix = f'font-collection-{kind}-standalone-control'
            self.assertEqual((folder / f'{prefix}-main-1-candidate.png').read_bytes(),
                             (folder / f'{prefix}-fixed-1-candidate.png').read_bytes())

    def test_native_evidence_is_bound_and_rejects_font_or_text_loss(self):
        folder = ROOT / 'docs/results/font-collections'
        bundle = read_json(folder / 'reference-bundle.json')
        manifest = read_json(folder / 'capture-manifest.json')
        runner.validate_bundle(bundle, folder, manifest, {'contract': bundle['environment']})
        records = {case['id']: case for case in read_json(ROOT / 'fixtures/manifest.json')['cases']}
        self.assertEqual(len(manifest['cases']), 4)
        for case in manifest['cases']:
            self.assertEqual(case['sha256'], records[case['id']]['sha256'])
            capture = bundle['cases'][case['id']]
            self.assertTrue(capture['eligible'])
            self.assertEqual(pdf.reference_failures(case, capture['inspection']), [])
            changed = copy.deepcopy(capture['inspection'])
            changed['fonts'] = []
            self.assertIn('assertion-required-font-family', pdf.reference_failures(case, changed))
            changed = copy.deepcopy(capture['inspection'])
            changed['tokens']['LIATRISEND'] -= 1
            self.assertIn('expected-visible-tokens', pdf.reference_failures(case, changed))
            changed = copy.deepcopy(capture['inspection'])
            marker = pdf.marker(changed, 'LIATRISEND')
            marker['rect'][1] += 1
            marker['rect'][3] += 1
            self.assertTrue(any(check['name'] == 'assertion-marker-reference-position' and not check['passed']
                                for check in pdf.correctness(case, capture['inspection'], changed)))

    def test_original_fonts_regenerate_and_reject_mutated_assets(self):
        self.assertEqual(len(collection_fonts.validate()), 3)
        with tempfile.TemporaryDirectory() as folder:
            collection_fonts.generate(folder)
            path = Path(folder) / 'fixtures/collection-fonts/liatris-plain.ttf'
            path.write_bytes(path.read_bytes() + b'changed')
            with self.assertRaisesRegex(ValueError, 'differ'):
                collection_fonts.validate(folder)

    def test_standalone_checksum_and_absolute_collection_table_offsets(self):
        font = collection_fonts.font('Liatris Plain')
        self.assertEqual(collection_fonts.checksum(font), 0xb1b0afba)
        bundled = collection_fonts.collection(['Liatris One', 'Liatris Two'])
        self.assertEqual(bundled[:4], b'ttcf')
        self.assertEqual(struct.unpack_from('>I', bundled, 8)[0], 2)
        for offset in struct.unpack_from('>II', bundled, 12):
            count = struct.unpack_from('>H', bundled, offset + 4)[0]
            for index in range(count):
                record = offset + 12 + index * 16
                start, length = struct.unpack_from('>II', bundled, record + 8)
                self.assertGreaterEqual(start, offset + 12 + count * 16)
                self.assertLessEqual(start + length, len(bundled))

    def test_collection_pairs_change_only_the_requested_family(self):
        cases = {c['id']: c for c in read_json(ROOT / 'fixtures/manifest.json')['cases']}
        for kind in ('ttc', 'otc'):
            requested = cases[f'font-collection-{kind}-requested']
            control = cases[f'font-collection-{kind}-standalone-control']
            self.assertEqual(requested['tokens'], control['tokens'])
            with ZipFile(ROOT / requested['input']) as left, ZipFile(ROOT / control['input']) as right:
                self.assertEqual(left.namelist(), right.namelist())
                for name in left.namelist():
                    self.assertEqual(left.read(name).replace(('Liatris ' + kind.upper()).encode(), b'Liatris Plain'), right.read(name))
            self.assertIn({'type': 'required-font-family', 'version': 1, 'family': 'Liatris ' + kind.upper()}, requested['assertions'])


if __name__ == '__main__':
    unittest.main()
