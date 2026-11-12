import copy
import hashlib
import json
import unittest
from bench import font_fixtures, fonts


class FontDiagnosticTests(unittest.TestCase):
    def positive(self):
        case = {'sha256': 'a' * 64, 'pages': [
            {'family': 'Absent Birch Sans', 'text': 'Birch', 'missing': True, 'partial': False},
            {'family': 'Liberation Serif', 'text': 'Cedar', 'missing': False, 'partial': False}]}
        uses = [{'requestId': f'font-{i}', 'pageNumber': i, 'anchorId': f'p:body:{i}', 'fragmentId': f'p{i}',
                 'faces': [{'family': face, 'postscriptName': face, 'glyphCount': 5, 'isCustomFont': i == 2}],
                 'textDigest': 'b' * 64, 'textCodePointCount': 5}
                for i, face in [(1, 'FallbackFace'), (2, 'LiberationSerif')]]
        report = {'source': {'rawPackageBytesDigest': case['sha256']}, 'warnings': [{'code': 'font_unavailable'}],
                  'fonts': [{'requestId': f'font-{i}', 'requestedFamily': p['family'],
                             'status': 'missing' if p['missing'] else 'resolved', 'verified': not p['missing']}
                            for i, p in enumerate(case['pages'], 1)],
                  'fontObservation': {'status': 'observed', 'method': 'chromium-cdp', 'media': 'print',
                                      'fileIdentity': 'unavailable', 'uses': uses}}
        screen = copy.deepcopy(report); screen['fontObservation']['media'] = 'screen'
        for r in [report, screen]:
            value = json.dumps(r['fontObservation'], ensure_ascii=False, sort_keys=True, separators=(',', ':'))
            r['fontObservationDigest'] = hashlib.sha256(('docxodus:font-observation:v1\0' + value).encode()).hexdigest()
        page_map = {'rendererFingerprint': 'c' * 64, 'pages': [{}, {}],
                    'fragments': [{k: u[k] for k in ['pageNumber', 'anchorId', 'fragmentId']} for u in uses]}
        for r in [report, screen]:
            r['environment'] = {'rendererFingerprint': 'c' * 64}
            r['bindings'] = {'pageMapDigest': hashlib.sha256(json.dumps(page_map, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}
        html = [{'number': i, 'text': p['text']} for i, p in enumerate(case['pages'], 1)]
        info = {'geometry': [{'media': [0, 0, 612, 792], 'crop': [0, 0, 612, 792], 'rotation': 0}] * 2,
                'words': [{'page': i, 'text': p['text'], 'rect': [72, 72, 110, 85], 'inkPixels': 12}
                          for i, p in enumerate(case['pages'], 1)]}
        nodes = [{k: v for k, v in u.items() if k not in ['requestId', 'faces']} for u in uses]
        return [case, report, screen, page_map, html, info, [['FallbackFace'], ['LiberationSerif']], nodes, copy.deepcopy(page_map)]

    def test_original_registry(self):
        registry = font_fixtures.validate()
        self.assertEqual(len(registry['cases']), 7)
        self.assertEqual(sum(c['control'] for c in registry['cases']), 3)

    def test_independent_positive(self):
        self.assertTrue(all(c['passed'] for c in fonts.checks(*self.positive())))

    def test_pdf_subset_prefix_is_exact(self):
        value = 'name type\n---- ----\nABCDEF+RealFace TrueType\nabcDEF+KeepMe Type3\nLong+KeepMe Type3\nRealFace Type3\n'
        self.assertEqual(fonts.pdf_font_names(value), ['Long+KeepMe', 'RealFace', 'abcDEF+KeepMe'])

    def test_negative_mutations(self):
        mutations = {
            'missing-face': lambda a: a[1]['fontObservation']['uses'][0]['faces'].clear(),
            'wrong-face': lambda a: a[1]['fontObservation']['uses'][0]['faces'][0].update(postscriptName='GuessedFace'),
            'swapped-request': lambda a: a[1]['fontObservation']['uses'][0].update(requestId='font-2'),
            'swapped-page': lambda a: a[1]['fontObservation']['uses'][0].update(pageNumber=2),
            'missing-warning': lambda a: a[1]['warnings'].clear(),
            'missing-screen-warning': lambda a: a[2]['warnings'].clear(),
            'boolean-glyph-count': lambda a: a[1]['fontObservation']['uses'][0]['faces'][0].update(glyphCount=True),
            'boolean-code-point-count': lambda a: a[1]['fontObservation']['uses'][0].update(textCodePointCount=True),
            'non-boolean-custom': lambda a: a[1]['fontObservation']['uses'][0]['faces'][0].update(isCustomFont='true'),
            'promoted-verification': lambda a: a[1]['fonts'][0].update(verified=True),
            'invented-file': lambda a: a[1]['fontObservation']['uses'][0]['faces'][0].update(fileSha256='c' * 64),
            'missing-character': lambda a: a[5]['words'][0].update(text='Bir'),
            'unpainted-text': lambda a: a[5]['words'][0].update(inkPixels=0),
            'extra-html': lambda a: a[4][0].update(text='Birch hidden'),
            'wrong-source': lambda a: a[1]['source'].update(rawPackageBytesDigest='c' * 64),
            'wrong-binding': lambda a: a[1].update(fontObservationDigest='c' * 64),
            'dropped-text-node': lambda a: a[1]['fontObservation']['uses'].pop(),
            'duplicated-text-node': lambda a: a[1]['fontObservation']['uses'].append(copy.deepcopy(a[1]['fontObservation']['uses'][0])),
            'wrong-map-fingerprint': lambda a: a[3].update(rendererFingerprint='d' * 64),
            'wrong-screen-map-fingerprint': lambda a: a[8].update(rendererFingerprint='d' * 64),
            'wrong-map-digest': lambda a: a[1]['bindings'].update(pageMapDigest='d' * 64),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                args = self.positive(); mutate(args)
                if name in ['wrong-map-fingerprint', 'wrong-screen-map-fingerprint']:
                    index, r = (3, args[1]) if name == 'wrong-map-fingerprint' else (8, args[2])
                    r['bindings']['pageMapDigest'] = hashlib.sha256(json.dumps(args[index], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
                if name != 'wrong-binding':
                    # Keep the digest valid so it cannot mask a weak independent semantic check.
                    for report in args[1:3]:
                        value = json.dumps(report['fontObservation'], ensure_ascii=False, sort_keys=True, separators=(',', ':'))
                        report['fontObservationDigest'] = hashlib.sha256(('docxodus:font-observation:v1\0' + value).encode()).hexdigest()
                self.assertTrue(any(not c['passed'] for c in fonts.checks(*args)))


if __name__ == '__main__':
    unittest.main()
