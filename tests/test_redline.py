import copy
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from unittest.mock import patch

from bench import common, redline, redline_fixtures, revisions

W = '{' + revisions.W + '}'


def load(record):
    return revisions.Package(str(common.ROOT / record['path']))


def members(record):
    with zipfile.ZipFile(common.ROOT / record['path']) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def rewrite(record, change):
    """A package whose main document is `change(document root)`; the other members are unchanged."""
    parts = members(record)
    root = ET.fromstring(parts['word/document.xml'])
    change(root)
    parts['word/document.xml'] = ET.tostring(root)
    return revisions.Package(parts)


def views(package):
    parts = package.story_parts()
    return revisions.view(package, revisions.resolve(parts, 'accept')), revisions.view(package, revisions.resolve(parts, 'reject'))


def cases(kind=None, operation=None):
    registry = redline.validate_registry()
    return [c for c in registry['cases'] if (kind is None or c['kind'] == kind) and (operation is None or c['operation'] == operation)]


def case(case_id):
    return next(c for c in redline.validate_registry()['cases'] if c['id'] == case_id)


class RedlineRegistry(unittest.TestCase):
    def test_registry_is_valid_and_versioned(self):
        registry = redline.validate_registry()
        self.assertEqual(registry['suite']['id'], 'redline-v17')
        self.assertEqual(len(registry['cases']), 152)
        issues = {c['issue'] for c in registry['cases'] if c['issue']}
        self.assertEqual(issues, {f'JSv4/Docxodus#{n}' for n in (1165, 1166, 1167, 1170, 1174, 1175, 1176, 1183, 1184, 1188, 1190, 1195, 1196, 1197, 1206, 1210, 1211, 1212, 1218, 1312, 1317, 1322, 1330, 1331, 1337, 1340, 1342, 1352)})

    def test_every_issue_has_a_reproducer_and_a_control(self):
        by_issue = {}
        for record in cases():
            if record['issue']:
                by_issue.setdefault(record['issue'], set()).add(record['kind'])
        for issue, kinds in by_issue.items():
            self.assertEqual(kinds, {'reproducer', 'control'}, issue)

    def test_fixtures_regenerate_exactly(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(redline_fixtures, 'ROOT', Path(temp)):
            generated = redline_fixtures.generate()
            expected = common.read_json(redline.MANIFEST)
            self.assertEqual(generated, expected)
            for record in expected['cases']:
                for item in redline.artifact_records(record):
                    self.assertEqual((Path(temp) / item['path']).read_bytes(), (common.ROOT / item['path']).read_bytes())

    def test_stale_digest_and_unknown_assertion_are_rejected(self):
        registry = common.read_json(redline.MANIFEST)
        broken = copy.deepcopy(registry)
        broken['cases'][0]['inputs'][0]['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            redline.validate_registry(broken)
        broken = copy.deepcopy(registry)
        broken['cases'][0]['assertions'].append({'type': 'unimplemented', 'version': 1, 'scope': 'redline'})
        with self.assertRaises(ValueError):
            redline.validate_registry(broken)
        broken = copy.deepcopy(registry)
        broken['cases'][0]['libreoffice'] = {'accepted': False, 'rejected': True}
        with self.assertRaises(ValueError):
            redline.validate_registry(broken)

    def test_inputs_carry_no_embedded_fonts_or_custom_xml_parts(self):
        for record in cases():
            for item in redline.artifact_records(record):
                for name in members(item):
                    self.assertNotIn('font', name.lower())
                    self.assertFalse(name.startswith('customXml/'))

    def test_reviewer_expectations_require_all_authors_and_valid_digests(self):
        registry = common.read_json(redline.MANIFEST)
        target = next(c for c in registry['cases'] if 'reviewerExpected' in c)
        projection = target['reviewerExpected'].pop('Reviewer1')
        with self.assertRaisesRegex(ValueError, 'every consolidation reviewer'):
            redline.validate_registry(registry)
        target['reviewerExpected']['Reviewer1'] = dict(projection, sha256='0' * 64)
        with self.assertRaisesRegex(ValueError, 'Stale redline input digest'):
            redline.validate_registry(registry)

    def test_conflict_projections_still_reject_wrong_attribution(self):
        record = case('redline-bookmark-name-consensus-control')
        package = load(record['authored'])
        parts = package.story_parts()
        for author, expected in record['reviewerExpected'].items():
            self.assertEqual(revisions.view(package, revisions.resolve(parts, 'accept', author)), revisions.view(load(expected)))
        for root in parts.values():
            for e in root.iter():
                if e.get(revisions.w('author')) == 'Reviewer2':
                    e.set(revisions.w('author'), 'Reviewer1')
        self.assertNotEqual(revisions.view(package, revisions.resolve(parts, 'accept', 'Reviewer2')),
                            revisions.view(load(record['reviewerExpected']['Reviewer2'])))


class AuthoredCalibration(unittest.TestCase):
    """The authored redline of every case satisfies the benchmark's own engine and assertions."""

    def test_authored_redlines_round_trip(self):
        for record in cases():
            package = load(record['authored'])
            if record['operation'] in {'reject', 'column-edit', 'block-insert'}:
                self.assertEqual(revisions.view(package), revisions.view(load(record['expected']['output'])), record['id'])
                if record['operation'] in {'column-edit', 'block-insert'}:
                    continue
                tracked = load(record['inputs'][0])
                rejected = revisions.resolve(tracked.story_parts(), 'reject')
                self.assertEqual(revisions.view(tracked, rejected), revisions.view(load(record['expected']['output'])), record['id'])
                continue
            accepted, rejected = views(package)
            self.assertEqual(accepted, revisions.view(load(record['expected']['accepted'])), record['id'])
            self.assertEqual(rejected, revisions.view(load(record['expected']['rejected'])), record['id'])

    def test_authored_redlines_pass_their_assertions(self):
        for record in cases():
            package = load(record['authored'])
            resolved = {'redline': None, 'output': None}
            if record['operation'] != 'reject':
                resolved.update(accepted=revisions.resolve(package.story_parts(), 'accept'),
                                rejected=revisions.resolve(package.story_parts(), 'reject'))
            for assertion in record['assertions']:
                self.assertTrue(redline._assertion(assertion, package, resolved)['passed'], record['id'] + ' ' + assertion['type'])

    def test_reproducers_and_controls_differ_from_their_original(self):
        for record in cases(operation='compare'):
            if record['kind'] == 'identity' or 'semanticPreflight' in record:
                continue
            self.assertNotEqual(revisions.view(load(record['expected']['accepted'])), revisions.view(load(record['expected']['rejected'])), record['id'])


class GamingIsRejected(unittest.TestCase):
    def test_mixed_run_marker_order_is_not_hidden_by_unchanged_letters(self):
        for marker in ('tab', 'br'):
            record = case('redline-mixed-run-' + marker + '-direct-before')
            package = load(record['expected']['accepted'])
            parts = package.story_parts()
            paragraph = list(parts[package.main].iter(revisions.w('p')))[1]
            carrier = next(run for run in paragraph if run.find(revisions.w(marker)) is not None)
            paragraph.remove(carrier)
            paragraph.insert(0, carrier)
            letters = lambda root: ''.join(e.text or '' for e in root.iter(revisions.w('t')))
            self.assertEqual(letters(package.story_parts()[package.main]), letters(parts[package.main]))
            self.assertNotEqual(revisions.view(package), revisions.view(package, parts))

    def test_resolved_column_state_catches_changes_the_text_view_ignores(self):
        record = case('redline-pending-grid-merged-insert')
        package = load(record['authored'])
        declaration = next(a for a in record['assertions'] if a['type'] == 'table-state')
        for target, attribute, value in [('tblGrid/gridCol', 'w', '9999'), ('tr/tc/tcPr/gridSpan', 'val', '2'),
                                         ('tr/tc/tcPr/tcW', 'w', '9999'), ('tr/tc/tcPr/shd', 'fill', '000000')]:
            parts = package.story_parts()
            table = next(parts[package.main].iter(revisions.w('tbl')))
            path = '/'.join(revisions.w(name) for name in target.split('/'))
            table.find(path).set(revisions.w(attribute), value)
            self.assertEqual(revisions.view(package, parts), revisions.view(load(record['expected']['output'])))
            self.assertFalse(redline._assertion(declaration, package, {'output': parts})['passed'], target)
        record = case('redline-pending-grid-omitted-insert')
        package = load(record['authored'])
        declaration = next(a for a in record['assertions'] if a['type'] == 'table-state')
        for name, value in [('gridBefore', '1'), ('trHeight', '480')]:
            parts = package.story_parts()
            row = next(parts[package.main].iter(revisions.w('tr')))
            row.find(revisions.w('trPr') + '/' + revisions.w(name)).set(revisions.w('val'), value)
            self.assertEqual(revisions.view(package, parts), revisions.view(load(record['expected']['output'])))
            self.assertFalse(redline._assertion(declaration, package, {'output': parts})['passed'], name)

    def test_table_width_changes_cannot_hide_behind_unchanged_text(self):
        record = case('redline-table-column-widths-full')
        declaration = next(a for a in record['assertions'] if a['type'] == 'table-widths' and a['scope'] == 'accepted')
        package = load(record['authored'])
        for target in ('tblGrid/gridCol', 'tr/tc/tcPr/tcW', 'tblPr/tblW'):
            parts = revisions.resolve(package.story_parts(), 'accept')
            table = next(parts[package.main].iter(revisions.w('tbl')))
            path = '/'.join(revisions.w(name) for name in target.split('/'))
            table.find(path).set(revisions.w('w'), '9999')
            self.assertEqual(revisions.view(package, parts), revisions.view(load(record['expected']['accepted'])))
            self.assertFalse(redline._assertion(declaration, package, {'accepted': parts})['passed'], target)

    def test_moving_a_table_boundary_bookmark_changes_the_semantic_view(self):
        for level in ('tbl', 'tr'):
            with self.subTest(level=level):
                record = case('redline-boundary-bookmark-compare-' + level)
                package = load(record['expected']['accepted'])
                parts = package.story_parts()
                root = parts[package.main]
                marker = next(root.iter(revisions.w('bookmarkStart')))
                parent = next(e for e in root.iter() if marker in list(e))
                parent.remove(marker)
                parent.insert(0, marker)
                self.assertNotEqual(revisions.view(package), revisions.view(package, parts))

    def test_copying_either_input_fails_a_round_trip(self):
        for record in cases(operation='compare'):
            if record['kind'] == 'identity' or 'semanticPreflight' in record:
                continue
            left, right = load(record['expected']['rejected']), load(record['expected']['accepted'])
            for candidate in (left, right):
                accepted, rejected = views(candidate)
                self.assertFalse(accepted == revisions.view(right) and rejected == revisions.view(left), record['id'])

    def test_whole_document_churn_round_trips_but_fails_preservation(self):
        record = case('redline-field-shared-end-append')
        left = ET.fromstring(members(record['inputs'][0])['word/document.xml'])
        right = ET.fromstring(members(record['inputs'][1])['word/document.xml'])
        def tracked(paragraph, kind, final=False):
            paragraph = copy.deepcopy(paragraph)
            runs = [c for c in paragraph if c.tag != W + 'pPr']
            for run in runs:
                paragraph.remove(run)
                for text in run.iter(W + 't'):
                    if kind == 'del':
                        text.tag = W + 'delText'
                for instruction in run.iter(W + 'instrText'):
                    if kind == 'del':
                        instruction.tag = W + 'delInstrText'
            wrapper = ET.SubElement(paragraph, W + kind, {W + 'id': '1', W + 'author': 'Churn'})
            wrapper.extend(runs)
            if not final:
                properties = paragraph.find(W + 'pPr')
                if properties is None:
                    properties = ET.Element(W + 'pPr')
                    paragraph.insert(0, properties)
                ET.SubElement(ET.SubElement(properties, W + 'rPr'), W + kind, {W + 'id': '2', W + 'author': 'Churn'})
            return paragraph
        def churn(root):
            body = root.find(W + 'body')
            section = body.find(W + 'sectPr')
            olds = [tracked(p, 'del') for p in left.find(W + 'body').findall(W + 'p')]
            news = right.find(W + 'body').findall(W + 'p')
            news = [tracked(p, 'ins', final=i == len(news) - 1) for i, p in enumerate(news)]
            body[:] = olds + news + [section]
        package = rewrite(record['inputs'][0], churn)
        accepted, rejected = views(package)
        self.assertEqual(accepted, revisions.view(load(record['expected']['accepted'])))
        self.assertEqual(rejected, revisions.view(load(record['expected']['rejected'])))
        check = redline._assertion(record['assertions'][0], package, {'redline': None})
        self.assertFalse(check['passed'])

    def test_text_parked_in_an_unreferenced_part_cannot_satisfy_preservation(self):
        record = case('redline-field-result-end-control')
        parts = members(record['inputs'][0])
        parts['word/comments.xml'] = (f'<w:comments xmlns:w="{revisions.W}"><w:comment w:id="9" w:author="x"><w:p><w:r><w:t>'
                                      + ' '.join(record['assertions'][0]['texts']) + '</w:t></w:r></w:p></w:comment></w:comments>').encode()
        rels = parts['word/_rels/document.xml.rels'].decode().replace('</Relationships>',
            '<Relationship Id="rOrphan" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" Target="comments.xml"/></Relationships>')
        parts['word/_rels/document.xml.rels'] = rels.encode()
        document = ET.fromstring(parts['word/document.xml'])
        for text in document.iter(W + 't'):
            text.text = 'churned'
        parts['word/document.xml'] = ET.tostring(document)
        check = redline._assertion(record['assertions'][0], revisions.Package(parts), {'redline': None})
        self.assertFalse(check['passed'])

    def test_header_preservation_reads_only_referenced_headers(self):
        record = case('redline-header-bookmark-only')
        assertion = record['assertions'][0]
        self.assertEqual(assertion['story'], 'headers')
        self.assertTrue(redline._assertion(assertion, load(record['authored']), {'redline': None})['passed'])
        self.assertFalse(redline._assertion(dict(assertion, story='body'), load(record['authored']), {'redline': None})['passed'])

    def test_consolidation_credits_each_reviewer(self):
        record = case('redline-consolidate-cell-text-control')
        package = load(record['authored'])
        for item in record['inputs'][1:]:
            resolved = revisions.resolve(package.story_parts(), 'accept', item['author'])
            self.assertEqual(revisions.view(package, resolved), revisions.view(load(item)), item['author'])
        parts = members(record['authored'])
        parts['word/document.xml'] = parts['word/document.xml'].replace(b'Reviewer1', b'Reviewer2')
        swapped = revisions.Package(parts)
        resolved = revisions.resolve(swapped.story_parts(), 'accept', 'Reviewer1')
        self.assertNotEqual(revisions.view(swapped, resolved), revisions.view(load(record['inputs'][1])))

    def test_doubled_field_end_fails_the_markup_comparison(self):
        record = case('redline-field-shared-end-append')
        def double(root):
            run = next(r for r in root.iter(W + 'r') if r.find(W + 'fldChar') is not None and r.find(W + 'fldChar').get(W + 'fldCharType') == 'end')
            paragraph = next(p for p in root.iter(W + 'p') if run in list(p))
            paragraph.insert(list(paragraph).index(run), copy.deepcopy(run))
        accepted, rejected = views(rewrite(record['authored'], double))
        self.assertNotEqual(rejected, revisions.view(load(record['expected']['rejected'])))

    def test_duplicate_style_id_and_para_id_findings(self):
        record = case('redline-style-id-cross-type')
        parts = members(record['authored'])
        styles = ET.fromstring(parts['word/styles.xml'])
        styles.append(ET.fromstring(f'<w:style xmlns:w="{revisions.W}" w:type="character" w:styleId="DocID"><w:name w:val="DocID"/></w:style>'))
        parts['word/styles.xml'] = ET.tostring(styles)
        self.assertEqual(revisions.style_id_findings(revisions.Package(parts)), [{'styleId': 'DocID', 'types': ['paragraph', 'character']}])
        record = case('redline-comment-para-id-collision')
        parts = members(record['authored'])
        document = ET.fromstring(parts['word/document.xml'])
        first = document.find('.//' + W + 'p')
        first.set('{' + revisions.W14 + '}paraId', '00000011')
        second = document.findall('.//' + W + 'p')[1]
        second.set('{' + revisions.W14 + '}paraId', '80000000')
        parts['word/document.xml'] = ET.tostring(document)
        problems = sorted(f['problem'] for f in revisions.para_id_findings(revisions.Package(parts)))
        self.assertEqual(problems, ['duplicate of word/comments.xml', 'out of range'])


    def test_comment_thread_findings(self):
        record = case('redline-comment-reply-id-less-root')
        threads = [['Friday is confirmed.', 'Check the delivery date.']]
        self.assertEqual(revisions.comment_thread_findings(load(record['authored']), threads), [])
        # Docxodus #1312 before its fix: the root keeps the original's missing paraId and has no entry.
        parts = members(record['authored'])
        comments = ET.fromstring(parts['word/comments.xml'])
        del comments.find(W + 'comment').find(W + 'p').attrib['{' + revisions.W14 + '}paraId']
        parts['word/comments.xml'] = ET.tostring(comments)
        extended = ET.fromstring(parts['word/commentsExtended.xml'])
        extended.remove(extended[0])
        parts['word/commentsExtended.xml'] = ET.tostring(extended)
        problems = [f['problem'] for f in revisions.comment_thread_findings(revisions.Package(parts), threads)]
        self.assertEqual(problems, ['parent is not a comment with its own entry', 'not threaded under its parent'])
        # A reply threaded under the wrong comment fails even when every link resolves.
        self.assertEqual([f['problem'] for f in revisions.comment_thread_findings(load(record['authored']), [threads[0][::-1]])],
                         ['not threaded under its parent'])
        self.assertEqual([f['problem'] for f in revisions.comment_thread_findings(load(record['authored']), [['Absent.', 'Check the delivery date.']])],
                         ['0 comments carry this text'])
        # An entry keyed to a paraId no comment holds.
        parts = members(record['authored'])
        extended = ET.fromstring(parts['word/commentsExtended.xml'])
        extended.append(ET.fromstring(f'<w15:commentEx xmlns:w15="{revisions.W15}" w15:paraId="0000ABCD" w15:done="0"/>'))
        parts['word/commentsExtended.xml'] = ET.tostring(extended)
        self.assertEqual([f['problem'] for f in revisions.comment_thread_findings(revisions.Package(parts), threads)],
                         ['entry names no comment'])


def fragment(body, extra=''):
    xml = (f'<w:document xmlns:w="{revisions.W}" xmlns:m="{revisions.M}"><w:body>{body}<w:sectPr/></w:body></w:document>')
    parts = {'[Content_Types].xml': b'<Types/>',
             '_rels/.rels': b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="r" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
             'word/document.xml': xml.encode()}
    return revisions.Package(parts)


def body_texts(package, mode=None):
    parts = package.story_parts()
    resolved = revisions.resolve(parts, mode) if mode else None
    value = revisions.view(package, resolved)
    return [''.join(v for k, v in b['content'] if k == 't') if 'content' in b else b['marker'] for b in value['stories']['body']]


class EngineSemantics(unittest.TestCase):
    def test_custom_xml_envelopes_resolve_markup_without_removing_payload(self):
        payload = '<w:r><w:t>kept</w:t></w:r>'
        empty = '<w:customXml w:element="empty"><w:customXmlPr/></w:customXml>'
        for kind in ('Ins', 'Del', 'MoveFrom', 'MoveTo'):
            start = lambda id: f'<w:customXml{kind}RangeStart w:id="{id}" w:author="Rae"/>'
            end = lambda id: f'<w:customXml{kind}RangeEnd w:id="{id}"/>'
            for split in (False, True):
                marked = ('<w:customXml w:element="marked"><w:customXmlPr/>' +
                          (end(1) if split else '') + payload +
                          (start(2) if split else '') + '</w:customXml>')
                package = fragment('<w:p><w:customXml w:element="outer">' + start(1) + marked +
                                   end(2 if split else 1) + '</w:customXml>' + empty + '</w:p>')
                for mode, author in (('accept', None), ('reject', None), ('accept', 'Rae'), ('accept', 'Other')):
                    with self.subTest(kind=kind, split=split, mode=mode, author=author):
                        effective = mode if author is None else 'accept' if author == 'Rae' else 'reject'
                        removed = kind in (('Del', 'MoveFrom') if effective == 'accept' else ('Ins', 'MoveTo'))
                        resolved = revisions.resolve(package.story_parts(), mode, author)
                        root = resolved[package.main]
                        self.assertEqual([e.get(W + 'element') for e in root.iter(W + 'customXml')],
                                         ['outer', 'empty'] if removed else ['outer', 'marked', 'empty'])
                        self.assertEqual(len(list(root.iter(W + 'customXmlPr'))), 1 if removed else 2)
                        self.assertEqual(revisions.revision_count(resolved), 0)
                        expected = fragment('<w:p><w:customXml w:element="outer">' +
                                            (payload if removed else '<w:customXml w:element="marked">' + payload + '</w:customXml>') +
                                            '</w:customXml>' + empty + '</w:p>')
                        self.assertEqual(revisions.view(package, resolved), revisions.view(expected))

    def test_custom_xml_range_resolution_rejects_incomplete_or_ambiguous_markup(self):
        start = '<w:customXmlDelRangeStart w:id="1"/>'
        end = '<w:customXmlDelRangeEnd w:id="1"/>'
        payload = '<w:r><w:t>kept</w:t></w:r>'
        for markup in (start + '<w:customXml>' + end + payload + '</w:customXml>',
                       start + '<w:customXml>' + payload + '</w:customXml>',
                       start + start + '<w:customXml>' + payload + '</w:customXml>' + end):
            with self.subTest(markup=markup), self.assertRaises(ValueError):
                revisions.resolve(fragment('<w:p>' + markup + '</w:p>').story_parts(), 'accept')

    def test_custom_xml_enclosing_range_removes_nested_tags_but_not_nested_text(self):
        package = fragment('<w:p><w:customXmlDelRangeStart w:id="1"/>'
                           '<w:customXml><w:customXml><w:r><w:t>kept</w:t></w:r></w:customXml></w:customXml>'
                           '<w:customXmlDelRangeEnd w:id="1"/></w:p>')
        expected = fragment('<w:p><w:r><w:t>kept</w:t></w:r></w:p>')
        self.assertEqual(revisions.view(package, revisions.resolve(package.story_parts(), 'accept')),
                         revisions.view(expected))

    def test_deleted_paragraph_mark_joins_the_following_paragraph(self):
        package = fragment('<w:p><w:pPr><w:rPr><w:del w:id="1"/></w:rPr></w:pPr><w:r><w:t>one </w:t></w:r></w:p><w:p><w:r><w:t>two</w:t></w:r></w:p>')
        self.assertEqual(body_texts(package, 'accept'), ['one two'])
        self.assertEqual(body_texts(package, 'reject'), ['one ', 'two'])

    def test_inserted_paragraph_mark_joins_on_reject(self):
        package = fragment('<w:p><w:pPr><w:rPr><w:ins w:id="1"/></w:rPr></w:pPr><w:ins w:id="2"><w:r><w:t>new</w:t></w:r></w:ins></w:p><w:p><w:r><w:t>kept</w:t></w:r></w:p>')
        self.assertEqual(body_texts(package, 'accept'), ['new', 'kept'])
        self.assertEqual(body_texts(package, 'reject'), ['kept'])

    def test_deleted_text_restores_and_instructions_survive_reject(self):
        package = fragment('<w:p><w:del w:id="1"><w:r><w:delText>gone</w:delText></w:r><w:r><w:delInstrText> PAGE </w:delInstrText></w:r></w:del><w:ins w:id="2"><w:r><w:t>new</w:t></w:r></w:ins></w:p><w:p/>')
        self.assertEqual(body_texts(package, 'accept'), ['new'])
        rejected = revisions.view(package, revisions.resolve(package.story_parts(), 'reject'))['stories']['body'][0]['content']
        self.assertEqual(rejected, [['t', 'gone'], ['m', 'field-instruction:PAGE']])

    def test_rows_and_cells_follow_their_markers(self):
        row = '<w:tr><w:trPr><w:{k} w:id="1"/></w:trPr><w:tc><w:p><w:r><w:t>{t}</w:t></w:r></w:p></w:tc></w:tr>'
        table = '<w:tbl>' + row.format(k='ins', t='added') + row.format(k='del', t='removed') + '</w:tbl><w:p/>'
        package = fragment(table)
        self.assertEqual(body_texts(package, 'accept'), ['added'])
        self.assertEqual(body_texts(package, 'reject'), ['removed'])

    def test_property_change_restores_the_prior_style_on_reject(self):
        package = fragment('<w:p><w:pPr><w:pStyle w:val="New"/><w:pPrChange w:id="1"><w:pPr><w:pStyle w:val="Old"/></w:pPr></w:pPrChange></w:pPr><w:r><w:t>x</w:t></w:r></w:p>')
        accepted = revisions.view(package, revisions.resolve(package.story_parts(), 'accept'))['stories']['body'][0]['style']
        rejected = revisions.view(package, revisions.resolve(package.story_parts(), 'reject'))['stories']['body'][0]['style']
        self.assertEqual((accepted, rejected), ('id:New', 'id:Old'))

    def test_revisions_inside_inline_containers_are_resolved(self):
        package = fragment('<w:p><w:customXml w:element="x"><w:ins w:id="1"><w:r><w:t>a</w:t></w:r></w:ins><w:del w:id="2"><w:r><w:delText>b</w:delText></w:r></w:del></w:customXml>'
                           '<m:oMath><w:ins w:id="3"><m:r><m:t>c</m:t></m:r></w:ins><w:del w:id="4"><m:r><m:t>d</m:t></m:r></w:del></m:oMath></w:p>')
        self.assertEqual(body_texts(package, 'accept'), ['ac'])
        self.assertEqual(body_texts(package, 'reject'), ['bd'])

    def test_emptied_block_wrapper_is_removed_and_trailing_empty_paragraphs_ignored(self):
        package = fragment('<w:sdt><w:sdtContent><w:p><w:pPr><w:rPr><w:del w:id="1"/></w:rPr></w:pPr><w:del w:id="2"><w:r><w:delText>old</w:delText></w:r></w:del></w:p></w:sdtContent></w:sdt>'
                           '<w:p><w:r><w:t>body</w:t></w:r></w:p><w:p/>')
        accepted = revisions.view(package, revisions.resolve(package.story_parts(), 'accept'))['stories']['body']
        self.assertEqual(accepted, [{'path': 'body', 'style': '', 'content': [['t', 'body']]}])

    def test_bookmarks_between_blocks_are_their_own_view_records(self):
        package = fragment('<w:p><w:r><w:t>a</w:t></w:r></w:p><w:bookmarkStart w:id="0" w:name="M"/><w:p><w:r><w:t>b</w:t></w:r></w:p><w:bookmarkEnd w:id="0"/>')
        self.assertEqual(body_texts(package), ['a', 'bookmark-start:M', 'b', 'bookmark-end:M'])

    def test_stray_deleted_text_counts_as_a_revision_left_behind(self):
        package = fragment('<w:p><w:r><w:delText>left</w:delText></w:r><w:del w:id="1"><w:r><w:delText>fine</w:delText></w:r></w:del></w:p>')
        self.assertEqual(revisions.revision_count(package.story_parts()), 2)

    def test_alternate_content_is_read_once(self):
        mc = 'http://schemas.openxmlformats.org/markup-compatibility/2006'
        package = fragment(f'<w:p><mc:AlternateContent xmlns:mc="{mc}"><mc:Choice Requires="w14"><w:r><w:t>A</w:t></w:r></mc:Choice>'
                           f'<mc:Fallback><w:r><w:t>A</w:t></w:r></mc:Fallback></mc:AlternateContent></w:p>')
        self.assertEqual(body_texts(package), ['A'])

    def test_only_one_trailing_empty_paragraph_is_ignored(self):
        self.assertEqual(body_texts(fragment('<w:p><w:r><w:t>x</w:t></w:r></w:p><w:p/>')), ['x'])
        self.assertEqual(body_texts(fragment('<w:p><w:r><w:t>x</w:t></w:r></w:p><w:p/><w:p/>')), ['x', ''])

    def test_revision_count_and_untracked_text(self):
        package = fragment('<w:p><w:r><w:t>kept</w:t></w:r><w:ins w:id="1"><w:r><w:t>new</w:t></w:r></w:ins><w:r><w:t>tail</w:t></w:r></w:p>')
        self.assertEqual(revisions.revision_count(package.story_parts()), 1)
        texts = revisions.untracked_text(package)
        self.assertTrue(any('kept' in t for t in texts))
        self.assertFalse(any('keptnew' in t or 'kepttail' in t for t in texts))


class ScoringContract(unittest.TestCase):
    def test_column_review_observations_are_mandatory_typed_and_successful(self):
        import shutil
        record = case('redline-column-gap-leading')
        def candidate(_adapter, _build, _case, output, _candidate):
            shutil.copyfile(common.ROOT / record['authored']['path'], output)
            return dict(response, status='ok', revisionRegistryCount=0)
        expected = {'beforeCount': 1, 'supported': True, 'resolutionSuccess': True}
        mutants = [None, dict(expected, beforeCount=True), dict(expected, beforeCount=2),
                   dict(expected, supported=1), dict(expected, supported=False),
                   dict(expected, resolutionSuccess=1), dict(expected, resolutionSuccess=False), expected]
        for observed in mutants:
            response = {} if observed is None else {'columnReview': observed}
            with self.subTest(observed=observed), tempfile.TemporaryDirectory() as temp, \
                    patch.object(redline, 'run_candidate', side_effect=candidate), \
                    patch.object(redline, '_libreoffice_checks', return_value=[]), \
                    patch.object(redline, 'validate_packages', side_effect=lambda _v, paths: {str(p): [] for p in paths}):
                outcome = redline.score_case(record, Path(temp), 'docxodus', 'build', 'commit', {}, 'validator')
                self.assertEqual(outcome['status'], 'measured')
                self.assertEqual(outcome['score'], 100 if observed is expected else 0)

    def test_v2_column_declarations_require_a_consistent_review_contract(self):
        for key, value in [('beforeCount', True), ('beforeCount', 2), ('supported', 1), ('resolutionSuccess', False)]:
            registry = common.read_json(redline.MANIFEST)
            target = next(c for c in registry['cases'] if 'columnReview' in c)
            target['columnReview'][key] = value
            with self.assertRaisesRegex(ValueError, 'column review'):
                redline.validate_registry(registry)

    def test_span_edit_declarations_require_typed_nonempty_ranges(self):
        for key, value in [('tracked', 1), ('start', True), ('paragraphIndex', -1), ('length', 0), ('replacement', None)]:
            registry = common.read_json(redline.MANIFEST)
            target = next(c for c in registry['cases'] if c['operation'] == 'replace-span')
            target['spanEdit'][key] = value
            with self.assertRaisesRegex(ValueError, 'span edit'):
                redline.validate_registry(registry)

    def test_block_insertion_outcomes_are_mandatory_and_typed(self):
        import shutil
        record = case('redline-block-insert-paragraph')
        def candidate(_adapter, _build, _case, output, _candidate):
            shutil.copyfile(common.ROOT / record['authored']['path'], output)
            return dict(response, status='ok')
        expected = record['editOutcome']
        mutants = [None, dict(expected, success=0), dict(expected, versionDelta=False),
                   dict(expected, undoAvailable=0), dict(expected, errorCode=None),
                   dict(expected, success=True, versionDelta=1, undoAvailable=True), expected]
        for observed in mutants:
            response = {} if observed is None else {'blockInsertion': observed}
            with self.subTest(observed=observed), tempfile.TemporaryDirectory() as temp, \
                    patch.object(redline, 'run_candidate', side_effect=candidate), \
                    patch.object(redline, '_libreoffice_checks', return_value=[]), \
                    patch.object(redline, 'validate_packages', side_effect=lambda _v, paths: {str(p): [] for p in paths}):
                outcome = redline.score_case(record, Path(temp), 'docxodus', 'build', 'commit', {}, 'validator')
                self.assertEqual(outcome['status'], 'measured')
                self.assertEqual(outcome['score'], 100 if observed is expected else 0)

    def test_block_insertion_declarations_reject_incompatible_results(self):
        for key, value in [('success', 0), ('versionDelta', False), ('undoAvailable', 0), ('errorCode', None)]:
            registry = common.read_json(redline.MANIFEST)
            target = next(c for c in registry['cases'] if c['operation'] == 'block-insert')
            target['editOutcome'][key] = value
            with self.assertRaisesRegex(ValueError, 'block insertion'):
                redline.validate_registry(registry)

    def test_resolved_column_operations_require_an_empty_public_registry(self):
        import shutil
        record = case('redline-pending-grid-plain-insert')
        def candidate(_adapter, _build, _case, output, _candidate):
            shutil.copyfile(common.ROOT / record['authored']['path'], output)
            return dict(response, status='ok')
        for count, expected_score in [(None, 0), (False, 0), (1, 0), (0, 100)]:
            response = {} if count is None else {'revisionRegistryCount': count}
            with self.subTest(count=count), tempfile.TemporaryDirectory() as temp, \
                    patch.object(redline, 'run_candidate', side_effect=candidate), \
                    patch.object(redline, '_libreoffice_checks', return_value=[]), \
                    patch.object(redline, 'validate_packages', side_effect=lambda _v, paths: {str(p): [] for p in paths}):
                outcome = redline.score_case(record, Path(temp), 'docxodus', 'build', 'commit', {}, 'validator')
                self.assertEqual(outcome['status'], 'measured')
                self.assertEqual(outcome['score'], expected_score)

    def test_column_operation_and_table_state_declarations_are_validated(self):
        for key, value in [('action', 'move'), ('cellIndex', True), ('resolution', 'ignore')]:
            registry = common.read_json(redline.MANIFEST)
            target = next(c for c in registry['cases'] if c['operation'] == 'column-edit')
            target['columnEdit'][key] = value
            with self.assertRaisesRegex(ValueError, 'column edit'):
                redline.validate_registry(registry)
        record = case('redline-pending-grid-merged-insert')
        state = copy.deepcopy(next(a['state'] for a in record['assertions'] if a['type'] == 'table-state'))
        self.assertTrue(redline.valid_table_state(state))
        state['rows'][0]['cells'][0]['span'] = 2
        self.assertFalse(redline.valid_table_state(state))

    def test_public_registry_count_is_mandatory_and_typed_for_width_operations(self):
        import shutil
        record = case('redline-table-column-widths-full')
        def candidate(_adapter, _build, _case, output, _candidate):
            shutil.copyfile(common.ROOT / record['authored']['path'], output)
            return dict(response, status='ok')
        for count, expected_score in [(None, 0), (True, 0), (3, 0), (1, 100)]:
            response = {} if count is None else {'revisionRegistryCount': count}
            with self.subTest(count=count), tempfile.TemporaryDirectory() as temp, \
                    patch.object(redline, 'run_candidate', side_effect=candidate), \
                    patch.object(redline, '_libreoffice_checks', return_value=[]), \
                    patch.object(redline, 'validate_packages', side_effect=lambda _v, paths: {str(p): [] for p in paths}):
                outcome = redline.score_case(record, Path(temp), 'docxodus', 'build', 'commit', {}, 'validator')
                self.assertEqual(outcome['status'], 'measured')
                self.assertEqual(outcome['score'], expected_score)

    def test_missing_or_wrong_semantic_measurements_cannot_pass_an_identity_case(self):
        import shutil
        record = case('redline-semantic-raw-limits-transitional-control')
        def candidate(_adapter, _build, _case, output, _candidate):
            shutil.copyfile(common.ROOT / record['authored']['path'], output)
            return dict(response, status='ok')
        for counts, expected_score in [(None, 0), ({'withPackageChanges': 0}, 0),
                                       ({'withPackageChanges': 1, 'withoutPackageChanges': 0}, 0),
                                       ({'withPackageChanges': False, 'withoutPackageChanges': False}, 0),
                                       ({'withPackageChanges': 0, 'withoutPackageChanges': 0}, 100)]:
            response = {} if counts is None else {'semanticPreflight': counts}
            with self.subTest(counts=counts), tempfile.TemporaryDirectory() as temp, \
                    patch.object(redline, 'run_candidate', side_effect=candidate), \
                    patch.object(redline, '_libreoffice_checks', return_value=[]), \
                    patch.object(redline, 'validate_packages', side_effect=lambda _v, paths: {str(p): [] for p in paths}):
                outcome = redline.score_case(record, Path(temp), 'docxodus', 'build', 'commit', {}, 'validator')
                self.assertEqual(outcome['status'], 'measured')
                self.assertEqual(outcome['score'], expected_score)

    def test_semantic_preflight_is_only_a_declared_identity_comparison(self):
        for key, value in [('version', 2), ('limits', 'unbounded'), ('changeCount', 1)]:
            registry = common.read_json(redline.MANIFEST)
            target = next(c for c in registry['cases'] if 'semanticPreflight' in c)
            target['semanticPreflight'][key] = value
            with self.assertRaisesRegex(ValueError, 'semantic preflight'):
                redline.validate_registry(registry)

    def test_validator_counts_findings_as_a_multiset_over_inputs(self):
        finding = {'id': 'Sem_UniqueAttributeValue', 'part': '/word/styles.xml', 'description': 'dup', 'path': '/a'}
        moved = dict(finding, path='/b')
        documents = {'l': [finding], 'r': [], 'o': [moved]}
        self.assertTrue(redline._validity(documents, ['l', 'r'], 'o')['passed'])
        documents['o'] = [finding, moved]
        self.assertFalse(redline._validity(documents, ['l', 'r'], 'o')['passed'])

    def test_any_failed_check_zeroes_the_case_and_not_applicable_is_ignored(self):
        outcome = {'checks': [{'name': 'a', 'passed': True}, {'name': 'b', 'passed': None, 'ineligible': True}]}
        self.assertEqual(redline._finish(outcome, 'measured')['score'], 100.0)
        outcome['checks'].append({'name': 'c', 'passed': False})
        self.assertEqual(redline._finish(outcome, 'measured')['score'], 0.0)

    def test_suite_needs_every_case_measured(self):
        measured = {'id': 'a', 'category': 'fields', 'kind': 'control', 'status': 'measured', 'score': 100.0, 'checks': []}
        self.assertIsNone(redline.aggregate([measured], ['a', 'b'])['score'])
        other = dict(measured, id='b', category='styles', score=0.0)
        third = dict(measured, id='c', category='styles')
        self.assertEqual(redline.aggregate([measured, other, third], ['a', 'b', 'c'])['score'], 75.0)

    def result(self, scores):
        cases = [{'id': k, 'category': 'fields', 'kind': 'control', 'status': 'measured', 'score': v, 'checks': []} for k, v in scores.items()]
        contract = {'metric': redline.CONTRACT, 'adapter': {'name': 'docxodus', 'build': {'commit': 'x'}}}
        return {'track': 'redline', 'suite': {'cases': list(scores)}, 'contract': contract, 'contractDigest': common.identity(contract),
                'cases': cases, 'summary': redline.aggregate(cases, list(scores))}

    def test_subset_runs_are_never_complete(self):
        measured = {'id': 'a', 'category': 'fields', 'kind': 'control', 'status': 'measured', 'score': 100.0, 'checks': []}
        self.assertFalse(redline.aggregate([measured], ['a', 'b'])['complete'])

    def test_compare_reports_regressions_and_refuses_changed_contracts(self):
        before, after = self.result({'a': 100.0, 'b': 0.0}), self.result({'a': 0.0, 'b': 100.0})
        self.assertEqual(redline.compare(before, after), ['a: regressed from 100 to 0'])
        other = self.result({'a': 0.0, 'c': 100.0})
        with self.assertRaises(ValueError):
            redline.compare(before, other)
        changed = copy.deepcopy(after)
        changed['contract']['metric'] = dict(redline.CONTRACT, version=99)
        changed['contractDigest'] = common.identity(changed['contract'])
        with self.assertRaises(ValueError):
            redline.compare(before, changed)

    def libreoffice(self, record, authored, candidate, authored_view_ok=True):
        def batch(env, folder, items):
            results = []
            for item in items:
                source = Path(item['input'])
                if authored_view_ok or not Path(item['output']).name.startswith('authored'):
                    Path(item['output']).write_bytes(source.read_bytes())
                else:
                    Path(item['output']).write_bytes((common.ROOT / record['inputs'][0]['path']).read_bytes())
                name = Path(item['output']).name
                run = authored if name.startswith('authored') else candidate if name.startswith('candidate') else {'redlinesBefore': 0, 'redlinesAfter': 0}
                results.append({'operation': item['operation'], **run})
            return results
        return batch

    def test_libreoffice_calibration_must_match_the_declaration(self):
        record = case('redline-identity-bytes')
        with tempfile.TemporaryDirectory() as temp:
            for name, authored, candidate, expected in [
                    ('ok', {'redlinesBefore': 0, 'redlinesAfter': 0}, {'redlinesBefore': 0, 'redlinesAfter': 0}, True),
                    ('unresolved', {'redlinesBefore': 0, 'redlinesAfter': 0}, {'redlinesBefore': 1, 'redlinesAfter': 1}, False),
                    ('candidate-error', {'redlinesBefore': 0, 'redlinesAfter': 0}, {'error': 'RuntimeError: cannot load'}, False),
                    ('fixture-error', {'error': 'RuntimeError: cannot load'}, {'redlinesBefore': 0, 'redlinesAfter': 0}, None)]:
                folder = Path(temp) / name
                folder.mkdir()
                with patch.object(redline, 'libreoffice_batch', self.libreoffice(record, authored, candidate)):
                    paths = {k: common.ROOT / v['path'] for k, v in record['expected'].items()}
                    checks = redline._libreoffice_checks(record, folder, {}, common.ROOT / record['authored']['path'], common.ROOT / record['authored']['path'], paths)
                self.assertEqual([c['passed'] for c in checks], [expected, expected], name)
        record = case('redline-header-bookmark-only')
        with tempfile.TemporaryDirectory() as temp, patch.object(redline, 'libreoffice_batch', self.libreoffice(record, {'redlinesBefore': 0, 'redlinesAfter': 0}, {'redlinesBefore': 0, 'redlinesAfter': 0})):
            paths = {k: common.ROOT / v['path'] for k, v in record['expected'].items()}
            checks = redline._libreoffice_checks(record, Path(temp), {}, common.ROOT / record['authored']['path'], common.ROOT / record['authored']['path'], paths)
            self.assertTrue(all(c['passed'] is None and c.get('ineligible') for c in checks))


if __name__ == '__main__':
    unittest.main()
