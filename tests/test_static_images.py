import copy
import unittest

from bench import audit, fixtures, pdf


class StaticImages(unittest.TestCase):
    def test_color_measurement_keeps_antialiasing_and_excludes_black_text(self):
        pixels = bytes([255, 255, 255, 48, 96, 160, 0, 0, 0, 248, 248, 248,
                        255, 255, 255, 152, 176, 208, 255, 0, 0, 248, 248, 248])
        observed = pdf.color_region(4, 2, pixels, [48, 96, 160])
        self.assertEqual(observed['boundsPt'], [.75, 0, 1.5, 1.5])
        self.assertAlmostEqual(observed['coverage'], 1.5, delta=.01)
        self.assertEqual(pdf.color_region(1, 1, b'\0\0\0', [0, 0, 1]), {'boundsPt': None, 'coverage': 0})

    def test_only_exact_authored_legacy_image_bytes_are_admitted(self):
        for name, payload in fixtures.static_image_assets().items():
            self.assertTrue(audit.permitted_bytes(payload), name)
            if name != 'png':
                self.assertFalse(audit.permitted_bytes(payload + b'\0extra'), name)
                self.assertFalse(audit.permitted_bytes(payload[:-1]), name)

    def test_color_geometry_rejects_missing_shifted_and_distorted_paint(self):
        declaration = {'type': 'color-reference-geometry', 'version': 1, 'page': 1,
                       'rgb': [48, 96, 160], 'tolerancePt': 1.5, 'coverageTolerance': 0.08}
        case = {'tokens': {'PoplarReceipt': 1}, 'fonts': ['Liberation Serif'], 'assertions': [declaration]}
        good = {'tokens': case['tokens'], 'fonts': ['LiberationSerif'], 'words': [],
                'geometry': [{'rotation': 0, 'media': [0, 0, 330, 420], 'crop': [0, 0, 330, 420]}],
                'colorRegions': [{'page': 1, 'rgb': [48, 96, 160], 'boundsPt': [42, 116, 126, 173], 'coverage': 1100}]}
        self.assertTrue(all(check['passed'] for check in pdf.correctness(case, good, good)))
        for defect in ('missing', 'shifted', 'thick', 'thin', 'wrong-color'):
            candidate = copy.deepcopy(good)
            if defect == 'missing': candidate['colorRegions'][0].update(boundsPt=None, coverage=0)
            if defect == 'shifted': candidate['colorRegions'][0]['boundsPt'][0] += 4
            if defect == 'thick': candidate['colorRegions'][0]['coverage'] *= 1.5
            if defect == 'thin': candidate['colorRegions'][0]['coverage'] *= 0.7
            if defect == 'wrong-color': candidate['colorRegions'][0]['rgb'] = [0, 0, 0]
            self.assertTrue(any(not c['passed'] for c in pdf.correctness(case, good, candidate)), defect)
        missing = copy.deepcopy(good)
        missing['colorRegions'][0].update(boundsPt=None, coverage=0)
        self.assertTrue(any(not c['passed'] for c in pdf.correctness(case, missing, missing)))

    def test_each_figure_has_an_independent_geometry_contract(self):
        from bench import common
        cases = [case for case in common.validate_registry()['cases'] if case['id'].startswith('images-static-')]
        self.assertEqual(len(cases), 10)
        for case in cases:
            self.assertEqual([a['rgb'] for a in case['assertions']], [[48, 96, 160], [160, 64, 96]])
            reference = {'colorRegions': [dict(page=1, rgb=a['rgb'], boundsPt=a.get('boundsPt', [10, 10, 40, 80]),
                                              coverage=a.get('coverage', 500)) for a in case['assertions']]}
            shifted = copy.deepcopy(reference)
            shifted['colorRegions'][1]['boundsPt'][1] += 9
            shifted['colorRegions'][1]['boundsPt'][3] += 9
            self.assertEqual([pdf.color_geometry_pass(a, reference, shifted) for a in case['assertions']], [True, False])

    def test_absolute_word_geometry_does_not_follow_a_disagreeing_reference(self):
        declaration = {'type': 'color-geometry', 'version': 1, 'page': 1,
                       'rgb': [48, 96, 160], 'boundsPt': [10, 20, 40, 80], 'coverage': 500,
                       'tolerancePt': 1.5, 'coverageTolerance': 0.08, 'adjudicated': 'word'}
        good = {'colorRegions': [dict(page=1, rgb=declaration['rgb'], boundsPt=declaration['boundsPt'], coverage=500)]}
        wrong = copy.deepcopy(good)
        wrong['colorRegions'][0]['boundsPt'] = [19, 20, 49, 80]
        self.assertTrue(pdf.color_geometry_pass(declaration, wrong, good))
        self.assertFalse(pdf.color_geometry_pass(declaration, wrong, wrong))
        self.assertFalse(pdf.color_geometry_pass(declaration, good, {'colorRegions': []}))
        thick = copy.deepcopy(good)
        thick['colorRegions'][0]['coverage'] *= 1.5
        self.assertFalse(pdf.color_geometry_pass(declaration, good, thick))
        self.assertFalse(pdf.color_geometry_pass(declaration, good, {'colorRegions': good['colorRegions'] * 2}))
        case = {'assertions': [declaration]}
        self.assertEqual(pdf.binding_case(case, 'libreoffice', reproduces_reference=True)['assertions'], [])
        self.assertEqual(pdf.binding_case(case, 'libreoffice')['assertions'], [declaration])

    def test_absolute_geometry_declarations_reject_invalid_measurements(self):
        from bench import common
        registry = common.validate_registry()
        case = next(c for c in registry['cases'] if c['id'] == 'images-static-body-wmf')
        registry['cases'] = [case]
        registry['suite']['cases'] = [case['id']]
        for key, value in [('boundsPt', [0, 0, 1]), ('boundsPt', [0, 0, -1, 1]),
                           ('boundsPt', [0, float('nan'), 1, 1]), ('boundsPt', [False, 0, 1, 1]),
                           ('coverage', 0), ('coverage', float('inf')), ('coverage', True),
                           ('rgb', [255, 0, 0]), ('rgb', [20, 20, 20]), ('page', True),
                           ('tolerancePt', 2.01), ('coverageTolerance', .101), ('adjudicated', 'libreoffice')]:
            changed = copy.deepcopy(registry)
            changed['cases'][0]['assertions'][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                common.validate_registry(changed)


if __name__ == '__main__':
    unittest.main()
