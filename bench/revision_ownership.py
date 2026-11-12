"""Independent raw-package assertions for reviewer accounts and retained proposals."""
from . import revisions

PEOPLE = '{http://schemas.microsoft.com/office/word/2012/wordml}'
STATUSES = {'free', 'own', 'taken'}


def valid_identities(value):
    return isinstance(value, list) and all(
        isinstance(item, dict) and set(item) == {'providerId', 'userId'}
        and all(isinstance(text, str) and text.strip() for text in item.values()) for item in value)


def valid_spec(spec, status):
    if (not isinstance(spec, dict) or set(spec) != {'version', 'author', 'identities', 'configure', 'action', 'paragraphIndex', 'text', 'queryAuthor'}
            or type(spec['version']) is not int or spec['version'] != 1
            or not isinstance(spec['author'], str) or not spec['author'].strip()
            or (spec['identities'] is not None and not valid_identities(spec['identities']))
            or not isinstance(spec['configure'], str) or spec['configure'] not in {'open', 'operation'} or not isinstance(spec['action'], str) or spec['action'] not in {'delete-block', 'replace-text', 'add-comment'}
            or type(spec['paragraphIndex']) is not int or spec['paragraphIndex'] < 0
            or not isinstance(spec['text'], str) or (spec['action'] != 'delete-block' and not spec['text'])):
        return False
    author = spec['queryAuthor']
    if author is None:
        return status is None
    return (isinstance(author, str) and bool(author.strip()) and isinstance(status, dict)
            and set(status) == {'version', 'before', 'after'} and type(status['version']) is int and status['version'] == 1
            and all(isinstance(status[key], str) and status[key] in STATUSES for key in ('before', 'after')))


def people_identities(package, author):
    targets = [target for kind, target in package.main_rels.values() if kind == 'people']
    if not targets:
        return []
    if len(targets) != 1 or targets[0] not in package.members:
        return None
    root = package.xml(targets[0])
    if root.tag != PEOPLE + 'people':
        return None
    result = []
    for person in root.findall(PEOPLE + 'person'):
        if person.get(PEOPLE + 'author') != author:
            continue
        presence = person.findall(PEOPLE + 'presenceInfo')
        if len(presence) != 1:
            return None
        result.append({'providerId': presence[0].get(PEOPLE + 'providerId'), 'userId': presence[0].get(PEOPLE + 'userId')})
    return result


def retained_deletion(package, author, deleted_by, text):
    matches = []
    for insertion in package.xml(package.main).iter(revisions.w('ins')):
        if insertion.get(revisions.w('author')) != author:
            continue
        for deletion in insertion.iter(revisions.w('del')):
            deleted = ''.join(node.text or '' for node in deletion.iter(revisions.w('delText')))
            if deletion.get(revisions.w('author')) == deleted_by and deleted == text:
                matches.append(deleted)
    return matches == [text]


def name_status_check(case, observed):
    declaration = case['authorNameStatus']
    author = case['revisionOwnership']['queryAuthor']
    expected = {key: {'author': author, 'status': declaration[key]} for key in ('before', 'after')}
    return {'name': 'revision-author-name-status', 'passed': observed == expected, 'expected': expected, 'observed': observed}
