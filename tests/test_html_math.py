import copy
import unittest
from bench import html_artifacts, pdf


DECLARATION = {'type': 'math-expression', 'version': 1, 'marker': 'MapleFormula',
               'display': 'inline', 'tree': ['mfrac', ['mn', '27.5'], ['mn', '9']]}


def observation():
    # Protocol facts only; real browser mutant checks live in test-math-browser.mjs.
    return {'index': 0, 'marker': 'MapleFormula', 'matches': 1, 'display': 'inline',
            'computedDisplay': 'math', 'fractionBars': [None],
            'namespace': 'http://www.w3.org/1998/Math/MathML', 'tree': copy.deepcopy(DECLARATION['tree']),
            'visible': True, 'rectangle': [10, 10, 30, 40]}


class MathHtml(unittest.TestCase):
    def test_native_body_font_cannot_satisfy_the_required_math_face(self):
        declaration = {'type': 'required-font-family', 'version': 1, 'family': 'DejaVu Serif'}
        case = {'tokens': {'27.5': 1}, 'fonts': ['Liberation Serif', 'DejaVu Serif'], 'assertions': [declaration]}
        info = {'tokens': {'27.5': 1}, 'fonts': ['LiberationSerif'], 'geometry': [], 'words': []}
        self.assertIn('assertion-required-font-family', pdf.reference_failures(case, info, 'libreoffice'))
        self.assertIn('assertion-required-font-family', pdf.reference_failures(case, dict(info, fonts=[]), 'libreoffice'))
        self.assertEqual(pdf.reference_failures(case, dict(info, fonts=['LiberationSerif', 'DejaVuSerif']), 'libreoffice'), [])

    def test_structure_and_display_are_mandatory(self):
        html_artifacts.validate_declaration(DECLARATION)
        self.assertTrue(html_artifacts.math_expression_pass(DECLARATION, observation(), 0))
        for change in [{'tree': ['mfrac', ['mn', '9'], ['mn', '27.5']]},
                       {'tree': ['mrow', ['mn', '27.5'], ['mn', '9']]},
                       {'matches': 0}, {'matches': 2}, {'namespace': 'http://www.w3.org/1999/xhtml'},
                       {'computedDisplay': 'block math'}, {'fractionBars': ['0']},
                       {'display': 'block'}, {'visible': False}, {'rectangle': [10, 10, 10, 10]}]:
            self.assertFalse(html_artifacts.math_expression_pass(DECLARATION, dict(observation(), **change), 0))

    def test_unknown_or_unbounded_declarations_fail(self):
        for change in [{'display': 'auto'}, {'tree': ['mn', '']}, {'tree': ['mroot', ['mn', '3']]},
                       {'tree': ['svg', ['mn', '9']]}, {'version': True}, {'extra': 1}]:
            with self.assertRaises(ValueError): html_artifacts.validate_declaration(dict(DECLARATION, **change))

    def test_runner_and_aggregation_replay_the_structural_result(self):
        from test_html_artifacts import HtmlRunnerIntegration
        from bench import runner
        declaration = dict(DECLARATION, marker='FormatLabel')
        facts = dict(observation(), marker='FormatLabel')
        result, request, _ = HtmlRunnerIntegration().measured('ignored', declaration=declaration,
            browser_facts={'observations': [facts]})
        self.assertEqual(request['htmlAssertions'], [declaration])
        self.assertEqual(result['htmlSummary']['passed'], 1)
        result['cases'][0]['html']['checks'][0]['observation']['tree'][1:] = [['mn', '9'], ['mn', '27.5']]
        with self.assertRaisesRegex(ValueError, 'coverage'): runner.validate_result(result)
