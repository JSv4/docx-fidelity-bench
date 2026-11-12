import copy
import unittest
from bench import html_artifacts


DECLARATION = {'type': 'marker-block-width', 'version': 1, 'marker': 'CedarWidth2',
               'reference': 'CedarWidth0', 'tolerancePx': 0.5}


def observation(width=211.4, reference_width=211.4):
    # Protocol geometry only, never a browser measurement or fidelity result.
    return {'index': 0, 'marker': 'CedarWidth2', 'matches': 1, 'text': 'CedarWidth0 CedarWidth2',
            'before': [0, 0, 60, 14], 'after': [0, 0, 60, 14], 'viewport': [0, 0, 1280, 1024], 'ports': [],
            'blockWidth': width, 'reference': {'marker': 'CedarWidth0', 'matches': 1, 'blockWidth': reference_width}}


class HtmlBlockWidth(unittest.TestCase):
    def test_marker_block_must_match_the_reference_block_width(self):
        html_artifacts.validate_declaration(DECLARATION)
        self.assertTrue(html_artifacts.block_width_pass(DECLARATION, observation(), 0))
        self.assertTrue(html_artifacts.block_width_pass(DECLARATION, observation(211.0, 211.4), 0))
        # A nested box that narrows the text by one reply level, or by a sub-pixel border, fails.
        for width in [189.5, 210.4, 212.4]:
            self.assertFalse(html_artifacts.block_width_pass(DECLARATION, observation(width), 0))

    def test_zero_width_clipped_missing_or_duplicate_markers_cannot_pass(self):
        self.assertFalse(html_artifacts.block_width_pass(DECLARATION, observation(0, 0), 0))
        value = observation(); value['ports'] = [{'overflowX': 'hidden', 'overflowY': 'hidden',
            'before': [0, 0, 60, 14], 'clipBefore': [0, 0, 30, 14], 'clipAfter': [0, 0, 30, 14],
            'scrollHeight': 14, 'clientHeight': 14}]
        self.assertFalse(html_artifacts.block_width_pass(DECLARATION, value, 0))
        for count in [0, 2]:
            value = observation(); value.update(matches=count, text=' '.join(['CedarWidth0'] + ['CedarWidth2'] * count))
            self.assertFalse(html_artifacts.block_width_pass(DECLARATION, value, 0))
        for count in [0, 2]:
            value = observation(); value['text'] = ' '.join(['CedarWidth0'] * count + ['CedarWidth2'])
            value['reference'] = {'marker': 'CedarWidth0', 'matches': count}
            self.assertFalse(html_artifacts.block_width_pass(DECLARATION, value, 0))

    def test_missing_or_inconsistent_width_facts_are_unmeasured_not_a_pass(self):
        for change in [{'blockWidth': None}, {'blockWidth': '211px'}, {'blockWidth': float('nan')}]:
            value = observation(); value.update(change)
            with self.assertRaises(ValueError): html_artifacts.block_width_pass(DECLARATION, value, 0)
        for reference in [None, {}, {'marker': 'Other', 'matches': 1, 'blockWidth': 1},
                          {'marker': 'CedarWidth0', 'matches': 2, 'blockWidth': 1},
                          {'marker': 'CedarWidth0', 'matches': 1}]:
            value = observation(); value['reference'] = reference
            with self.assertRaises(ValueError): html_artifacts.block_width_pass(DECLARATION, value, 0)

    def test_malformed_declarations_are_rejected(self):
        for change in [{'reference': ''}, {'reference': 'CedarWidth2'}, {'tolerancePx': 0}, {'tolerancePx': 3},
                       {'tolerancePx': '0.5'}, {'tolerancePx': float('inf')}, {'version': 2}, {'extra': 1}]:
            with self.assertRaises(ValueError): html_artifacts.validate_declaration(dict(DECLARATION, **change))
        missing = dict(DECLARATION); del missing['reference']
        with self.assertRaises(ValueError): html_artifacts.validate_declaration(missing)

    def test_runner_requests_width_observations_and_aggregation_recomputes_them(self):
        from test_html_artifacts import HtmlRunnerIntegration
        from bench import runner
        declaration = dict(DECLARATION, marker='FormatLabel')
        value = observation(); value.update(marker='FormatLabel', text='CedarWidth0 FormatLabel')
        profile = {'review': 'final', 'comments': 'margin'}
        result, request, _ = HtmlRunnerIntegration().measured('ignored', declaration=declaration,
            html_profile=profile, browser_facts={'observations': [value]})
        self.assertEqual(request['htmlAssertions'], [declaration])
        self.assertEqual(result['htmlSummary']['passed'], 1)
        changed = copy.deepcopy(result)
        changed['cases'][0]['html']['checks'][0]['observation']['blockWidth'] = 189.5
        with self.assertRaisesRegex(ValueError, 'coverage'): runner.validate_result(changed)


if __name__ == '__main__':
    unittest.main()
