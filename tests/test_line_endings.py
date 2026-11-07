import json
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile
from bench.common import ROOT

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


class LineEndingFixtures(unittest.TestCase):
    def test_raw_endings_and_explicit_carriage_return_controls_are_distinct(self):
        registry = json.loads((ROOT / 'fixtures/manifest.json').read_text())
        cases = {c['id'].removeprefix('text-line-endings-'): c for c in registry['cases']
                 if c['id'].startswith('text-line-endings-')}
        self.assertEqual(len(cases), 8)
        expected = {'body-lf': '\n', 'header-cr': '\n', 'footer-crlf': '\n', 'deleted-lf': '\n',
                    'spaces-control': ' ', 'break-control': '', 'encoded-cr-control': '\r',
                    'encoded-crlf-control': '\r\n'}
        for kind, case in cases.items():
            with ZipFile(ROOT / case['input']) as archive:
                part = 'word/header1.xml' if kind == 'header-cr' else 'word/footer1.xml' if kind == 'footer-crlf' else 'word/document.xml'
                raw = archive.read(part)
            root = ET.fromstring(raw)
            following = next(n for n in root.iter() if 'AspenFollowing' in (n.text or ''))
            self.assertEqual(following.text, expected[kind] + ' AspenFollowing')
            self.assertEqual(len(list(root.iter(W + 'tab'))), 1 if kind == 'break-control' or kind.startswith('encoded-cr') else 2)
            self.assertEqual(len(list(root.iter(W + 'br'))), int(kind == 'break-control'))
            if kind == 'header-cr': self.assertIn(b'>\r AspenFollowing', raw)
            if kind == 'footer-crlf': self.assertIn(b'>\r\n AspenFollowing', raw)
            if kind.startswith('encoded-cr'): self.assertIn(b'&#13;', raw)
            self.assertEqual(case['tokens']['AspenFollowing'], 1)
            self.assertEqual(case['profile']['review'], 'markup' if kind == 'deleted-lf' else 'final')
