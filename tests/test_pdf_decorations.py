"""PDF text leaders are decoration only under an explicit, source-verified fixture policy."""
from copy import deepcopy
from collections import Counter
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile
from unittest.mock import patch
from bench import pdf, common, runner, metrics

POLICY = 'isolated-dot-leaders-v1'


class DecorativePdfTextContract(unittest.TestCase):
    def info(self):
        words = [{'text': t, 'page': 1, 'rect': [x, 72, x + 10, 84]}
                 for x, t in enumerate(['CedarTitle', '...', '7', '..', 'title...7', 'extra'])]
        return {'words': words, 'tokens': dict(Counter(w['text'] for w in words)), 'fonts': ['LiberationSerif'], 'geometry': []}

    def test_only_isolated_three_or_more_dots_are_decorative(self):
        raw = self.info()
        original = deepcopy(raw)
        actual = pdf.normalize_text(raw, POLICY)
        self.assertEqual(raw, original)
        self.assertEqual(actual['words'], original['words'])
        self.assertEqual(actual['tokens'], {'CedarTitle': 1, '7': 1, '..': 1, 'title...7': 1, 'extra': 1})
        self.assertEqual(actual['decorativeWords'], [original['words'][1]])
        self.assertEqual(actual['pdfTextNormalization'], POLICY)

    def test_default_policy_retains_literal_ellipsis(self):
        raw = self.info()
        self.assertEqual(pdf.normalize_text(raw, None), raw)

    def test_missing_numbers_and_extra_words_still_fail_exact_inventory(self):
        actual = pdf.normalize_text(self.info(), POLICY)
        expected = {'tokens': {'CedarTitle': 1, '7': 1, '..': 1, 'title...7': 1, 'extra': 1}}
        self.assertTrue(pdf.inventory_check(actual, expected))
        self.assertFalse(pdf.inventory_check(actual, {'tokens': dict(expected['tokens'], **{'7': 2})}))
        self.assertFalse(pdf.inventory_check(actual, {'tokens': {'CedarTitle': 1, '7': 1}}))

    def test_unknown_policy_is_rejected(self):
        for policy in ['ignore-punctuation', '', [], {}, True, 1]:
            with self.subTest(policy=policy), self.assertRaises(ValueError): pdf.normalize_text(self.info(), policy)

    def test_fixture_policy_requires_authored_dot_tabs_without_literal_ellipses(self):
        for leader, text, valid in [('dot', 'Cedar title', True), ('none', 'Cedar title', False), ('dot', 'Cedar...title', False)]:
            with self.subTest(leader=leader, text=text), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                path = root / 'input.docx'
                with ZipFile(path, 'w') as archive:
                    archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:pPr><w:tabs><w:tab w:val="right" w:leader="' + leader + '" w:pos="9000"/></w:tabs></w:pPr><w:r><w:t>' + text + '</w:t></w:r><w:r><w:tab/></w:r></w:p></w:body></w:document>')
                case = {'input': 'input.docx', 'pdfTextNormalization': POLICY}
                if valid:
                    common.validate_pdf_text_policy(case, root)
                    with patch.object(common, 'ROOT', root): common.validate_pdf_text_policy(case)
                else:
                    with self.assertRaises(ValueError): common.validate_pdf_text_policy(case, root)

    def test_case_inspection_applies_the_declared_policy(self):
        with patch.object(pdf, 'inspect_pdf', return_value=self.info()) as read:
            info = pdf.inspect_case_pdf('candidate.pdf', {'pdfTextNormalization': POLICY})
        read.assert_called_once_with('candidate.pdf')
        self.assertNotIn('...', info['tokens'])
        self.assertIn('7', info['tokens'])

    def test_measurement_contract_rejects_unknown_or_malformed_policy_identity(self):
        outcome = {'id': 'a', 'category': 'paragraphs', 'status': 'measured', 'score': 100,
                   'checks': [{'name': 'required', 'passed': True},
                              {'name': 'declared-pdf-text-normalization', 'passed': True}],
                   'pages': [{'score': 100, 'ssim': 1, 'inkF1': 1}], 'close': True}
        contract = {'metric': metrics.CONTRACT, 'referenceDigest': 'fixed',
                    'pdfTextNormalizations': {'a': POLICY}, 'pdfTextInspectorVersion': 1,
                    'pdfTextInspectorSha256': common.digest(Path(pdf.__file__))}
        result = {'schema': 1, 'contract': contract, 'contractDigest': common.identity(contract),
                  'suite': {'cases': ['a']}, 'cases': [outcome], 'summary': metrics.aggregate([outcome], ['a'])}
        runner.validate_result(result)
        absent = deepcopy(result)
        absent['cases'][0]['checks'].pop()
        with self.assertRaisesRegex(ValueError, 'PDF text normalization observation'):
            runner.validate_result(absent)
        for field, value in [('pdfTextNormalizations', []), ('pdfTextNormalizations', {'a': True}),
                             ('pdfTextNormalizations', {'unknown': POLICY}),
                             ('pdfTextInspectorVersion', True), ('pdfTextInspectorSha256', 'bad')]:
            changed = deepcopy(result)
            changed['contract'][field] = value
            changed['contractDigest'] = common.identity(changed['contract'])
            with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, 'PDF text normalization'):
                runner.validate_result(changed)


class PdfLeaderRunnerIntegration(unittest.TestCase):
    """Fake PDF I/O leaves the actual inspector policy, mandatory checks and runner wiring live."""
    def measured(self, candidate_dots=False, missing_number=False, shifted_number=False):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'input.docx'; source.write_bytes(b'contract source')
            (root / 'reference.pdf').write_bytes(b'contract reference')
            raster = root / 'page.ppm'; raster.write_bytes(b'P6\n1 1\n255\n\xff\xff\xff')
            case = {'id': 'sample', 'category': 'paragraphs', 'input': 'input.docx', 'sha256': common.digest(source),
                    'profile': {'review': 'final', 'comments': 'hidden'}, 'fonts': ['Liberation Serif'],
                    'tokens': {'CedarTitle': 1, '7': 1}, 'pdfTextNormalization': POLICY,
                    'assertions': [{'type': 'marker-reference-position', 'version': 1, 'marker': '7', 'tolerancePt': 0.5}]}
            registry = {'suite': {'id': 'contract', 'version': 1, 'cases': ['sample']}, 'cases': [case]}
            common.write_json(root / 'bundle.json', {'track': 'libreoffice',
                'cases': {'sample': {'eligible': True, 'pdf': 'reference.pdf'}}})
            def raw(dots, missing=False, shifted=False):
                words = [{'text': 'CedarTitle', 'page': 1, 'rect': [72, 72, 140, 84]}]
                if dots: words.append({'text': '............', 'page': 1, 'rect': [140, 72, 500, 84]})
                if not missing: words.append({'text': '7', 'page': 1, 'rect': [400 if shifted else 510, 72, 522, 84]})
                return {'words': words, 'tokens': dict(Counter(w['text'] for w in words)), 'fonts': ['LiberationSerif'],
                        'geometry': [{'media': [0, 0, 612, 792], 'crop': [0, 0, 612, 792], 'rotation': 0, 'userUnit': 1}]}
            def inspect(path):
                return raw(True) if Path(path).name == 'reference.pdf' else raw(candidate_dots, missing_number, shifted_number)
            def render(adapter, request):
                Path(request['output']).write_bytes(b'contract candidate')
                return {'status': 'ok', 'renderer': {'name': 'contract'}}
            with patch.object(runner, 'ROOT', root), patch.object(runner, 'validate_registry', return_value=registry), \
                 patch.object(runner, 'environment', return_value={'contract': {}, 'fontDirectories': []}), \
                 patch.object(runner, 'validate_bundle'), patch.object(runner.adapters, 'render', side_effect=render), \
                 patch.object(runner.pdf, 'inspect_pdf', side_effect=inspect), \
                 patch.object(runner.pdf, 'rasterize', return_value=[raster]):
                result = runner.run(root / 'run', root / 'bundle.json', 'contract', 'source')
            runner.validate_result(result)
            return result

    def test_text_and_graphic_leaders_share_strict_content_and_raw_geometry_checks(self):
        for dots in (False, True):
            with self.subTest(text_leader=dots):
                result = self.measured(candidate_dots=dots)
                self.assertEqual(result['summary']['score'], 100)
                self.assertEqual(result['contract']['pdfTextNormalizations'], {'sample': POLICY})
                check = next(c for c in result['cases'][0]['checks'] if c['name'] == 'expected-visible-tokens')
                self.assertEqual(len(check['decorativeWords']), int(dots))

    def test_normalization_does_not_hide_a_missing_page_number(self):
        good, bad = self.measured(), self.measured(missing_number=True)
        self.assertEqual(bad['summary']['score'], 0)
        self.assertIn('sample: mandatory check failure', runner.compare(good, bad, 0))

    def test_normalization_does_not_move_a_misaligned_page_number(self):
        bad = self.measured(shifted_number=True)
        self.assertEqual(bad['summary']['score'], 0)
        check = next(c for c in bad['cases'][0]['checks'] if 'marker-reference-position' in c['name'])
        self.assertFalse(check['passed'])
