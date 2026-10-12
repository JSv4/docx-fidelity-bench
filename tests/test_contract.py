import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from bench import common, fixtures, metrics, pdf, runner


def raster(width=16, height=16, positions=()):
    pixels = bytearray(b'\xff' * (width * height * 3))
    for x, y in positions:
        pixels[(y * width + x) * 3:(y * width + x) * 3 + 3] = b'\0\0\0'
    return bytes(pixels)


def case(cid, category, score=100, passed=True, status='measured'):
    return {'id': cid, 'category': category, 'status': status, 'score': score if passed else 0, 'checks': [{'name': 'required', 'passed': passed}], 'pages': [{'score': score, 'ssim': score / 100, 'inkF1': score / 100}], 'close': score == 100 and passed}


def result(cases):
    contract = {'metric': metrics.CONTRACT, 'referenceDigest': 'fixed'}
    ids = [c['id'] for c in cases]
    return {'schema': 1, 'contract': contract, 'contractDigest': common.identity(contract), 'cases': cases, 'suite': {'cases': ids}, 'summary': metrics.aggregate(cases, ids)}


class MetricContract(unittest.TestCase):
    def test_identical_ink_is_100(self):
        image = raster(positions=[(5, 5), (6, 5), (5, 6)])
        self.assertEqual(metrics.page_metrics(image, image, 16, 16)['score'], 100)

    def test_identical_blank_is_100(self):
        image = raster()
        self.assertEqual(metrics.page_metrics(image, image, 16, 16)['score'], 100)

    def test_empty_candidate_loses_ink(self):
        self.assertEqual(metrics.page_metrics(raster(positions=[(5, 5)]), raster(), 16, 16)['score'], 0)

    def test_extra_candidate_ink_is_zero_for_blank_reference(self):
        self.assertEqual(metrics.page_metrics(raster(), raster(positions=[(5, 5)]), 16, 16)['score'], 0)

    def test_one_pixel_tolerance_does_not_align_ssim(self):
        m = metrics.page_metrics(raster(positions=[(5, 5)]), raster(positions=[(6, 5)]), 16, 16)
        self.assertEqual(m['inkF1'], 1)
        self.assertLess(m['ssim'], 1)

    def test_two_pixel_motion_is_not_tolerated(self):
        m = metrics.page_metrics(raster(positions=[(5, 5)]), raster(positions=[(7, 5)]), 16, 16)
        self.assertEqual(m['inkF1'], 0)

    def test_dilation_does_not_wrap_rows(self):
        m = metrics.page_metrics(raster(positions=[(15, 5)]), raster(positions=[(0, 6)]), 16, 16)
        self.assertEqual(m['inkF1'], 0)

    def test_threshold_is_exact(self):
        self.assertEqual(list(metrics.ink_mask(bytes([231, 255, 255, 230, 255, 255]))), [0, 1])

    def test_color_change_is_measured(self):
        self.assertLess(metrics.page_metrics(bytes([255, 0, 0]), bytes([0, 0, 255]), 1, 1)['ssim'], 1)

    def test_single_window_ssim_matches_constant_image_formula(self):
        self.assertAlmostEqual(metrics.ssim(b'\0' * 9, b'\xff' * 9, 3, 1), 6.5025 / (65025 + 6.5025), places=12)

    def test_ppm_keeps_whitespace_valued_first_pixel(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'page.ppm'
            path.write_bytes(b'P6\n# own test\n1 1\n255\n\x0a\x20\xff')
            self.assertEqual(metrics.read_ppm(path), (1, 1, b'\x0a\x20\xff'))

    def test_ppm_rejects_truncation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'page.ppm'
            path.write_bytes(b'P6\n1 1\n255\n\0')
            with self.assertRaises(ValueError):
                metrics.read_ppm(path)


class CoverageContract(unittest.TestCase):
    def test_worst_page_wins(self):
        self.assertEqual(metrics.case_score([{'score': 97.1}, {'score': 92.9}], [{'passed': True}]), 92.9)

    def test_mandatory_failure_zeroes_case(self):
        self.assertEqual(metrics.case_score([{'score': 100}], [{'passed': False}]), 0)

    def test_missing_page_zeroes_case(self):
        self.assertEqual(metrics.case_score([{'score': 100}, {'score': 0, 'unmatched': 'reference'}], [{'passed': False}]), 0)

    def test_categories_receive_equal_weight(self):
        cases = [case('a', 'columns', 99), case('b', 'columns', 97), case('c', 'notes', 60), case('d', 'tables', 100)]
        self.assertEqual(metrics.aggregate(cases, ['a', 'b', 'c', 'd'])['score'], 86)

    def test_conversion_failure_stays_in_denominator(self):
        cases = [case('a', 'columns', 99), case('b', 'columns', 97), case('c', 'notes', 0, False), case('d', 'tables', 100)]
        self.assertEqual(metrics.aggregate(cases, ['a', 'b', 'c', 'd'])['score'], 66)

    def test_absent_case_blocks_headline(self):
        self.assertIsNone(metrics.aggregate([case('a', 'columns')], ['a', 'b'])['score'])

    def test_unmeasured_case_blocks_headline(self):
        self.assertIsNone(metrics.aggregate([case('a', 'columns', status='unmeasured')], ['a'])['score'])

    def test_duplicate_case_blocks_headline(self):
        self.assertIsNone(metrics.aggregate([case('a', 'columns'), case('a', 'columns')], ['a'])['score'])

    def test_changed_reference_cannot_pass_regression(self):
        a = result([case('a', 'columns')])
        b = copy.deepcopy(a)
        b['contract']['referenceDigest'] = 'changed'
        b['contractDigest'] = common.identity(b['contract'])
        with self.assertRaises(ValueError):
            runner.compare(a, b, 0)

    def test_changed_metric_cannot_pass_regression(self):
        a = result([case('a', 'columns')])
        b = copy.deepcopy(a)
        b['contract']['metric'] = {'version': 2}
        b['contractDigest'] = common.identity(b['contract'])
        with self.assertRaises(ValueError):
            runner.compare(a, b, 0)

    def test_incomplete_cannot_pass_regression(self):
        a = result([case('a', 'columns', status='unmeasured')])
        with self.assertRaises(ValueError):
            runner.compare(a, a, 0)

    def test_forged_coverage_is_rejected(self):
        a = result([case('a', 'columns', status='unmeasured')])
        a['summary']['complete'] = True
        with self.assertRaises(ValueError):
            runner.validate_result(a)

    def test_per_page_regression_is_retained(self):
        a, b = result([case('a', 'columns', 90)]), result([case('a', 'columns', 89)])
        self.assertTrue(runner.compare(a, b, 0))

    def test_negative_tolerance_is_rejected(self):
        a = result([case('a', 'columns')])
        with self.assertRaises(ValueError):
            runner.compare(a, a, -1)


class PdfContract(unittest.TestCase):
    def region_check(self, x=100, version=2, page=1):
        geometry = [{'media': [0, 0, 612, 792], 'crop': [0, 0, 612, 792], 'rotation': 0}]
        reference = {'geometry': geometry, 'fonts': ['LiberationSerif'], 'tokens': {'Marker': 1}, 'words': [{'text': 'Marker', 'page': 1, 'rect': [100, 200, 130, 212]}]}
        candidate = copy.deepcopy(reference)
        candidate['words'][0] = {'text': 'Marker', 'page': page, 'rect': [x, 200, x + 30, 212]}
        declaration = {'fonts': ['Liberation Serif'], 'tokens': {'Marker': 1}, 'assertions': [{'type': 'marker-region', 'version': version, 'marker': 'Marker', 'occurrence': 1, 'page': 'reference', 'rect': [100, 190, 140, 220], 'tolerancePt': 0.0001}]}
        return pdf.correctness(declaration, reference, candidate)[-1]['passed']

    def test_region_tolerates_pdf_serialization_rounding(self):
        self.assertTrue(self.region_check(x=99.999987))

    def test_region_rejects_position_outside_declared_tolerance(self):
        self.assertFalse(self.region_check(x=99.999))

    def test_region_tolerance_cannot_change_page_membership(self):
        self.assertFalse(self.region_check(page=2))

    def test_region_version_one_keeps_exact_boundaries(self):
        self.assertFalse(self.region_check(x=99.999987, version=1))

    def position_checks(self, x=100, y=200, page=1):
        geometry = [{'media': [0, 0, 612, 792], 'crop': [0, 0, 612, 792], 'rotation': 0}]
        reference = {'geometry': geometry, 'fonts': ['LiberationSerif'], 'tokens': {'Note': 1}, 'words': [{'text': 'Note', 'page': 1, 'rect': [100, 200, 130, 212]}]}
        candidate = copy.deepcopy(reference)
        candidate['words'][0] = {'text': 'Note', 'page': page, 'rect': [x, y, x + 30, y + 12]}
        declaration = {'fonts': ['Liberation Serif'], 'tokens': {'Note': 1}, 'assertions': [{'type': 'marker-reference-position', 'version': 1, 'marker': 'Note', 'tolerancePt': 0.5}]}
        return pdf.correctness(declaration, reference, candidate)[-1]['passed']

    def test_marker_reference_position_tolerates_declared_distance(self):
        self.assertTrue(self.position_checks(x=100.25, y=200.25))

    def test_marker_reference_position_rejects_moved_note(self):
        self.assertFalse(self.position_checks(y=202))

    def test_marker_reference_position_rejects_wrong_page(self):
        self.assertFalse(self.position_checks(page=2))

    def doc(self, extra=None):
        page = {'/Parent': '2 0 R'}
        page.update(extra or {})
        return {'pages': [{'object': '1 0 R'}], 'qpdf': [{}, {'obj:1 0 R': {'value': page}, 'obj:2 0 R': {'value': {'/MediaBox': [0, 0, 612, 792], '/Rotate': 90}}}]}

    def test_inherited_boxes_and_rotation(self):
        self.assertEqual(pdf.geometries(self.doc())[0], {'media': [0, 0, 612, 792], 'crop': [0, 0, 612, 792], 'rotation': 90, 'userUnit': 1})

    def test_user_unit_changes_physical_size(self):
        self.assertEqual(pdf.geometries(self.doc({'/UserUnit': 2}))[0]['media'], [0, 0, 1224, 1584])

    def test_invalid_boxes_are_rejected(self):
        with self.assertRaises(ValueError):
            pdf.geometries(self.doc({'/MediaBox': [0, 0, 0, 792]}))

    def test_page_tree_cycle_is_rejected(self):
        doc = self.doc()
        doc['qpdf'][1]['obj:2 0 R']['value'] = {'/Parent': '1 0 R'}
        with self.assertRaises(ValueError):
            pdf.geometries(doc)

    def test_ambiguous_marker_fails(self):
        with self.assertRaises(ValueError):
            pdf.marker({'words': [{'text': 'Marker'}, {'text': 'Marker'}]}, 'Marker')

    def test_lost_note_fails_inventory(self):
        self.assertFalse(pdf.inventory_check({'tokens': {'Body': 1}}, {'tokens': {'Body': 1, 'Note': 1}}))

    def test_duplicate_text_fails_inventory(self):
        self.assertFalse(pdf.inventory_check({'tokens': {'Body': 2}}, {'tokens': {'Body': 1}}))

    def test_wrong_font_fails(self):
        self.assertFalse(pdf.font_check({'fonts': ['OtherSerif']}, ['Liberation Serif']))

    def test_subset_font_name_is_recognized(self):
        self.assertTrue(pdf.font_check({'fonts': ['LiberationSerif-Bold']}, ['Liberation Serif']))


class RegistryContract(unittest.TestCase):
    def test_registry_is_valid(self):
        self.assertEqual(len(common.validate_registry()['cases']), 14)

    def test_textbox_pair_differs_only_in_zero_relative_dimensions(self):
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile
        registry = common.validate_registry()
        records = {c['id']: c for c in registry['cases']}
        pair = [records['drawings-textbox-' + suffix] for suffix in ('absolute', 'zero-relative')]
        wp = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
        wp14 = '{http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing}'
        with ZipFile(common.ROOT / pair[0]['input']) as control, ZipFile(common.ROOT / pair[1]['input']) as zero:
            self.assertEqual(control.namelist(), zero.namelist())
            for name in control.namelist():
                if name != 'word/document.xml':
                    self.assertEqual(control.read(name), zero.read(name))
            original = ET.fromstring(control.read('word/document.xml'))
            actual = ET.fromstring(zero.read('word/document.xml'))
            anchor = actual.find('.//' + wp + 'anchor')
            self.assertEqual(anchor.find(wp + 'extent').attrib, {'cx': '2743200', 'cy': '914400'})
            for axis, percent in [('H', 'Width'), ('V', 'Height')]:
                relative = anchor.find(wp14 + 'sizeRel' + axis)
                self.assertEqual(relative.find(wp14 + 'pct' + percent).text, '0')
                anchor.remove(relative)
            self.assertEqual(ET.tostring(original), ET.tostring(actual))
        self.assertEqual(pair[0]['tokens'], pair[1]['tokens'])
        self.assertEqual(pair[0]['assertions'], pair[1]['assertions'])
        self.assertEqual(registry['suite']['id'], 'core-v4')

    def test_unknown_assertion_is_rejected(self):
        registry = common.read_json(common.ROOT / 'fixtures/manifest.json')
        registry['cases'][0]['assertions'].append({'type': 'unimplemented', 'version': 1})
        with self.assertRaises(ValueError):
            common.validate_registry(registry)

    def test_unknown_version_is_rejected(self):
        registry = common.read_json(common.ROOT / 'fixtures/manifest.json')
        registry['schema'] = 2
        with self.assertRaises(ValueError):
            common.validate_registry(registry)

    def test_next_suite_version_is_extensible(self):
        registry = common.read_json(common.ROOT / 'fixtures/manifest.json')
        registry['suite']['version'] = 4
        self.assertEqual(common.validate_registry(registry)['suite']['version'], 4)

    def test_stale_input_digest_is_rejected(self):
        registry = common.read_json(common.ROOT / 'fixtures/manifest.json')
        registry['cases'][0]['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            common.validate_registry(registry)

    def test_stale_generator_digest_is_rejected(self):
        registry = common.read_json(common.ROOT / 'fixtures/manifest.json')
        registry['cases'][0]['generator']['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            common.validate_registry(registry)

    def test_escape_path_is_rejected(self):
        with self.assertRaises(ValueError):
            common.contained(common.ROOT, '../../outside.docx')

    def test_duplicate_json_properties_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'data.json'
            path.write_text('{"id":1,"id":2}')
            with self.assertRaises(ValueError):
                common.read_json(path)

    def test_fixtures_regenerate_exactly(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(fixtures, 'ROOT', Path(temp)):
            generated = fixtures.generate()
            expected = common.read_json(common.ROOT / 'fixtures/manifest.json')
            self.assertEqual(generated, expected)
            for case_record in expected['cases']:
                self.assertEqual((Path(temp) / case_record['input']).read_bytes(), (common.ROOT / case_record['input']).read_bytes())


if __name__ == '__main__':
    unittest.main()
