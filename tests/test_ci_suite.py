import copy
import json
import unittest
from pathlib import Path
from bench import common, pdf
from bench.suites import select_cases, select_suite


class HistoricalCiSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = common.validate_registry()
        cls.proof = json.loads((Path(__file__).resolve().parents[1]
            / 'docs/results/table-horizontal-placement/nested-ci-proof.json').read_text())

    def test_default_keeps_the_complete_corpus(self):
        self.assertIs(select_suite(self.registry), self.registry)
        self.assertEqual(len(self.registry['cases']), 533)

    def test_explicit_cases_have_a_diagnostic_identity_and_canonical_order(self):
        ids = self.registry['suite']['cases'][:2]
        selected = select_cases(self.registry, ids[::-1])
        self.assertTrue(selected['suite']['id'].startswith('diagnostic-'))
        self.assertEqual(selected['suite']['cases'], ids)
        self.assertEqual(len(selected['cases']), 2)
        selected['cases'][0]['assertions'].append({'untrusted': True})
        self.assertNotEqual(selected['cases'][0], self.registry['cases'][0])

    def test_malformed_diagnostic_selections_are_rejected(self):
        cid = self.registry['suite']['cases'][0]
        for ids in (None, cid, [], [None], [[]], [{}], [cid, cid], ['unknown']):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                select_cases(self.registry, ids)

    def test_diagnostics_cannot_hide_a_changed_unselected_input(self):
        changed = copy.deepcopy(self.registry)
        changed['cases'][-1]['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            select_cases(changed, [changed['cases'][0]['id']])

    def test_historical_twelve_inputs_are_preserved(self):
        selected = select_suite(self.registry, 'core-ci-v2')
        self.assertEqual(selected['suite']['cases'], self.proof['ciSuite']['cases'])
        self.assertEqual(len(selected['cases']), 12)
        self.assertEqual({c['id']: c['sha256'] for c in selected['cases']}, self.proof['ciSuite']['inputSha256'])

    def test_unknown_suite_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unknown registered suite'):
            select_suite(self.registry, 'arbitrary-shortcut')

    def test_missing_or_changed_original_input_is_rejected(self):
        cid = self.proof['ciSuite']['cases'][0]
        for remove in [True, False]:
            changed = copy.deepcopy(self.registry)
            if remove:
                changed['cases'] = [c for c in changed['cases'] if c['id'] != cid]
            else:
                next(c for c in changed['cases'] if c['id'] == cid)['sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'CI input is missing or changed'):
                select_suite(changed, 'core-ci-v2')

    def test_selected_declarations_do_not_mutate_the_full_registry(self):
        before = copy.deepcopy(self.registry)
        selected = select_suite(self.registry, 'core-ci-v2')
        selected['cases'][0]['assertions'].append({'untrusted': True})
        self.assertEqual(self.registry, before)

    def test_real_ci_padding_regression_fixes_the_word_requirement(self):
        case = next(c for c in select_suite(self.registry, 'core-ci-v2')['cases'] if c['id'] == 'tables-nested')
        reference = self.proof['ci']['calibration']['inspection']
        old = pdf.correctness(case, reference, self.proof['ci']['baseline']['inspection'])
        fixed = pdf.correctness(case, reference, self.proof['ci']['candidate']['inspection'])
        self.assertEqual([c['name'] for c in old if not c['passed']], ['assertion-marker-region'] * 2)
        self.assertTrue(all(c['passed'] for c in fixed))
        self.assertLess(self.proof['ci']['candidate']['score'], self.proof['ci']['baseline']['score'])

    def test_libreoffice_still_calibrates_against_its_own_reference(self):
        case = next(c for c in self.registry['cases'] if c['id'] == 'tables-nested')
        reference = self.proof['ci']['calibration']['inspection']
        checks = pdf.correctness(pdf.binding_case(case, 'libreoffice', True), reference, reference)
        self.assertTrue(all(c['passed'] for c in checks))

    def test_substituted_word_capture_is_not_promoted(self):
        case = next(c for c in self.registry['cases'] if c['id'] == 'tables-nested')
        word = next(c for c in self.proof['wordCaptures'] if c['id'] == 'nested-benchmark-original-diagnostic')
        self.assertIn('declared-font-families', pdf.reference_failures(case, word['inspection'], 'word'))
