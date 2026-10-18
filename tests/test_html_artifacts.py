import copy
import tempfile
import unittest
from pathlib import Path
from bench import common, html_artifacts, metrics, runner


ASSERTION = {'type': 'marker-attribute', 'version': 1, 'marker': 'FormatLabel', 'attribute': 'title', 'equals': 'Bold added'}


class HtmlArtifactContract(unittest.TestCase):
    def check(self, source):
        return html_artifacts.check(source, [ASSERTION])[0]

    def test_delivered_title_is_checked(self):
        self.assertTrue(self.check('<span title="Bold added">FormatLabel</span>')['passed'])
        self.assertFalse(self.check('<span title="Bold added, Font changed">FormatLabel</span>')['passed'])

    def test_nearest_attribute_wins(self):
        self.assertFalse(self.check('<p title="Bold added"><span title="Wrong">FormatLabel</span></p>')['passed'])
        self.assertFalse(self.check('<p title="Bold added"><span title="">FormatLabel</span></p>')['passed'])

    def test_nested_inline_fragments_keep_the_same_label(self):
        self.assertTrue(self.check('<span title="Bold added">Format<i>La</i>bel</span>')['passed'])
        self.assertFalse(self.check('<span title="Bold added">Format<i title="Wrong">La</i>bel</span>')['passed'])

    def test_entities_are_decoded_in_text_and_attributes(self):
        declaration = dict(ASSERTION, marker='Cedar&Elm', equals='Bold & italic')
        self.assertTrue(html_artifacts.check('<span title="Bold &amp; italic">Cedar&amp;Elm</span>', [declaration])[0]['passed'])

    def test_duplicate_attributes_use_the_browser_first_value(self):
        self.assertFalse(self.check('<span title="Wrong" title="Bold added">FormatLabel</span>')['passed'])

    def test_missing_duplicate_or_partial_marker_cannot_pass(self):
        for value in ('Other', 'FormatLabelExtra', 'FormatLabel FormatLabel'):
            self.assertFalse(self.check(f'<span title="Bold added">{value}</span>')['passed'])

    def test_noncontent_and_hidden_text_cannot_supply_a_marker(self):
        for tag in ('head', 'script', 'style', 'template'):
            self.assertFalse(self.check(f'<{tag} title="Bold added">FormatLabel</{tag}>')['passed'])
        self.assertFalse(self.check('<span hidden title="Bold added">FormatLabel</span>')['passed'])

    def test_block_boundaries_do_not_join_words(self):
        self.assertTrue(self.check('<p>Before</p><p title="Bold added">FormatLabel</p>')['passed'])

    def test_delivery_and_hash_are_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(html_artifacts.inspect(root, {}, [ASSERTION])['status'], 'unmeasured')
            path = root / 'candidate.html'
            path.write_text('<span title="Bold added">FormatLabel</span>')
            response = {'htmlArtifact': {'status': 'ok', 'sha256': '0' * 64}}
            self.assertEqual(html_artifacts.inspect(root, response, [ASSERTION])['status'], 'unmeasured')
            response['htmlArtifact']['sha256'] = common.digest(path)
            measured = html_artifacts.inspect(root, response, [ASSERTION])
            self.assertEqual(measured['status'], 'measured')
            self.assertTrue(measured['checks'][0]['passed'])

    def result(self, source):
        declaration = {'sample': [ASSERTION]}
        contract = {'metric': metrics.CONTRACT, 'htmlAssertions': declaration, 'htmlInspectorVersion': 1,
                    'htmlInspectorSha256': common.digest(Path(html_artifacts.__file__))}
        case = {'id': 'sample', 'category': 'paragraphs', 'status': 'measured', 'score': 100,
                'checks': [{'name': 'pdf', 'passed': True}], 'pages': [{'score': 100}], 'close': True,
                'html': {'status': 'measured', 'checks': html_artifacts.check(source, [ASSERTION])}}
        return {'schema': 1, 'contract': contract, 'contractDigest': common.identity(contract), 'cases': [case],
                'suite': {'cases': ['sample']}, 'summary': metrics.aggregate([case], ['sample']),
                'htmlSummary': html_artifacts.aggregate([case], declaration)}

    def test_html_failure_does_not_change_pdf_score_but_fails_comparison(self):
        good = self.result('<span title="Bold added">FormatLabel</span>')
        bad = self.result('<span title="Wrong">FormatLabel</span>')
        self.assertEqual(bad['summary']['score'], 100)
        self.assertEqual(runner.compare(good, good, 0), [])
        self.assertEqual(runner.compare(good, bad, 0), ['sample: delivered HTML check failure'])

    def test_missing_html_cannot_claim_complete_coverage_or_gate(self):
        good = self.result('<span title="Bold added">FormatLabel</span>')
        missing = copy.deepcopy(good)
        del missing['cases'][0]['html']
        missing['htmlSummary'] = html_artifacts.aggregate(missing['cases'], missing['contract']['htmlAssertions'])
        self.assertFalse(missing['htmlSummary']['complete'])
        self.assertEqual(missing['summary']['score'], 100)
        with self.assertRaisesRegex(ValueError, 'unmeasured delivered HTML'):
            runner.compare(good, missing, 0)

    def test_tampered_summary_or_missing_check_is_rejected(self):
        value = self.result('<span title="Bold added">FormatLabel</span>')
        value['htmlSummary']['passed'] = 0
        with self.assertRaisesRegex(ValueError, 'summary'):
            runner.validate_result(value)
        value = self.result('<span title="Bold added">FormatLabel</span>')
        value['cases'][0]['html']['checks'].clear()
        with self.assertRaisesRegex(ValueError, 'coverage'):
            runner.validate_result(value)

    def test_changed_inspector_code_cannot_pass_regression_comparison(self):
        good = self.result('<span title="Bold added">FormatLabel</span>')
        changed = copy.deepcopy(good)
        changed['contract']['htmlInspectorSha256'] = '0' * 64
        changed['contractDigest'] = common.identity(changed['contract'])
        with self.assertRaisesRegex(ValueError, 'contract changed'):
            runner.compare(good, changed, 0)

    def test_unknown_or_malformed_declarations_are_rejected(self):
        registry = common.validate_registry()
        for declaration in (None, [1], [dict(ASSERTION, version=True)], [dict(ASSERTION, version=2)],
                            [dict(ASSERTION, marker='')], [dict(ASSERTION, extra='ignored')]):
            changed = copy.deepcopy(registry)
            changed['cases'][0]['htmlAssertions'] = declaration
            with self.assertRaises(ValueError):
                common.validate_registry(changed)

    def test_a_forged_pass_cannot_override_an_observed_wrong_attribute(self):
        value = self.result('<span title="Wrong">FormatLabel</span>')
        value['cases'][0]['html']['checks'][0]['passed'] = True
        with self.assertRaisesRegex(ValueError, 'coverage'):
            runner.validate_result(value)

    def test_malformed_measurements_and_assertion_contracts_are_rejected(self):
        for declarations in (None, [], {'sample': None}, {'sample': []}, {'other': [ASSERTION]}):
            value = self.result('<span title="Bold added">FormatLabel</span>')
            value['contract']['htmlAssertions'] = declarations
            value['contractDigest'] = common.identity(value['contract'])
            with self.assertRaises(ValueError): runner.validate_result(value)
        value = self.result('<span title="Bold added">FormatLabel</span>')
        value['cases'][0]['html'] = None
        with self.assertRaisesRegex(ValueError, 'measurement'):
            runner.validate_result(value)

    def test_cli_gates_distinguish_failed_and_unmeasured_html(self):
        import sys
        from unittest.mock import patch
        from bench import __main__ as cli
        good = self.result('<span title="Bold added">FormatLabel</span>')
        wrong = self.result('<span title="Wrong">FormatLabel</span>')
        missing = copy.deepcopy(good)
        missing['cases'][0]['html'] = {'status': 'unmeasured'}
        missing['htmlSummary'] = html_artifacts.aggregate(missing['cases'], missing['contract']['htmlAssertions'])
        for value, expected in [(good, [0, 0, 0]), (wrong, [0, 1, 1]), (missing, [2, 2, 2])]:
            for gate, status in zip(['report', 'mandatory', 'close'], expected):
                argv = ['bench', 'run', '--reference', 'ref', '--adapter', 'libreoffice',
                        '--candidate', 'source', '--out', 'out', '--gate', gate]
                with patch.object(sys, 'argv', argv), patch.object(cli, 'validate_registry', return_value={}), \
                     patch.object(cli.runner, 'run', return_value=value):
                    self.assertEqual(cli.main(), status)

    def test_record_proposal_cannot_hide_unmeasured_html(self):
        import sys
        from unittest.mock import patch
        from bench import __main__ as cli
        value = self.result('<span title="Bold added">FormatLabel</span>')
        value['cases'][0]['html'] = {'status': 'unmeasured'}
        value['htmlSummary'] = html_artifacts.aggregate(value['cases'], value['contract']['htmlAssertions'])
        with tempfile.TemporaryDirectory() as temp:
            source, destination = Path(temp) / 'result.json', Path(temp) / 'proposal.json'
            common.write_json(source, value)
            with patch.object(sys, 'argv', ['bench', 'record-propose', str(source), '--out', str(destination)]), \
                 patch.object(cli, 'validate_registry', return_value={}):
                with self.assertRaisesRegex(ValueError, 'Incomplete'):
                    cli.main()
            self.assertFalse(destination.exists())


class HtmlRunnerIntegration(unittest.TestCase):
    def measured(self, title, adapter='contract', declaration=ASSERTION, html_profile=None, browser_facts=None):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'input.docx'; source.write_bytes(b'fixture')
            reference = root / 'reference.pdf'; reference.write_bytes(b'pdf')
            raster = root / 'page.ppm'; raster.write_bytes(b'P6\n1 1\n255\n\xff\xff\xff')
            case = {'id': 'sample', 'category': 'paragraphs', 'input': 'input.docx', 'sha256': common.digest(source),
                    'profile': {'review': 'markup', 'comments': 'hidden'}, 'fonts': [], 'tokens': {'FormatLabel': 1},
                    'assertions': [], 'htmlAssertions': [declaration]}
            if html_profile is not None: case['htmlProfile'] = html_profile
            registry = {'suite': {'id': 'contract', 'version': 1, 'cases': ['sample']}, 'cases': [case]}
            bundle = {'track': 'libreoffice', 'cases': {'sample': {'eligible': True, 'pdf': 'reference.pdf'}}}
            common.write_json(root / 'bundle.json', bundle)
            requests = []
            def render(name, request):
                requests.append(request)
                Path(request['output']).write_bytes(b'pdf')
                response = {'status': 'ok', 'renderer': {'name': 'contract'}}
                if 'htmlOutput' in request and title is not None:
                    path = Path(request['htmlOutput'])
                    path.write_text(f'<span title="{title}">FormatLabel</span>')
                    response['htmlArtifact'] = {'status': 'ok', 'sha256': common.digest(path)}
                    if html_profile is not None: response['htmlArtifact']['profile'] = html_profile
                    if browser_facts is not None and 'htmlObservations' in request:
                        facts = dict(browser_facts, schema=1, htmlSha256=common.digest(path),
                                     inspectorSha256=common.digest(html_artifacts.BROWSER_SOURCE),
                                     policy=html_artifacts.BROWSER_POLICY, executableSha256='a' * 64)
                        facts_path = Path(request['htmlObservations'])
                        common.write_json(facts_path, facts)
                        response['htmlArtifact']['browserFactsSha256'] = common.digest(facts_path)
                        response['renderer']['runtime'] = {'executableSha256': 'a' * 64}
                return response
            with patch.object(runner, 'ROOT', root), patch.object(runner, 'validate_registry', return_value=registry), \
                 patch.object(runner, 'environment', return_value={'contract': {}, 'fontDirectories': []}), \
                 patch.object(runner, 'validate_bundle'), patch.object(runner.adapters, 'render', side_effect=render), \
                 patch.object(runner.pdf, 'inspect_pdf', return_value={}), \
                 patch.object(runner.pdf, 'reference_failures', return_value=[]), \
                 patch.object(runner.pdf, 'correctness', return_value=[{'name': 'pdf', 'passed': True}]), \
                 patch.object(runner.pdf, 'rasterize', return_value=[raster]):
                result = runner.run(root / 'run', root / 'bundle.json', adapter, 'contract-source')
            page = (root / 'run/index.html').read_text()
            runner.validate_result(result)
            return result, requests[0], page

    def test_runner_requests_reads_and_reports_real_html(self):
        good, request, page = self.measured('Bold added')
        self.assertIn('htmlOutput', request)
        self.assertIn('htmlReport', request)
        self.assertEqual(good['summary']['score'], 100)
        self.assertEqual(good['htmlSummary'], {'required': 1, 'measured': 1, 'passed': 1, 'complete': True})
        self.assertIn('Delivered HTML feature checks: 1 cases passed', page)
        self.assertIn('Delivered HTML</a>', page)
        bad, _, page = self.measured('Bold added, Font changed')
        self.assertEqual(bad['summary']['score'], 100)
        self.assertEqual(bad['htmlSummary']['passed'], 0)
        self.assertIn('Bold added, Font changed', page)
        self.assertIn('<td>Failed</td>', page)
        self.assertIn('<th>HTML features</th>', page)
        self.assertEqual(runner.compare(good, bad, 0), ['sample: delivered HTML check failure'])

    def test_runner_retains_pdf_and_reports_missing_html_coverage(self):
        result, _, page = self.measured(None)
        self.assertEqual(result['summary']['score'], 100)
        self.assertFalse(result['htmlSummary']['complete'])
        self.assertIn('Delivered HTML: unmeasured', page)

    def test_reference_engine_calibration_is_explicitly_pdf_only(self):
        result, request, page = self.measured(None, adapter='libreoffice')
        self.assertNotIn('htmlOutput', request)
        self.assertNotIn('htmlAssertions', result['contract'])
        self.assertNotIn('htmlSummary', result)
        self.assertNotIn('Delivered HTML feature checks', page)
        self.assertEqual(result['summary']['score'], 100)

    def test_readable_html_request_and_profile_cannot_be_silently_omitted(self):
        # Protocol-only measurements: prove orchestration, not renderer fidelity.
        declaration = {'type': 'marker-readable', 'version': 1, 'marker': 'FormatLabel', 'tokens': ['FormatLabel']}
        observation = {'index': 0, 'marker': 'FormatLabel', 'matches': 1, 'text': 'FormatLabel',
                       'blockText': 'FormatLabel', 'before': [0, 0, 50, 10], 'after': [0, 0, 50, 10],
                       'viewport': [0, 0, 1280, 1024], 'ports': []}
        profile = {'review': 'final', 'comments': 'margin'}
        result, request, _ = self.measured('ignored', declaration=declaration, html_profile=profile,
                                          browser_facts={'observations': [observation]})
        self.assertEqual(request['htmlProfile'], profile)
        self.assertEqual(request['htmlAssertions'], [declaration])
        self.assertTrue(request['htmlObservations'].endswith('/html-browser.json'))
        self.assertEqual(result['contract']['htmlProfiles'], {'sample': profile})
        self.assertEqual(result['contract']['htmlBrowserInspectorSha256'], common.digest(html_artifacts.BROWSER_SOURCE))
        self.assertEqual(result['htmlSummary']['passed'], 1)
        missing, _, _ = self.measured('ignored', declaration=declaration, html_profile=profile)
        self.assertFalse(missing['htmlSummary']['complete'])
        changed = copy.deepcopy(result)
        changed['contract'].pop('htmlBrowserInspectorSha256')
        changed['contractDigest'] = common.identity(changed['contract'])
        with self.assertRaisesRegex(ValueError, 'browser inspector'):
            runner.validate_result(changed)
