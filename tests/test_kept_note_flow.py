import copy
import hashlib
import json
import unittest
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from bench import common, pdf


class KeptNoteFlowContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.cases = {c['id']: c for c in common.validate_registry()['cases']
                     if c['id'].startswith(('heading-note-', 'heading-policy-note-', 'dense-chain-note-'))}
        cls.native = json.loads((cls.root / 'docs/results/kept-note-flow/native-word.json').read_text())['cases']
        cls.candidate = json.loads((cls.root / 'docs/results/kept-note-flow/candidate-proof.json').read_text())
        cls.w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

    def package_parts(self, cid):
        with ZipFile(self.root / self.cases[cid]['input']) as archive:
            return {n: archive.read(n) for n in archive.namelist()}

    def test_all_nineteen_native_inputs_and_public_exports_pass_the_complete_contract(self):
        self.assertEqual(len(self.cases), 19)
        self.assertEqual(set(self.cases), set(self.native))
        self.assertEqual(set(self.cases), set(self.candidate['cases']))
        for cid, case in self.cases.items():
            with self.subTest(case=cid):
                native = self.native[cid]
                candidate = self.candidate['cases'][cid]
                self.assertEqual(case['fonts'], ['Times New Roman'])
                self.assertEqual(case['sha256'], native['inputSha256'])
                self.assertEqual(case['sha256'], candidate['inputSha256'])
                self.assertEqual(hashlib.sha256((self.root / case['input']).read_bytes()).hexdigest(), native['inputSha256'])
                self.assertEqual(pdf.reference_failures(case, native['inspection'], 'word'), [])
                checks = pdf.correctness(case, native['inspection'], candidate['inspection'])
                self.assertTrue(all(c['passed'] for c in checks), checks)
                self.assertEqual(len(checks), candidate['mandatoryChecksPassed'])

    def test_implicit_package_defaults_and_all_authored_markers_survive(self):
        w = self.w
        for cid, case in self.cases.items():
            with self.subTest(case=cid):
                parts = self.package_parts(cid)
                self.assertEqual(len(parts), 6)
                self.assertNotIn('word/settings.xml', parts)
                doc = ET.fromstring(parts['word/document.xml'])
                notes = ET.fromstring(parts['word/footnotes.xml'])
                dense = cid.startswith('dense-')
                self.assertEqual(len(doc.findall('.//' + w + 'keepNext')), 8 if dense else int('keep-false' not in cid))
                self.assertEqual(len(doc.findall('.//' + w + 'keepLines')), 8 if dense else int('no-keep-lines' not in cid))
                self.assertEqual(len(notes.findall(w + 'footnote')), (8 if dense else 1) + (2 if 'separator-' in cid else 0))
                self.assertEqual(len(case['assertions']), 41 if dense else 28)
                # Every literal line is required, including the semantic number touching
                # each note's first token. No clipped/optional words or normalization.
                self.assertNotIn('clippedTokens', case)
                self.assertNotIn('pdfTextNormalization', case)
                for note in notes:
                    if note.get(w + 'type'):
                        continue
                    number = note.get(w + 'id')
                    for i, text in enumerate(note.iter(w + 't')):
                        self.assertEqual(case['tokens'][(number if i == 0 else '') + text.text], 1)
                    self.assertEqual(case['tokens'][number], 1)
                self.assertEqual({tuple(a['rect']) for a in case['assertions']}, {(0, 0, 400, 320)})
                self.assertTrue(all(a['adjudicated'] == 'word' and a['version'] == 2
                                    and a['tolerancePt'] == 0.0001 for a in case['assertions']))

    def test_keep_and_separator_controls_change_only_the_named_ooxml(self):
        for pitch in (20, 40):
            base = self.package_parts(f'heading-note-{pitch}pt-keep-true-times-new-roman')
            for variant in ('no-keep-lines', 'separator-15pt', 'separator-one-twip'):
                with self.subTest(pitch=pitch, variant=variant):
                    actual = self.package_parts(f'heading-policy-note-{pitch}pt-{variant}-times-new-roman')
                    if variant == 'no-keep-lines':
                        self.assertEqual(actual['word/document.xml'], base['word/document.xml'].replace(b'<w:keepLines/>', b''))
                        actual['word/document.xml'] = base['word/document.xml']
                    else:
                        notes = ET.fromstring(actual['word/footnotes.xml'])
                        for note in list(notes):
                            if note.get(self.w + 'type'):
                                self.assertEqual(note.find('.//' + self.w + 'spacing').get(self.w + 'line'), '300' if variant == 'separator-15pt' else '1')
                                notes.remove(note)
                        self.assertEqual(ET.tostring(notes), ET.tostring(ET.fromstring(base['word/footnotes.xml'])))
                        actual['word/footnotes.xml'] = base['word/footnotes.xml']
                    self.assertEqual(actual, base)

    def test_explicit_widow_controls_change_only_one_element(self):
        base = self.package_parts('heading-note-40pt-keep-true-times-new-roman')
        for variant, mark in [('off', b'<w:widowControl w:val="0"/>'), ('on', b'<w:widowControl/>')]:
            actual = self.package_parts(f'heading-policy-note-40pt-widow-{variant}-times-new-roman')
            self.assertEqual(actual['word/document.xml'].replace(mark, b''), base['word/document.xml'])
            actual['word/document.xml'] = base['word/document.xml']
            self.assertEqual(actual, base)

    def assert_wrong_page_fails(self, cid, marker, wrong_page):
        reference = self.native[cid]['inspection']
        changed = copy.deepcopy(reference)
        next(w for w in changed['words'] if w['text'] == marker)['page'] = wrong_page
        checks = pdf.correctness(self.cases[cid], reference, changed)
        self.assertTrue(any(not c['passed'] and c.get('declaration', {}).get('marker') == marker for c in checks))
        self.assertTrue(next(c for c in checks if c['name'] == 'expected-visible-tokens')['passed'])
        self.assertTrue(next(c for c in checks if c['name'] == 'page-count')['passed'])

    def test_dense_sixth_citation_cannot_be_deferred_with_its_whole_note(self):
        for pitch in (39, 40, 41):
            self.assert_wrong_page_fails(f'dense-chain-note-{pitch}pt-times-new-roman', 'WillowCite0601', 4)

    def test_widow_off_allows_sixteenth_line_on_page_three_but_default_and_on_do_not(self):
        self.assert_wrong_page_fails('heading-policy-note-40pt-widow-off-times-new-roman', 'WillowCite16', 4)
        self.assert_wrong_page_fails('heading-policy-note-40pt-widow-on-times-new-roman', 'WillowCite16', 3)
        self.assert_wrong_page_fails('heading-note-40pt-keep-true-times-new-roman', 'WillowCite16', 3)

    def test_missing_last_note_line_fails_even_if_first_note_and_citation_survive(self):
        cid = 'dense-chain-note-91pt-times-new-roman'
        reference = self.native[cid]['inspection']
        changed = copy.deepcopy(reference)
        changed['words'] = [w for w in changed['words'] if w['text'] != 'WillowNote08Part0301']
        changed['tokens'].pop('WillowNote08Part0301')
        checks = pdf.correctness(self.cases[cid], reference, changed)
        self.assertFalse(next(c for c in checks if c['name'] == 'expected-visible-tokens')['passed'])

    def test_same_page_duplicate_marker_fails(self):
        cid = 'dense-chain-note-40pt-times-new-roman'
        reference = self.native[cid]['inspection']
        changed = copy.deepcopy(reference)
        changed['words'].append(copy.deepcopy(next(w for w in changed['words'] if w['text'] == 'WillowCite0601')))
        changed['tokens']['WillowCite0601'] += 1
        checks = pdf.correctness(self.cases[cid], reference, changed)
        self.assertFalse(next(c for c in checks if c['name'] == 'expected-visible-tokens')['passed'])
        self.assertTrue(any(not c['passed'] and c.get('declaration', {}).get('marker') == 'WillowCite0601' for c in checks))
