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


class ComputedLinkStyle(unittest.TestCase):
    """Colour and painted decoration lines, as the field-link cases declare them (Docxodus #1870)."""

    def setUp(self):
        from bench.common import ROOT, read_json
        self.cases = {c['id']: c for c in read_json(ROOT / 'fixtures/manifest.json')['cases']
                      if c['id'].startswith('field-link-')}

    @staticmethod
    def observe(declaration, index, colour, lines):
        value = observation()
        value.update(index=index, marker=declaration['marker'], text=declaration['marker'],
                     computedStyle={declaration['property']: [colour if declaration['property'] == 'color' else lines]})
        return value

    def failures(self, case_id, painted):
        """The style checks a rendering fails; `painted` maps each label to its colour and decoration lines."""
        failed = []
        for index, declaration in enumerate(self.cases[case_id]['htmlAssertions']):
            if declaration['type'] != 'marker-computed-style': continue
            html_artifacts.validate_declaration(declaration)
            if not html_artifacts.computed_style_pass(declaration, self.observe(declaration, index, *painted[declaration['marker']]), index):
                failed.append((declaration['marker'], declaration['property']))
        return failed

    BLACK, STYLE_BLUE, LINK_BLUE = 'rgb(0, 0, 0)', 'rgb(5, 99, 193)', 'rgb(0, 0, 238)'
    ENTRIES = ('WisteriaGate', 'WisteriaTerrace', 'WisteriaCourt')

    def correct(self, case_id):
        if 'simple-hyperlink' in case_id:
            return {'WisteriaArbor': (self.BLACK, 'none'), 'WisteriaPergola': (self.STYLE_BLUE, 'underline')}
        return {**{entry: (self.BLACK, 'none') for entry in self.ENTRIES}, 'WisteriaLantern': (self.STYLE_BLUE, 'underline')}

    def test_colour_and_decoration_values_have_one_browser_serialization(self):
        base = dict(DECLARATION)
        for prop, value in [('color', 'rgb(0, 0, 0)'), ('color', 'rgb(5, 99, 193)'), ('color', 'rgb(255, 255, 255)'),
                            ('text-decoration-line', 'none'), ('text-decoration-line', 'underline'),
                            ('text-decoration-line', 'underline line-through')]:
            html_artifacts.validate_declaration(dict(base, property=prop, equals=value))
        for prop, value in [('color', '#0563C1'), ('color', 'rgb(5,99,193)'), ('color', 'rgb(256, 0, 0)'),
                            ('color', 'rgb(05, 99, 193)'), ('color', 'rgba(0, 0, 0, 0.5)'), ('color', 'blue'),
                            ('color', '13.6px'), ('font-size', 'rgb(0, 0, 0)'), ('text-decoration-line', 'underline '),
                            ('text-decoration-line', 'line-through underline'), ('text-decoration-line', ''),
                            ('text-decoration-line', 'underline underline'), ('text-decoration-line', 'solid'),
                            ('text-decoration', 'underline')]:
            with self.assertRaises(ValueError, msg=(prop, value)):
                html_artifacts.validate_declaration(dict(base, property=prop, equals=value))

    def test_every_label_declares_the_colour_and_decoration_its_document_gives_it(self):
        self.assertEqual(len(self.cases), 5)
        for case_id, case in self.cases.items():
            styles = {(d['marker'], d['property']): d['equals'] for d in case['htmlAssertions']
                      if d['type'] == 'marker-computed-style'}
            expected = {(label, prop): value for label, (colour, lines) in self.correct(case_id).items()
                        for prop, value in (('color', colour), ('text-decoration-line', lines))}
            self.assertEqual(styles, expected, case_id)
            # The link-target checks keep their places, so their check names do not move.
            self.assertTrue(all(d['type'] == 'marker-attribute' for d in case['htmlAssertions'][:len(case['htmlAssertions']) - len(styles)]))

    def test_a_correct_rendering_passes_every_style_check(self):
        for case_id in self.cases:
            self.assertEqual(self.failures(case_id, self.correct(case_id)), [], case_id)

    def test_the_review_mutants_that_pass_the_pdf_colour_check_fail_here(self):
        # The independent review's LibreOffice mutants passed every mandatory PDF check, because the colour
        # check counts only 0563C1 ink: (a) contents entries black but underlined, (b) entries in the
        # browser's link blue 0000EE and underlined, (b') the plain WisteriaArbor as a 0000EE underlined link.
        for case_id in ('field-link-toc-complex-entries', 'field-link-toc-simple-entries', 'field-link-toc-element-entries-control'):
            black_underlined = dict(self.correct(case_id), **{e: (self.BLACK, 'underline') for e in self.ENTRIES})
            self.assertEqual(self.failures(case_id, black_underlined),
                             [(e, 'text-decoration-line') for e in self.ENTRIES], case_id)
            link_blue = dict(self.correct(case_id), **{e: (self.LINK_BLUE, 'underline') for e in self.ENTRIES})
            self.assertEqual(self.failures(case_id, link_blue),
                             [(e, p) for e in self.ENTRIES for p in ('color', 'text-decoration-line')], case_id)
        for case_id in ('field-link-simple-hyperlink', 'field-link-simple-hyperlink-control'):
            arbor = dict(self.correct(case_id), WisteriaArbor=(self.LINK_BLUE, 'underline'))
            self.assertEqual(self.failures(case_id, arbor),
                             [('WisteriaArbor', 'color'), ('WisteriaArbor', 'text-decoration-line')], case_id)
            # The review's control mutant, WisteriaArbor in the Hyperlink style, already failed the PDF check.
            styled = dict(self.correct(case_id), WisteriaArbor=(self.STYLE_BLUE, 'underline'))
            self.assertEqual(self.failures(case_id, styled),
                             [('WisteriaArbor', 'color'), ('WisteriaArbor', 'text-decoration-line')], case_id)

    def test_a_link_that_loses_its_colour_or_underline_fails(self):
        for case_id in self.cases:
            outside = 'WisteriaPergola' if 'simple-hyperlink' in case_id else 'WisteriaLantern'
            for painted, failed in [((self.BLACK, 'underline'), [(outside, 'color')]),
                                    ((self.STYLE_BLUE, 'none'), [(outside, 'text-decoration-line')])]:
                self.assertEqual(self.failures(case_id, dict(self.correct(case_id), **{outside: painted})), failed, case_id)


class RecordedLinkStyleObservations(unittest.TestCase):
    """Replay what the real browser observer saw (tests/test-link-style-browser.mjs records it).

    The validate workflow runs no browser. This record is bound to the observer's source digest, so CI
    fails once bench/html_browser.mjs changes until the browser test records it again."""

    def setUp(self):
        from bench.common import ROOT, digest, read_json
        self.record = read_json(ROOT / 'tests/link-style-observations.json')
        self.observer = digest(ROOT / 'bench/html_browser.mjs')
        self.cases = {c['id']: c for c in read_json(ROOT / 'fixtures/manifest.json')['cases'] if c['id'].startswith('field-link-')}

    def test_the_record_comes_from_the_current_observer(self):
        self.assertEqual(self.record['inspectorSha256'], self.observer,
                         'Record again: LINK_STYLE_RECORD=1 node --test tests/test-link-style-browser.mjs')

    def test_recorded_observations_give_the_expected_verdicts(self):
        names = [c['name'] for c in self.record['cases']]
        self.assertEqual(len(names), len(set(names)))
        for case in self.record['cases']:
            declarations = case['declarations']
            if 'id' in case:
                # The field-link cases' own declarations, not a copy that could drift from the manifest.
                self.assertEqual(declarations, [d for d in self.cases[case['id']]['htmlAssertions']
                                                if d['type'] == 'marker-computed-style'], case['name'])
            self.assertEqual([o['index'] for o in case['observations']], list(range(len(declarations))))
            failed = []
            for index, (declaration, observation) in enumerate(zip(declarations, case['observations'])):
                html_artifacts.validate_declaration(declaration)
                if not html_artifacts.computed_style_pass(declaration, observation, index):
                    failed.append(f"{declaration['marker']} {declaration['property']}")
            self.assertEqual(failed, case['failed'], case['name'])
            if 'painted' in case:
                lines = case['observations'][0]['computedStyle']['text-decoration-line']
                self.assertEqual(lines != ['none'], case['painted'], case['name'])

    def test_the_record_covers_the_review_mutants_svg_text_and_each_propagation_stop(self):
        names = {c['name'] for c in self.record['cases']}
        for name in ["review mutant (a): black, underlined entries", "review mutant (b): entries in the link blue, underlined",
                     "review mutant (b'): WisteriaArbor as a link-blue underlined link",
                     'WisteriaPergola as black SVG text in a blue, underlined link',
                     'correct simple fields, WisteriaArbor as black SVG text in a default link',
                     'inline table in an underlined paragraph', 'inline flex box in an underlined paragraph',
                     'inline grid in an underlined paragraph', 'float in an underlined paragraph',
                     'absolutely positioned in an underlined paragraph', 'fixed in an underlined paragraph',
                     'underlined flex container', 'underlined grid container', 'SVG text in an underlined link']:
            self.assertIn(name, names)
        self.assertEqual({c['id'] for c in self.record['cases'] if 'id' in c}, set(self.cases))
