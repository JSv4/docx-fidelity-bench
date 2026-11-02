import unittest
import copy
from bench.common import validate_render_profile, validate_pdf_companion
from bench.pdf import companion_checks
from bench import html_artifacts


class VisibilityPolicy(unittest.TestCase):
    def test_review_display_observation_detects_each_wrong_family_and_empty_area(self):
        expected = dict(formatBalloons=0, commentBalloons=0, insertions=1, deletions=1, areas=0, layers=0)
        declaration = dict(type='review-display', version=1, marker='HazelCurrent', expected=expected)
        html_artifacts.validate_declaration(declaration)
        facts = dict(index=0, marker='HazelCurrent', matches=1, text='HazelCurrent', ports=[],
                     before=[10, 10, 90, 30], after=[10, 10, 90, 30], viewport=[0, 0, 1280, 1024], reviewCounts=expected.copy())
        self.assertTrue(html_artifacts.review_display_pass(declaration, facts, 0))
        for key in expected:
            wrong = copy.deepcopy(facts)
            wrong['reviewCounts'][key] = 1 - expected[key]
            self.assertFalse(html_artifacts.review_display_pass(declaration, wrong, 0))
        with self.assertRaises(ValueError): html_artifacts.validate_declaration(dict(declaration, expected={'areas': 0}))

    def test_closed_boolean_policy_and_placement(self):
        base = {'review': 'markup', 'comments': 'margin', 'markupPresentation': 'word',
                'commentColumnPlacement': 'balloons'}
        for policy in ({}, {'formatting': False}, {'comments': True, 'insertionsAndDeletions': False}):
            profile = dict(base, markupVisibility=policy)
            self.assertEqual(validate_render_profile(profile), profile)
        for policy in (None, [], True, {'formatting': 0}, {'comments': 'false'}, {'unknown': False}):
            with self.assertRaises(ValueError): validate_render_profile(dict(base, markupVisibility=policy))
        with self.assertRaises(ValueError): validate_render_profile(dict(base, commentColumnPlacement='outside'))

    def test_hidden_source_tokens_cannot_pass_as_extra_renderer_labels(self):
        declaration = {'profile': {'review': 'markup', 'comments': 'hidden'}, 'pageSizePt': [612, 792],
                       'requiredTokens': {'HazelCurrent': 1}, 'forbiddenTokens': ['HazelDeleted']}
        validate_pdf_companion(declaration)
        info = {'geometry': [{'rotation': 0, 'media': [0, 0, 612, 792], 'crop': [0, 0, 612, 792]}],
                'words': [{'text': 'HazelCurrent', 'page': 1, 'rect': [72, 72, 140, 90], 'inkPixels': 30}]}
        self.assertTrue(all(check['passed'] for check in companion_checks(declaration, info)))
        info['words'].append({'text': 'HazelDeleted', 'page': 1, 'rect': [145, 72, 210, 90], 'inkPixels': 30})
        checks = companion_checks(declaration, info)
        self.assertTrue(next(check['passed'] for check in checks if check['name'] == 'companion-pdf-source-tokens'))
        self.assertFalse(next(check['passed'] for check in checks if check['name'] == 'companion-pdf-forbidden-tokens'))
        with self.assertRaises(ValueError): validate_pdf_companion(dict(declaration, forbiddenTokens=['HazelCurrent']))


if __name__ == '__main__':
    unittest.main()
