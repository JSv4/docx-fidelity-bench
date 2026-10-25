import copy
import hashlib
import json
import unittest
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from bench import common, pdf


class NoteTableFlowContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.cases = {c['id']: c for c in common.validate_registry()['cases']
                     if c['id'].startswith('notes-table-flow-')}
        cls.native = json.loads((cls.root / 'docs/results/note-table-flow/native-word.json').read_text())['cases']

    def test_eight_native_references_bind_the_exact_generated_inputs(self):
        self.assertEqual(len(self.cases), 8)
        self.assertEqual(set(self.cases), set(self.native))
        for cid, case in self.cases.items():
            with self.subTest(case=cid):
                capture = self.native[cid]
                self.assertEqual(case['fonts'], ['Times New Roman'])
                self.assertEqual(case['sha256'], capture['inputSha256'])
                self.assertEqual(hashlib.sha256((self.root / case['input']).read_bytes()).hexdigest(), capture['inputSha256'])
                self.assertEqual(pdf.reference_failures(case, capture['inspection'], 'word'), [])

    def test_wrapped_nested_and_ordinary_controls_keep_their_source_shapes(self):
        w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        for cid, case in self.cases.items():
            with self.subTest(case=cid), ZipFile(self.root / case['input']) as archive:
                notes = ET.fromstring(archive.read('word/footnotes.xml'))
                note = next(n for n in notes if n.get(w + 'id') == '1')
                outer = note.find(w + 'tbl')
                self.assertIsNotNone(outer)
                self.assertEqual(outer.find('.//' + w + 'tbl') is not None, '-nested' in cid)
                count = 3 if ('wrapped-control' in cid or 'tall-row-control' in cid) else 80
                columns = 2 if 'wrapped' in cid else 1
                for col in range(1, columns + 1):
                    for row in range(1, count + 1):
                        self.assertEqual(case['tokens'][f'Pine{col}N{row:03d}'], 1)
                markers = {a['marker'] for a in case['assertions'] if a.get('adjudicated') == 'word'}
                self.assertEqual(len(markers), 61 + columns * count)
                self.assertEqual(len(self.native[cid]['inspection']['geometry']), 2 if count == 3 else 4)

    def test_missing_last_note_line_fails_even_when_citation_and_first_line_survive(self):
        cid = 'notes-table-flow-nested-times-new-roman'
        reference = self.native[cid]['inspection']
        changed = copy.deepcopy(reference)
        changed['words'] = [w for w in changed['words'] if w['text'] != 'Pine1N080']
        changed['tokens'].pop('Pine1N080')
        checks = pdf.correctness(self.cases[cid], reference, changed)
        self.assertFalse(next(c for c in checks if c['name'] == 'expected-visible-tokens')['passed'])

    def test_wrong_continuation_page_fails_with_unchanged_tokens_and_page_count(self):
        cid = 'notes-table-flow-nested-times-new-roman'
        reference = self.native[cid]['inspection']
        changed = copy.deepcopy(reference)
        next(w for w in changed['words'] if w['text'] == 'Pine1N035')['page'] = 1
        checks = pdf.correctness(self.cases[cid], reference, changed)
        self.assertTrue(any(not c['passed'] and c.get('declaration', {}).get('marker') == 'Pine1N035' for c in checks))
        self.assertTrue(next(c for c in checks if c['name'] == 'expected-visible-tokens')['passed'])
        self.assertTrue(next(c for c in checks if c['name'] == 'page-count')['passed'])
