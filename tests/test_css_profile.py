import unittest
from bench import common

CSS = 'p > span { font-size: 32px !important; }'
PROFILE = {'review': 'final', 'comments': 'hidden', 'additionalCss': CSS}

class CssProfile(unittest.TestCase):
    def test_stylesheet_is_allowed_only_for_the_html_companion(self):
        self.assertEqual(common.validate_render_profile(PROFILE, allow_additional_css=True), PROFILE)
        with self.assertRaises(ValueError): common.validate_render_profile(PROFILE)
        registry = common.read_json(common.ROOT / 'fixtures/manifest.json')
        registry['cases'][0]['profile'] = PROFILE
        with self.assertRaises(ValueError): common.validate_registry(registry)

    def test_empty_nontext_and_malformed_stylesheet_declarations_are_rejected(self):
        for css in ['', None, 42, {}, '\ud800']:
            with self.assertRaises(ValueError):
                common.validate_render_profile(dict(PROFILE, additionalCss=css), allow_additional_css=True)

    def test_runner_binds_the_entire_stylesheet_profile_to_observed_html(self):
        from test_html_artifacts import HtmlRunnerIntegration
        from test_html_style import DECLARATION, observation
        value = observation(); value.update(marker='FormatLabel', text='FormatLabel')
        declaration = dict(DECLARATION, marker='FormatLabel')
        result, request, _ = HtmlRunnerIntegration().measured('ignored', declaration=declaration,
            html_profile=PROFILE, browser_facts={'observations': [value]})
        self.assertEqual(request['htmlProfile'], PROFILE)
        self.assertEqual(result['contract']['htmlProfiles']['sample'], PROFILE)
        self.assertEqual(result['htmlSummary']['passed'], 1)

    def test_child_and_descendant_controls_have_identical_docx_and_pdf_profile(self):
        records = {c['id']: c for c in common.validate_registry()['cases']}
        child, control = [records[c] for c in ['html-css-child-selector', 'html-css-descendant-control']]
        self.assertEqual(child['sha256'], control['sha256'])
        self.assertEqual(child['profile'], control['profile'])
        self.assertNotIn('additionalCss', child['profile'])
        self.assertEqual(child['htmlAssertions'], control['htmlAssertions'])
        self.assertEqual(child['htmlProfile']['additionalCss'].replace(' > ', ' '), control['htmlProfile']['additionalCss'])
        self.assertEqual(child['tokens'], control['tokens'])
