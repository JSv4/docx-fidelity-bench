import copy
import hashlib
import json
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from bench import common, fixtures, pdf


class NativeTextPrecisionControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        folder = cls.root / 'docs/results/native-text-precision'
        cls.native = json.loads((folder / 'native-word.json').read_text())['cases']
        cls.candidate = json.loads((folder / 'candidate-proof.json').read_text())['cases']
        cls.cases = {c['id']: c for c in common.validate_registry()['cases'] if c['id'] in cls.native}

    def test_generated_packages_retain_the_captured_bytes_and_full_text(self):
        self.assertEqual(len(self.cases), 3)
        total = 0
        for cid, description, parts, text, fonts in fixtures.native_precision_inputs():
            with self.subTest(case=cid), ZipFile(self.root / self.cases[cid]['input']) as package:
                self.assertEqual({name: package.read(name).decode() for name in package.namelist()}, parts)
                document = ET.fromstring(parts['word/document.xml'])
                w = '{' + fixtures.W + '}'
                self.assertEqual([''.join(t.text or '' for t in p.iter(w + 't'))
                                  for p in document.iter(w + 'p')], text)
                total += len(text)
                case = self.cases[cid]
                self.assertEqual(case['fonts'], fonts)
                self.assertEqual(case['sha256'], self.native[cid]['inputSha256'])
                self.assertEqual(case['sha256'], hashlib.sha256((self.root / case['input']).read_bytes()).hexdigest())
                self.assertNotIn('clippedTokens', case)
                self.assertNotIn('pdfTextNormalization', case)
        self.assertEqual(total, 40)

    def test_native_and_candidate_pass_unchanged_mandatory_contracts(self):
        for cid, case in self.cases.items():
            with self.subTest(case=cid):
                native = self.native[cid]['inspection']
                for actual in (native, self.candidate[cid]['inspection']):
                    self.assertTrue(all(c['passed'] for c in pdf.correctness(case, native, actual)))
                paragraphs = self.candidate[cid]['paragraphLineAndPageContracts']
                self.assertEqual(len(paragraphs), 8 if cid.startswith('baseline-') else 16)
                self.assertTrue(all(p['sameLines'] and p['samePages'] for p in paragraphs))

    def test_missing_and_duplicated_words_fail_the_full_inventory(self):
        for cid, case in self.cases.items():
            for duplicate in (False, True):
                with self.subTest(case=cid, duplicate=duplicate):
                    native = self.native[cid]['inspection']
                    changed = copy.deepcopy(native)
                    word = changed['words'][0]
                    if duplicate:
                        changed['words'].append(copy.deepcopy(word))
                        changed['tokens'][word['text']] += 1
                    else:
                        changed['words'].pop(0)
                        changed['tokens'][word['text']] -= 1
                    checks = pdf.correctness(case, native, changed)
                    self.assertFalse(next(c for c in checks if c['name'] == 'expected-visible-tokens')['passed'])

    def test_extra_pages_and_substituted_font_families_fail(self):
        for cid, case in self.cases.items():
            with self.subTest(case=cid):
                native = self.native[cid]['inspection']
                changed = copy.deepcopy(native)
                changed['geometry'].append(copy.deepcopy(changed['geometry'][-1]))
                checks = pdf.correctness(case, native, changed)
                self.assertFalse(next(c for c in checks if c['name'] == 'page-count')['passed'])
                changed = copy.deepcopy(native)
                changed['fonts'] = ['UnqualifiedEmbeddedAlias']
                checks = pdf.correctness(case, native, changed)
                self.assertFalse(next(c for c in checks if c['name'] == 'declared-font-families')['passed'])
