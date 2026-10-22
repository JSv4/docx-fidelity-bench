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
MERGED = 'tables-vmerge-boundary-merged'
KEPT = 'tables-vmerge-boundary-merged-kept'
RUN_IN = 'paragraph-mark-hidden-run-in-keep'
RUN_IN_CONTROL = RUN_IN + '-control'


class EquivalentControlContract(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.registry = common.validate_registry()
        self.records = {c['id']: c for c in self.registry['cases']}
        self.env = {'contract': {'tools': {}, 'fonts': {}}, 'fontDirectories': []}

    def changed_pair(self, case_id, part, change, pair=(LEGACY, FIELD)):
        registry = copy.deepcopy(self.registry)
        records = {c['id']: c for c in registry['cases']}
        for cid in pair:
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
        return registry, records[pair[0]]

    def direct_bundle(self):
        root = self.root / 'raw'
        root.mkdir()
        cases = {}
        missing = {LEGACY, 'paragraphs-page-number-restarted-legacy', 'tables-row-height-exact-pt',
                   'tables-vmerge-boundary-merged', RUN_IN}
        for case in self.registry['cases']:
            path = root / case['id'] / 'reference.pdf'
            path.parent.mkdir()
            # Byte-level bundle tests use opaque artifacts, not claimed real PDF measurements.
            path.write_bytes(('contract-artifact:' + case['id']).encode())
            cases[case['id']] = {
                'inputSha256': case['sha256'], 'pdf': str(path.relative_to(root)),
                'pdfSha256': common.digest(path), 'eligible': case['id'] not in missing,
                'renderer': {'name': 'libreoffice', 'version': 'test-only'},
                'inspection': {'tokens': case['tokens'], 'fonts': ['LiberationSerif'],
                               **({'pdfTextNormalization': case['pdfTextNormalization'], 'decorativeWords': []}
                                  if case.get('pdfTextNormalization') else {})},
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

    def test_original_pr_exact_point_height_proves_720_twip_control(self):
        cid = 'tables-row-height-exact-pt'
        source = reference_controls.source(self.records[cid], self.registry, common.ROOT)
        self.assertEqual(source['kind'], 'equivalent-control')
        self.assertEqual(source['caseId'], 'tables-row-height-exact-twips')
        self.assertEqual(source['rule'], 'exact-row-height-points-to-twips-v1')

    def test_different_numeric_height_is_rejected(self):
        pair = ('tables-row-height-exact-pt', 'tables-row-height-exact-twips')
        registry, case = self.changed_pair(pair[1], 'word/document.xml',
            lambda data: data.replace(b'w:val="720"', b'w:val="719"'), pair=pair)
        with self.assertRaisesRegex(ValueError, 'row layout'):
            reference_controls.source(case, registry, self.root)

    def test_exact_height_cannot_be_replaced_with_minimum_height(self):
        pair = ('tables-row-height-exact-pt', 'tables-row-height-exact-twips')
        registry, case = self.changed_pair(pair[1], 'word/document.xml',
            lambda data: data.replace(b'w:hRule="exact"', b'w:hRule="atLeast"'), pair=pair)
        with self.assertRaisesRegex(ValueError, 'row layout'):
            reference_controls.source(case, registry, self.root)

    def test_different_point_height_is_rejected(self):
        pair = ('tables-row-height-exact-pt', 'tables-row-height-exact-twips')
        registry, case = self.changed_pair(pair[0], 'word/document.xml',
            lambda data: data.replace(b'w:val="36pt"', b'w:val="35pt"'), pair=pair)
        with self.assertRaisesRegex(ValueError, 'three exact 36pt'):
            reference_controls.source(case, registry, self.root)

    def test_changed_table_width_is_rejected(self):
        pair = ('tables-row-height-exact-pt', 'tables-row-height-exact-twips')
        registry, case = self.changed_pair(pair[1], 'word/document.xml',
            lambda data: data.replace(b'w:w="7200"', b'w:w="7300"'), pair=pair)
        with self.assertRaisesRegex(ValueError, 'row layout'):
            reference_controls.source(case, registry, self.root)

    def test_incomplete_exact_unit_capture_uses_complete_control_and_preserves_raw(self):
        root, bundle = self.derived_bundle()
        direct = common.read_json(root / 'direct/bundle.json')
        cid, control = 'tables-row-height-exact-pt', 'tables-row-height-exact-twips'
        self.assertFalse(direct['cases'][cid]['eligible'])
        self.assertTrue(bundle['cases'][cid]['eligible'])
        self.assertEqual(bundle['cases'][cid]['inputSha256'], self.records[cid]['sha256'])
        self.assertEqual(bundle['cases'][cid]['pdfSha256'], direct['cases'][control]['pdfSha256'])
        self.assertEqual(bundle['cases'][cid]['referenceSource']['inputSha256'], self.records[control]['sha256'])
        runner.validate_bundle(bundle, root, self.registry, self.env)

    def test_kept_ledger_proves_the_declared_intact_boundary_merge(self):
        source = reference_controls.source(self.records[MERGED], self.registry, common.ROOT)
        self.assertEqual((source['caseId'], source['rule']), (KEPT, 'vertical-merge-keep-with-next-v1'))

    def test_keeping_rows_beyond_the_merge_is_rejected(self):
        # Row 13 ends the merge; holding it with row 14 would move content the merge does not span.
        def keep_row_13(data):
            rows = data.split(b'<w:tr>')
            rows[13] = rows[13].replace(b'<w:pPr />', b'<w:pPr><w:keepNext /></w:pPr>').replace(
                b'<w:pPr/>', b'<w:pPr><w:keepNext/></w:pPr>').replace(b'<w:pPr></w:pPr>', b'<w:pPr><w:keepNext/></w:pPr>')
            return b'<w:tr>'.join(rows)
        registry, case = self.changed_pair(KEPT, 'word/document.xml', keep_row_13, pair=(MERGED, KEPT))
        with self.assertRaisesRegex(ValueError, 'merged rows together'):
            reference_controls.source(case, registry, self.root)

    def test_unmerged_ledger_cannot_be_a_kept_merge_control(self):
        registry, case = self.changed_pair(KEPT, 'word/document.xml',
            lambda data: data.replace(b'<w:vMerge w:val="restart"/>', b''), pair=(MERGED, KEPT))
        with self.assertRaisesRegex(ValueError, 'merged rows together'):
            reference_controls.source(case, registry, self.root)

    def test_split_merge_capture_uses_kept_control_and_preserves_raw(self):
        root, bundle = self.derived_bundle()
        direct = common.read_json(root / 'direct/bundle.json')
        self.assertFalse(direct['cases'][MERGED]['eligible'])
        self.assertTrue(bundle['cases'][MERGED]['eligible'])
        self.assertEqual(bundle['cases'][MERGED]['pdfSha256'], direct['cases'][KEPT]['pdfSha256'])
        runner.validate_bundle(bundle, root, self.registry, self.env)

    def test_run_in_pair_differs_only_in_the_headings_keep_properties(self):
        source = reference_controls.source(self.records[RUN_IN], self.registry, common.ROOT)
        self.assertEqual((source['caseId'], source['rule']), (RUN_IN_CONTROL, 'run-in-heading-keep-removed-v1'))

    def test_run_in_control_changing_anything_else_is_rejected(self):
        for change in (lambda data: data.replace(b'RunInCedar.', b'RunInCedar!', 1),
                       lambda data: data.replace(b'<w:keepLines/>', b'', 1)):
            registry, case = self.changed_pair(RUN_IN_CONTROL, 'word/document.xml', change, pair=(RUN_IN, RUN_IN_CONTROL))
            with self.assertRaisesRegex(ValueError, "headings' keep properties"):
                reference_controls.source(case, registry, self.root)

    def test_run_in_capture_uses_the_control_and_preserves_raw(self):
        root, bundle = self.derived_bundle()
        direct = common.read_json(root / 'direct/bundle.json')
        self.assertFalse(direct['cases'][RUN_IN]['eligible'])
        self.assertTrue(bundle['cases'][RUN_IN]['eligible'])
        self.assertEqual(bundle['cases'][RUN_IN]['pdfSha256'], direct['cases'][RUN_IN_CONTROL]['pdfSha256'])
        runner.validate_bundle(bundle, root, self.registry, self.env)

    def test_unit_minimum_heights_prove_whole_twip_controls(self):
        for unit in ('pt', 'in', 'cm', 'mm', 'pc', 'pi', 'multipage-pt'):
            cid = 'tables-row-height-' + unit
            source = reference_controls.source(self.records[cid], self.registry, common.ROOT)
            control = 'tables-row-height-multipage-twips' if unit.startswith('multipage') else 'tables-row-height-twips'
            self.assertEqual((source['kind'], source['caseId']), ('equivalent-control', control))

    def test_fractional_point_height_uses_bounded_nearest_twip_control(self):
        source = reference_controls.source(self.records['tables-row-height-fractional-pt'], self.registry, common.ROOT)
        self.assertEqual((source['kind'], source['caseId']), ('nearest-twip-control', 'tables-row-height-fractional-twips'))
        self.assertEqual(source['bound'], {'perRowPt': '0.025', 'maxDisplacementPt': '0.050'})

    def test_inexact_unit_height_cannot_claim_an_exact_twip_control(self):
        pair = ('tables-row-height-cm', 'tables-row-height-twips')
        registry, case = self.changed_pair(pair[0], 'word/document.xml',
            lambda data: data.replace(b'w:val="1.27cm"', b'w:val="1.28cm"'), pair=pair)
        with self.assertRaisesRegex(ValueError, 'not a whole number of twips'):
            reference_controls.source(case, registry, self.root)

    def test_minimum_height_cannot_be_replaced_with_exact_height(self):
        pair = ('tables-row-height-mm', 'tables-row-height-twips')
        registry, case = self.changed_pair(pair[1], 'word/document.xml',
            lambda data: data.replace(b'w:hRule="atLeast"', b'w:hRule="exact"'), pair=pair)
        with self.assertRaisesRegex(ValueError, 'minimum-height'):
            reference_controls.source(case, registry, self.root)

    def test_mixed_row_heights_are_rejected(self):
        pair = ('tables-row-height-pt', 'tables-row-height-twips')
        registry, case = self.changed_pair(pair[0], 'word/document.xml',
            lambda data: data.replace(b'w:val="36pt"', b'w:val="37pt"', 1), pair=pair)
        with self.assertRaisesRegex(ValueError, 'uniform'):
            reference_controls.source(case, registry, self.root)

    def test_nearest_twip_rule_rejects_wrong_rounding_and_loose_bounds(self):
        pair = ('tables-row-height-fractional-pt', 'tables-row-height-fractional-twips')
        registry, case = self.changed_pair(pair[1], 'word/document.xml',
            lambda data: data.replace(b'w:val="502"', b'w:val="501"'), pair=pair)
        with self.assertRaisesRegex(ValueError, 'minimum-height'):
            reference_controls.source(case, registry, self.root)
        data = b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">' + \
            b'<w:trHeight w:val="25.075pt" w:hRule="atLeast"/>' * 30 + b'</w:document>'
        loose = {'assertions': [{'type': 'marker-reference-position', 'version': 1, 'marker': 'M', 'tolerancePt': 0.5}]}
        with self.assertRaisesRegex(ValueError, 'not bounded'):
            reference_controls.nearest_twip_bound(loose, data)

    def test_conflicting_indentation_aliases_use_logical_only_controls(self):
        for form in ('pt', 'in', 'cm', 'mm', 'pc', 'pi', 'twips', 'small-pt', 'small-twips'):
            source = reference_controls.source(self.records['paragraphs-indentation-' + form], self.registry, common.ROOT)
            control = 'paragraphs-indentation-' + ('small-' if form.startswith('small') else '') + 'twips-logical-only'
            self.assertEqual((source['caseId'], source['rule']), (control, 'logical-indentation-without-conflicting-aliases-v1'))

    def test_logical_control_cannot_change_the_logical_edge(self):
        pair = ('paragraphs-indentation-twips', 'paragraphs-indentation-twips-logical-only')
        registry, case = self.changed_pair(pair[1], 'word/document.xml',
            lambda data: data.replace(b'w:start="720" w:end="720"', b'w:start="1440" w:end="1440"'), pair=pair)
        with self.assertRaisesRegex(ValueError, 'logical edges'):
            reference_controls.source(case, registry, self.root)

    def test_agreeing_aliases_are_not_a_conflict_to_remove(self):
        pair = ('paragraphs-indentation-twips', 'paragraphs-indentation-twips-logical-only')
        registry, case = self.changed_pair(pair[0], 'word/document.xml',
            lambda data: data.replace(b'w:left="1440" w:right="1440"', b'w:left="720" w:right="720"'), pair=pair)
        with self.assertRaisesRegex(ValueError, 'conflicting legacy aliases'):
            reference_controls.source(case, registry, self.root)

    def test_inexact_unit_indent_cannot_use_twip_control(self):
        pair = ('paragraphs-indentation-cm', 'paragraphs-indentation-twips-logical-only')
        registry, case = self.changed_pair(pair[0], 'word/document.xml',
            lambda data: data.replace(b'1.27cm', b'1.3cm'), pair=pair)
        with self.assertRaisesRegex(ValueError, 'whole number of twips'):
            reference_controls.source(case, registry, self.root)

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

        # Opaque captures carry no page geometry; reference self-checks are covered in test_contract.
        def inspect(path):
            record = self.records[Path(path).parent.name]
            return {'tokens': record['tokens'], 'fonts': ['LiberationSerif'],
                    'words': [{'text': token} for token, count in record['tokens'].items() for _ in range(count)]}

        def render(adapter, request):
            requests.append(request)
            return {'status': 'failed', 'error': 'Deliberate conversion failure for request inspection'}

        with patch.object(runner, 'environment', return_value=self.env), \
                patch.object(runner.pdf, 'inspect_pdf', side_effect=inspect), \
                patch.object(runner.pdf, 'reference_failures', return_value=[]), \
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
