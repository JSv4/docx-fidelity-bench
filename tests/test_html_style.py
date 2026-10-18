import copy
import unittest
from bench import html_artifacts


DECLARATION = {'type': 'marker-computed-style', 'version': 1, 'marker': 'CedarReply',
               'property': 'font-size', 'equals': '13.6px'}


def observation():
    # Protocol geometry only, never a browser measurement or fidelity result.
    return {'index': 0, 'marker': 'CedarReply', 'matches': 1, 'text': 'CedarReply',
            'before': [0, 0, 60, 14], 'after': [0, 0, 60, 14], 'viewport': [0, 0, 1280, 1024],
            'computedStyle': {'font-size': ['13.6px']}, 'ports': []}


class ComputedHtmlStyle(unittest.TestCase):
    def test_actual_browser_style_must_equal_the_declared_value(self):
        html_artifacts.validate_declaration(DECLARATION)
        self.assertTrue(html_artifacts.computed_style_pass(DECLARATION, observation(), 0))
        for size in ['11.56px', '9.826px', '0px']:
            value = observation(); value['computedStyle']['font-size'] = [size]
            self.assertFalse(html_artifacts.computed_style_pass(DECLARATION, value, 0))

    def test_hidden_clipped_missing_or_duplicate_text_cannot_supply_a_style_pass(self):
        value = observation(); value['ports'] = [{'overflowX': 'hidden', 'overflowY': 'hidden',
            'before': [0, 0, 60, 14], 'clipBefore': [0, 0, 30, 14], 'clipAfter': [0, 0, 30, 14],
            'scrollHeight': 14, 'clientHeight': 14}]
        self.assertFalse(html_artifacts.computed_style_pass(DECLARATION, value, 0))
        for count in [0, 2]:
            value = observation(); value.update(matches=count, text=' '.join(['CedarReply'] * count))
            self.assertFalse(html_artifacts.computed_style_pass(DECLARATION, value, 0))

    def test_missing_computed_facts_are_unmeasured_not_a_pass(self):
        for facts in [None, {}, {'font-size': 13.6}, {'font-size': []}, {'font-size': [13.6]}]:
            value = observation(); value['computedStyle'] = facts
            with self.assertRaises(ValueError): html_artifacts.computed_style_pass(DECLARATION, value, 0)

    def test_unknown_properties_and_malformed_expected_values_are_rejected(self):
        for change in [{'property': 'arbitrary'}, {'equals': ''}, {'equals': 13.6}, {'version': True}, {'extra': 1}]:
            with self.assertRaises(ValueError): html_artifacts.validate_declaration(dict(DECLARATION, **change))

    def test_runner_requests_style_observations_and_aggregation_recomputes_them(self):
        from test_html_artifacts import HtmlRunnerIntegration
        from bench import runner
        declaration = dict(DECLARATION, marker='FormatLabel')
        value = observation(); value.update(marker='FormatLabel', text='FormatLabel')
        profile = {'review': 'final', 'comments': 'margin'}
        result, request, _ = HtmlRunnerIntegration().measured('ignored', declaration=declaration,
            html_profile=profile, browser_facts={'observations': [value]})
        self.assertEqual(request['htmlAssertions'], [declaration])
        self.assertEqual(result['htmlSummary']['passed'], 1)
        changed = copy.deepcopy(result)
        changed['cases'][0]['html']['checks'][0]['observation']['computedStyle']['font-size'] = ['11.56px']
        with self.assertRaisesRegex(ValueError, 'coverage'): runner.validate_result(changed)

    def test_every_inline_fragment_of_a_marker_must_have_the_declared_style(self):
        value = observation(); value['computedStyle']['font-size'] = ['13.6px', '9.826px']
        self.assertFalse(html_artifacts.computed_style_pass(DECLARATION, value, 0))
