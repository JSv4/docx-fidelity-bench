import json
import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bench import adapters
from bench.common import ROOT, digest, read_json, validate_registry


class PdfPreparationTests(unittest.TestCase):
    def test_pdf_receives_prepared_document_and_preserves_source_pair(self):
        cases = read_json(ROOT / 'fixtures/manifest.json')['cases']
        for case_id in ('builder-cross-type-style', 'compare-inline-customxml-final'):
            with self.subTest(case=case_id):
                self.assert_prepared_document(next(c for c in cases if c['id'] == case_id))

    def assert_prepared_document(self, case):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'candidate.pdf'
            request = {'protocol': 1, 'candidate': 'a' * 40, 'timeoutMs': 120000,
                       'input': str(ROOT / case['input']), 'inputSha256': case['sha256'],
                       'output': str(output), 'preparation': case['preparation']}

            def build(adapter, folder, preparation, path, candidate, timeout):
                self.assertEqual(preparation, case['preparation'])
                path.write_bytes((ROOT / case['input']).read_bytes())
                return {'protocol': 1, 'status': 'ok', 'outputSha256': digest(path)}

            def render(command, input, timeout):
                received = json.loads(input)
                self.assertEqual(received['input'], str(output.with_suffix('.docx')))
                self.assertEqual(received['inputSha256'], digest(received['input']))
                self.assertNotIn('preparation', received)
                output.write_bytes(b'candidate-pdf')
                return json.dumps({'protocol': 1, 'status': 'ok', 'pdfSha256': digest(output)})

            with patch.dict(os.environ, DOCXODUS_OPERATION_BUILD=directory), \
                    patch('bench.redline_build.verify_docxodus', return_value={'commit': 'a' * 40}), \
                    patch('bench.redline.run_candidate', side_effect=build), \
                    patch('bench.adapters.execute', side_effect=render):
                result = adapters.render(['node', str(ROOT / 'adapters/docxodus.mjs')], request)
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(result['preparation']['result']['outputSha256'], digest(output.with_suffix('.docx')))

    def test_preparation_rejects_unknown_operations_and_wrong_source_counts(self):
        registry = read_json(ROOT / 'fixtures/manifest.json')
        for operation, count in [('compare', 1), ('compare', 3), ('build', 1), ('unknown', 2)]:
            with self.subTest(operation=operation, count=count):
                changed = copy.deepcopy(registry)
                case = next(c for c in changed['cases'] if c.get('preparation'))
                case['preparation'] = {'operation': operation, 'inputs': [case['preparation']['inputs'][0]] * count}
                with self.assertRaisesRegex(ValueError, 'Invalid document preparation'):
                    validate_registry(changed)

    def test_missing_operation_build_cannot_silently_render_the_authored_reference(self):
        with patch.dict(os.environ, {}, clear=True), patch('bench.adapters.execute') as execute:
            result = adapters.render(['node', str(ROOT / 'adapters/docxodus.mjs')],
                                     {'preparation': {'operation': 'build', 'inputs': []}})
        self.assertEqual(result['status'], 'unmeasured')
        execute.assert_not_called()

    def test_duplicate_style_ids_fail_before_pdf_conversion(self):
        from zipfile import ZipFile
        case = next(c for c in read_json(ROOT / 'fixtures/manifest.json')['cases'] if c.get('preparation'))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'candidate.docx'
            with ZipFile(ROOT / case['input']) as original, ZipFile(output, 'w') as invalid:
                for name in original.namelist():
                    data = original.read(name)
                    if name == 'word/styles.xml':
                        data = data.replace(b'w:styleId="Separate"', b'w:styleId="Shared"')
                    invalid.writestr(name, data)
            with patch.dict(os.environ, DOCXODUS_OPERATION_BUILD=directory), \
                    patch('bench.redline_build.verify_docxodus', return_value={}), \
                    patch('bench.redline.run_candidate', return_value={'status': 'ok', 'outputSha256': digest(output)}), \
                    patch('bench.adapters.execute') as render:
                result = adapters.render(['node', str(ROOT / 'adapters/docxodus.mjs')],
                    {'candidate': 'a' * 40, 'timeoutMs': 120000, 'output': str(output.with_suffix('.pdf')),
                     'preparation': case['preparation']})
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['error']['check'], 'style-ids-unique')
            render.assert_not_called()
