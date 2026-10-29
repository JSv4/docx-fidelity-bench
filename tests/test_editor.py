import tempfile
import unittest
from pathlib import Path
from bench import editor, editor_fixtures
from bench.common import read_json, write_json
from bench.fixtures import package, para


class EditorDiagnosticContractTests(unittest.TestCase):
    def test_original_packages_and_exact_expectations_regenerate(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            declared = editor_fixtures.generate(root)
            self.assertEqual(declared, editor_fixtures.validate(root))
            self.assertEqual(5, sum(c['control'] for c in declared['cases']))
            first = read_json(root / 'fixtures/editor/manifest.json')
            first['cases'][0]['expected']['badge'] = '2 changes'
            write_json(root / 'fixtures/editor/manifest.json', first)
            with self.assertRaisesRegex(ValueError, 'declarations differ'):
                editor_fixtures.validate(root)

    def test_input_mutation_cannot_be_selected_away(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            registry = editor_fixtures.generate(root)
            (root / registry['cases'][-1]['input']).write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'input missing or changed'):
                editor_fixtures.validate(root)

    def test_literal_tab_text_does_not_satisfy_native_tab_expectation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'literal.docx'
            package(path, para(runs='<w:r><w:t>1.2\tCedar</w:t></w:r>'), styles_xml=editor_fixtures.STYLES)
            facts = editor.package_facts(path)
            case = {'action': 'copy', 'expected': {'text': '1.2\tCedar', 'tabs': 1, 'insertions': 0, 'rangeMarkers': 0}}
            observed = {'copiedPlain': '1.2\tCedar', 'pageErrors': []}
            result = editor.checks(case, observed, facts, [])
            self.assertTrue(next(c for c in result if c['name'] == 'text')['passed'])
            self.assertFalse(next(c for c in result if c['name'] == 'tabs')['passed'])

    def test_rich_clipboard_requires_full_text_and_full_formatting(self):
        case = {'action': 'copy-classes', 'expected': {'text': '1.2\tCedar', 'tabs': 1, 'insertions': 0, 'rangeMarkers': 0}}
        facts = dict(case['expected'])
        observed = {'copiedPlain': case['expected']['text'], 'richText': '1.2',
                    'richFormatted': True, 'pageErrors': []}
        partial = editor.checks(case, observed, facts, [])
        self.assertFalse(next(c for c in partial if c['name'] == 'native-rich-text')['passed'])
        observed.update(richText=case['expected']['text'], richFormatted=False)
        unformatted = editor.checks(case, observed, facts, [])
        self.assertFalse(next(c for c in unformatted if c['name'] == 'native-rich-paste')['passed'])

    def test_empty_revision_carrier_is_still_unresolved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'revision.docx'
            package(path, para(runs=f'<w:ins w:id="11" {editor_fixtures.STAMP}/><w:r><w:t>New Cedar clause</w:t></w:r>'),
                    styles_xml=editor_fixtures.STYLES)
            facts = editor.package_facts(path)
            case = {'action': 'revision-target', 'expected': {'text': 'New Cedar clause', 'tabs': 0, 'insertions': 0, 'rangeMarkers': 0}}
            checks = editor.checks(case, {'pageErrors': []}, facts, [])
            self.assertFalse(next(c for c in checks if c['name'] == 'insertions')['passed'])


if __name__ == '__main__':
    unittest.main()
