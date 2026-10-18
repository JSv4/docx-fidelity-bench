"""The benchmark's own tracked-change engine and semantic document views.

Nothing here is derived from a comparison product. `resolve` applies ECMA-376 Part 1 §17.13.5
revision markup to parsed WordprocessingML parts: accepting keeps insertions and drops deletions,
rejecting does the reverse, and both drop property-change records or restore their prior
properties. `view` reads a package (or resolved parts) into a declared, normalized semantic view:
per story, the ordered blocks with their container path, paragraph style and an inline token
stream of text, field characters, bookmark and comment markers and note references. Formatting
other than the paragraph style is outside view version 1.
"""
from __future__ import annotations

import copy
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
W14 = 'http://schemas.microsoft.com/office/word/2010/wordml'
MC = 'http://schemas.openxmlformats.org/markup-compatibility/2006'
FALLBACK = '{' + MC + '}Fallback'
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
VIEW_VERSION = 1


def w(name):
    return '{' + W + '}' + name


def m(name):
    return '{' + M + '}' + name


WRAPPERS = {w('ins'), w('del'), w('moveFrom'), w('moveTo')}
# A revision element under these parents marks its owner (a paragraph mark, a math run, a row or a
# numbering reference) rather than wrapping content.
MARKER_PARENTS = {w('rPr'), w('trPr'), w('numPr')}
CHANGES = {w(n) for n in ('rPrChange', 'pPrChange', 'sectPrChange', 'tblPrChange', 'trPrChange',
                          'tcPrChange', 'tblGridChange', 'tblPrExChange', 'numberingChange')}
CELL_MARKERS = {w('cellIns'), w('cellDel'), w('cellMerge')}
RANGE_REVISIONS = {w(n) for n in ('moveFromRangeStart', 'moveFromRangeEnd', 'moveToRangeStart', 'moveToRangeEnd',
                                  'customXmlInsRangeStart', 'customXmlInsRangeEnd', 'customXmlDelRangeStart',
                                  'customXmlDelRangeEnd', 'customXmlMoveFromRangeStart', 'customXmlMoveFromRangeEnd',
                                  'customXmlMoveToRangeStart', 'customXmlMoveToRangeEnd')}
BLOCK_MARKERS = {w(n) for n in ('bookmarkStart', 'bookmarkEnd', 'commentRangeStart', 'commentRangeEnd', 'permStart', 'permEnd')}
RUNS = {w('r'), m('r')}
REMOVED = {'accept': {w('del'), w('moveFrom')}, 'reject': {w('ins'), w('moveTo')}}
CELL_REMOVED = {'accept': w('cellDel'), 'reject': w('cellIns')}
# Story parts whose content the engine resolves, by relationship type from the main document.
STORY_TYPES = ('header', 'footer', 'footnotes', 'endnotes', 'comments')
MARK_REMOVED = '{urn:docx-fidelity-bench}markRemoved'


class Package:
    """A read-only OOXML package: raw members, relationships and the main story parts."""

    def __init__(self, source):
        if isinstance(source, dict):
            self.members = dict(source)
        else:
            with zipfile.ZipFile(source) as archive:
                self.members = {name: archive.read(name) for name in archive.namelist()}
        root_rels = self.relationships('')
        mains = [target for kind, target in root_rels.values() if kind == 'officeDocument']
        if len(mains) != 1 or mains[0] not in self.members:
            raise ValueError('Package has no unique main document part')
        self.main = mains[0]
        self.main_rels = self.relationships(self.main)

    def relationships(self, part):
        folder, name = posixpath.split(part)
        path = posixpath.join(folder, '_rels', name + '.rels')
        if path not in self.members:
            return {}
        result = {}
        for item in ET.fromstring(self.members[path]):
            if item.get('TargetMode') == 'External':
                continue
            target = item.get('Target', '')
            target = target[1:] if target.startswith('/') else posixpath.normpath(posixpath.join(folder, target))
            result[item.get('Id')] = (item.get('Type', '').rsplit('/', 1)[-1], target)
        return result

    def xml(self, name):
        return ET.fromstring(self.members[name])

    def story_parts(self):
        """The main part and every story part it relates to, as freshly parsed trees."""
        parts = {self.main: self.xml(self.main)}
        for kind, target in self.main_rels.values():
            if kind in STORY_TYPES and target in self.members and target not in parts:
                parts[target] = self.xml(target)
        return parts


# ---------------------------------------------------------------------------------------------
# Accept / reject engine
# ---------------------------------------------------------------------------------------------

def _policy(mode, author=None):
    """The resolution each revision record takes: one mode for all, or accept one author's only."""
    if author is None:
        return lambda record: mode
    return lambda record: 'accept' if record.get(w('author')) == author else 'reject'


def _removes(record, policy):
    return record.tag in REMOVED[policy(record)]


def _marked(element, policy):
    """Whether a run, row or paragraph mark carries a revision marker that removes its owner."""
    holder = element.find(w('rPr')) if element.tag in RUNS else element.find(w('trPr'))
    return holder is not None and any(child.tag in WRAPPERS and _removes(child, policy) for child in holder)


def _removed_custom_xml(root, policy):
    """Find envelopes whose opening and closing tags are both removed by markup ranges.

    ECMA-376 §17.13.5.5/7/9/11 ranges apply to XML tags, independently of their payload.
    Event positions allow one enclosing range or separate ranges crossing each boundary.
    Partial tag removal needs tree reconstruction that this engine does not implement.
    """
    positions, starts, ends = {}, {}, {}
    clock = 0

    def visit(element):
        nonlocal clock
        opening = clock
        clock += 1
        tag = element.tag
        if tag in RANGE_REVISIONS and tag.startswith(w('customXml')):
            start = tag.endswith('Start')
            key = (tag[:-5] if start else tag[:-3], element.get(w('id')))
            records = starts if start else ends
            if key[1] is None or (start and key in records):
                raise ValueError('Invalid custom-XML revision range identity')
            records.setdefault(key, (opening, element))
        for child in element:
            visit(child)
        positions[element] = (opening, clock)
        clock += 1

    visit(root)
    removed_ranges = []
    for key, (opening, record) in starts.items():
        if key not in ends or ends[key][0] <= opening:
            raise ValueError('Unmatched custom-XML revision range')
        kind = key[0].removeprefix(w('customXml')).removesuffix('Range')
        if w(kind[0].lower() + kind[1:]) in REMOVED[policy(record)]:
            removed_ranges.append((opening, ends[key][0]))
    removed = set()
    for element, boundaries in positions.items():
        if element.tag != w('customXml'):
            continue
        covered = [any(start < boundary < end for start, end in removed_ranges) for boundary in boundaries]
        if any(covered) and not all(covered):
            raise ValueError('Partial custom-XML tag removal is unsupported')
        if all(covered):
            removed.add(element)
    return removed


def _resolve_content(element, policy, removed_xml):
    kept = []
    for child in list(element):
        tag = child.tag
        if tag in WRAPPERS and element.tag not in MARKER_PARENTS:
            if not _removes(child, policy):
                _resolve_content(child, policy, removed_xml)
                kept.extend(list(child))
            continue
        if tag in RANGE_REVISIONS:
            continue
        if tag in RUNS and _marked(child, policy):
            continue
        if tag == w('tr') and _marked(child, policy):
            continue
        if tag == w('tc'):
            properties = child.find(w('tcPr'))
            markers = [c for c in properties if c.tag in (w('cellIns'), w('cellDel'))] if properties is not None else []
            if any(CELL_REMOVED[policy(c)] == c.tag for c in markers):
                continue
        if tag == w('p'):
            mark = child.find(w('pPr') + '/' + w('rPr'))
            if mark is not None and any(item.tag in WRAPPERS and _removes(item, policy) for item in mark):
                child.set(MARK_REMOVED, '1')
        _resolve_content(child, policy, removed_xml)
        if child in removed_xml:
            kept.extend(c for c in child if c.tag != w('customXmlPr'))
            continue
        if tag in MARKER_PARENTS or tag == w('tcPr'):
            for item in [c for c in child if c.tag in WRAPPERS or c.tag in CELL_MARKERS]:
                child.remove(item)
        kept.append(child)
    element[:] = kept


def _resolve_properties(element, policy):
    retained = {w('pPr'): (w('rPr'), w('sectPr')), w('sectPr'): (w('headerReference'), w('footerReference'))}
    for parent in list(element.iter()):
        for change in [c for c in parent if c.tag in CHANGES]:
            parent.remove(change)
            # A numbering change records its prior numbering in attributes only; it is dropped.
            if policy(change) != 'reject' or change.tag == w('numberingChange'):
                continue
            prior = list(change)[0] if len(change) else None
            keep = [c for c in parent if c.tag in retained.get(parent.tag, ())]
            restored = list(prior) if prior is not None else []
            parent[:] = restored + keep


def _content(paragraph):
    return [c for c in paragraph if c.tag != w('pPr')]


def _merge_paragraphs(container, story_root, body):
    for child in container:
        _merge_paragraphs(child, story_root, body)
    children = list(container)
    index = 0
    changed = False
    while index < len(children):
        paragraph = children[index]
        if paragraph.tag != w('p') or paragraph.get(MARK_REMOVED) is None:
            index += 1
            continue
        following = index + 1
        while following < len(children) and children[following].tag in BLOCK_MARKERS:
            following += 1
        if following < len(children) and children[following].tag == w('p'):
            target = children[following]
            properties = target.find(w('pPr'))
            moved = _content(paragraph) + children[index + 1:following] + _content(target)
            target[:] = ([properties] if properties is not None else []) + moved
            del children[index:following]
            changed = True
            continue
        paragraphs = [c for c in children if c.tag == w('p')]
        final_body = container is body and paragraph is paragraphs[-1]
        sole = container.tag in (w('tc'), w('footnote'), w('endnote'), w('comment'), w('hdr'), w('ftr')) and len(paragraphs) == 1
        if not _content(paragraph) and not final_body and not sole:
            del children[index]
            changed = True
            continue
        del paragraph.attrib[MARK_REMOVED]
        index += 1
    if changed:
        container[:] = children


def _prune(element):
    for child in list(element):
        _prune(child)
    kept = []
    for child in element:
        block = element.tag not in (w('p'), w('r'), w('hyperlink'), w('fldSimple'), w('smartTag'))
        if block and child.tag == w('sdt'):
            content = child.find(w('sdtContent'))
            if content is not None and not len(content):
                continue
        if block and child.tag == w('customXml') and not any(c.tag != w('customXmlPr') for c in child):
            continue
        if child.tag == w('tbl') and child.find(w('tr')) is None:
            continue
        if child.tag == w('tr') and child.find(w('tc')) is None:
            continue
        kept.append(child)
    element[:] = kept


def resolve(parts, mode, author=None):
    """Return new trees with every revision accepted (`accept`) or rejected (`reject`).

    With `author`, only that author's revisions are accepted and every other revision is rejected,
    which reproduces one reviewer's document from a consolidation.
    """
    if mode not in REMOVED:
        raise ValueError('Unknown revision mode: ' + mode)
    policy = _policy(mode, author)
    resolved = {}
    for name, root in parts.items():
        tree = copy.deepcopy(root)
        _resolve_content(tree, policy, _removed_custom_xml(tree, policy))
        _resolve_properties(tree, policy)
        body = tree.find(w('body'))
        _merge_paragraphs(tree, tree, body)
        _prune(tree)
        resolved[name] = tree
    return resolved


def revision_count(parts):
    """Revision records in the given parts: wrappers, owner markers, cell markers and changes, plus
    deleted-text elements left outside any deletion."""
    total = 0
    def walk(element, deleted):
        nonlocal total
        for child in element:
            if child.tag in WRAPPERS or child.tag in CHANGES or child.tag in CELL_MARKERS or child.tag in RANGE_REVISIONS:
                total += 1
            if child.tag in (w('delText'), w('delInstrText')) and not deleted:
                total += 1
            walk(child, deleted or child.tag in (w('del'), w('moveFrom')))
    for root in parts.values():
        walk(root, False)
    return total


# ---------------------------------------------------------------------------------------------
# Semantic view
# ---------------------------------------------------------------------------------------------

class _Walker:
    def __init__(self, styles):
        self.styles = styles
        self.comments = {}
        self.footnotes = {}
        self.endnotes = {}
        self.bookmarks = {}

    def ordinal(self, table, key):
        if key not in table:
            table[key] = len(table) + 1
        return table[key]

    def style(self, paragraph):
        node = paragraph.find(w('pPr') + '/' + w('pStyle'))
        if node is None:
            return ''
        identifier = node.get(w('val'), '')
        resolved = self.styles.get(identifier)
        return resolved if resolved else 'id:' + identifier

    def inline(self, element, tokens):
        tag = element.tag
        local = tag.split('}', 1)[-1]
        namespace = tag[1:].split('}', 1)[0] if tag.startswith('{') else ''
        if tag == FALLBACK:
            return
        if tag in (w('pPr'), w('rPr'), w('sdtPr'), w('sdtEndPr'), w('customXmlPr'), w('proofErr'),
                   w('lastRenderedPageBreak'), w('separator'), w('continuationSeparator')) or tag in RANGE_REVISIONS:
            return
        if namespace == M and local in ('rPr', 'ctrlPr') or tag in CHANGES:
            return
        if tag in (w('t'), w('delText'), m('t')):
            tokens.append(['t', element.text or ''])
        elif tag in (w('instrText'), w('delInstrText')):
            tokens.append(['i', element.text or ''])
        elif tag in (w('tab'), w('ptab')):
            tokens.append(['t', '\t'])
        elif tag in (w('br'), w('cr')):
            kind = element.get(w('type'), 'textWrapping')
            tokens.append(['t', {'page': '\f', 'column': '\v'}.get(kind, '\n')])
        elif tag == w('noBreakHyphen'):
            tokens.append(['t', '‑'])
        elif tag == w('softHyphen'):
            tokens.append(['t', '­'])
        elif tag == w('sym'):
            tokens.append(['m', 'symbol:' + element.get(w('font'), '') + ':' + element.get(w('char'), '')])
        elif tag == w('fldChar'):
            tokens.append(['m', 'field-' + element.get(w('fldCharType'), '?')])
        elif tag == w('fldSimple'):
            tokens.append(['m', 'field-simple:' + ' '.join(element.get(w('instr'), '').split())])
            self.children(element, tokens)
            tokens.append(['m', 'field-simple-end'])
        elif tag in (w('footnoteReference'), w('endnoteReference')):
            table = self.footnotes if local == 'footnoteReference' else self.endnotes
            tokens.append(['m', local[:-9] + ':' + str(self.ordinal(table, element.get(w('id'))))])
        elif tag in (w('footnoteRef'), w('endnoteRef'), w('annotationRef')):
            tokens.append(['m', local])
        elif tag == w('commentReference'):
            tokens.append(['m', 'comment-reference:' + str(self.ordinal(self.comments, element.get(w('id'))))])
        elif tag in BLOCK_MARKERS:
            tokens.append(['m', self.marker(element)])
        elif tag in (w('drawing'), w('pict'), w('object')):
            tokens.append(['m', 'object:' + local])
        elif tag == w('customXml'):
            tokens.append(['m', 'customXml-begin:' + element.get(w('uri'), '') + '|' + element.get(w('element'), '')])
            self.children(element, tokens)
            tokens.append(['m', 'customXml-end'])
        elif tag in (w('sdt'), w('hyperlink'), w('smartTag'), w('ruby'), w('rt'), w('rubyBase')) or tag in (m('oMath'), m('oMathPara')):
            tokens.append(['m', local + '-begin'])
            self.children(element, tokens)
            tokens.append(['m', local + '-end'])
        else:
            self.children(element, tokens)

    def children(self, element, tokens):
        for child in element:
            self.inline(child, tokens)

    def marker(self, element):
        local = element.tag.split('}', 1)[-1]
        identifier = element.get(w('id'))
        if local == 'bookmarkStart':
            return 'bookmark-start:' + element.get(w('name'), '')
        if local == 'bookmarkEnd':
            return 'bookmark-end:' + self.bookmarks.get(identifier, '#' + str(identifier))
        if local.startswith('commentRange'):
            return 'comment-' + local[12:].lower() + ':' + str(self.ordinal(self.comments, identifier))
        return local

    def paragraph(self, paragraph, path):
        raw = []
        self.children(paragraph, raw)
        tokens = []
        for kind, value in raw:
            if tokens and kind == tokens[-1][0] and kind in ('t', 'i'):
                tokens[-1][1] += value
            elif kind == 't' and not value:
                continue
            else:
                tokens.append([kind, value])
        content = []
        for kind, value in tokens:
            if kind == 'i':
                content.append(['m', 'field-instruction:' + ' '.join(value.split())])
            else:
                content.append([kind, value])
        return {'path': path, 'style': self.style(paragraph), 'content': content}

    def blocks(self, container, path, out, counters=None):
        counters = {} if counters is None else counters
        def index(kind):
            counters[kind] = counters.get(kind, -1) + 1
            return counters[kind]
        for child in container:
            tag = child.tag
            if tag == w('p'):
                out.append(self.paragraph(child, path))
            elif tag == w('tbl'):
                table = path + '/tbl' + str(index('tbl'))
                rows = [r for r in _flatten(child, w('tr'))]
                for r, row in enumerate(rows):
                    for c, cell in enumerate(_flatten(row, w('tc'))):
                        self.blocks(cell, f'{table}/tr{r}/tc{c}', out)
            elif tag == w('sdt'):
                content = child.find(w('sdtContent'))
                self.blocks(content if content is not None else [], path + '/sdt' + str(index('sdt')), out)
            elif tag == w('customXml'):
                self.blocks(child, path + '/customXml' + str(index('customXml')) + ':' + child.get(w('element'), ''), out)
            elif tag in BLOCK_MARKERS:
                out.append({'path': path, 'marker': self.marker(child)})
            elif tag in WRAPPERS or (tag.startswith('{' + MC + '}') and tag != FALLBACK):
                self.blocks(child, path, out, counters)


def _flatten(element, tag):
    """Rows of a table or cells of a row, looking through row/cell-level sdt and customXml wrappers."""
    for child in element:
        if child.tag == tag:
            yield child
        elif child.tag in (w('sdt'), w('customXml')):
            inner = child.find(w('sdtContent')) if child.tag == w('sdt') else child
            if inner is not None:
                yield from _flatten(inner, tag)


def style_names(package):
    names = {}
    styles = [t for k, t in package.main_rels.values() if k == 'styles']
    if styles and styles[0] in package.members:
        for style in package.xml(styles[0]).findall(w('style')):
            name = style.find(w('name'))
            names.setdefault(style.get(w('styleId'), ''), style.get(w('type'), 'paragraph') + ':' + (name.get(w('val'), '') if name is not None else ''))
    return names


def view(package, parts=None, text_only=False):
    """The semantic view of a package, optionally over already resolved story parts."""
    parts = parts if parts is not None else package.story_parts()
    walker = _Walker(style_names(package))
    # Bookmark ends are named by their start wherever the start lies, so walk order cannot leak ids.
    for root in parts.values():
        for start in root.iter(w('bookmarkStart')):
            walker.bookmarks.setdefault(start.get(w('id')), start.get(w('name'), ''))
    stories = {}
    main = parts[package.main]
    body = main.find(w('body'))
    blocks = []
    walker.blocks(body, 'body', blocks)
    # A document's final paragraph mark cannot be deleted, so accepting the deletion of trailing
    # paragraphs leaves an empty last paragraph. One trailing body paragraph with no content is not
    # part of the view.
    if blocks and blocks[-1].get('content') == [] and blocks[-1]['path'] == 'body':
        blocks.pop()
    stories['body'] = blocks
    sections = [s for s in body.iter(w('sectPr'))]
    for number, section in enumerate(sections):
        for reference in section:
            if reference.tag not in (w('headerReference'), w('footerReference')):
                continue
            kind = reference.tag.split('}', 1)[1][:6]
            target = package.main_rels.get(reference.get('{' + REL[:-1] + '}id'), (None, None))[1]
            if target in parts:
                story = []
                walker.blocks(parts[target], kind, story)
                stories[f'section{number}:{kind}:{reference.get(w("type"), "default")}'] = story
    for kind in ('footnote', 'endnote'):
        table = walker.footnotes if kind == 'footnote' else walker.endnotes
        targets = [t for k, t in package.main_rels.values() if k == kind + 's' and t in parts]
        notes = {n.get(w('id')): n for t in targets for n in parts[t].findall(w(kind))}
        done = set()
        while set(table) - done:
            for identifier, ordinal in sorted(table.items(), key=lambda item: item[1]):
                if identifier in done:
                    continue
                done.add(identifier)
                story = []
                if identifier in notes:
                    walker.blocks(notes[identifier], kind, story)
                stories[f'{kind}{ordinal}'] = story if identifier in notes else None
    targets = [t for k, t in package.main_rels.values() if k == 'comments' and t in parts]
    comments = {c.get(w('id')): c for t in targets for c in parts[t].findall(w('comment'))}
    done = set()
    while set(walker.comments) - done:
        for identifier, ordinal in sorted(walker.comments.items(), key=lambda item: item[1]):
            if identifier in done:
                continue
            done.add(identifier)
            comment = comments.get(identifier)
            if comment is None:
                stories[f'comment{ordinal}'] = None
                continue
            story = []
            walker.blocks(comment, 'comment', story)
            stories[f'comment{ordinal}'] = {'author': comment.get(w('author'), ''), 'blocks': story}
    if text_only:
        return text_view(stories)
    return {'version': VIEW_VERSION, 'stories': stories}


def text_view(stories):
    """Paragraph texts and container paths only: the view compared through LibreOffice."""
    result = {}
    for key, story in stories.items():
        blocks = story['blocks'] if isinstance(story, dict) else story
        if blocks is None:
            result[key] = None
            continue
        result[key] = [{'path': b['path'], 'text': ''.join(v for k, v in b['content'] if k == 't')}
                       for b in blocks if 'content' in b]
    return {'version': VIEW_VERSION, 'text': True, 'stories': result}


def flatten_view(value):
    """A token sequence for the similarity diagnostic."""
    items = []
    for key, story in value['stories'].items():
        items.append('story|' + key)
        blocks = story['blocks'] if isinstance(story, dict) else story
        for block in blocks or []:
            if 'marker' in block:
                items.append('block-marker|' + block['path'] + '|' + block['marker'])
            elif 'content' in block:
                items.append('p|' + block['path'] + '|' + block['style'])
                items.extend(k + '|' + v for k, v in block['content'])
            else:
                items.append('p|' + block['path'])
                items.append('t|' + block['text'])
    return items


# ---------------------------------------------------------------------------------------------
# Raw-package facts for declared assertions
# ---------------------------------------------------------------------------------------------

def body_paragraph_count(package, parts=None):
    root = parts[package.main] if parts is not None else package.xml(package.main)
    return sum(1 for _ in root.find(w('body')).iter(w('p')))


def story_roots(package, story):
    """The elements whose paragraphs a scored story holds: the body, or every referenced header and footer."""
    main = package.xml(package.main)
    if story == 'body':
        return [main.find(w('body'))]
    if story == 'headers':
        targets = []
        for reference in main.iter():
            if reference.tag in (w('headerReference'), w('footerReference')):
                target = package.main_rels.get(reference.get('{' + REL[:-1] + '}id'), (None, None))[1]
                if target in package.members and target not in targets:
                    targets.append(target)
        return [package.xml(t) for t in targets]
    raise ValueError('Unknown story: ' + story)


def untracked_text(package, story='body'):
    """Each paragraph's text outside revision wrappers in one scored story; a tracked span leaves a
    separator. Only stories the view reads count, so text parked in an unreferenced part cannot
    satisfy a preservation check."""
    texts = []
    for root in story_roots(package, story):
        for paragraph in root.iter(w('p')):
            pieces = []
            def walk(element, tracked):
                for child in element:
                    if child.tag in WRAPPERS and element.tag not in MARKER_PARENTS:
                        pieces.append('\0')
                        walk(child, True)
                        pieces.append('\0')
                    elif child.tag == w('p') or child.tag == FALLBACK:
                        continue
                    elif child.tag == w('t') and not tracked:
                        pieces.append(child.text or '')
                    else:
                        walk(child, tracked)
            walk(paragraph, False)
            texts.append(''.join(pieces))
    return texts


def para_id_findings(package):
    seen, findings = {}, []
    for name in sorted(package.members):
        if not name.endswith('.xml'):
            continue
        try:
            root = ET.fromstring(package.members[name])
        except ET.ParseError:
            continue
        for element in root.iter():
            value = element.get('{' + W14 + '}paraId')
            if value is None:
                continue
            if not re.fullmatch('[0-9A-Fa-f]{8}', value) or int(value, 16) >= 0x80000000:
                findings.append({'part': name, 'paraId': value, 'problem': 'out of range'})
            key = value.upper()
            if key in seen:
                findings.append({'part': name, 'paraId': value, 'problem': 'duplicate of ' + seen[key]})
            seen.setdefault(key, name)
    return findings


def style_id_findings(package):
    styles = [t for k, t in package.main_rels.values() if k == 'styles']
    if not styles or styles[0] not in package.members:
        return []
    counts = {}
    for style in package.xml(styles[0]).findall(w('style')):
        identifier = style.get(w('styleId'), '')
        counts.setdefault(identifier, []).append(style.get(w('type'), ''))
    return [{'styleId': k, 'types': v} for k, v in sorted(counts.items()) if len(v) > 1]
