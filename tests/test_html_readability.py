import copy
import json
import tempfile
import unittest
from pathlib import Path
from bench import common, html_artifacts


DECLARATION = {'type': 'marker-readable', 'version': 1, 'marker': 'Reader2',
               'tokens': ['Reader0', 'Reader1', 'Reader2']}


def observation():
    # Protocol-only geometry fixtures, not renderer measurements or fidelity results.
    return {'index': 0, 'marker': 'Reader2', 'matches': 1, 'text': 'Reader0 Reader1 Reader2',
            'blockText': 'Reader0 Reader1 Reader2', 'before': [8, 100, 65, 117], 'after': [8, 31, 65, 48], 'viewport': [0, 0, 1280, 1024],
            'ports': [{'overflowY': 'auto', 'overflowX': 'hidden', 'before': [8, 100, 65, 117],
                       'clipBefore': [8, 8, 108, 48], 'clipAfter': [8, 8, 108, 48],
                       'scrollHeight': 140, 'clientHeight': 40}]}


class ReadableHtmlContract(unittest.TestCase):
    def test_complete_note_can_be_read_by_user_scrolling(self):
        self.assertTrue(html_artifacts.readable_pass(DECLARATION, observation(), 0))

    def test_programmatic_hidden_overflow_is_not_a_user_scroll_control(self):
        value = observation()
        value['ports'][0]['overflowY'] = 'hidden'
        self.assertFalse(html_artifacts.readable_pass(DECLARATION, value, 0))

    def test_missing_or_reordered_middle_words_cannot_pass_with_visible_tail(self):
        for text in ['Reader0 Reader2', 'Reader1 Reader0 Reader2']:
            value = observation()
            value['text'] = text
            value['blockText'] = text
            self.assertFalse(html_artifacts.readable_pass(DECLARATION, value, 0))

    def test_extra_word_in_the_comment_paragraph_is_not_ignored(self):
        value = observation()
        value['text'] += ' Extra'
        value['blockText'] += ' Extra'
        self.assertFalse(html_artifacts.readable_pass(DECLARATION, value, 0))

    def test_duplicate_and_missing_tail_are_measured_failures(self):
        for count, text in [(2, 'Reader0 Reader1 Reader2 Reader2'), (0, 'Reader0 Reader1')]:
            value = observation()
            value['matches'], value['text'] = count, text
            self.assertFalse(html_artifacts.readable_pass(DECLARATION, value, 0))

    def test_inconsistent_marker_count_is_not_accepted_as_evidence(self):
        value = observation()
        value['text'] += ' Reader2'
        with self.assertRaisesRegex(ValueError, 'inventory'):
            html_artifacts.readable_pass(DECLARATION, value, 0)

    def test_later_parent_clipping_or_offscreen_tail_is_still_a_failure(self):
        value = observation()
        value['ports'].append({'overflowY': 'hidden', 'overflowX': 'hidden',
                               'before': [8, 31, 65, 48], 'clipBefore': [0, 0, 100, 30],
                               'clipAfter': [0, 0, 100, 30], 'scrollHeight': 100, 'clientHeight': 30})
        self.assertFalse(html_artifacts.readable_pass(DECLARATION, value, 0))
        value = observation()
        value['after'] = [8, 1100, 65, 1117]
        self.assertFalse(html_artifacts.readable_pass(DECLARATION, value, 0))

    def test_zero_size_or_horizontally_clipped_glyphs_do_not_pass(self):
        for rectangle in [[8, 31, 8, 48], [8, 31, 65, 31], [8, 31, 200, 48]]:
            value = observation()
            value['after'] = rectangle
            self.assertFalse(html_artifacts.readable_pass(DECLARATION, value, 0))

    def test_nonfinite_boolean_and_missing_geometry_are_rejected(self):
        for key, change in [('after', None), ('after', [False, 1, 20, 10]),
                            ('after', [float('nan'), 1, 20, 10]), ('index', False)]:
            value = observation()
            value[key] = change
            with self.assertRaises(ValueError): html_artifacts.readable_pass(DECLARATION, value, 0)

    def test_unknown_or_malformed_declarations_and_profiles_are_rejected(self):
        for value in [dict(DECLARATION, version=True), dict(DECLARATION, extra=1),
                      dict(DECLARATION, tokens=[]), dict(DECLARATION, tokens=['Reader0']),
                      dict(DECLARATION, tokens=['Reader 0', 'Reader2'])]:
            with self.assertRaises(ValueError): html_artifacts.validate_declaration(value)
        for value in [None, {'review': []}, {'review': 'final', 'comments': []},
                      {'review': 'final', 'comments': 'margin', 'unknown': True}]:
            with self.assertRaises(ValueError): common.validate_render_profile(value)

    def test_identity_and_html_profile_are_bound_to_the_delivered_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            html = folder / 'candidate.html'
            html.write_text('<p>Reader0 Reader1 Reader2</p>')
            profile = {'review': 'final', 'comments': 'margin'}
            runtime = {'executableSha256': 'a' * 64}
            facts = {'schema': 1, 'htmlSha256': common.digest(html),
                     'inspectorSha256': common.digest(html_artifacts.BROWSER_SOURCE),
                     'policy': html_artifacts.BROWSER_POLICY, **runtime, 'observations': [observation()]}
            path = folder / 'html-browser.json'
            path.write_text(json.dumps(facts))
            response = {'htmlArtifact': {'status': 'ok', 'sha256': common.digest(html),
                        'profile': profile, 'browserFactsSha256': common.digest(path)}, 'renderer': {'runtime': runtime}}
            result = html_artifacts.inspect(folder, response, [DECLARATION], profile)
            self.assertEqual(result['status'], 'measured')
            self.assertTrue(result['checks'][0]['passed'])
            case = {'id': 'reader', 'html': result, 'adapter': response}
            summary = html_artifacts.aggregate([case], {'reader': [DECLARATION]},
                        common.digest(html_artifacts.BROWSER_SOURCE), {'reader': profile})
            self.assertEqual(summary['passed'], 1)
            for key, change in [('profile', {'review': 'final', 'comments': 'hidden'}), ('browserFactsSha256', '0' * 64)]:
                changed = copy.deepcopy(response)
                changed['htmlArtifact'][key] = change
                self.assertEqual(html_artifacts.inspect(folder, changed, [DECLARATION], profile)['status'], 'unmeasured')
            changed = copy.deepcopy(case)
            changed['html']['checks'][0]['observation']['ports'][0]['overflowY'] = 'hidden'
            with self.assertRaisesRegex(ValueError, 'coverage'):
                html_artifacts.aggregate([changed], {'reader': [DECLARATION]},
                    common.digest(html_artifacts.BROWSER_SOURCE), {'reader': profile})


if __name__ == '__main__': unittest.main()
