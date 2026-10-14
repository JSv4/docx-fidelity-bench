"""Trust boundaries for the explicitly derived LibreOffice reference track."""
import copy
from contextlib import redirect_stdout
from io import StringIO
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
from bench import common, reference_controls, runner


LEGACY = 'paragraphs-page-number-ordinary-legacy'
FIELD = 'paragraphs-page-number-ordinary-field'


class EquivalentControlContract(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.registry = common.validate_registry()
        self.records = {c['id']: c for c in self.registry['cases']}
        self.env = {'contract': {'tools': {}, 'fonts': {}}, 'fontDirectories': []}

    def changed_pair(self, case_id, part, change):
        registry = copy.deepcopy(self.registry)
        records = {c['id']: c for c in registry['cases']}
        for cid in (LEGACY, FIELD):
            record = records[cid]
            with ZipFile(common.ROOT / record['input']) as archive:
                parts = {name: archive.read(name) for name in archive.namelist()}
            if cid == case_id:
                parts[part] = change(parts[part])
            target = self.root / record['input']
            target.parent.mkdir(parents=True, exist_ok=True)
            with ZipFile(target, 'w') as archive:
                for name, data in parts.items():
                    archive.writestr(name, data)
            record['sha256'] = common.digest(target)
        return registry, records[LEGACY]

    def direct_bundle(self):
        root = self.root / 'raw'
        root.mkdir()
        cases = {}
        missing = {LEGACY, 'paragraphs-page-number-restarted-legacy', 'tables-row-height-exact-pt'}
        for case in self.registry['cases']:
            path = root / case['id'] / 'reference.pdf'
            path.parent.mkdir()
            # Byte-level bundle tests use opaque artifacts, not claimed real PDF measurements.
            path.write_bytes(('contract-artifact:' + case['id']).encode())
            cases[case['id']] = {
                'inputSha256': case['sha256'], 'pdf': str(path.relative_to(root)),
                'pdfSha256': common.digest(path), 'eligible': case['id'] not in missing,
                'renderer': {'name': 'libreoffice', 'version': 'test-only'},
                'inspection': {'tokens': case['tokens'], 'fonts': ['LiberationSerif']},
            }
        bundle = {'schema': 1, 'track': 'libreoffice', 'suiteDigest': common.identity(self.registry),
                  'environment': self.env['contract'], 'cases': cases}
        common.write_json(root / 'bundle.json', bundle)
        return root / 'bundle.json'

    def derived_bundle(self, extra_ineligible=None):
        source = self.direct_bundle()
        if extra_ineligible is not None:
            direct = common.read_json(source)
            direct['cases'][extra_ineligible]['eligible'] = False
            common.write_json(source, direct)
        root = self.root / 'derived'
        with patch.object(runner, 'environment', return_value=self.env), redirect_stdout(StringIO()):
            bundle = runner.equivalent_reference_bundle(root, source)
        return root, bundle

    def test_original_pr_pairs_prove_decimal_fields_in_both_numbering_modes(self):
        for variant in ('ordinary', 'restarted'):
            cid = 'paragraphs-page-number-' + variant + '-legacy'
            source = reference_controls.source(self.records[cid], self.registry, common.ROOT)
            self.assertEqual(source['kind'], 'equivalent-control')
            self.assertEqual(source['caseId'], 'paragraphs-page-number-' + variant + '-field')
            self.assertEqual(source['inputSha256'], self.records[source['caseId']]['sha256'])

    def test_roman_field_cannot_replace_decimal_legacy_number(self):
        registry, case = self.changed_pair(FIELD, 'word/header1.xml',
                                           lambda data: data.replace(b'Arabic', b'ROMAN'))
        with self.assertRaisesRegex(ValueError, 'decimal PAGE'):
            reference_controls.source(case, registry, self.root)

    def test_changed_header_font_is_not_an_equivalent_control(self):
        registry, case = self.changed_pair(FIELD, 'word/header1.xml',
                                           lambda data: data.replace(b'w:val="24"', b'w:val="28"'))
        with self.assertRaisesRegex(ValueError, 'decimal PAGE'):
            reference_controls.source(case, registry, self.root)

    def test_changed_section_numbering_is_not_an_equivalent_control(self):
        registry, case = self.changed_pair(FIELD, 'word/document.xml',
                                           lambda data: data.replace(b'w:start="1"', b'w:start="7"'))
        with self.assertRaisesRegex(ValueError, 'package part'):
            reference_controls.source(case, registry, self.root)

    def test_missing_legacy_block_cannot_be_repaired_by_unrelated_field(self):
        registry, case = self.changed_pair(LEGACY, 'word/header1.xml',
                                           lambda data: data.replace(b'<w:pgNum/>', b''))
        with self.assertRaisesRegex(ValueError, 'one empty legacy'):
            reference_controls.source(case, registry, self.root)

    def test_different_assertions_cannot_share_a_control(self):
        registry = copy.deepcopy(self.registry)
        control = next(c for c in registry['cases'] if c['id'] == FIELD)
        control['assertions'][0]['page'] = 2
        with self.assertRaisesRegex(ValueError, 'changes assertions'):
            reference_controls.source(self.records[LEGACY], registry, common.ROOT)

    def test_derivation_preserves_invalid_direct_capture_and_binds_control_digest(self):
        root, bundle = self.derived_bundle()
        direct = common.read_json(root / 'direct/bundle.json')
        self.assertFalse(direct['cases'][LEGACY]['eligible'])
        self.assertTrue(bundle['cases'][LEGACY]['eligible'])
        self.assertEqual(bundle['cases'][LEGACY]['inputSha256'], self.records[LEGACY]['sha256'])
        self.assertEqual(bundle['cases'][LEGACY]['pdfSha256'], direct['cases'][FIELD]['pdfSha256'])
        self.assertEqual(bundle['cases'][LEGACY]['referenceSource']['inputSha256'], self.records[FIELD]['sha256'])
        runner.validate_bundle(bundle, root, self.registry, self.env)

    def test_equivalent_capture_cannot_claim_the_direct_track(self):
        root, bundle = self.derived_bundle()
        bundle['track'] = 'libreoffice'
        with self.assertRaisesRegex(ValueError, 'cannot be labeled'):
            runner.validate_bundle(bundle, root, self.registry, self.env)

    def test_changed_source_declaration_is_rejected(self):
        root, bundle = self.derived_bundle()
        bundle['cases'][LEGACY]['referenceSource']['caseId'] = LEGACY
        with self.assertRaisesRegex(ValueError, 'source declaration'):
            runner.validate_bundle(bundle, root, self.registry, self.env)

    def test_changed_policy_is_rejected(self):
        root, bundle = self.derived_bundle()
        bundle['controlPolicy']['version'] = 2
        with self.assertRaisesRegex(ValueError, 'policy'):
            runner.validate_bundle(bundle, root, self.registry, self.env)

    def test_unrelated_ineligible_capture_cannot_be_promoted(self):
        root, bundle = self.derived_bundle(extra_ineligible='columns-continuous')
        bundle['cases']['columns-continuous']['eligible'] = True
        with self.assertRaisesRegex(ValueError, 'capture evidence'):
            runner.validate_bundle(bundle, root, self.registry, self.env)

    def test_different_pdf_cannot_be_substituted_for_declared_control(self):
        root, bundle = self.derived_bundle()
        entry = bundle['cases'][LEGACY]
        path = root / entry['pdf']
        path.write_bytes(b'other artifact')
        entry['pdfSha256'] = common.digest(path)
        with self.assertRaisesRegex(ValueError, 'capture evidence'):
            runner.validate_bundle(bundle, root, self.registry, self.env)

    def test_changed_original_capture_bytes_are_rejected(self):
        root, bundle = self.derived_bundle()
        source = common.read_json(root / 'direct/bundle.json')
        (root / 'direct' / source['cases'][LEGACY]['pdf']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Stale or unknown reference'):
            runner.validate_bundle(bundle, root, self.registry, self.env)

    def run_with_capture(self, adapter):
        root, bundle = self.derived_bundle()
        requests = []

        def inspect(path):
            record = self.records[Path(path).parent.name]
            return {'tokens': record['tokens'], 'fonts': ['LiberationSerif']}

        def render(adapter, request):
            requests.append(request)
            return {'status': 'failed', 'error': 'Deliberate conversion failure for request inspection'}

        with patch.object(runner, 'environment', return_value=self.env), \
                patch.object(runner.pdf, 'inspect_pdf', side_effect=inspect), \
                patch.object(runner.adapters, 'render', side_effect=render), redirect_stdout(StringIO()):
            result = runner.run(self.root / 'run', root / 'bundle.json', adapter, 'test-candidate')
        return {Path(r['input']).stem: r for r in requests}, result

    def test_production_renderer_still_receives_original_legacy_fixture(self):
        requests, result = self.run_with_capture(['test-production-adapter'])
        self.assertEqual(requests[LEGACY]['input'], str(common.ROOT / self.records[LEGACY]['input']))
        self.assertEqual(requests[LEGACY]['inputSha256'], self.records[LEGACY]['sha256'])
        legacy = next(c for c in result['cases'] if c['id'] == LEGACY)
        self.assertEqual(legacy['referenceSource']['caseId'], FIELD)
        self.assertEqual(legacy['score'], 0)

    def test_provider_calibration_repeats_the_recorded_control_source(self):
        requests, result = self.run_with_capture('libreoffice-reference')
        self.assertNotIn(LEGACY, requests)
        self.assertEqual(requests[FIELD]['inputSha256'], self.records[FIELD]['sha256'])
        self.assertEqual(result['contract']['adapter'], 'libreoffice-reference')


if __name__ == '__main__':
    unittest.main()
