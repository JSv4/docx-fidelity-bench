import copy
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from unittest.mock import patch

from bench import common, fixtures, redline, redline_build, redline_fixtures, revisions

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
        self.assertEqual(registry['suite']['id'], 'redline-v32')
        self.assertEqual(len(registry['cases']), 245)
        issues = {c['issue'] for c in registry['cases'] if c['issue']}
        self.assertEqual(issues, {f'JSv4/Docxodus#{n}' for n in (1165, 1166, 1167, 1170, 1174, 1175, 1176, 1183, 1184, 1188, 1190, 1195, 1196, 1197, 1206, 1210, 1211, 1212, 1218, 1312, 1317, 1322, 1330, 1331, 1337, 1340, 1342, 1352, 1384, 1387, 1388, 1406, 1409, 1420, 1421, 1425, 1426, 1428, 1526, 1533, 1534, 1535, 1545, 1557, 1560)})

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
        # Checked here independently of bench/audit.py: no custom XML parts, every font relationship
        # comes from the font table and reaches the declared placeholder (not a font program), and
        # the only font-named entries are the font table, its relationships and those targets.
        for record in cases():
            for item in redline.artifact_records(record):
                parts = members(item)
                placeholders = set()
                for name, payload in parts.items():
                    if not name.endswith('.rels'):
                        continue
                    for relationship in ET.fromstring(payload):
                        if relationship.get('Type', '').endswith('/font'):
                            self.assertEqual(name, 'word/_rels/fontTable.xml.rels')
                            target = 'word/' + relationship.get('Target')
                            self.assertEqual(parts.get(target), common.PLACEHOLDER_FONT_BYTES, item['path'])
                            placeholders.add(target)
                for name in parts:
                    self.assertFalse(name.startswith('customXml/'))
                    if 'font' in name.lower():
                        self.assertIn(name, {'word/fontTable.xml', 'word/_rels/fontTable.xml.rels'} | placeholders)

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

    def test_section_boundaries_reject_wrong_carrier_with_equal_semantic_views(self):
        for shape in ('add', 'remove', 'stable-control'):
            record = case('redline-retained-section-' + shape)
            package = load(record['authored'])
            for assertion in record['assertions']:
                if assertion['type'] != 'section-boundaries':
                    continue
                scope = assertion['scope']
                parts = revisions.resolve(package.story_parts(), 'accept' if scope == 'accepted' else 'reject')
                self.assertTrue(redline._assertion(assertion, package, {scope: parts})['passed'])
                if not assertion['afterParagraphs']:
                    continue
                before = revisions.view(package, parts)
                body = parts[package.main].find(W + 'body')
                first, second = body.findall(W + 'p')
                props = first.find(W + 'pPr')
                boundary = props.find(W + 'sectPr')
                props.remove(boundary)
                new_props = second.find(W + 'pPr')
                if new_props is None:
                    new_props = ET.Element(W + 'pPr')
                    second.insert(0, new_props)
                new_props.append(boundary)
                # A final empty paragraph leaves both sections nonempty but is normalized out of the view.
                body.insert(len(body) - 1, ET.Element(W + 'p'))
                self.assertEqual(before, revisions.view(package, parts))
                self.assertFalse(redline._assertion(assertion, package, {scope: parts})['passed'])

    def test_section_boundary_declarations_reject_ambiguous_indices(self):
        original = common.read_json(redline.MANIFEST)
        for indices in (None, [True], [-1], [0, 0], [1, 0], ['0'], [{}]):
            registry = copy.deepcopy(original)
            registry['cases'][-1]['assertions'].append({
                'type': 'section-boundaries', 'version': 1, 'scope': 'accepted', 'afterParagraphs': indices})
            with self.subTest(indices=indices), self.assertRaises(ValueError):
                redline.validate_registry(registry)

    def test_section_stories_reject_phantom_deletion_and_missing_target(self):
        for story in ('header', 'footer'):
            record = case('redline-inserted-section-' + story)
            assertion = next(a for a in record['assertions'] if a['type'] == 'section-stories')
            package = load(record['authored'])
            endpoints = views(package)
            blank = 'word/' + story + '2.xml'
            root = package.xml(blank)
            root.set('xmlns:w14', revisions.W14)
            paragraph = root.find(W + 'p')
            deletion = ET.SubElement(paragraph, W + 'del', {W + 'id': '90', W + 'author': 'Bench'})
            ET.SubElement(ET.SubElement(deletion, W + 'r'), W + 'delText').text = 'CEDAR REFERENCE'
            package.members[blank] = ET.tostring(root)
            self.assertEqual(views(package), endpoints)
            self.assertFalse(redline._assertion(assertion, package, {})['passed'])
            del package.members[blank]
            self.assertFalse(redline._assertion(assertion, package, {})['passed'])

    def test_section_stories_follow_inheritance_and_ignore_property_history(self):
        record = case('redline-inserted-section-footer')
        assertion = {'type': 'section-stories', 'version': 1, 'scope': 'redline', 'story': 'footer',
                     'kind': 'default', 'values': ['', 'CEDAR REFERENCE', 'CEDAR REFERENCE']}
        def inherited(root):
            root.set('xmlns:w14', revisions.W14)
            body = root.find(W + 'body')
            final = body.find(W + 'sectPr')
            paragraph = ET.Element(W + 'p')
            ET.SubElement(paragraph, W + 'pPr').append(copy.deepcopy(final))
            body.insert(len(body) - 1, paragraph)
            final.remove(final.find(W + 'footerReference'))
            history = ET.SubElement(final, W + 'sectPrChange', {W + 'id': '99', W + 'author': 'Bench'})
            history.append(ET.Element(W + 'sectPr'))
        package = rewrite(record['authored'], inherited)
        self.assertTrue(redline._assertion(assertion, package, {})['passed'])

    def test_section_stories_reject_ambiguous_references_with_unchanged_endpoints(self):
        for story in ('header', 'footer'):
            with self.subTest(story=story):
                record = case('redline-inserted-section-' + story)
                assertion = next(a for a in record['assertions'] if a['type'] == 'section-stories')
                def duplicate(root):
                    root.set('xmlns:w14', revisions.W14)
                    section = root.find('.//' + W + 'sectPr')
                    reference = copy.deepcopy(section.find(W + story + 'Reference'))
                    reference.set('{' + revisions.REL[:-1] + '}id', 'rStory')
                    section.insert(0, reference)
                mutant = rewrite(record['authored'], duplicate)
                self.assertEqual(views(mutant), views(load(record['authored'])))
                self.assertFalse(redline._assertion(assertion, mutant, {})['passed'])

    def test_section_stories_distinguish_kinds_and_relationship_types(self):
        record = case('redline-inserted-section-footer')
        original = next(a for a in record['assertions'] if a['type'] == 'section-stories')
        for kind in ('first', 'even'):
            def change_kind(root):
                root.set('xmlns:w14', revisions.W14)
                for reference in root.iter(W + 'footerReference'):
                    reference.set(W + 'type', kind)
            package = rewrite(record['authored'], change_kind)
            assertion = dict(original, kind=kind)
            self.assertTrue(redline._assertion(assertion, package, {})['passed'])
            self.assertFalse(redline._assertion(original, package, {})['passed'])
            # A same-text target of another relationship type is not a footer.
            relationships = package.xml('word/_rels/document.xml.rels')
            next(r for r in relationships if r.get('Id') == 'rStory').set('Type', revisions.REL + 'header')
            package.members['word/_rels/document.xml.rels'] = ET.tostring(relationships)
            self.assertFalse(redline._assertion(assertion, revisions.Package(package.members), {})['passed'])

    def test_revision_blocks_detects_interleaving_without_changing_endpoints(self):
        for shape in ('articles', 'numbered', 'linked', 'distinct-control'):
            record = case('redline-complete-rewrite-' + shape)
            assertion = record['assertions'][0]
            original = views(load(record['authored']))
            for index in (1, 3):
                def interleave(root):
                    root.set('xmlns:w14', revisions.W14)
                    body = root.find(W + 'body')
                    paragraphs = body.findall(W + 'p')
                    body.remove(paragraphs[4])
                    body.insert(index, paragraphs[4])
                broken = rewrite(record['authored'], interleave)
                self.assertEqual(views(broken), original)
                self.assertFalse(redline._assertion(assertion, broken, {})['passed'])
            def untrack(root):
                root.set('xmlns:w14', revisions.W14)
                for deletion in root.iter(W + 'delText'):
                    deletion.text = ''
            self.assertFalse(redline._assertion(assertion, rewrite(record['authored'], untrack), {})['passed'])

    def test_revision_blocks_accepts_shared_boundary_paragraph(self):
        record = case('redline-complete-rewrite-articles')
        def join_boundary(root):
            root.set('xmlns:w14', revisions.W14)
            body = root.find(W + 'body')
            paragraphs = body.findall(W + 'p')
            # The common boundary remains in both resolved views.
            paragraphs[3].remove(paragraphs[3].find(W + 'pPr'))
            for child in list(paragraphs[4]):
                if child.tag != W + 'pPr':
                    paragraphs[3].append(child)
            body.remove(paragraphs[4])
        package = rewrite(record['authored'], join_boundary)
        self.assertEqual(views(package), views(load(record['authored'])))
        self.assertTrue(redline._assertion(record['assertions'][0], package, {})['passed'])

    def test_revision_blocks_rejects_interleaved_words_at_shared_boundary(self):
        record = case('redline-complete-rewrite-linked')
        def interleave(root):
            root.set('xmlns:w14', revisions.W14)
            body = root.find(W + 'body')
            paragraphs = body.findall(W + 'p')
            boundary = paragraphs[3]
            deleted = [c for c in boundary if c.tag != W + 'pPr']
            inserted = [c for c in paragraphs[4] if c.tag != W + 'pPr']
            boundary[:] = []
            for i in range(max(len(deleted), len(inserted))):
                if i < len(deleted): boundary.append(deleted[i])
                if i < len(inserted): boundary.append(inserted[i])
            body.remove(paragraphs[4])
        package = rewrite(record['authored'], interleave)
        self.assertEqual(views(package), views(load(record['authored'])))
        self.assertFalse(redline._assertion(record['assertions'][0], package, {})['passed'])

    def test_paragraph_spacing_checks_style_revisions_and_direct_precedence(self):
        record = case('redline-field-default-spacing-simple')
        package = load(record['authored'])
        for assertion in record['assertions']:
            if assertion['type'] != 'paragraph-spacing':
                continue
            scope = assertion['scope']
            mode = 'accept' if scope == 'accepted' else 'reject'
            resolved = {scope: revisions.resolve(package.story_parts(), mode)}
            self.assertTrue(redline._assertion(assertion, package, resolved)['passed'])
            # Lost style history is text-equivalent but cannot restore the original spacing.
            parts = dict(package.members)
            styles = ET.fromstring(parts['word/styles.xml'])
            normal = styles.find(W + 'style')
            if scope == 'accepted':
                normal.remove(normal.find(W + 'pPr'))
            else:
                props = normal.find(W + 'pPr')
                props.remove(props.find(W + 'pPrChange'))
            parts['word/styles.xml'] = ET.tostring(styles)
            mutant = revisions.Package(parts)
            self.assertFalse(redline._assertion(assertion, mutant, resolved)['passed'])
            # A direct per-attribute override wins, while the other attributes still inherit.
            paragraph = resolved[scope][package.main].find(W + 'body').find(W + 'p')
            props = paragraph.find(W + 'pPr')
            if props is None:
                props = ET.Element(W + 'pPr')
                paragraph.insert(0, props)
            ET.SubElement(props, W + 'spacing', {W + 'after': '999'})
            observed = redline.paragraph_spacing(package, resolved[scope], scope)
            self.assertEqual(observed[0], dict(assertion['values'][0], after='999'))
            self.assertFalse(redline._assertion(assertion, package, resolved)['passed'])

    def test_paragraph_spacing_rejects_unmeasured_override_modes(self):
        record = case('redline-field-default-spacing-simple')
        package = load(record['authored'])
        assertion = next(a for a in record['assertions'] if a['type'] == 'paragraph-spacing' and a['scope'] == 'accepted')
        resolved = {'accepted': revisions.resolve(package.story_parts(), 'accept')}
        for attribute in ('beforeAutospacing', 'afterAutospacing', 'beforeLines', 'afterLines'):
            with self.subTest(attribute=attribute):
                parts = dict(package.members)
                styles = ET.fromstring(parts['word/styles.xml'])
                spacing = styles.find(W + 'style/' + W + 'pPr/' + W + 'spacing')
                spacing.set(W + attribute, '1' if attribute.endswith('Autospacing') else '999')
                parts['word/styles.xml'] = ET.tostring(styles)
                self.assertFalse(redline._assertion(assertion, revisions.Package(parts), resolved)['passed'])

    def test_paragraph_spacing_resolves_based_on_and_direct_attributes(self):
        package = load(case('redline-field-default-spacing-simple')['authored'])
        parts = dict(package.members)
        styles = ET.fromstring(parts['word/styles.xml'])
        normal = styles.find(W + 'style')
        normal.insert(1, ET.Element(W + 'basedOn', {W + 'val': 'Base'}))
        styles.append(ET.fromstring(f'<w:style xmlns:w="{revisions.W}" w:type="paragraph" w:styleId="Base">'
            '<w:name w:val="Base"/><w:pPr><w:spacing w:before="111" w:after="222" w:line="333" w:lineRule="exact"/></w:pPr></w:style>'))
        styles.append(ET.fromstring(f'<w:style xmlns:w="{revisions.W}" w:type="paragraph" w:styleId="Derived">'
            '<w:name w:val="Derived"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="444"/></w:pPr></w:style>'))
        parts['word/styles.xml'] = ET.tostring(styles)
        package = revisions.Package(parts)
        for scope, mode, count, after, line in [('accepted', 'accept', 4, '280', '380'), ('rejected', 'reject', 2, '80', '260')]:
            resolved = revisions.resolve(package.story_parts(), mode)
            paragraph = resolved[package.main].find(W + 'body/' + W + 'p')
            properties = paragraph.find(W + 'pPr')
            if properties is None:
                properties = ET.Element(W + 'pPr')
                paragraph.insert(0, properties)
            properties.insert(0, ET.Element(W + 'pStyle', {W + 'val': 'Derived'}))
            ET.SubElement(properties, W + 'spacing', {W + 'line': '555'})
            expected = [dict(before='111', after=after, line=line, lineRule='auto') for _ in range(count)]
            expected[0].update(after='444', line='555')
            self.assertEqual(redline.paragraph_spacing(package, resolved, scope), expected)

    def test_field_spacing_cases_reject_field_loss_despite_equal_text_and_spacing(self):
        for shape in ('simple', 'complex'):
            with self.subTest(shape=shape):
                record = case('redline-field-default-spacing-' + shape)
                package = load(record['authored'])
                def flatten(root):
                    root.set('xmlns:w14', revisions.W14)
                    for parent in root.iter():
                        for child in list(parent):
                            if child.tag == W + 'fldSimple':
                                offset = list(parent).index(child)
                                parent.remove(child)
                                for index, run in enumerate(list(child)):
                                    parent.insert(offset + index, run)
                            elif child.tag == W + 'r' and any(e.tag in (W + 'fldChar', W + 'instrText') for e in child):
                                parent.remove(child)
                mutant = rewrite(record['authored'], flatten)
                for scope, mode in [('accepted', 'accept'), ('rejected', 'reject')]:
                    resolved = {scope: revisions.resolve(mutant.story_parts(), mode)}
                    assertion = next(a for a in record['assertions'] if a['type'] == 'paragraph-spacing' and a['scope'] == scope)
                    self.assertTrue(redline._assertion(assertion, mutant, resolved)['passed'])
                    self.assertNotEqual(revisions.view(package, revisions.resolve(package.story_parts(), mode)),
                                        revisions.view(mutant, resolved[scope]))

    def test_inline_trees_calibrate_and_reject_operator_changes(self):
        for record in cases():
            for assertion in record['assertions']:
                if assertion['type'] != 'inline-trees':
                    continue
                package = load(record['authored'])
                resolved = {scope: revisions.resolve(package.story_parts(), mode)
                            for scope, mode in (('accepted', 'accept'), ('rejected', 'reject'))}
                self.assertTrue(redline._assertion(assertion, package, resolved)['passed'], record['id'])
        record = case('redline-tab-equation')
        def change(root):
            for operator in root.iter(revisions.m('chr')):
                operator.set(revisions.m('val'), '∏')
        package = rewrite(record['authored'], change)
        for assertion in record['assertions']:
            if assertion['type'] == 'inline-trees':
                mode = 'accept' if assertion['scope'] == 'accepted' else 'reject'
                resolved = {assertion['scope']: revisions.resolve(package.story_parts(), mode)}
                self.assertFalse(redline._assertion(assertion, package, resolved)['passed'])

    def test_vml_textbox_assertion_rejects_geometry_and_body_loss(self):
        record = case('redline-textbox-geometry')
        for attribute in ('style', 'body'):
            def change(root):
                if attribute == 'style':
                    for shape in root.iter('{urn:schemas-microsoft-com:vml}shape'):
                        shape.set('style', shape.get('style').replace('width:120pt', 'width:80pt'))
                else:
                    for box in root.iter(W + 'txbxContent'):
                        for text in box.iter():
                            if text.tag in {W + 't', W + 'delText'}: text.text = 'Missing body'
            wrong = rewrite(record['authored'], change)
            assertion = next(a for a in record['assertions'] if a['type'] == 'inline-trees' and a['scope'] == 'accepted')
            self.assertFalse(redline._assertion(assertion, wrong,
                {'accepted': revisions.resolve(wrong.story_parts(), 'accept')})['passed'])

    def test_inline_trees_allow_equivalent_math_run_splits(self):
        record = case('redline-tab-equation')
        def split(root):
            for parent in root.iter():
                for run in list(parent):
                    text = run.find(revisions.m('t'))
                    if run.tag != revisions.m('r') or text is None or text.text != 'i=1':
                        continue
                    at = list(parent).index(run)
                    first, second = copy.deepcopy(run), copy.deepcopy(run)
                    first.find(revisions.m('t')).text = 'i='
                    second.find(revisions.m('t')).text = '1'
                    parent.remove(run)
                    parent.insert(at, second)
                    parent.insert(at, first)
        package = rewrite(record['authored'], split)
        for assertion in record['assertions']:
            if assertion['type'] == 'inline-trees':
                mode = 'accept' if assertion['scope'] == 'accepted' else 'reject'
                resolved = {assertion['scope']: revisions.resolve(package.story_parts(), mode)}
                self.assertTrue(redline._assertion(assertion, package, resolved)['passed'])

    def test_drawing_assertion_rejects_lost_fill_text_and_image_bytes(self):
        record = case('redline-shared-drawing-source')
        assertion = next(a for a in record['assertions'] if a['type'] == 'inline-trees' and a['scope'] == 'accepted')
        wrong = load(case('redline-shared-drawing-source-control')['authored'])
        self.assertFalse(redline._assertion(assertion, wrong,
            {'accepted': revisions.resolve(wrong.story_parts(), 'accept')})['passed'])
        def change_text(root):
            for box in root.iter(W + 'txbxContent'):
                for text in box.iter():
                    if text.tag in {W + 't', W + 'delText'}: text.text = 'Lost text'
        wrong = rewrite(record['authored'], change_text)
        self.assertFalse(redline._assertion(assertion, wrong,
            {'accepted': revisions.resolve(wrong.story_parts(), 'accept')})['passed'])
        assertion = next(a for a in record['assertions'] if a['type'] == 'inline-trees' and a['scope'] == 'rejected')
        parts = members(record['authored'])
        parts['word/media/fill.png'] = fixtures.png(8, 8, lambda x, y: (0x88, 0x22, 0x66))
        wrong = revisions.Package(parts)
        self.assertFalse(redline._assertion(assertion, wrong,
            {'rejected': revisions.resolve(wrong.story_parts(), 'reject')})['passed'])

    def test_inline_tree_declarations_reject_invalid_values(self):
        for key, value in [('name', []), ('name', 'p'), ('trees', ['<broken']),
                           ('trees', ['<other/>']), ('trees', None), ('images', []),
                           ('images', {'rFill': 'not-a-digest'}), ('scope', 'redline')]:
            registry = common.read_json(redline.MANIFEST)
            record = next(c for c in registry['cases'] if c['id'] == 'redline-shared-drawing-source')
            assertion = next(a for a in record['assertions'] if a['type'] == 'inline-trees')
            assertion[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                redline.validate_registry(registry)

    def test_equation_suffix_must_remain_untracked(self):
        record = case('redline-tab-equation')
        def churn(root):
            paragraph = root.find(W + 'body/' + W + 'p')
            run = next(e for e in paragraph if e.tag == W + 'r' and ''.join(e.itertext()) == ' Survey ledger.')
            at = list(paragraph).index(run)
            paragraph.remove(run)
            for offset, (kind, text_name) in enumerate((('del', 'delText'), ('ins', 't'))):
                wrapper = ET.Element(W + kind, {W + 'id': str(900 + offset), W + 'author': 'Bench'})
                text = ET.SubElement(ET.SubElement(wrapper, W + 'r'), W + text_name)
                text.text = ' Survey ledger.'
                paragraph.insert(at + offset, wrapper)
        wrong = rewrite(record['authored'], churn)
        assertion = next(a for a in record['assertions'] if a['type'] == 'untracked-text')
        self.assertFalse(redline._assertion(assertion, wrong, {'redline': None})['passed'])

    def test_move_from_text_rejects_deletion_carriers_and_missing_moves(self):
        record = case('redline-moved-from-text')
        assertion = next(a for a in record['assertions'] if a['type'] == 'revision-text')
        self.assertTrue(redline._assertion(assertion, load(record['authored']), {'redline': None})['passed'])
        for mutation in ('deleted-text', 'deleted-instruction', 'missing-move'):
            def change(root):
                move = next(e for e in root.iter(W + 'moveFrom') if list(e.iter(W + 't')))
                if mutation == 'deleted-text':
                    next(move.iter(W + 't')).tag = W + 'delText'
                elif mutation == 'deleted-instruction':
                    next(move.iter(W + 'r')).append(ET.Element(W + 'delInstrText'))
                else:
                    move.tag = W + 'del'
            altered = rewrite(record['authored'], change)
            self.assertFalse(redline._assertion(assertion, altered, {'redline': None})['passed'], mutation)

    def test_revision_text_rejects_wrong_deletion_carrier(self):
        record = case('redline-moved-from-text-control')
        assertion = next(a for a in record['assertions'] if a['type'] == 'revision-text')
        self.assertTrue(redline._assertion(assertion, load(record['authored']), {'redline': None})['passed'])
        def change(root):
            next(root.iter(W + 'delText')).tag = W + 't'
        self.assertFalse(redline._assertion(assertion, rewrite(record['authored'], change), {'redline': None})['passed'])

    def test_split_deletion_may_cross_proofing_marks_but_not_content(self):
        record = case('redline-moved-from-text-control')
        assertion = next(a for a in record['assertions'] if a['type'] == 'revision-text')
        def split(root, marker):
            deletion = next(e for e in root.iter(W + 'del') if list(e.iter(W + 'delText')))
            parent = next(e for e in root.iter() if deletion in list(e))
            first = next(deletion.iter(W + 'delText'))
            second = copy.deepcopy(deletion); second.set(W + 'id', '999')
            tail = next(second.iter(W + 'delText'))
            first.text, tail.text = first.text[:3], first.text[3:]
            parent.insert(list(parent).index(deletion) + 1, marker)
            parent.insert(list(parent).index(marker) + 1, second)
        proof = ET.Element(W + 'proofErr', {W + 'type': 'spellStart'})
        with_proof = rewrite(record['authored'], lambda root: split(root, proof))
        self.assertTrue(redline._assertion(assertion, with_proof, {'redline': None})['passed'])
        intervening = ET.Element(W + 'r'); ET.SubElement(intervening, W + 't').text = 'intervening'
        with_content = rewrite(record['authored'], lambda root: split(root, intervening))
        self.assertFalse(redline._assertion(assertion, with_content, {'redline': None})['passed'])

    def test_move_text_joins_only_wrappers_in_the_same_body_range(self):
        record = case('redline-moved-from-text')
        assertion = next(a for a in record['assertions'] if a['type'] == 'revision-text')
        def split(root):
            move = next(e for e in root.iter(W + 'moveFrom') if list(e.iter(W + 't')))
            parent = next(e for e in root.iter() if move in list(e))
            text = next(move.iter(W + 't'))
            second = copy.deepcopy(move)
            second.set(W + 'id', '999')
            second_text = next(second.iter(W + 't'))
            text.text, second_text.text = text.text[:20], text.text[20:]
            parent.insert(list(parent).index(move) + 1, second)
        self.assertTrue(redline._assertion(assertion, rewrite(record['authored'], split), {'redline': None})['passed'])

        def other_range(root):
            split(root)
            parent = next(e for e in root.iter(W + 'p') if len(list(e.iter(W + 'moveFrom'))) == 2)
            second = list(parent.iter(W + 'moveFrom'))[1]
            before = ET.Element(W + 'moveFromRangeEnd', {W + 'id': '101'})
            after = ET.Element(W + 'moveFromRangeStart', {W + 'id': '998', W + 'name': 'other'})
            parent.insert(list(parent).index(second), before)
            parent.insert(list(parent).index(second), after)
            next(e for e in parent if e.tag == W + 'moveFromRangeEnd' and e.get(W + 'id') == '101' and e is not before).set(W + 'id', '998')
        self.assertFalse(redline._assertion(assertion, rewrite(record['authored'], other_range), {'redline': None})['passed'])

        parts = members(record['authored'])
        root = ET.fromstring(parts['word/document.xml'])
        move = next(e for e in root.iter(W + 'moveFrom') if list(e.iter(W + 't')))
        header = ET.Element(W + 'hdr'); paragraph = ET.SubElement(header, W + 'p'); paragraph.append(copy.deepcopy(move))
        move.tag = W + 'del'
        parts['word/document.xml'] = ET.tostring(root)
        parts['word/header1.xml'] = ET.tostring(header)
        rels = ET.fromstring(parts['word/_rels/document.xml.rels'])
        ET.SubElement(rels, '{http://schemas.openxmlformats.org/package/2006/relationships}Relationship',
                      Id='rTestHeader', Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/header', Target='header1.xml')
        parts['word/_rels/document.xml.rels'] = ET.tostring(rels)
        self.assertFalse(redline._assertion(assertion, revisions.Package(parts), {'redline': None})['passed'])

    def test_malformed_revision_text_declarations_are_rejected(self):
        for scope, kind, text in [('redline', 'moveFrom', ''), ('redline', 'del', None),
                                  ('accepted', 'del', 'text'), ('redline', [], 'text')]:
            registry = common.read_json(redline.MANIFEST)
            registry['cases'][0]['assertions'].append(dict(type='revision-text', version=1, scope=scope, kind=kind, text=text))
            with self.subTest(scope=scope, kind=kind, text=text), self.assertRaises(ValueError):
                redline.validate_registry(registry)

    def test_run_atom_assertion_rejects_changed_attributes_and_equivalent_carriers(self):
        for name, attribute in [('ptab', 'alignment'), ('symbol', 'font'), ('page', 'clear'), ('cr', None)]:
            record = case('redline-visible-atom-' + name)
            assertion = next(a for a in record['assertions'] if a['scope'] == 'rejected')
            original = load(record['expected']['rejected'])
            self.assertTrue(redline._assertion(assertion, original, {'rejected': None})['passed'])
            def change(root):
                atom = next(e for run in root.iter(W + 'r') for e in run if e.tag == W + assertion['atoms'][0]['name'])
                if attribute:
                    atom.set(W + attribute, 'changed')
                else:
                    atom.tag = W + 'br'
            altered = rewrite(record['expected']['rejected'], change)
            self.assertFalse(redline._assertion(assertion, altered, {'rejected': None})['passed'], name)

    def test_malformed_run_atom_declarations_are_rejected(self):
        for atoms in ([{}], [None], [{'name': [], 'attributes': {}}], [{'name': {}, 'attributes': {}}],
                      [{'name': 'unknown', 'attributes': {}}], [{'name': 'br', 'attributes': []}],
                      [{'name': 'br', 'attributes': {'type': None}}], [{'name': 'br', 'attributes': {}, 'extra': 1}]):
            registry = common.read_json(redline.MANIFEST)
            registry['cases'][0]['assertions'].append(dict(type='run-atoms', version=1, scope='rejected', atoms=atoms))
            with self.subTest(atoms=atoms), self.assertRaises(ValueError):
                redline.validate_registry(registry)
        registry = common.read_json(redline.MANIFEST)
        registry['cases'][0]['assertions'].append(dict(type='run-atoms', version=1, scope='redline', atoms=[]))
        with self.assertRaises(ValueError):
            redline.validate_registry(registry)

    def test_native_control_metadata_is_mandatory_even_when_visible_text_matches(self):
        for kind, mutation in [('binding', 'xpath'), ('binding', 'storeItemID'),
                               ('binding', 'remove'), ('citation', 'instruction'), ('citation', 'remove')]:
            record = case('redline-control-rewrite-' + kind + '-echo')
            assertion = record['assertions'][0]
            def change(root):
                control = next(root.iter(W + 'sdt'))
                if mutation == 'remove':
                    parent = next(e for e in root.iter() if control in list(e))
                    at = list(parent).index(control)
                    for child in list(control.find(W + 'sdtContent')):
                        parent.insert(at, child); at += 1
                    parent.remove(control)
                elif mutation == 'instruction':
                    next(control.iter(W + 'instrText')).text = ' CITATION Elm '
                else:
                    control.find(W + 'sdtPr/' + W + 'dataBinding').set(W + mutation, 'changed')
            altered = rewrite(record['expected']['accepted'], change)
            # The existing semantic view detects wrappers, but omits binding properties.
            if kind == 'binding' and mutation != 'remove':
                self.assertEqual(revisions.view(altered), revisions.view(load(record['expected']['accepted'])))
            self.assertFalse(redline._assertion(assertion, altered, {'accepted': None})['passed'], (kind, mutation))

    def test_untracked_rewrite_cannot_hide_pending_revisions_in_resolved_views(self):
        record = case('redline-control-rewrite-binding-echo')
        def change(root):
            paragraph = next(root.iter(W + 'p'))
            paragraph.append(ET.Element(W + 'ins', {W + 'id': '99', W + 'author': 'Other',
                                                    W + 'date': '2026-01-01T00:00:00Z'}))
        altered = rewrite(record['expected']['accepted'], change)
        resolved = dict(redline=None, accepted=revisions.resolve(altered.story_parts(), 'accept'),
                        rejected=revisions.resolve(altered.story_parts(), 'reject'))
        self.assertEqual(views(altered), views(load(record['expected']['accepted'])))
        checks = [redline._assertion(a, altered, resolved)['passed'] for a in record['assertions']]
        self.assertEqual(checks, [True, True, False])

    def test_malformed_control_and_paragraph_rewrite_declarations_are_rejected(self):
        for controls in (None, {}, [None], ['<broken'], ['<w:r xmlns:w="' + W[1:-1] + '"/>']):
            registry = common.read_json(redline.MANIFEST)
            target = next(c for c in registry['cases'] if c['operation'] == 'replace-text')
            target['assertions'][0]['controls'] = controls
            with self.subTest(controls=controls), self.assertRaises(ValueError):
                redline.validate_registry(registry)
        for spec in (None, [], 'invalid'):
            registry = common.read_json(redline.MANIFEST)
            next(c for c in registry['cases'] if c['operation'] == 'replace-text')['paragraphRewrite'] = spec
            with self.subTest(spec=spec), self.assertRaisesRegex(ValueError, 'paragraph rewrite'):
                redline.validate_registry(registry)
        registry = common.read_json(redline.MANIFEST)
        target = next(c for c in registry['cases'] if c['operation'] == 'replace-text')
        target['assertions'] = [a for a in target['assertions'] if a['type'] != 'revision-count']
        with self.assertRaisesRegex(ValueError, 'without revisions'):
            redline.validate_registry(registry)
        for key, value in [('version', True), ('paragraphIndex', True), ('paragraphIndex', -1), ('markdown', None)]:
            registry = common.read_json(redline.MANIFEST)
            target = next(c for c in registry['cases'] if c['operation'] == 'replace-text')
            target['paragraphRewrite'][key] = value
            with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, 'paragraph rewrite'):
                redline.validate_registry(registry)

    def test_reproducers_and_controls_differ_from_their_original(self):
        for record in cases(operation='compare'):
            if record['kind'] == 'identity' or 'semanticPreflight' in record:
                continue
            accepted, rejected = load(record['expected']['accepted']), load(record['expected']['rejected'])
            wrong_resolutions = {scope: revisions.resolve(accepted.story_parts(), mode)
                                 for scope, mode in (('accepted', 'accept'), ('rejected', 'reject'))}
            structural_difference = any(not redline._assertion(a, accepted, wrong_resolutions)['passed']
                                        for a in record['assertions'] if a['scope'] in {'accepted', 'rejected'})
            self.assertTrue(revisions.view(accepted) != revisions.view(rejected) or structural_difference, record['id'])


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
                resolved = {'redline': None, 'output': None,
                            'accepted': revisions.resolve(candidate.story_parts(), 'accept'),
                            'rejected': revisions.resolve(candidate.story_parts(), 'reject')}
                assertions_pass = all(redline._assertion(a, candidate, resolved)['passed'] for a in record['assertions'])
                self.assertFalse(accepted == revisions.view(right) and rejected == revisions.view(left) and assertions_pass, record['id'])

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

    def test_hyperlink_emptied_by_resolution_is_removed(self):
        package = fragment('<w:p><w:r><w:t>a</w:t></w:r><w:hyperlink w:anchor="x"><w:ins w:id="1"><w:r><w:t>new</w:t></w:r></w:ins></w:hyperlink>'
                           '<w:hyperlink w:anchor="y"><w:del w:id="2"><w:r><w:delText>old</w:delText></w:r></w:del></w:hyperlink>'
                           '<w:hyperlink w:anchor="z"/></w:p>')
        def content(mode):
            return revisions.view(package, revisions.resolve(package.story_parts(), mode))['stories']['body'][0]['content']
        # The hyperlink the source wrote empty survives either way; only one the resolution emptied goes.
        kept = [['m', 'hyperlink-begin'], ['m', 'hyperlink-end']]
        self.assertEqual(content('accept'), [['t', 'a'], ['m', 'hyperlink-begin'], ['t', 'new'], ['m', 'hyperlink-end']] + kept)
        self.assertEqual(content('reject'), [['t', 'a'], ['m', 'hyperlink-begin'], ['t', 'old'], ['m', 'hyperlink-end']] + kept)

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

    def test_match_edit_declarations_require_a_typed_pattern(self):
        for key, value in [('version', True), ('version', 3), ('tracked', 1),
                           ('pattern', ''), ('pattern', None), ('pattern', 4), ('replacement', None), ('start', 0)]:
            registry = common.read_json(redline.MANIFEST)
            target = next(c for c in registry['cases'] if c['id'] == 'redline-alternate-textbox-match')
            target['spanEdit'][key] = value
            with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, 'span edit'):
                redline.validate_registry(registry)

    def test_alternate_textbox_assertions_reject_a_stale_hidden_copy(self):
        for operation in ('span', 'match'):
            record = case('redline-alternate-textbox-' + operation)
            package = load(record['authored'])
            parts = revisions.resolve(package.story_parts(), 'accept')
            assertion = next(a for a in record['assertions'] if a['name'] == 'pict' and a['scope'] == 'accepted')
            self.assertTrue(redline._assertion(assertion, package, {'accepted': parts})['passed'])
            fallback = parts[package.main].find('.//{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback')
            replacement = next(e for e in fallback.iter(W + 't') if e.text == 'Bob')
            replacement.text = 'Alice'
            self.assertFalse(redline._assertion(assertion, package, {'accepted': parts})['passed'])

    def test_header_drawing_assertions_reject_lost_text_geometry_and_carriers(self):
        record = case('redline-header-textbox-label')
        package = load(record['authored'])
        assertion = next(a for a in record['assertions'] if a['type'] == 'inline-trees' and a['scope'] == 'accepted')
        for mutation in ('text', 'geometry', 'drawing'):
            parts = revisions.resolve(package.story_parts(), 'accept')
            self.assertTrue(redline._assertion(assertion, package, {'accepted': parts})['passed'])
            header = parts['word/header1.xml']
            if mutation == 'text':
                next(e for e in header.iter(W + 't') if e.text == 'Oak').text = 'Cedar'
            elif mutation == 'geometry':
                next(header.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}ext')).set('cx', '1')
            else:
                parent = next(e for e in header.iter() if e.find(W + 'drawing') is not None)
                parent.remove(parent.find(W + 'drawing'))
            self.assertFalse(redline._assertion(assertion, package, {'accepted': parts})['passed'], mutation)

    def test_header_drawing_assertions_require_the_running_story_scope(self):
        for story in (None, 'body', [], 1):
            registry = common.read_json(redline.MANIFEST)
            record = next(c for c in registry['cases'] if c['id'] == 'redline-header-textbox-label')
            next(a for a in record['assertions'] if a['type'] == 'inline-trees')['story'] = story
            with self.subTest(story=story), self.assertRaises(ValueError):
                redline.validate_registry(registry)

    def test_running_story_trees_normalize_only_effective_text_spaces(self):
        whole = ET.fromstring('<w:p xmlns:w="' + revisions.W + '"><w:r><w:t xml:space="preserve">Oak bulletin</w:t></w:r></w:p>')
        split = ET.fromstring('<w:p xmlns:w="' + revisions.W + '"><w:r><w:t>Oak</w:t></w:r><w:r><w:t xml:space="preserve"> bulletin</w:t></w:r></w:p>')
        self.assertNotEqual(redline.inline_tree(whole, {}), redline.inline_tree(split, {}))
        self.assertEqual(redline.inline_tree(whole, {}, version=2), redline.inline_tree(split, {}, version=2))
        split.findall('.//' + W + 't')[1].attrib.clear()
        self.assertNotEqual(redline.inline_tree(whole, {}, version=2), redline.inline_tree(split, {}, version=2))
        split.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        expected = copy.deepcopy(whole)
        expected.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        self.assertEqual(redline.inline_tree(expected, {}, version=2), redline.inline_tree(split, {}, version=2))

    def test_running_story_vml_images_compare_bytes_and_require_a_target(self):
        image = ET.fromstring('<v:imagedata xmlns:v="urn:schemas-microsoft-com:vml" xmlns:r="' + revisions.REL[:-1] + '" r:id="rImg"/>')
        old = redline.inline_tree(image, {'rImg': 'a' * 64}, version=2)
        self.assertNotEqual(old, redline.inline_tree(image, {'rImg': 'b' * 64}, version=2))
        self.assertNotEqual(old, redline.inline_tree(image, {}, version=2))
        renamed = copy.deepcopy(image)
        renamed.set('{' + revisions.REL[:-1] + '}id', 'renamed')
        self.assertEqual(old, redline.inline_tree(renamed, {'renamed': 'a' * 64}, version=2))

    def test_candidate_crash_does_not_poison_fixture_calibration(self):
        import shutil
        record = case('redline-header-textbox-label')
        expected = {key: common.ROOT / value['path'] for key, value in record['expected'].items()}
        def crashing_session(_env, _folder, items):
            crashed = False
            results = []
            for item in items:
                if item['key'].startswith('candidate-'):
                    crashed = True
                if crashed:
                    results.append({'error': 'bridge disposed'})
                else:
                    mode = item['key'].split('-', 1)[1]
                    shutil.copyfile(expected[mode], item['output'])
                    results.append({'redlinesBefore': 1 if item['key'].startswith('authored-') else 0, 'redlinesAfter': 0})
            return results
        with tempfile.TemporaryDirectory() as temp, patch.object(redline, 'libreoffice_batch', side_effect=crashing_session):
            checks = redline._libreoffice_checks(record, Path(temp), {}, Path(temp) / 'candidate.docx',
                common.ROOT / record['authored']['path'], expected)
        self.assertEqual([False, False], [check['passed'] for check in checks])
        self.assertTrue(all('candidate output' in check['reason'] for check in checks))

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

    def test_a_validator_only_sees_copies_and_one_that_rewrites_them_is_refused(self):
        # Opening a package by path, the SDK writes its rewrite of an unparseable link target back
        # into the file; the harness hands the validator copies and refuses a run that changes one.
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'input.docx'
            path.write_bytes(b'original')
            seen = []
            def rewriting(argv, **_kwargs):
                seen.extend(argv[2:])
                for name in argv[2:]:
                    Path(name).write_bytes(b'rewritten')
                return json.dumps({'documents': {name: [] for name in argv[2:]}})
            with patch.object(redline_build, 'execute', side_effect=rewriting), self.assertRaisesRegex(ValueError, 'modified'):
                redline_build.validate_packages(temp, [path])
            self.assertEqual(path.read_bytes(), b'original')
            self.assertNotIn(str(path), seen)
            finding = {'id': 'x', 'part': None, 'path': None, 'description': 'd'}
            with patch.object(redline_build, 'execute', side_effect=lambda argv, **_k: json.dumps({'documents': {argv[2]: [finding]}})):
                self.assertEqual(redline_build.validate_packages(temp, [path]), {str(path): [finding]})

    def test_hyperlink_targets_must_resolve_to_the_declared_external_targets(self):
        record = case('redline-hyperlink-mailto-recipients')
        target = 'mailto:first@example.com;second@example.com'
        self.assertEqual(revisions.hyperlink_target_findings(load(record['authored']), [target]), [])
        # A second link to the same relationship is not a different target.
        twice = members(record['authored'])
        twice['word/document.xml'] = twice['word/document.xml'].replace(b'</w:hyperlink>', b'</w:hyperlink><w:hyperlink r:id="rLink"><w:r><w:t>again</w:t></w:r></w:hyperlink>', 1)
        self.assertEqual(revisions.hyperlink_target_findings(revisions.Package(twice), [target]), [])
        def relationships(change):
            parts = members(record['authored'])
            rels = ET.fromstring(parts['word/_rels/document.xml.rels'])
            change(rels)
            parts['word/_rels/document.xml.rels'] = ET.tostring(rels)
            return revisions.Package(parts)
        def link(rels):
            return next(r for r in rels if r.get('Id') == 'rLink')
        # The SDK's stream-open workaround, written back out: both round trips would still pass.
        rewritten = relationships(lambda rels: link(rels).set('Target', 'rewritten://87561fa0-50f4-491e-863e-39ceab24833f'))
        self.assertEqual([f['problem'] for f in revisions.hyperlink_target_findings(rewritten, [target])], ['targets differ'])
        # A target "repaired" by dropping a recipient is not the target the document wrote.
        trimmed = relationships(lambda rels: link(rels).set('Target', 'mailto:first@example.com'))
        self.assertEqual([f['problem'] for f in revisions.hyperlink_target_findings(trimmed, [target])], ['targets differ'])
        # A dropped relationship, and a hyperlink left on an id another relationship also holds.
        dropped = relationships(lambda rels: rels.remove(link(rels)))
        self.assertEqual([f['problem'] for f in revisions.hyperlink_target_findings(dropped, [target])],
                         ['resolves to 0 relationships, not one external hyperlink', 'targets differ'])
        shared = relationships(lambda rels: link(rels).set('Id', 'rStyles'))
        shared = revisions.Package({**shared.members, 'word/document.xml': shared.members['word/document.xml'].replace(b'r:id="rLink"', b'r:id="rStyles"')})
        self.assertEqual([f['problem'] for f in revisions.hyperlink_target_findings(shared, [target])],
                         ['resolves to 2 relationships, not one external hyperlink', 'targets differ'])
        # The link pointed at the styles relationship instead of its own.
        misdirected = revisions.Package({**members(record['authored']), 'word/document.xml': members(record['authored'])['word/document.xml'].replace(b'r:id="rLink"', b'r:id="rStyles"')})
        self.assertEqual([f['problem'] for f in revisions.hyperlink_target_findings(misdirected, [target])],
                         ['resolves to 1 relationships, not one external hyperlink', 'targets differ'])

    def test_an_output_that_fails_to_open_is_never_licensed_by_its_inputs(self):
        # Inputs the SDK refuses at open carry one Package_Open finding and no schema findings; an
        # output keeping that defect would otherwise pass validity without ever being validated.
        failed = {'id': 'Package_Open', 'part': None, 'description': 'OpenXmlPackageException: invalid part', 'path': None}
        documents = {'l': [failed], 'r': [failed], 'o': [failed]}
        self.assertFalse(redline._validity(documents, ['l', 'r'], 'o')['passed'])
        documents['o'] = []
        self.assertTrue(redline._validity(documents, ['l', 'r'], 'o')['passed'])

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
