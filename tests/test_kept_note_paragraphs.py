import copy
import hashlib
import json
import unittest
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from bench import common, pdf


class KeptNoteParagraphContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.cases = {c['id']: c for c in common.validate_registry()['cases']
                     if c['id'].startswith('kept-note-')}
        folder = cls.root / 'docs/results/kept-note-paragraphs'
        cls.native = json.loads((folder / 'native-word.json').read_text())['cases']
        cls.before = json.loads((folder / 'candidate-before.json').read_text())['cases']
        cls.after = json.loads((folder / 'candidate-proof.json').read_text())['cases']
        cls.w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

    def test_all_fourteen_exact_word_inputs_and_candidates_pass_the_complete_contract(self):
        self.assertEqual(len(self.cases), 14)
        self.assertEqual(set(self.cases), set(self.native))
        self.assertEqual(set(self.cases), set(self.after))
        for cid, case in self.cases.items():
            with self.subTest(case=cid):
                self.assertEqual(case['sha256'], self.native[cid]['inputSha256'])
                self.assertEqual(case['sha256'], self.after[cid]['inputSha256'])
                self.assertEqual(hashlib.sha256((self.root / case['input']).read_bytes()).hexdigest(), case['sha256'])
                reference = self.native[cid]['inspection']
                self.assertEqual(pdf.reference_failures(case, reference, 'word'), [])
                self.assertTrue(all(c['passed'] for c in pdf.correctness(case, reference, self.after[cid]['inspection'])))
                self.assertNotIn('clippedTokens', case)
                self.assertNotIn('pdfTextNormalization', case)

    def test_every_authored_body_and_note_line_has_a_word_page_assertion(self):
        for cid, case in self.cases.items():
            with self.subTest(case=cid), ZipFile(self.root / case['input']) as z:
                root = ET.fromstring(z.read('word/document.xml'))
                notes = ET.fromstring(z.read('word/footnotes.xml'))
                note = next(n for n in notes if n.get(self.w + 'id') == '1')
                words = [t.text for t in root.iter(self.w + 't')]
                words += [t.text.strip() for t in note.iter(self.w + 't')]
                markers = {a['marker'] for a in case['assertions']}
                if '120-lines' in cid:
                    self.assertEqual(len(markers), 150)
                    self.assertEqual(len(list(note.iter(self.w + 'br'))), 119)
                    self.assertEqual(case['tokens']['1'], 2)
                    self.assertEqual(set(words), markers)
                else:
                    words[2] = '1' + words[2]
                    self.assertEqual(set(words), markers)
                self.assertTrue(all(a['adjudicated'] == 'word' and a['version'] == 2
                                    and a['tolerancePt'] == 0.0001 for a in case['assertions']))

    def test_settings_and_package_defaults_are_preserved(self):
        for cid, case in self.cases.items():
            with self.subTest(case=cid), ZipFile(self.root / case['input']) as z:
                mode = 14 if 'mode14' in cid or 'mode-14' in cid else 15 if 'mode15' in cid or 'mode-15' in cid else None
                self.assertEqual(len(z.namelist()), 7 if mode else 6)
                if mode:
                    settings = ET.fromstring(z.read('word/settings.xml'))
                    actual = settings.find('.//' + self.w + 'compatSetting').get(self.w + 'val')
                    self.assertEqual(actual, str(mode))
                else:
                    self.assertNotIn('word/settings.xml', z.namelist())

    def test_mode_pairs_change_only_the_compatibility_setting(self):
        pairs = [('kept-note-mechanism-normal-mode14-opc-default-ns-times-new-roman',
                  'kept-note-mechanism-normal-mode15-opc-default-ns-times-new-roman')]
        pairs += [(f'kept-note-120-lines-citation-{cite}-mode-14-times-new-roman',
                   f'kept-note-120-lines-citation-{cite}-mode-15-times-new-roman') for cite in (1, 16)]
        for legacy, modern in pairs:
            with self.subTest(legacy=legacy), ZipFile(self.root / self.cases[legacy]['input']) as a, ZipFile(self.root / self.cases[modern]['input']) as b:
                parts = {n: a.read(n) for n in a.namelist()}
                parts['word/settings.xml'] = parts['word/settings.xml'].replace(b'w:val="14"', b'w:val="15"')
                self.assertEqual(parts, {n: b.read(n) for n in b.namelist()})

    def test_previous_candidate_exposes_both_legacy_long_note_boundary_failures(self):
        expected = {f'kept-note-120-lines-citation-{cite}-mode-14-times-new-roman' for cite in (1, 16)}
        actual = set()
        for cid, case in self.cases.items():
            checks = pdf.correctness(case, self.native[cid]['inspection'], self.before[cid]['inspection'])
            failures = [c for c in checks if not c['passed']]
            if failures:
                actual.add(cid)
                self.assertEqual({c['declaration']['marker'] for c in failures}, {'SpruceLongNote054', 'SpruceLongNote109'})
        self.assertEqual(actual, expected)

    def assert_wrong_page_fails(self, cid, marker, page):
        reference = self.native[cid]['inspection']
        changed = copy.deepcopy(reference)
        next(w for w in changed['words'] if w['text'] == marker)['page'] = page
        checks = pdf.correctness(self.cases[cid], reference, changed)
        self.assertTrue(next(c for c in checks if c['name'] == 'expected-visible-tokens')['passed'])
        self.assertTrue(next(c for c in checks if c['name'] == 'page-count')['passed'])
        self.assertTrue(any(not c['passed'] and c.get('declaration', {}).get('marker') == marker for c in checks))

    def test_mode15_cannot_start_note_beside_citation(self):
        self.assert_wrong_page_fails('kept-note-mechanism-normal-mode15-opc-default-ns-times-new-roman', '1SpruceNoteLine01', 1)

    def test_widow_default_and_explicit_off_have_different_last_line_pages(self):
        self.assert_wrong_page_fails('kept-note-19-lines-deferred-times-new-roman', 'SpruceNoteLine18', 1)
        self.assert_wrong_page_fails('kept-note-19-lines-widow-off-times-new-roman', 'SpruceNoteLine18', 2)

    def test_long_note_final_line_cannot_be_missing_or_duplicated(self):
        cid = 'kept-note-120-lines-citation-16-mode-15-times-new-roman'
        reference = self.native[cid]['inspection']
        for duplicate in (False, True):
            changed = copy.deepcopy(reference)
            if duplicate:
                changed['words'].append(copy.deepcopy(next(w for w in changed['words'] if w['text'] == 'SpruceLongNote120')))
                changed['tokens']['SpruceLongNote120'] += 1
            else:
                changed['words'] = [w for w in changed['words'] if w['text'] != 'SpruceLongNote120']
                changed['tokens'].pop('SpruceLongNote120')
            checks = pdf.correctness(self.cases[cid], reference, changed)
            self.assertFalse(next(c for c in checks if c['name'] == 'expected-visible-tokens')['passed'])
