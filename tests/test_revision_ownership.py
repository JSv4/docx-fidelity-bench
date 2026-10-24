import copy
import unittest
import xml.etree.ElementTree as ET

from bench import common, redline, revision_ownership, revisions


def cases():
    return [case for case in redline.validate_registry()['cases'] if case['operation'] == 'revision-ownership']


def package(case, key='authored'):
    return revisions.Package(common.ROOT / case[key]['path'])


class RevisionOwnershipContracts(unittest.TestCase):
    def test_every_case_has_independent_metadata_and_round_trip_expectations(self):
        records = cases()
        self.assertEqual(len(records), 7)
        for case in records:
            with self.subTest(case=case['id']):
                self.assertTrue(revision_ownership.valid_spec(case['revisionOwnership'], case.get('authorNameStatus')))
                candidate = package(case)
                for mode, key in [('accept', 'accepted'), ('reject', 'rejected')]:
                    expected = revisions.Package(common.ROOT / case['expected'][key]['path'])
                    self.assertEqual(revisions.view(candidate, revisions.resolve(candidate.story_parts(), mode)), revisions.view(expected))
                for assertion in case['assertions']:
                    self.assertTrue(redline._assertion(assertion, candidate, {})['passed'])

    def test_invalid_operation_declarations_are_rejected(self):
        case = cases()[0]
        for key, value in [('version', True), ('action', 'accept'), ('configure', []), ('paragraphIndex', True),
                           ('identities', [{}]), ('identities', [{'providerId': 'AD', 'userId': ''}]), ('queryAuthor', '')]:
            changed = copy.deepcopy(case)
            changed['revisionOwnership'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                redline.validate_registry({'schema': 1, 'suite': {'version': 1, 'cases': [changed['id']]}, 'cases': [changed]})
        self.assertFalse(revision_ownership.valid_spec(case['revisionOwnership'], {'version': True, 'before': 'taken', 'after': 'taken'}))
        self.assertFalse(revision_ownership.valid_spec(case['revisionOwnership'], {'version': 1, 'before': 'maybe', 'after': 'own'}))

    def test_name_status_is_mandatory_and_cannot_be_replaced_by_a_truthy_value(self):
        case = cases()[0]
        expected = revision_ownership.name_status_check(case, None)['expected']
        self.assertTrue(revision_ownership.name_status_check(case, expected)['passed'])
        for value in [None, True, {'before': 'taken', 'after': 'taken'},
                      dict(expected, after={'author': 'another reviewer', 'status': 'taken'}),
                      dict(expected, after={'author': 'Taylor', 'status': 'own'})]:
            self.assertFalse(revision_ownership.name_status_check(case, value)['passed'])

    def test_round_trips_alone_do_not_detect_a_namesakes_erased_proposal(self):
        case = next(c for c in cases() if c['id'].endswith('namesake-account'))
        source = package(case)
        parts = dict(source.members)
        root = source.xml(source.main)
        body = root.find(revisions.w('body'))
        body.remove(body.findall(revisions.w('p'))[1])
        parts[source.main] = ET.tostring(root)
        erased = revisions.Package(parts)
        for mode, key in [('accept', 'accepted'), ('reject', 'rejected')]:
            expected = revisions.Package(common.ROOT / case['expected'][key]['path'])
            self.assertEqual(revisions.view(erased, revisions.resolve(erased.story_parts(), mode)), revisions.view(expected))
        assertion = next(a for a in case['assertions'] if a['type'] == 'pending-insertion-deletion')
        self.assertFalse(redline._assertion(assertion, erased, {})['passed'])

    def test_retained_deletion_rejects_wrong_author_text_and_duplicate_proposals(self):
        case = next(c for c in cases() if c['id'].endswith('namesake-account'))
        source = package(case)
        assertion = next(a for a in case['assertions'] if a['type'] == 'pending-insertion-deletion')
        for mutation in ('author', 'text', 'duplicate'):
            parts = dict(source.members)
            root = source.xml(source.main)
            insertion = next(e for e in root.iter(revisions.w('ins')) if e.find('.//' + revisions.w('del')) is not None)
            if mutation == 'author':
                insertion.find('.//' + revisions.w('del')).set(revisions.w('author'), 'someone else')
            elif mutation == 'text':
                insertion.find('.//' + revisions.w('delText')).text = 'different text'
            else:
                root.find(revisions.w('body')).findall(revisions.w('p'))[1].append(copy.deepcopy(insertion))
            parts[source.main] = ET.tostring(root)
            self.assertFalse(redline._assertion(assertion, revisions.Package(parts), {})['passed'])

    def test_metadata_claim_is_checked_even_though_the_semantic_view_ignores_people(self):
        case = next(c for c in cases() if c['id'].endswith('first-revision'))
        source = package(case)
        assertion = next(a for a in case['assertions'] if a['type'] == 'people-identity')
        for mutation in ('missing', 'wrong-account', 'duplicate', 'ambiguous'):
            parts = dict(source.members)
            target = next(t for kind, t in source.main_rels.values() if kind == 'people')
            root = source.xml(target)
            person = root[0]
            if mutation == 'missing':
                del parts[target]
            else:
                if mutation == 'wrong-account': person[0].set(revision_ownership.PEOPLE + 'userId', 'another account')
                elif mutation == 'duplicate': root.append(copy.deepcopy(person))
                else: person.append(copy.deepcopy(person[0]))
                parts[target] = ET.tostring(root)
            changed = revisions.Package(parts)
            self.assertEqual(revisions.view(source), revisions.view(changed))
            self.assertFalse(redline._assertion(assertion, changed, {})['passed'])

    def test_absent_account_assertion_does_not_silently_claim_a_taken_name(self):
        case = next(c for c in cases() if c['id'].endswith('unattributed-name'))
        source = package(case)
        self.assertEqual(revision_ownership.people_identities(source, 'Taylor'), [])
        registered = next(c for c in cases() if c['id'].endswith('namesake-account'))
        self.assertNotEqual(revision_ownership.people_identities(package(registered), 'Taylor'), [])
