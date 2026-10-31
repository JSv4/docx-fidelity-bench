import copy
import base64
import hashlib
import unittest
from bench import html_artifacts


DECLARATION = {'type': 'named-checkbox', 'version': 1, 'marker': 'ElmCheckA', 'checked': False, 'sizePt': 12, 'caption': 'Caption'}


def observation():
    # Protocol fixtures only; actual browser geometry is recorded by the independent observer.
    return {'index': 0, 'marker': 'ElmCheckA', 'matches': 1, 'text': 'ElmCheckA',
            'before': [20, 20, 36, 36], 'after': [20, 20, 36, 36], 'viewport': [0, 0, 1280, 1024],
            'visible': True, 'checked': False, 'caption': [0, 20, 16, 36], 'ports': [],
            'raster': raster(False)}


def raster(checked):
    pixels = bytearray([255] * 20 * 20 * 4)
    for y in range(2, 18):
        for x in range(2, 18):
            if x in (2, 17) or y in (2, 17) or checked and (x == y or x + y == 19):
                pixels[(y * 20 + x) * 4:(y * 20 + x) * 4 + 3] = bytes(3)
    return {'x': 18, 'y': 18, 'width': 20, 'height': 20, 'rgba': base64.b64encode(pixels).decode(),
            'sha256': hashlib.sha256(pixels).hexdigest()}


class CheckboxHtmlContract(unittest.TestCase):
    def test_exact_checked_and_unchecked_states_are_required(self):
        html_artifacts.validate_declaration(DECLARATION)
        self.assertTrue(html_artifacts.checkbox_pass(DECLARATION, observation(), 0))
        for checked in (True, None):
            value = observation(); value['checked'] = checked
            self.assertFalse(html_artifacts.checkbox_pass(DECLARATION, value, 0))
        checked = dict(DECLARATION, checked=True)
        self.assertTrue(html_artifacts.checkbox_pass(checked, dict(observation(), checked=True, raster=raster(True)), 0))

    def test_missing_duplicate_or_hidden_controls_cannot_pass(self):
        for count in (0, 2):
            value = observation(); value.update(matches=count, text=' '.join(['ElmCheckA'] * count))
            self.assertFalse(html_artifacts.checkbox_pass(DECLARATION, value, 0))
        value = observation(); value['visible'] = False
        self.assertFalse(html_artifacts.checkbox_pass(DECLARATION, value, 0))

    def test_zero_size_offscreen_or_clipped_controls_fail(self):
        for rectangle in ([20, 20, 20, 36], [20, 1100, 36, 1116]):
            value = observation(); value['after'] = rectangle; value.pop('raster')
            self.assertFalse(html_artifacts.checkbox_pass(DECLARATION, value, 0))
        value = observation(); value['ports'] = [{'overflowX': 'hidden', 'overflowY': 'hidden',
            'before': [20, 20, 36, 36], 'clipBefore': [20, 20, 24, 24], 'clipAfter': [20, 20, 24, 24],
            'scrollHeight': 20, 'clientHeight': 4}]
        self.assertFalse(html_artifacts.checkbox_pass(DECLARATION, value, 0))

    def test_unknown_or_nonboolean_expected_states_are_rejected(self):
        for change in ({'checked': 0}, {'checked': 'false'}, {'checked': None}, {'sizePt': True}, {'caption': ''}, {'version': True}, {'extra': 1}):
            with self.assertRaises(ValueError): html_artifacts.validate_declaration(dict(DECLARATION, **change))

    def test_malformed_observations_are_not_a_measured_pass(self):
        for change in ({'checked': 0}, {'checked': 'false'}, {'visible': 1}):
            with self.assertRaises(ValueError): html_artifacts.checkbox_pass(DECLARATION, dict(observation(), **change), 0)
        value = observation(); del value['checked']
        with self.assertRaises(ValueError): html_artifacts.checkbox_pass(DECLARATION, value, 0)

    def test_pixels_cannot_be_replaced_without_updating_their_digest(self):
        value = observation(); value['raster']['rgba'] = base64.b64encode(bytes([255] * 1600)).decode()
        with self.assertRaisesRegex(ValueError, 'digest'): html_artifacts.checkbox_pass(DECLARATION, value, 0)
        value = observation(); value['raster']['x'] += 1
        with self.assertRaisesRegex(ValueError, 'crop'): html_artifacts.checkbox_pass(DECLARATION, value, 0)

    def test_wrong_painted_state_size_or_caption_alignment_fails(self):
        for change in ({'raster': raster(True)}, {'caption': [0, 40, 16, 56]}):
            self.assertFalse(html_artifacts.checkbox_pass(DECLARATION, dict(observation(), **change), 0))
        self.assertFalse(html_artifacts.checkbox_pass(dict(DECLARATION, sizePt=20), observation(), 0))

    def test_runner_requests_observation_and_recomputes_the_state(self):
        from test_html_artifacts import HtmlRunnerIntegration
        from bench import runner
        declaration = dict(DECLARATION, marker='FormatLabel')
        value = dict(observation(), marker='FormatLabel', text='FormatLabel')
        result, request, _ = HtmlRunnerIntegration().measured('ignored', declaration=declaration,
            browser_facts={'observations': [value]})
        self.assertEqual(request['htmlAssertions'], [declaration])
        self.assertEqual(result['htmlSummary']['passed'], 1)
        changed = copy.deepcopy(result)
        changed['cases'][0]['html']['checks'][0]['observation']['checked'] = True
        with self.assertRaisesRegex(ValueError, 'coverage'): runner.validate_result(changed)
