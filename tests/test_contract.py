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

    def test_one_pixel_blank_canvas_edge_is_not_a_layout_difference(self):
        reference = raster(16, 17, positions=[(5, 5), (6, 5)])
        candidate = raster(16, 16, positions=[(5, 5), (6, 5)])
        self.assertTrue(metrics.canvas_compatible((16, 17), (16, 16)))
        padded = metrics.union_canvas(candidate, 16, 16, 16, 17)
        self.assertEqual(padded, reference)
        self.assertEqual(metrics.page_metrics(reference, padded, 16, 17)['score'], 100)

    def test_union_canvas_keeps_origin_and_edge_ink(self):
        # Ink on the reference's extra edge row has no candidate counterpart and is still measured.
        reference = raster(17, 17, positions=[(5, 5), (16, 16)])
        candidate = metrics.union_canvas(raster(16, 16, positions=[(5, 5)]), 16, 16, 17, 17)
        self.assertEqual(candidate[(5 * 17 + 5) * 3:(5 * 17 + 5) * 3 + 3], b'\0\0\0')
        self.assertLess(metrics.page_metrics(reference, candidate, 17, 17)['recall'], 1)

    def test_canvas_difference_beyond_one_pixel_fails(self):
        self.assertFalse(metrics.canvas_compatible((16, 18), (16, 16)))
        self.assertFalse(metrics.canvas_compatible((14, 16), (16, 16)))

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
    def test_fractional_chromium_page_size_error_remains_a_mandatory_failure(self):
        declaration = {'fonts': ['Liberation Serif'], 'tokens': {}, 'assertions': []}
        for expected, actual in [([0, 0, 606, 878.5], [0, 0, 606, 877.91998]),
                                 ([0, 0, 626.5, 852], [0, 0, 625.91998, 852])]:
            reference = {'geometry': [{'media': expected, 'crop': expected, 'rotation': 0}],
                         'fonts': ['LiberationSerif'], 'tokens': {}, 'words': []}
            candidate = copy.deepcopy(reference)
            candidate['geometry'][0].update(media=actual, crop=actual)
            checks = pdf.correctness(declaration, reference, candidate)
            self.assertFalse(checks[-1]['passed'])
            self.assertEqual(checks[-1]['name'], 'physical-geometry-page-1')
            self.assertTrue(all(check['passed'] for check in checks[:-1]))
            self.assertEqual(metrics.case_score([{'score': 100}], checks), 0)

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

    @staticmethod
    def bbox(*texts):
        words = ''.join(f'<word xMin="{i}" yMin="1" xMax="{i + 1}" yMax="2">{t}</word>' for i, t in enumerate(texts))
        return f'<html xmlns="http://www.w3.org/1999/xhtml"><body><doc><page>{words}</page></doc></body></html>'

    def test_bidi_controls_do_not_change_visible_words(self):
        words = pdf.bbox_words(self.bbox('‎LogicalMarker', 'inspected‎', '‏', '⁧Elm⁩'))
        self.assertEqual([w['text'] for w in words], ['LogicalMarker', 'inspected', '', 'Elm'])
        self.assertEqual(words[0]['raw'], '‎LogicalMarker')
        self.assertNotIn('raw', pdf.bbox_words(self.bbox('Elm'))[0])
        self.assertEqual(pdf.marker({'words': words}, 'LogicalMarker')['rect'], [0.0, 1.0, 1.0, 2.0])

    def test_visible_characters_are_never_normalized(self):
        # Letters, punctuation and non-bidi invisible characters remain visible-text differences.
        words = pdf.bbox_words(self.bbox('Marker.', 'Mark​er', 'Mar­ker'))
        self.assertEqual([w['text'] for w in words], ['Marker.', 'Mark​er', 'Mar­ker'])
        with self.assertRaises(ValueError):
            pdf.marker({'words': words}, 'Marker')

    def test_reference_must_satisfy_its_declared_assertions(self):
        geometry = [{'media': [0, 0, 612, 792], 'crop': [0, 0, 612, 792], 'rotation': 0, 'userUnit': 1}] * 2
        declaration = {'fonts': ['Liberation Serif'], 'tokens': {'Entry11': 1, 'Entry12': 1},
                       'assertions': [{'type': 'same-page', 'version': 1, 'markers': ['Entry11', 'Entry12']},
                                      {'type': 'marker-reference-position', 'version': 1, 'marker': 'Entry12', 'tolerancePt': 0.5}]}
        def capture(second_page):
            words = [{'text': 'Entry11', 'page': 1, 'rect': [1, 2, 3, 4]}, {'text': 'Entry12', 'page': second_page, 'rect': [1, 9, 3, 11]}]
            return {'geometry': geometry, 'fonts': ['LiberationSerif'], 'tokens': {'Entry11': 1, 'Entry12': 1}, 'words': words}
        self.assertEqual(pdf.reference_failures(declaration, capture(1)), [])
        self.assertEqual(pdf.reference_failures(declaration, capture(2)), ['assertion-same-page'])

    def test_word_adjudicated_assertions_bind_candidates_and_word_references_only(self):
        geometry = [{'media': [0, 0, 612, 792], 'crop': [0, 0, 612, 792], 'rotation': 0, 'userUnit': 1}] * 2
        declaration = {'fonts': ['Liberation Serif'], 'tokens': {'Cite': 1, 'Note': 1},
                       'assertions': [{'type': 'same-page', 'version': 1, 'markers': ['Cite', 'Note'], 'adjudicated': 'word'}]}
        words = [{'text': 'Cite', 'page': 1, 'rect': [1, 2, 3, 4]}, {'text': 'Note', 'page': 2, 'rect': [1, 9, 3, 11]}]
        split = {'geometry': geometry, 'fonts': ['LiberationSerif'], 'tokens': {'Cite': 1, 'Note': 1}, 'words': words}
        self.assertEqual(pdf.reference_failures(declaration, split, 'libreoffice'), [])
        self.assertEqual(pdf.reference_failures(declaration, split, 'word'), ['assertion-same-page'])
        self.assertFalse(pdf.correctness(declaration, split, split)[-1]['passed'])

    def test_libreoffice_calibration_is_not_held_to_word_adjudicated_layout(self):
        declaration = {'assertions': [{'type': 'same-page', 'version': 1, 'markers': ['a'], 'adjudicated': 'word'}, {'type': 'same-page', 'version': 1, 'markers': ['b']}]}
        self.assertEqual(len(pdf.binding_case(declaration, 'libreoffice', reproduces_reference=True)['assertions']), 1)
        self.assertEqual(len(pdf.binding_case(declaration, 'libreoffice-equivalent-controls', reproduces_reference=True)['assertions']), 1)
        self.assertEqual(len(pdf.binding_case(declaration, 'libreoffice')['assertions']), 2)
        self.assertEqual(len(pdf.binding_case(declaration, 'word', reproduces_reference=True)['assertions']), 2)

    def test_word_capture_failing_adjudicated_layout_is_registered_ineligible(self):
        import argparse
        from bench import __main__ as cli
        registry = common.validate_registry()
        record = next(c for c in registry['cases'] if c['id'] == 'notes-keep-lines-note-in-table')
        info = {'geometry': [{'media': [0, 0, 612, 792], 'crop': [0, 0, 612, 792], 'rotation': 0, 'userUnit': 1}] * 2,
                'fonts': ['LiberationSerif'], 'tokens': dict(record['tokens']), 'words': []}
        markers = {'TableKeepNote001': 2, 'TableKeepNote012': 2, 'TableLead30': 1, 'TableCite': 1, 'TableKeepNote002': 2, 'TableTail01': 2}
        info['words'] = [{'text': m, 'page': page, 'rect': [72, 100, 120, 112]} for m, page in markers.items()]
        env = {'contract': {'fonts': {'font': 1}, 'tools': {}}, 'fontDirectories': []}
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'pdfs'
            source.mkdir()
            (source / (record['id'] + '.pdf')).write_bytes(b'%PDF-capture')
            metadata = {'track': 'word', 'rightsApproved': True, 'capturedAt': 'x', 'provider': 'Microsoft Word', 'method': 'PDF export',
                        'reportedBuild': None, 'platform': 'p', 'profile': {'review': 'final', 'comments': 'hidden'}, 'fontContract': {'font': 1},
                        'cases': {record['id']: {'inputSha256': record['sha256'], 'pdfSha256': common.digest(source / (record['id'] + '.pdf'))}}}
            common.write_json(Path(temp) / 'capture.json', metadata)
            args = argparse.Namespace(metadata=str(Path(temp) / 'capture.json'), pdf_dir=str(source), out=str(Path(temp) / 'out'))
            with patch.object(cli, 'environment', return_value=env), patch.object(cli.pdf, 'inspect_pdf', return_value=info):
                cli.import_reference(registry, args)
            entry = common.read_json(Path(temp) / 'out' / 'bundle.json')['cases'][record['id']]
        self.assertFalse(entry['eligible'])
        self.assertEqual(entry['ineligibleChecks'], ['assertion-same-page'])

    def test_adjudicated_assertion_cannot_be_reference_relative(self):
        registry = common.read_json(common.ROOT / 'fixtures/manifest.json')
        registry['cases'][0]['assertions'].append({'type': 'marker-reference-position', 'version': 1, 'marker': 'x', 'tolerancePt': 0.5, 'adjudicated': 'word'})
        with self.assertRaises(ValueError):
            common.validate_registry(registry)

    def test_unknown_adjudication_is_rejected(self):
        registry = common.read_json(common.ROOT / 'fixtures/manifest.json')
        registry['cases'][0]['assertions'].append({'type': 'same-page', 'version': 1, 'markers': ['a'], 'adjudicated': 'libreoffice'})
        with self.assertRaises(ValueError):
            common.validate_registry(registry)

    def test_word_track_is_a_known_reference_track(self):
        self.assertIn('word', common.WORD_TRACKS)

    def test_lost_note_fails_inventory(self):
        self.assertFalse(pdf.inventory_check({'tokens': {'Body': 1}}, {'tokens': {'Body': 1, 'Note': 1}}))

    def test_duplicate_text_fails_inventory(self):
        self.assertFalse(pdf.inventory_check({'tokens': {'Body': 2}}, {'tokens': {'Body': 1}}))

    def test_clipped_words_may_be_whole_or_absent_but_never_fragmented_or_duplicated(self):
        case = {'tokens': {'Body': 1}, 'clippedTokens': {'HiddenCedar': 1, 'HiddenBirch': 1}}
        for extra in [{}, {'HiddenCedar': 1}, {'HiddenBirch': 1}, {'HiddenCedar': 1, 'HiddenBirch': 1}]:
            self.assertTrue(pdf.inventory_check({'tokens': {'Body': 1, **extra}}, case))
        for actual in [{'Body': 1, 'H': 1}, {'Body': 1, 'HiddenCedar': 2}, {'HiddenBirch': 1}, {'Body': 2}]:
            self.assertFalse(pdf.inventory_check({'tokens': actual}, case))

    def test_wrong_font_fails(self):
        self.assertFalse(pdf.font_check({'fonts': ['OtherSerif']}, ['Liberation Serif']))

    def test_subset_font_name_is_recognized(self):
        self.assertTrue(pdf.font_check({'fonts': ['LiberationSerif-Bold']}, ['Liberation Serif']))


class RegistryContract(unittest.TestCase):
    def test_clipped_inventory_cannot_exempt_visible_or_missing_source_text(self):
        registry = common.read_json(common.ROOT / 'fixtures/manifest.json')
        common.validate_registry(registry)
        for optional in [{}, {'HdrBirch': True}, {'HdrBirch': 2}, {'Missing': 1}, {'Hdr Alder': 1},
                         {'BodyWillow': 1}, {'HdrAlder': 1}]:
            with self.subTest(optional=optional):
                edited = copy.deepcopy(registry)
                edited['cases'][-1]['clippedTokens'] = optional
                with self.assertRaises(ValueError): common.validate_registry(edited)

    def test_registry_is_valid(self):
        self.assertEqual(len(common.validate_registry()['cases']), 243)

    def test_agreement_font_variant_changes_only_the_declared_family(self):
        from zipfile import ZipFile
        records = {c['id']: c for c in common.validate_registry()['cases']}
        original, word = [records[c] for c in ('paragraph-contract', 'paragraph-contract-times-new-roman')]
        self.assertEqual(original['sha256'], '6b2926adc3bec2bb319d74097a834bace936d207f833791710ab3ce55b955c6b')
        self.assertEqual(original['fonts'], ['Liberation Serif'])
        self.assertEqual(word['fonts'], ['Times New Roman'])
        for key in ('tokens', 'profile', 'assertions'):
            self.assertEqual(original[key], word[key])
        with ZipFile(common.ROOT / original['input']) as a, ZipFile(common.ROOT / word['input']) as b:
            self.assertEqual(a.namelist(), b.namelist())
            for name in a.namelist():
                expected = a.read(name)
                if name == 'word/styles.xml':
                    expected = expected.replace(b'Liberation Serif', b'Times New Roman')
                self.assertEqual(expected, b.read(name), name)
        self.assertTrue(pdf.font_check({'fonts': ['TimesNewRomanPSMT', 'TimesNewRomanPS-BoldMT']}, word['fonts']))
        self.assertFalse(pdf.font_check({'fonts': ['LiberationSerif']}, word['fonts']))
        self.assertFalse(pdf.font_check({'fonts': ['TimesNewRomanPSMT']}, original['fonts']))

    def test_return_link_pair_keeps_a_real_comment_reference_and_body_bookmark_control(self):
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile
        records = {c['id']: c for c in common.validate_registry()['cases']}
        note, control = [records[c] for c in ('comments-paginated-return-link', 'comments-body-bookmark-return-control')]
        w = '{' + fixtures.W + '}'
        with ZipFile(common.ROOT / note['input']) as first, ZipFile(common.ROOT / control['input']) as second:
            root, plain = [ET.fromstring(z.read('word/document.xml')) for z in (first, second)]
            reference = root.find('.//' + w + 'commentReference')
            self.assertEqual(reference.get(w + 'id'), '4')
            comment = ET.fromstring(first.read('word/comments.xml')).find(w + 'comment')
            self.assertEqual(comment.get(w + 'id'), reference.get(w + 'id'))
            self.assertEqual(comment.get(w + 'author'), '')
            self.assertIsNone(comment.get(w + 'date'))
            self.assertNotIn('word/comments.xml', second.namelist())
            for parent in root.iter():
                for child in list(parent):
                    if child.tag in {w + 'commentRangeStart', w + 'commentRangeEnd'} or (
                            child.tag == w + 'r' and child.find(w + 'commentReference') is not None):
                        parent.remove(child)
            self.assertEqual(ET.tostring(root), ET.tostring(plain))
            bookmark = plain.find('.//' + w + 'bookmarkStart').get(w + 'name')
            self.assertEqual(bookmark, 'JuniperDestination')
            self.assertEqual(plain.find('.//' + w + 'hyperlink').get(w + 'anchor'), bookmark)
            self.assertEqual(first.read('word/styles.xml'), second.read('word/styles.xml'))
        self.assertEqual(note['tokens'], control['tokens'])
        self.assertEqual(note['profile'], {'review': 'final', 'comments': 'hidden'})
        self.assertEqual(note['htmlProfile'], {'review': 'final', 'comments': 'margin'})
        self.assertEqual(note['htmlProfile'], control['htmlProfile'])
        self.assertEqual(note['htmlAssertions'], [
            {'type': 'marker-attribute', 'version': 1, 'marker': '↩', 'attribute': 'href', 'equals': '#comment-ref-4'},
            {'type': 'marker-attribute', 'version': 1, 'marker': '[4]', 'attribute': 'id', 'equals': 'comment-ref-4'}])
        self.assertEqual(control['htmlAssertions'], [
            {'type': 'marker-attribute', 'version': 1, 'marker': 'JuniperBodyReturn', 'attribute': 'href', 'equals': '#JuniperDestination'}])

    def test_comment_date_pair_joins_last_paragraph_to_durable_utc_record(self):
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile
        records = {c['id']: c for c in common.validate_registry()['cases']}
        modern, legacy = [records[c] for c in ('comments-durable-utc-timestamp', 'comments-legacy-utc-control')]
        w = '{' + fixtures.W + '}'
        cid = '{http://schemas.microsoft.com/office/word/2016/wordml/cid}'
        cex = '{http://schemas.microsoft.com/office/word/2018/wordml/cex}'
        w14 = '{http://schemas.microsoft.com/office/word/2010/wordml}'
        with ZipFile(common.ROOT / modern['input']) as first, ZipFile(common.ROOT / legacy['input']) as second:
            self.assertEqual(first.read('word/document.xml'), second.read('word/document.xml'))
            comment = ET.fromstring(first.read('word/comments.xml')).find(w + 'comment')
            control = ET.fromstring(second.read('word/comments.xml')).find(w + 'comment')
            mapping = ET.fromstring(first.read('word/commentsIds.xml')).find(cid + 'commentId')
            utc = ET.fromstring(first.read('word/commentsExtensible.xml')).find(cex + 'commentExtensible')
            self.assertEqual(comment.findall(w + 'p')[-1].get(w14 + 'paraId'), mapping.get(cid + 'paraId'))
            self.assertEqual(mapping.get(cid + 'durableId'), utc.get(cex + 'durableId'))
            self.assertNotEqual(comment.get(w + 'date'), utc.get(cex + 'dateUtc'))
            self.assertEqual(control.get(w + 'date'), utc.get(cex + 'dateUtc'))
            self.assertNotIn('word/commentsExtensible.xml', second.namelist())
        self.assertEqual(modern['tokens'], legacy['tokens'])
        for record in [modern, legacy]:
            self.assertEqual(record['profile'], {'review': 'final', 'comments': 'hidden'})
            self.assertEqual(record['htmlProfile'], {'review': 'final', 'comments': 'inline'})
            self.assertEqual(record['htmlAssertions'], [{'type': 'marker-attribute', 'version': 1,
                'marker': 'BirchDateAnchor', 'attribute': 'data-date', 'equals': '2027-01-02T04:30:00Z'}])

    def test_year_caption_and_authored_token_control_have_explicit_coverage(self):
        records = {c['id']: c for c in common.validate_registry()['cases']}
        margin, authored = [records[c] for c in ('comments-margin-year', 'comments-authored-year-control')]
        self.assertEqual(margin['tokens'], authored['tokens'])
        self.assertEqual(margin['htmlProfile'], authored['htmlProfile'])
        self.assertEqual(margin['htmlProfile']['comments'], 'margin')
        for record, marker in [(margin, '2027'), (authored, 'YearProof2027')]:
            self.assertEqual(record['htmlAssertions'], [
                {'type': 'marker-attribute', 'version': 1, 'marker': marker, 'attribute': 'data-date', 'equals': '2027-01-02T04:30:00Z'},
                {'type': 'marker-readable', 'version': 1, 'marker': marker, 'tokens': ['Jan', '2,', marker] if marker == '2027' else ['BirchYearNote', marker]}])

    def test_comment_pair_changes_only_note_length_and_declares_both_profiles(self):
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile
        records = {c['id']: c for c in common.validate_registry()['cases']}
        pair = [records[c] for c in ('comments-long-scrollable-margin', 'comments-short-margin-control')]
        self.assertEqual(pair[0]['tokens'], pair[1]['tokens'])
        with ZipFile(common.ROOT / pair[0]['input']) as long, ZipFile(common.ROOT / pair[1]['input']) as short:
            self.assertEqual(long.namelist(), short.namelist())
            for name in long.namelist():
                if name != 'word/comments.xml': self.assertEqual(long.read(name), short.read(name))
            for archive, record, count in zip((long, short), pair, (240, 8)):
                tokens = ET.fromstring(archive.read('word/comments.xml')).find('.//{' + fixtures.W + '}t').text.split()
                self.assertEqual(tokens, [f'CedarNote{i:03d}' for i in range(count)])
                self.assertEqual(record['profile'], {'review': 'final', 'comments': 'hidden'})
                self.assertEqual(record['htmlProfile'], {'review': 'final', 'comments': 'margin'})
                self.assertEqual(record['htmlAssertions'], [{'type': 'marker-readable', 'version': 1,
                                                          'marker': tokens[-1], 'tokens': tokens}])

    def test_nested_comment_control_changes_only_parent_links(self):
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile
        records = {c['id']: c for c in common.validate_registry()['cases']}
        pair = [records[c] for c in ('comments-nested-reply-size', 'comments-flat-note-size-control')]
        self.assertEqual(pair[0]['tokens'], pair[1]['tokens'])
        self.assertEqual(pair[0]['htmlAssertions'], pair[1]['htmlAssertions'])
        w15 = '{http://schemas.microsoft.com/office/word/2012/wordml}'
        with ZipFile(common.ROOT / pair[0]['input']) as nested, ZipFile(common.ROOT / pair[1]['input']) as flat:
            self.assertEqual(nested.namelist(), flat.namelist())
            for name in nested.namelist():
                if name != 'word/commentsExtended.xml': self.assertEqual(nested.read(name), flat.read(name))
            first = ET.fromstring(nested.read('word/commentsExtended.xml'))
            second = ET.fromstring(flat.read('word/commentsExtended.xml'))
            parents = [entry.attrib.pop(w15 + 'paraIdParent', None) for entry in first]
            self.assertEqual(parents, [None, '00000010', '00000020'])
            self.assertEqual(ET.tostring(first), ET.tostring(second))

    def test_comment_header_control_changes_only_the_author(self):
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile
        records = {c['id']: c for c in common.validate_registry()['cases']}
        pair = [records[c] for c in ('comments-long-author-header', 'comments-short-author-header-control')]
        self.assertEqual(pair[0]['tokens'], pair[1]['tokens'])
        with ZipFile(common.ROOT / pair[0]['input']) as long, ZipFile(common.ROOT / pair[1]['input']) as short:
            self.assertEqual(long.namelist(), short.namelist())
            for name in long.namelist():
                if name != 'word/comments.xml': self.assertEqual(long.read(name), short.read(name))
            first, second = [ET.fromstring(z.read('word/comments.xml')) for z in (long, short)]
            w = '{' + fixtures.W + '}'
            for tree, record in zip((first, second), pair):
                author = tree.find(w + 'comment').get(w + 'author')
                self.assertTrue(author.endswith(' '))
                self.assertEqual(record['htmlAssertions'], [{'type': 'marker-computed-style', 'version': 1,
                    'marker': author.strip(), 'property': 'font-size', 'equals': '12.24px'}])
            first.find(w + 'comment').set(w + 'author', second.find(w + 'comment').get(w + 'author'))
            self.assertEqual(ET.tostring(first), ET.tostring(second))

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
        self.assertEqual(registry['suite']['id'], 'core-v50')

    def test_hidden_paragraph_mark_pair_changes_only_mark_visibility(self):
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile
        records = {c['id']: c for c in common.validate_registry()['cases']}
        pair = [records[c] for c in ('paragraph-mark-hidden-numbered-heading', 'paragraph-mark-visible-numbered-control')]
        w = '{' + fixtures.W + '}'
        with ZipFile(common.ROOT / pair[0]['input']) as hidden, ZipFile(common.ROOT / pair[1]['input']) as visible:
            self.assertEqual(hidden.namelist(), visible.namelist())
            for name in hidden.namelist():
                if name != 'word/document.xml':
                    self.assertEqual(hidden.read(name), visible.read(name))
            first, second = [ET.fromstring(z.read('word/document.xml')) for z in (hidden, visible)]
            mark = first.find('.//' + w + 'pPr/' + w + 'rPr/' + w + 'vanish')
            self.assertEqual(mark.get(w + 'val'), '1')
            mark.set(w + 'val', '0')
            self.assertEqual(ET.tostring(first), ET.tostring(second))
            numbering = ET.fromstring(hidden.read('word/numbering.xml'))
            self.assertEqual(numbering.find('.//' + w + 'lvlText').get(w + 'val'), '%1.')
            self.assertEqual(first.find('.//' + w + 'numPr/' + w + 'numId').get(w + 'val'), '1')
        self.assertEqual(pair[0]['tokens'], pair[1]['tokens'])
        self.assertEqual(pair[0]['tokens']['1.'], 1)
        self.assertEqual({a['marker'] for a in pair[0]['assertions']}, {'CedarHeading.', 'CedarBody'})

    def test_footer_frame_pair_changes_only_frame_properties(self):
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile
        records = {c['id']: c for c in common.validate_registry()['cases']}
        pair = [records[c] for c in ('footer-paragraph-text-frame', 'footer-paragraph-flow-control')]
        w = '{' + fixtures.W + '}'
        with ZipFile(common.ROOT / pair[0]['input']) as framed, ZipFile(common.ROOT / pair[1]['input']) as control:
            self.assertEqual(framed.namelist(), control.namelist())
            for name in framed.namelist():
                if name != 'word/footer1.xml': self.assertEqual(framed.read(name), control.read(name))
            first, second = [ET.fromstring(z.read('word/footer1.xml')) for z in (framed, control)]
            properties = first.find(w + 'p/' + w + 'pPr')
            frame = properties.find(w + 'framePr')
            self.assertEqual(frame.attrib, {w + 'w': '10080', w + 'hAnchor': 'page', w + 'vAnchor': 'text',
                                           w + 'x': '840', w + 'y': '20', w + 'wrap': 'auto'})
            properties.remove(frame)
            self.assertEqual(ET.tostring(first), ET.tostring(second))
        self.assertEqual(pair[0]['tokens'], pair[1]['tokens'])
        self.assertEqual(pair[0]['assertions'], pair[1]['assertions'])
        self.assertEqual({a['marker'] for a in pair[0]['assertions']}, {'CedarFrameBody', 'CedarFrame01', 'CedarSheet01'})

    def test_style_frame_pair_changes_only_direct_frame_attributes(self):
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile
        records = {c['id']: c for c in common.validate_registry()['cases']}
        pair = [records[c] for c in ('footer-style-frame-partial-direct', 'footer-style-frame-full-direct-control')]
        w = '{' + fixtures.W + '}'
        with ZipFile(common.ROOT / pair[0]['input']) as partial, ZipFile(common.ROOT / pair[1]['input']) as control:
            self.assertEqual(partial.namelist(), control.namelist())
            for name in partial.namelist():
                if name != 'word/footer1.xml': self.assertEqual(partial.read(name), control.read(name))
            style = ET.fromstring(partial.read('word/styles.xml')).find(w + 'style/' + w + 'pPr/' + w + 'framePr')
            first, second = [ET.fromstring(z.read('word/footer1.xml')) for z in (partial, control)]
            frames = [f.find(w + 'p/' + w + 'pPr/' + w + 'framePr') for f in (first, second)]
            self.assertEqual(frames[0].attrib, {w + 'wrap': 'auto'})
            self.assertEqual(frames[1].attrib, style.attrib)
            frames[1].attrib = dict(frames[0].attrib)
            self.assertEqual(ET.tostring(first), ET.tostring(second))
        self.assertEqual(pair[0]['tokens'], pair[1]['tokens'])
        self.assertEqual(pair[0]['assertions'], pair[1]['assertions'])
        self.assertEqual({a['marker'] for a in pair[0]['assertions']}, {'ElmStampBody', 'ElmStamp01', 'ElmSheet01'})

    def test_manual_tab_reproducer_and_narrow_left_control(self):
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile
        records = {c['id']: c for c in common.validate_registry()['cases']}
        repro, control = [records[c] for c in ('tabs-hanging-manual-labels', 'tabs-left-narrow-label-control')]
        w = '{' + fixtures.W + '}'
        with ZipFile(common.ROOT / repro['input']) as many, ZipFile(common.ROOT / control['input']) as one:
            for name in many.namelist():
                if name != 'word/document.xml': self.assertEqual(many.read(name), one.read(name))
            paragraphs = ET.fromstring(many.read('word/document.xml')).findall('.//' + w + 'body/' + w + 'p')
            self.assertEqual(len(paragraphs), 3)
            self.assertEqual([p.find(w + 'r/' + w + 't').text for p in paragraphs], ['3.2.', '3.12.', '3.13.'])
            for paragraph in paragraphs:
                stops = paragraph.findall(w + 'pPr/' + w + 'tabs/' + w + 'tab')
                self.assertEqual([(t.get(w + 'val'), t.get(w + 'pos'), t.get(w + 'leader')) for t in stops],
                                 [('left', '1800', None), ('right', '9000', 'dot')])
                self.assertEqual(len(paragraph.findall(w + 'r/' + w + 'tab')), 2)
                self.assertEqual(paragraph.find(w + 'pPr/' + w + 'spacing').get(w + 'lineRule'), 'exact')
            ordinary = ET.fromstring(one.read('word/document.xml'))
            self.assertEqual(len(ordinary.findall('.//' + w + 'body/' + w + 'p')), 1)
            self.assertEqual(len(ordinary.findall('.//' + w + 'r/' + w + 'tab')), 1)
        for number in ('7', '18', '104'):
            self.assertEqual(repro['tokens'][number], 1)
            self.assertNotIn(number, control['tokens'])
        self.assertEqual(len(repro['assertions']), 6)
        self.assertEqual(control['assertions'][0]['marker'], 'CedarTitle01')

    def test_legacy_header_pairs_preserve_everything_except_number_representation(self):
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile
        records = {c['id']: c for c in common.validate_registry()['cases']}
        w = '{' + fixtures.W + '}'
        for variant in ['ordinary', 'restarted']:
            for kind in ('field', 'simple-field'):
                pair = [records[f'paragraphs-page-number-{variant}-{k}'] for k in (kind, 'legacy')]
                with ZipFile(common.ROOT / pair[0]['input']) as field, ZipFile(common.ROOT / pair[1]['input']) as legacy:
                    self.assertEqual(field.namelist(), legacy.namelist())
                    for name in field.namelist():
                        if name != 'word/header1.xml':
                            self.assertEqual(field.read(name), legacy.read(name))
                    expected = ET.fromstring(field.read('word/header1.xml'))
                    actual = ET.fromstring(legacy.read('word/header1.xml'))
                    paragraph = expected.find(w + 'p')
                    if kind == 'simple-field':
                        simple = paragraph.find(w + 'fldSimple')
                        self.assertEqual(simple.get(w + 'instr'), ' PAGE \\* Arabic ')
                        r = simple.find(w + 'r')
                        paragraph.remove(simple)
                    else:
                        self.assertEqual(paragraph.find('.//' + w + 'instrText').text, ' PAGE \\* Arabic ')
                        self.assertEqual([e.get(w + 'fldCharType') for e in paragraph.iter(w + 'fldChar')],
                                         ['begin', 'separate', 'end'])
                        runs = paragraph.findall(w + 'r')
                        r = next(e for e in runs if e.find(w + 't') is not None)
                        for run in runs:
                            paragraph.remove(run)
                    r.remove(r.find(w + 't')); ET.SubElement(r, w + 'pgNum')
                    paragraph.append(r)
                    self.assertEqual(ET.tostring(expected), ET.tostring(actual))
                self.assertEqual(pair[0]['tokens'], pair[1]['tokens'])
                self.assertEqual(pair[0]['assertions'], pair[1]['assertions'])

    def test_footnote_break_pairs_preserve_note_lines_and_other_parts(self):
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile
        records = {c['id']: c for c in common.validate_registry()['cases']}
        w = '{' + fixtures.W + '}'
        for variant in ('', 'blanks-'):
            pair = [records[f'notes-explicit-breaks-{variant}{kind}'] for kind in ('paragraph-control', 'breaks')]
            with ZipFile(common.ROOT / pair[0]['input']) as control, ZipFile(common.ROOT / pair[1]['input']) as breaks:
                self.assertEqual(control.namelist(), breaks.namelist())
                for name in control.namelist():
                    if name != 'word/footnotes.xml':
                        self.assertEqual(control.read(name), breaks.read(name))
                trees = [ET.fromstring(z.read('word/footnotes.xml')) for z in (control, breaks)]
                notes = [next(n for n in t if n.get(w + 'id') == '1') for t in trees]
                self.assertEqual(len(notes[1].findall(w + 'p')), 1)
                self.assertEqual(len(notes[1].findall('.//' + w + 'br')), len(notes[0]) - 1)
                self.assertEqual([t.text for t in notes[0].iter(w + 't')], [t.text for t in notes[1].iter(w + 't')])
                properties = ET.tostring(notes[1].find(w + 'p').find(w + 'pPr'))
                self.assertTrue(all(ET.tostring(p.find(w + 'pPr')) == properties for p in notes[0]))
                for n in notes:
                    self.assertEqual(len(n.findall('.//' + w + 'footnoteRef')), 1)
                self.assertEqual([ET.tostring(e) for e in list(trees[0])[:2]],
                                 [ET.tostring(e) for e in list(trees[1])[:2]])
            self.assertEqual(pair[0]['tokens'], pair[1]['tokens'])
            self.assertEqual(pair[0]['assertions'], pair[1]['assertions'])

    def test_indentation_units_change_only_equivalent_measure_attributes(self):
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile
        records = {c['id']: c for c in common.validate_registry()['cases']}
        w = '{' + fixtures.W + '}'
        for name, value, control in [('pt', '36pt', 'twips'), ('in', '0.5in', 'twips'), ('cm', '1.27cm', 'twips'),
                                     ('mm', '12.7mm', 'twips'), ('pc', '3pc', 'twips'), ('pi', '3pi', 'twips'),
                                     ('small-pt', '12pt', 'small-twips')]:
            actual, expected = [records['paragraphs-indentation-' + n] for n in (name, control)]
            with ZipFile(common.ROOT / actual['input']) as a, ZipFile(common.ROOT / expected['input']) as b:
                self.assertEqual(a.namelist(), b.namelist())
                for part in a.namelist():
                    if part != 'word/document.xml':
                        self.assertEqual(a.read(part), b.read(part))
                unit_xml, control_xml = [ET.fromstring(z.read('word/document.xml')) for z in (a, b)]
                changed = 0
                for ind in unit_xml.iter(w + 'ind'):
                    for attr in list(ind.attrib):
                        if ind.get(attr) == value:
                            ind.set(attr, '240' if control == 'small-twips' else '720')
                            changed += 1
                self.assertEqual(changed, 8)
                self.assertEqual(ET.tostring(unit_xml), ET.tostring(control_xml))
            self.assertEqual(actual['tokens'], expected['tokens'])
            self.assertEqual(actual['assertions'], expected['assertions'])

    def test_page_margin_units_change_only_declared_margin_attributes(self):
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile
        records = {c['id']: c for c in common.validate_registry()['cases']}
        w = '{' + fixtures.W + '}'
        for name, edge, band, control in [('pt', '54pt', '18pt', 'twips'),
                ('in', '0.75in', '0.25in', 'twips'), ('cm', '1.905cm', '0.635cm', 'twips'),
                ('mm', '19.05mm', '6.35mm', 'twips'), ('pc', '4.5pc', '1.5pc', 'twips'),
                ('pi', '4.5pi', '1.5pi', 'twips'), ('multipage-pt', '54pt', '18pt', 'multipage-twips'),
                ('small-mm', '25mm', None, 'small-twips')]:
            actual, expected = [records['paragraphs-page-margins-' + n] for n in (name, control)]
            with ZipFile(common.ROOT / actual['input']) as a, ZipFile(common.ROOT / expected['input']) as b:
                self.assertEqual(a.namelist(), b.namelist())
                for part in a.namelist():
                    if part != 'word/document.xml':
                        self.assertEqual(a.read(part), b.read(part))
                unit, numeric = [ET.fromstring(z.read('word/document.xml')) for z in (a, b)]
                margins = unit.find('.//' + w + 'pgMar')
                if band is None:
                    self.assertEqual(margins.get(w + 'left'), edge)
                    margins.set(w + 'left', '1417')
                else:
                    for attr in ('top', 'right', 'bottom', 'left', 'header', 'footer'):
                        self.assertEqual(margins.get(w + attr), band if attr in ('header', 'footer') else edge)
                        margins.set(w + attr, '360' if attr in ('header', 'footer') else '1080')
                self.assertEqual(ET.tostring(unit), ET.tostring(numeric))
            self.assertEqual(actual['tokens'], expected['tokens'])
            self.assertEqual(actual['assertions'], expected['assertions'])

    def test_row_height_pairs_change_only_the_height_lexical_value(self):
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile
        records = {c['id']: c for c in common.validate_registry()['cases']}
        w = '{' + fixtures.W + '}'
        for name, value, control in [('pt', '36pt', 'twips'), ('in', '0.5in', 'twips'),
                ('cm', '1.27cm', 'twips'), ('mm', '12.7mm', 'twips'), ('pc', '3pc', 'twips'),
                ('pi', '3pi', 'twips'), ('fractional-pt', '25.075pt', 'fractional-twips'),
                ('multipage-pt', '36pt', 'multipage-twips'), ('exact-pt', '36pt', 'exact-twips')]:
            actual, expected = [records['tables-row-height-' + n] for n in (name, control)]
            with ZipFile(common.ROOT / actual['input']) as a, ZipFile(common.ROOT / expected['input']) as b:
                self.assertEqual(a.namelist(), b.namelist())
                for part in a.namelist():
                    if part != 'word/document.xml':
                        self.assertEqual(a.read(part), b.read(part))
                unit, numeric = [ET.fromstring(z.read('word/document.xml')) for z in (a, b)]
                heights = unit.findall('.//' + w + 'trHeight')
                self.assertEqual(len(heights), 30 if name.startswith('multipage') else 3)
                self.assertIn({'type': 'marker-reference-position', 'version': 1,
                    'marker': 'Birch30' if name.startswith('multipage') else 'Birch03',
                    'tolerancePt': 0.5}, actual['assertions'])
                for height in heights:
                    self.assertEqual(height.get(w + 'val'), value)
                    height.set(w + 'val', '502' if name.startswith('fractional') else '720')
                self.assertEqual(ET.tostring(unit), ET.tostring(numeric))
            self.assertEqual(actual['tokens'], expected['tokens'])
            self.assertEqual(actual['assertions'], expected['assertions'])

    def test_standard_trash_pairs_add_only_the_declared_opaque_item(self):
        from zipfile import ZipFile
        records = {c['id']: c for c in common.validate_registry()['cases']}
        control = records['paragraphs-standard-trash-control']
        for name, entry in [('zero', '[trash]/0000.dat'), ('upper', '[trash]/ABCD.dat'), ('lower', '[trash]/00af.dat')]:
            actual = records['paragraphs-standard-trash-' + name]
            with ZipFile(common.ROOT / actual['input']) as a, ZipFile(common.ROOT / control['input']) as b:
                self.assertEqual(set(a.namelist()) - set(b.namelist()), {entry})
                for part in b.namelist(): self.assertEqual(a.read(part), b.read(part))
                self.assertEqual(a.read(entry), b'<obsolete>Discarded independent Acacia fragment')
            self.assertEqual(actual['tokens'], control['tokens'])
            self.assertEqual(actual['assertions'], control['assertions'])

    def test_border_size_cards_change_only_the_optional_size_attribute(self):
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile
        records = {c['id']: c for c in common.validate_registry()['cases']}
        w = '{' + fixtures.W + '}'
        for style in ('single', 'dashed'):
            omitted = records[f'paragraphs-border-size-{style}-omitted']
            for suffix, size in [('zero', '0'), ('thin', '2')]:
                control = records[f'paragraphs-border-size-{style}-{suffix}']
                with ZipFile(common.ROOT / omitted['input']) as a, ZipFile(common.ROOT / control['input']) as b:
                    self.assertEqual(a.namelist(), b.namelist())
                    for name in a.namelist():
                        if name != 'word/document.xml':
                            self.assertEqual(a.read(name), b.read(name))
                    expected, actual = [ET.fromstring(z.read('word/document.xml')) for z in (a, b)]
                    sides = actual.find('.//' + w + 'pBdr')
                    self.assertEqual(len(sides), 4)
                    for side in sides:
                        self.assertEqual(side.get(w + 'sz'), size)
                        del side.attrib[w + 'sz']
                    self.assertEqual(ET.tostring(expected), ET.tostring(actual))
                self.assertEqual(omitted['tokens'], control['tokens'])
                self.assertEqual(omitted['assertions'], control['assertions'])

    def test_fractional_page_pairs_change_only_one_half_point_dimension(self):
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile
        records = {c['id']: c for c in common.validate_registry()['cases']}
        w = '{' + fixtures.W + '}'
        for axis, attribute in [('height', 'h'), ('width', 'w')]:
            pair = [records[f'paragraphs-page-size-{axis}-{kind}'] for kind in ('control', 'fractional')]
            with ZipFile(common.ROOT / pair[0]['input']) as control, ZipFile(common.ROOT / pair[1]['input']) as fractional:
                self.assertEqual(control.namelist(), fractional.namelist())
                for name in control.namelist():
                    if name != 'word/document.xml':
                        self.assertEqual(control.read(name), fractional.read(name))
                original = ET.fromstring(control.read('word/document.xml'))
                actual = ET.fromstring(fractional.read('word/document.xml'))
                before = original.find('.//' + w + 'pgSz')
                after = actual.find('.//' + w + 'pgSz')
                self.assertEqual(int(after.get(w + attribute)) - int(before.get(w + attribute)), 10)
                after.set(w + attribute, before.get(w + attribute))
                self.assertEqual(ET.tostring(original), ET.tostring(actual))
            self.assertEqual(pair[0]['tokens'], pair[1]['tokens'])
            self.assertEqual(pair[0]['assertions'], pair[1]['assertions'])

    def test_line_break_pairs_preserve_line_runs_properties_and_package_content(self):
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile
        records = {c['id']: c for c in common.validate_registry()['cases']}
        w = '{' + fixtures.W + '}'
        for variant, count in [('plain', 90), ('blanks', 92)]:
            pair = [records[f'paragraphs-line-breaks-{variant}-{kind}'] for kind in ('control', 'breaks')]
            with ZipFile(common.ROOT / pair[0]['input']) as control, ZipFile(common.ROOT / pair[1]['input']) as breaks:
                self.assertEqual(control.namelist(), breaks.namelist())
                for name in control.namelist():
                    if name != 'word/document.xml':
                        self.assertEqual(control.read(name), breaks.read(name))
                original = ET.fromstring(control.read('word/document.xml'))
                actual = ET.fromstring(breaks.read('word/document.xml'))
                paragraphs = original.findall('.//' + w + 'p')
                paragraph = actual.find('.//' + w + 'p')
                self.assertEqual(len(paragraphs), count)
                self.assertEqual(len(actual.findall('.//' + w + 'p')), 1)
                self.assertEqual(len(actual.findall('.//' + w + 'br')), count - 1)
                self.assertTrue(all(not br.attrib for br in actual.iter(w + 'br')))
                reconstructed, block = [], []
                for child in list(paragraph)[1:]:
                    if child.find(w + 'br') is not None:
                        reconstructed.append(block)
                        block = []
                    else:
                        block.append(ET.tostring(child))
                reconstructed.append(block)
                self.assertEqual(reconstructed, [[ET.tostring(r) for r in list(p)[1:]] for p in paragraphs])
                properties = paragraph.find(w + 'pPr')
                self.assertEqual(properties.find(w + 'widowControl').get(w + 'val'), '0')
                self.assertEqual(properties.find(w + 'spacing').get(w + 'line'), '400')
                self.assertTrue(all(ET.tostring(p.find(w + 'pPr')) == ET.tostring(properties) for p in paragraphs))
                self.assertEqual(ET.tostring(original.find('.//' + w + 'sectPr')), ET.tostring(actual.find('.//' + w + 'sectPr')))
            self.assertEqual(pair[0]['tokens'], pair[1]['tokens'])
            self.assertEqual(pair[0]['assertions'], pair[1]['assertions'])

    def test_vertical_merge_pairs_preserve_all_other_package_content(self):
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile
        records = {c['id']: c for c in common.validate_registry()['cases']}
        w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        for location, expected_span in [('early', 2), ('boundary', 3)]:
            pair = [records[f'tables-vmerge-{location}-{kind}'] for kind in ('control', 'merged')]
            with ZipFile(common.ROOT / pair[0]['input']) as control, ZipFile(common.ROOT / pair[1]['input']) as merged:
                self.assertEqual(control.namelist(), merged.namelist())
                for name in control.namelist():
                    if name != 'word/document.xml':
                        self.assertEqual(control.read(name), merged.read(name))
                original = ET.fromstring(control.read('word/document.xml'))
                actual = ET.fromstring(merged.read('word/document.xml'))
                self.assertEqual(len(actual.findall('.//' + w + 'tr')), 20)
                self.assertEqual(len(actual.findall('.//' + w + 'vMerge')), expected_span)
                for properties in actual.iter(w + 'tcPr'):
                    for element in list(properties):
                        if element.tag == w + 'vMerge':
                            properties.remove(element)
                self.assertEqual(ET.tostring(original), ET.tostring(actual))
                self.assertEqual(pair[0]['tokens'], pair[1]['tokens'])

    def test_1417_margin_pairs_change_only_the_margin_values(self):
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile
        records = {c['id']: c for c in common.validate_registry()['cases']}
        w = '{' + fixtures.W + '}'
        for fill, page in [('underfull', 1), ('overfull', 2)]:
            pair = [records[f'paragraphs-page-margins-{name}-{fill}'] for name in ('1417', '1417-control')]
            with ZipFile(common.ROOT / pair[0]['input']) as a, ZipFile(common.ROOT / pair[1]['input']) as b:
                self.assertEqual(a.namelist(), b.namelist())
                for name in a.namelist():
                    if name != 'word/document.xml':
                        self.assertEqual(a.read(name), b.read(name))
                original, control = [ET.fromstring(z.read('word/document.xml')) for z in (a, b)]
                margins = original.find('.//' + w + 'pgMar')
                self.assertEqual([margins.get(w + side) for side in ('top', 'right', 'bottom', 'left')], ['1417'] * 4)
                for side, value in zip(('top', 'right', 'bottom', 'left'), ('1416', '1418', '1418', '1416')):
                    margins.set(w + side, value)
                self.assertEqual(ET.tostring(original), ET.tostring(control))
                heights = [int(s.get(w + 'line')) for s in original.iter(w + 'spacing')]
                self.assertEqual(sum(heights), 16838 - 2 * 1417 + (1 if page == 2 else -1))
            self.assertEqual(pair[0]['tokens'], pair[1]['tokens'])
            self.assertEqual(pair[0]['assertions'], pair[1]['assertions'])

    def test_rule_pairs_change_only_the_height_rule(self):
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile
        records = {c['id']: c for c in common.validate_registry()['cases']}
        w = '{' + fixtures.W + '}'
        for exact, at_least, rows in [('tables-header-repeat-exact', 'tables-header-repeat-atleast', 1),
                                      ('tables-row-height-exact-border-clip', 'tables-row-height-atleast-border-clip', 1)]:
            with ZipFile(common.ROOT / records[exact]['input']) as a, ZipFile(common.ROOT / records[at_least]['input']) as b:
                for name in a.namelist():
                    if name != 'word/document.xml':
                        self.assertEqual(a.read(name), b.read(name))
                original, control = [ET.fromstring(z.read('word/document.xml')) for z in (a, b)]
                changed = [h for h in original.iter(w + 'trHeight')][:rows]
                for height in changed:
                    self.assertEqual(height.get(w + 'hRule'), 'exact')
                    height.set(w + 'hRule', 'atLeast')
                self.assertEqual(ET.tostring(original), ET.tostring(control))
            self.assertEqual(records[exact]['tokens'], records[at_least]['tokens'])

    def test_repeated_header_text_is_counted_once_per_page(self):
        records = {c['id']: c for c in common.validate_registry()['cases']}
        for rule in ('exact', 'atleast'):
            tokens = records['tables-header-repeat-' + rule]['tokens']
            self.assertEqual((tokens['HeaderLeft'], tokens['HeaderRight']), (2, 2))
            self.assertNotIn('HeaderLeft', [a.get('marker') for a in records['tables-header-repeat-' + rule]['assertions']])

    def test_unknown_assertion_is_rejected(self):
        registry = common.read_json(common.ROOT / 'fixtures/manifest.json')
        registry['cases'][0]['assertions'].append({'type': 'unimplemented', 'version': 1})
        with self.assertRaises(ValueError):
            common.validate_registry(registry)

    def test_hidden_header_pair_changes_only_the_empty_paragraph_run(self):
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile
        records = {c['id']: c for c in common.validate_registry()['cases']}
        pair = [records['paragraphs-header-' + suffix] for suffix in ('empty', 'hidden')]
        w = '{' + fixtures.W + '}'
        with ZipFile(common.ROOT / pair[0]['input']) as control, ZipFile(common.ROOT / pair[1]['input']) as hidden:
            self.assertEqual(control.namelist(), hidden.namelist())
            for name in control.namelist():
                if name != 'word/header1.xml':
                    self.assertEqual(control.read(name), hidden.read(name))
            original = ET.fromstring(control.read('word/header1.xml'))
            actual = ET.fromstring(hidden.read('word/header1.xml'))
            first = actual.find(w + 'p')
            concealed = first.find(w + 'r')
            self.assertIsNotNone(concealed.find(w + 'rPr/' + w + 'vanish'))
            self.assertEqual(concealed.find(w + 't').text, 'SecretMarker Concealed archive note.')
            first.remove(concealed)
            self.assertEqual(ET.tostring(original), ET.tostring(actual))
        self.assertEqual(pair[0]['tokens'], pair[1]['tokens'])
        self.assertNotIn('SecretMarker', pair[1]['tokens'])
        self.assertEqual(pair[0]['assertions'], pair[1]['assertions'])

    def test_inline_pair_differs_only_in_paragraph_indentation(self):
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile
        records = {c['id']: c for c in common.validate_registry()['cases']}
        pair = [records[cid] for cid in ('paragraphs-inline-control', 'paragraphs-zero-width')]
        w = '{' + fixtures.W + '}'
        with ZipFile(common.ROOT / pair[0]['input']) as control, ZipFile(common.ROOT / pair[1]['input']) as zero:
            self.assertEqual(control.namelist(), zero.namelist())
            for name in control.namelist():
                if name != 'word/document.xml':
                    self.assertEqual(control.read(name), zero.read(name))
            original = ET.fromstring(control.read('word/document.xml'))
            actual = ET.fromstring(zero.read('word/document.xml'))
            properties = actual.find('.//' + w + 'pPr')
            indentation = properties.find(w + 'ind')
            self.assertEqual(indentation.attrib, {w + 'left': '5000', w + 'right': '5000'})
            properties.remove(indentation)
            self.assertEqual(ET.tostring(original), ET.tostring(actual))
        self.assertEqual(pair[0]['tokens'], {'Z': 1})
        self.assertEqual(pair[0]['tokens'], pair[1]['tokens'])

    def test_empty_drawing_host_keeps_absolute_drawing_and_following_content(self):
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile
        records = {c['id']: c for c in common.validate_registry()['cases']}
        pair = [records[cid] for cid in ('drawings-textbox-absolute', 'drawings-textbox-empty-host')]
        w = '{' + fixtures.W + '}'
        with ZipFile(common.ROOT / pair[0]['input']) as control, ZipFile(common.ROOT / pair[1]['input']) as empty:
            self.assertEqual(control.namelist(), empty.namelist())
            for name in control.namelist():
                if name != 'word/document.xml':
                    self.assertEqual(control.read(name), empty.read(name))
            original = ET.fromstring(control.read('word/document.xml'))
            actual = ET.fromstring(empty.read('word/document.xml'))
            host = original.find(w + 'body/' + w + 'p')
            host.remove(host.find(w + 'r'))
            self.assertEqual(ET.tostring(original), ET.tostring(actual))
        self.assertEqual(pair[0]['assertions'], pair[1]['assertions'])
        self.assertNotIn('Drawing', pair[1]['tokens'])
        self.assertIn('TextboxLabel', pair[1]['tokens'])
        self.assertIn('FollowingMarker', pair[1]['tokens'])

    def test_overindented_word_retains_literal_word_and_declares_reference_wrapping(self):
        import xml.etree.ElementTree as ET
        from zipfile import ZipFile
        record = next(c for c in common.validate_registry()['cases'] if c['id'] == 'paragraphs-overindented-word')
        with ZipFile(common.ROOT / record['input']) as archive:
            document = ET.fromstring(archive.read('word/document.xml'))
        self.assertEqual(document.find('.//{' + fixtures.W + '}t').text, 'ABC')
        self.assertEqual(record['tokens'], {'A': 1, 'B': 1, 'C': 1})
        self.assertEqual(record['assertions'][0]['markers'], ['A', 'B', 'C'])

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
