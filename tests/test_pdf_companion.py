import copy
import json
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
from bench import common, pdf, runner


class PdfCompanionTests(unittest.TestCase):
    declaration = {'profile': {'review': 'final', 'comments': 'margin'},
                   'pageSizePt': [612, 792],
                   'requiredTokens': {'MapleBody': 1, 'MapleTail': 1}}
    info = {'geometry': [{'crop': [0, 0, 612, 792], 'media': [0, 0, 612, 792]}], 'words': [
        {'text': 'MapleBody', 'page': 1, 'rect': [72, 72, 120, 84], 'inkPixels': 30},
        {'text': 'MapleTail', 'page': 1, 'rect': [72, 90, 120, 102], 'inkPixels': 30},
        {'text': 'Reviewer', 'page': 1, 'rect': [72, 60, 120, 72]}]}

    def test_visible_source_tokens_allow_renderer_metadata(self):
        common.validate_pdf_companion(self.declaration)
        self.assertTrue(all(c['passed'] for c in pdf.companion_checks(self.declaration, self.info)))

    def test_missing_duplicated_and_off_page_text_fail(self):
        for mode in ('missing', 'duplicate', 'below-page', 'zero-area', 'enlarged-crop', 'enlarged-media'):
            info = copy.deepcopy(self.info)
            if mode == 'missing': info['words'].pop(1)
            elif mode == 'duplicate': info['words'].append(info['words'][1])
            elif mode == 'below-page': info['words'][1]['rect'] = [72, 790, 120, 805]
            elif mode.startswith('enlarged-'): info['geometry'][0][mode.removeprefix('enlarged-')][3] = 900
            else: info['words'][1]['rect'] = [72, 90, 72, 102]
            with self.subTest(mode=mode):
                self.assertFalse(all(c['passed'] for c in pdf.companion_checks(self.declaration, info)))

    def test_declaration_refuses_empty_invalid_or_unknown_checks(self):
        for change in ({'requiredTokens': {}}, {'requiredTokens': {'two words': 1}},
                       {'requiredTokens': {'MapleTail': True}}, {'requiredTokens': {'MapleTail': 0}},
                       {'profile': {'review': 'final', 'comments': 'unknown'}}, {'unknown': True},
                       {'pageSizePt': [612, float('inf')]}, {'pageSizePt': [612, 0]}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                common.validate_pdf_companion(self.declaration | change)

    def test_printed_artifact_is_bound_to_source_profile_pdf_and_runtime(self):
        primary = {'renderer': {'name': 'docxodus', 'commit': 'c' * 40, 'runtime': {'browserBuild': 'pinned'}}}
        for mode in ('ok', 'source', 'profile', 'runtime', 'renderer', 'hash', 'report-hash',
                     'hidden-primary', 'missing-pdf', 'missing-report', 'refusal'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                folder = Path(temp)
                original = {'status': 'complete', 'source': {'rawPackageBytesDigest': 'a' * 64},
                            'options': {'reviewProfile': 'final', 'commentProfile': 'hidden'},
                            'environment': {'verification': 'nodeVerified', 'fidelityTier': 'releaseBaselined',
                                            'rendererFingerprint': 'primary-profile', 'observed': {'browserBuild': 'pinned'}}}
                common.write_json(folder / 'production.json', original)
                request = {'profile': {'review': 'final', 'comments': 'hidden'}, 'inputSha256': 'a' * 64,
                           'report': str(folder / 'production.json'), 'output': str(folder / 'candidate.pdf')}
                def render(adapter, actual):
                    self.assertEqual(actual['profile'], self.declaration['profile'])
                    if mode == 'refusal': return {'status': 'failed', 'error': 'pagination failure'}
                    target = Path(actual['output'])
                    target.write_bytes(b'protocol PDF; inspection is separately mocked')
                    digest = common.digest(target)
                    production = copy.deepcopy(original)
                    production['environment']['rendererFingerprint'] = 'companion-profile'
                    production['options']['commentProfile'] = 'margin'
                    production['bindings'] = {'pdfDigest': digest}
                    response = {'status': 'ok', **copy.deepcopy(primary), 'pdfSha256': digest}
                    if mode == 'source': production['source']['rawPackageBytesDigest'] = 'b' * 64
                    if mode in ('profile', 'hidden-primary'): production['options']['commentProfile'] = 'hidden'
                    if mode == 'runtime': production['environment']['observed']['browserBuild'] = 'other'
                    if mode == 'renderer': response['renderer']['commit'] = 'd' * 40
                    if mode == 'hash': response['pdfSha256'] = '0' * 64
                    if mode == 'report-hash': production['bindings']['pdfDigest'] = '0' * 64
                    if mode == 'missing-pdf': target.unlink()
                    if mode != 'missing-report': common.write_json(Path(actual['report']), production)
                    return response
                with patch.object(runner.adapters, 'render', side_effect=render), patch.object(pdf, 'inspect_companion_pdf', return_value=self.info):
                    evidence = runner.render_companion('production-adapter', request, self.declaration, folder, primary)
                self.assertEqual(all(c['passed'] for c in evidence['checks']), mode == 'ok')

    def test_fixtures_require_every_authored_body_and_comment_word(self):
        cases = {c['id']: c for c in common.validate_registry()['cases'] if c['id'].startswith('comments-complete-')}
        self.assertEqual(len(cases), 7)
        w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        for case in cases.values():
            with ZipFile(common.ROOT / case['input']) as archive:
                parts = ['word/document.xml'] + ([] if case['pdfCompanion']['profile']['comments'] == 'hidden' else ['word/comments.xml'])
                words = Counter(' '.join(t.text or '' for name in parts for t in ET.fromstring(archive.read(name)).iter(w + 't')).split())
                self.assertEqual(case['pdfCompanion']['requiredTokens'], words)
        self.assertEqual(cases['comments-complete-single-900']['sha256'], cases['comments-complete-hidden-control']['sha256'])

    @unittest.skipUnless(all(shutil.which(name) for name in ('qpdf', 'pdftotext', 'pdffonts', 'pdftoppm')), 'Requires qpdf and Poppler')
    def test_real_pdf_requires_paint_and_rejects_extra_hidden_comment_text(self):
        # Original literal PDF, without a PDF authoring dependency. All four text modes
        # remain extractable; only the black unoccluded version paints the source words.
        for mode in ('visible', 'white', 'invisible', 'covered', 'yellow', 'yellow-covered', 'hidden-leak'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                text = 'MapleBody MapleTail' + (' ExtraComment' if mode == 'hidden-leak' else '')
                content = ('1 1 1 rg\n' if mode == 'white' else '') + 'BT /F1 12 Tf 72 720 Td '
                if mode == 'yellow': content = '1 .97647 .76863 rg 0 0 612 792 re f 0 0 0 rg\n' + content
                content += ('3 Tr ' if mode == 'invisible' else '') + '(' + text + ') Tj ET\n'
                if mode == 'covered': content += '1 1 1 rg 0 0 612 792 re f\n'
                if mode == 'yellow-covered': content += '1 .97647 .76863 rg 0 0 612 792 re f\n'
                objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
                    b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
                    b'<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman >>',
                    f'<< /Length {len(content)} >>\nstream\n{content}endstream'.encode()]
                data, offsets = b'%PDF-1.4\n', [0]
                for number, obj in enumerate(objects, 1):
                    offsets.append(len(data)); data += f'{number} 0 obj\n'.encode() + obj + b'\nendobj\n'
                start = len(data)
                data += b'xref\n0 6\n0000000000 65535 f \n' + b''.join(f'{n:010d} 00000 n \n'.encode() for n in offsets[1:])
                data += f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode()
                path = Path(folder) / 'source.pdf'; path.write_bytes(data)
                declaration = self.declaration | ({'exactInventory': True} if mode == 'hidden-leak' else {})
                checks = pdf.companion_checks(declaration, pdf.inspect_companion_pdf(path, declaration))
                self.assertEqual(all(c['passed'] for c in checks), mode in ('visible', 'yellow'))
                if mode in ('white', 'invisible', 'covered', 'yellow-covered'):
                    self.assertTrue(next(c for c in checks if c['name'].endswith('source-tokens'))['passed'])
                    self.assertFalse(next(c for c in checks if c['name'].endswith('source-paint'))['passed'])
