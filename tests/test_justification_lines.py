import copy
import hashlib
import json
import unittest
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from bench import common, fixtures, pdf


class JustificationLineControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        folder = cls.root / 'docs/results/justification-lines'
        cls.native = json.loads((folder / 'native-word.json').read_text())['cases']
        cls.candidate = json.loads((folder / 'candidate-proof.json').read_text())['cases']
        cls.cases = {c['id']: c for c in common.validate_registry()['cases'] if c['id'] in cls.native}

    def test_literal_packages_and_complete_text_match_the_captured_inputs(self):
        self.assertEqual(len(self.cases), 2)
        for cid, size, parts, text in fixtures.justification_line_inputs():
            with self.subTest(case=cid), ZipFile(self.root / self.cases[cid]['input']) as z:
                self.assertEqual({name: z.read(name).decode() for name in z.namelist()}, parts)
                document = ET.fromstring(parts['word/document.xml'])
                w = '{' + fixtures.W + '}'
                self.assertEqual([''.join(t.text or '' for t in p.iter(w + 't'))
                                  for p in document.iter(w + 'p')], text)
                self.assertEqual(len(text), 18 if size == 11 else 27)
                self.assertEqual(self.cases[cid]['sha256'], self.native[cid]['inputSha256'])
                self.assertEqual(self.cases[cid]['sha256'], hashlib.sha256(
                    (self.root / self.cases[cid]['input']).read_bytes()).hexdigest())
                self.assertNotIn('clippedTokens', self.cases[cid])
                self.assertNotIn('pdfTextNormalization', self.cases[cid])

    def test_native_and_candidate_pass_every_existing_mandatory_contract(self):
        for cid, case in self.cases.items():
            with self.subTest(case=cid):
                native = self.native[cid]['inspection']
                for actual in (native, self.candidate[cid]['inspection']):
                    self.assertTrue(all(c['passed'] for c in pdf.correctness(case, native, actual)))
                paragraphs = self.candidate[cid]['paragraphLineAndPageContracts']
                self.assertEqual(len(paragraphs), 18 if cid.endswith('11') else 27)
                self.assertTrue(all(p['sameLines'] and p['samePages'] for p in paragraphs))

    def test_a_missing_or_duplicated_word_fails_the_complete_inventory(self):
        for cid, case in self.cases.items():
            for duplicate in (False, True):
                with self.subTest(case=cid, duplicate=duplicate):
                    reference = self.native[cid]['inspection']
                    changed = copy.deepcopy(reference)
                    word = changed['words'][0]
                    if duplicate:
                        changed['words'].append(copy.deepcopy(word))
                        changed['tokens'][word['text']] += 1
                    else:
                        changed['words'].pop(0)
                        changed['tokens'][word['text']] -= 1
                    checks = pdf.correctness(case, reference, changed)
                    self.assertFalse(next(c for c in checks if c['name'] == 'expected-visible-tokens')['passed'])

    def test_an_extra_page_fails_even_with_the_complete_inventory(self):
        for cid, case in self.cases.items():
            with self.subTest(case=cid):
                reference = self.native[cid]['inspection']
                changed = copy.deepcopy(reference)
                changed['geometry'].append(copy.deepcopy(changed['geometry'][-1]))
                checks = pdf.correctness(case, reference, changed)
                self.assertFalse(next(c for c in checks if c['name'] == 'page-count')['passed'])
                self.assertTrue(next(c for c in checks if c['name'] == 'expected-visible-tokens')['passed'])
