import copy
import unittest
from bench.projection import checks, normalize
from bench.projection_fixtures import validate


class ProjectionTests(unittest.TestCase):
    def test_original_inputs_regenerate(self):
        manifest = validate()
        self.assertEqual(36, len(manifest['cases']))
        self.assertEqual(18, sum(c['control'] for c in manifest['cases']))

    def test_complete_text_and_anchor_checks_reject_loss_duplication_and_wrong_anchor(self):
        case = {'expected': '# Document AshHost AshInside AshFollowing', 'anchored': ['AshInside']}
        good = {'errors': [], 'markdown': '# Document\n\n{#p:body:a} AshHost\n\n{#p:body:b} AshInside\n\n{#p:body:c} AshFollowing',
                'paragraphs': [{'text': 'AshInside', 'markdown': '{#p:body:b} AshInside'}]}
        self.assertTrue(all(checks(case, good).values()))
        for old, new in [('AshInside', ''), ('AshInside', 'AshInside AshInside'), ('AshFollowing', 'Unexpected')]:
            bad = copy.deepcopy(good)
            bad['markdown'] = bad['markdown'].replace(old, new)
            self.assertFalse(checks(case, bad)['completeText'])
        bad = copy.deepcopy(good)
        bad['paragraphs'][0]['markdown'] = '{#p:body:a} AshHost'
        self.assertFalse(checks(case, bad)['paragraphAnchors'])
        bad = copy.deepcopy(good)
        bad['errors'] = ['Invalid source']
        self.assertFalse(checks(case, bad)['schema'])

    def test_raw_refusal_checks_reject_success_mutation_revisions_and_history(self):
        case = {'operation': 'raw-replace', 'tracked': True, 'expected': 'LarchOriginal', 'anchored': []}
        good = {'errors': [], 'markdown': 'LarchOriginal', 'paragraphs': [],
                'raw': {'success': False, 'error': 'TrackedOperationUnsupported',
                        'revisionCount': 0, 'unchanged': True, 'undo': False}}
        self.assertTrue(all(checks(case, good).values()))
        for key, value in [('success', True), ('error', None), ('revisionCount', 1),
                           ('unchanged', False), ('undo', True)]:
            bad = copy.deepcopy(good)
            bad['raw'][key] = value
            self.assertFalse(checks(case, bad)['rawMutation'])
        del good['raw']
        self.assertFalse(checks(case, good)['rawMutation'])

    def test_table_insert_checks_reject_refusal_revision_count_resolution_and_history(self):
        case = {'operation': 'table-insert', 'tracked': True, 'expected': 'New', 'anchored': [],
                'tableInsert': {'revisions': 1, 'accepted': 'New', 'rejected': 'Old'}}
        good = {'errors': [], 'markdown': 'New', 'paragraphs': [],
                'table': {'success': True, 'error': None, 'revisionCount': 1,
                          'accepted': '{#p:body:a} New', 'rejected': 'Old', 'undo': True}}
        self.assertTrue(all(checks(case, good).values()))
        for key, value in [('success', False), ('error', 'TrackedOperationUnsupported'), ('revisionCount', 2),
                           ('accepted', 'Old'), ('rejected', 'Old New'), ('undo', False)]:
            bad = copy.deepcopy(good)
            bad['table'][key] = value
            self.assertFalse(checks(case, bad)['tableInsert'])
        del good['table']
        self.assertFalse(checks(case, good)['tableInsert'])

    def test_normalization_keeps_table_structure_and_duplicate_words(self):
        self.assertEqual('| Ash | Ash |', normalize('{#tbl:body:123}\n| Ash | Ash |'))


if __name__ == '__main__':
    unittest.main()
