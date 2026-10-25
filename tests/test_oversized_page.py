import copy
import json
import unittest
from pathlib import Path
from bench import common, pdf


class OversizedPageContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {c['id']: c for c in common.validate_registry()['cases']}
        cls.native = json.loads((Path(__file__).resolve().parents[1]
            / 'docs/results/oversized-page-blocks/native-word.json').read_text())['cases']

    def test_all_thirteen_native_captures_pass_their_own_checks(self):
        self.assertEqual(len(self.native), 13)
        for cid, capture in self.native.items():
            with self.subTest(case=cid):
                self.assertEqual(self.cases[cid]['sha256'], capture['inputSha256'])
                self.assertEqual(pdf.reference_failures(self.cases[cid], capture['inspection'], 'word'), [])

    def test_wholly_off_paper_words_cannot_leak_to_a_later_page(self):
        cid = 'tables-row-exact-paper-edge-lines-times-new-roman'
        case = self.cases[cid]
        reference = self.native[cid]['inspection']
        for token in ['Cedar11', 'Cedar12']:
            changed = copy.deepcopy(reference)
            changed['words'].append({'text': token, 'page': 3, 'rect': [10, 30, 60, 44]})
            changed['tokens'][token] = 1
            checks = pdf.correctness(case, reference, changed)
            self.assertFalse(next(c for c in checks if c['name'] == 'expected-visible-tokens')['passed'])

    def test_empty_final_pages_are_mandatory(self):
        for suffix, pages in [('exact-row', 2), ('header-row', 3)]:
            cid = 'tables-final-' + suffix + '-blank-page-times-new-roman'
            reference = self.native[cid]['inspection']
            self.assertEqual(len(reference['geometry']), pages)
            self.assertFalse(any(w['page'] == pages for w in reference['words']))
            changed = copy.deepcopy(reference)
            changed['geometry'].pop()
            self.assertFalse(next(c for c in pdf.correctness(self.cases[cid], reference, changed)
                if c['name'] == 'page-count')['passed'])

    def test_paragraph_after_oversized_header_stays_on_word_page_four(self):
        cid = 'tables-header-row-taller-than-page-times-new-roman'
        reference = self.native[cid]['inspection']
        changed = copy.deepcopy(reference)
        next(w for w in changed['words'] if w['text'] == 'MapleAfter')['page'] = 3
        checks = pdf.correctness(self.cases[cid], reference, changed)
        self.assertTrue(any(not c['passed'] and c.get('declaration', {}).get('marker') == 'MapleAfter'
            for c in checks))
