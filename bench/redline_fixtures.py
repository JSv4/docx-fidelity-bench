"""Author the redline-track corpus: document pairs, expected results and correct redlines.

Every package is built here from literal text and original OOXML; no input documents, templates or
product test code are imported. For each case the generator writes the inputs, the documents a
correct operation must reproduce (accept-all equals the revised document, reject-all equals the
original), and an authored redline that is correct by construction. The authored redline is the
calibration candidate: it must score 100, which shows the scorer can be satisfied.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
FONT = 'Liberation Serif'
AUTHOR = 'Bench'
DATE = '2026-01-01T00:00:00Z'
SUITE = {'id': 'redline-v2', 'version': 2}
NAMESPACES = (f'xmlns:w="{W}" xmlns:r="{R}" xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
              'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
              'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" mc:Ignorable="w14"')
SECTION = '<w:sectPr>{refs}<w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>'
CLOSING = 'Closing line remains unchanged.'
STYLE_NORMAL = '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
STYLE_TOC = '<w:style w:type="paragraph" w:styleId="TOC1"><w:name w:val="toc 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/></w:style>'


def styles_part(extra=''):
    return (f'<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" '
            f'w:eastAsia="{FONT}" w:cs="{FONT}"/><w:sz w:val="22"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>'
            f'<w:spacing w:after="120"/></w:pPr></w:pPrDefault></w:docDefaults>{STYLE_NORMAL}{extra}</w:styles>')


class Revisions:
    """Revision markup with document-unique ids, as a correct redline writes it."""

    def __init__(self, start=100):
        self.next = start

    def attrs(self, author):
        self.next += 1
        return f'w:id="{self.next}" w:author={quoteattr(author)} w:date="{DATE}"'

    def ins(self, content, author=AUTHOR):
        return f'<w:ins {self.attrs(author)}>{content}</w:ins>'

    def dele(self, content, author=AUTHOR):
        content = content.replace('<w:t ', '<w:delText ').replace('<w:t>', '<w:delText>').replace('</w:t>', '</w:delText>')
        content = content.replace('<w:instrText', '<w:delInstrText').replace('</w:instrText>', '</w:delInstrText>')
        return f'<w:del {self.attrs(author)}>{content}</w:del>'

    def mark(self, kind, author=AUTHOR):
        return f'<w:{kind} {self.attrs(author)}/>'


def t(text, props=''):
    return f'<w:r>{"<w:rPr>" + props + "</w:rPr>" if props else ""}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def p(content='', props='', mark='', para_id=None):
    identity = f' w14:paraId="{para_id}"' if para_id else ''
    rpr = f'<w:rPr>{mark}</w:rPr>' if mark else ''
    ppr = f'<w:pPr>{props}{rpr}</w:pPr>' if props or rpr else ''
    return f'<w:p{identity}>{ppr}{content}</w:p>'


def field(instruction, result_runs, begin=True, end=True):
    """Complex field characters; a field may open or close outside this run sequence."""
    out = ''
    if begin:
        out += ('<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
                f'<w:r><w:instrText xml:space="preserve">{escape(instruction)}</w:instrText></w:r>'
                '<w:r><w:fldChar w:fldCharType="separate"/></w:r>')
    out += result_runs
    if end:
        out += '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
    return out


def bookmark(start, identifier, name=None):
    return f'<w:bookmarkStart w:id="{identifier}" w:name="{name}"/>' if start else f'<w:bookmarkEnd w:id="{identifier}"/>'


def comment_marks(kind, identifier):
    if kind == 'reference':
        return f'<w:r><w:commentReference w:id="{identifier}"/></w:r>'
    return f'<w:comment{kind[0].upper() + kind[1:]} w:id="{identifier}"/>'


def comment(identifier, text, para_id=None):
    return (f'<w:comment w:id="{identifier}" w:author="Reviewer" w:date="{DATE}" w:initials="RV">'
            + p('<w:r><w:annotationRef/></w:r>' + t(text), para_id=para_id) + '</w:comment>')


def sdt(blocks, tag, identifier=4100):
    return f'<w:sdt><w:sdtPr><w:alias w:val="{tag}"/><w:tag w:val="{tag}"/><w:id w:val="{identifier}"/></w:sdtPr><w:sdtContent>{blocks}</w:sdtContent></w:sdt>'


def custom_block(blocks, element):
    return f'<w:customXml w:element="{element}">{blocks}</w:customXml>'


def table(rows, widths=(4680, 4680), row_props=None):
    grid = ''.join(f'<w:gridCol w:w="{x}"/>' for x in widths)
    body = ''
    for index, cells in enumerate(rows):
        trpr = f'<w:trPr>{row_props[index]}</w:trPr>' if row_props and row_props[index] else ''
        body += '<w:tr>' + trpr + ''.join(f'<w:tc><w:tcPr><w:tcW w:w="{x}" w:type="dxa"/></w:tcPr>{c}</w:tc>' for x, c in zip(widths, cells)) + '</w:tr>'
    borders = ''.join(f'<w:{s} w:val="single" w:sz="4" w:space="0" w:color="444444"/>' for s in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'))
    return f'<w:tbl><w:tblPr><w:tblW w:w="{sum(widths)}" w:type="dxa"/><w:tblBorders>{borders}</w:tblBorders><w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid>{grid}</w:tblGrid>{body}</w:tbl>'


def zip_write(path, parts):
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name, payload in sorted(parts.items()):
            item = ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            item.compress_type = ZIP_DEFLATED
            item.external_attr = 0o100644 << 16
            archive.writestr(item, payload.encode() if isinstance(payload, str) else payload)


def package(path, body, styles=None, header=None, comments=None, footnotes=None, settings_extra=''):
    """One minimal, valid WordprocessingML package. Optional story parts take literal XML."""
    relations = [('rStyles', 'styles', 'styles.xml'), ('rSettings', 'settings', 'settings.xml')]
    overrides = [('/word/document.xml', 'document.main'), ('/word/styles.xml', 'styles'), ('/word/settings.xml', 'settings')]
    refs = ''
    parts = {}
    if header is not None:
        parts['word/header1.xml'] = f'<w:hdr {NAMESPACES}>{header}</w:hdr>'
        relations.append(('rHeader', 'header', 'header1.xml'))
        overrides.append(('/word/header1.xml', 'header'))
        refs = '<w:headerReference w:type="default" r:id="rHeader"/>'
    if comments is not None:
        parts['word/comments.xml'] = f'<w:comments {NAMESPACES}>{comments}</w:comments>'
        relations.append(('rComments', 'comments', 'comments.xml'))
        overrides.append(('/word/comments.xml', 'comments'))
    if footnotes is not None:
        separators = ('<w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>'
                      '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>')
        parts['word/footnotes.xml'] = f'<w:footnotes {NAMESPACES}>{separators}{footnotes}</w:footnotes>'
        relations.append(('rFootnotes', 'footnotes', 'footnotes.xml'))
        overrides.append(('/word/footnotes.xml', 'footnotes'))
    parts['word/document.xml'] = f'<w:document {NAMESPACES}><w:body>{body}{SECTION.format(refs=refs)}</w:body></w:document>'
    parts['word/styles.xml'] = styles if styles is not None else styles_part()
    parts['word/settings.xml'] = (f'<w:settings xmlns:w="{W}">{settings_extra}<w:compat><w:compatSetting w:name="compatibilityMode" '
                                  'w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat></w:settings>')
    parts['word/_rels/document.xml.rels'] = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                             + ''.join(f'<Relationship Id="{i}" Type="{R}/{k}" Target="{target}"/>' for i, k, target in relations)
                                             + '</Relationships>')
    parts['_rels/.rels'] = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                            f'<Relationship Id="rDocument" Type="{R}/officeDocument" Target="word/document.xml"/></Relationships>')
    parts['[Content_Types].xml'] = ('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                                    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                                    '<Default Extension="xml" ContentType="application/xml"/>'
                                    + ''.join(f'<Override PartName="{n}" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.{k}+xml"/>' for n, k in overrides)
                                    + '</Types>')
    zip_write(path, parts)


# Comparisons LibreOffice 25.8.7.3 cannot make, established by running the authored redlines. A
# declared-ineligible comparison is not applied; the run fails as unmeasured if the calibration
# disagrees with this table in either direction.
LIBREOFFICE_INELIGIBLE = {
    'redline-field-result-beside-edit': (('accepted',), 'LibreOffice recomputes a PAGEREF result on import and ignores revisions inside it'),
    'redline-field-result-end-control': (('accepted', 'rejected'), 'LibreOffice recomputes a PAGEREF result on import and ignores revisions inside it'),
    'redline-field-result-tab-control': (('accepted', 'rejected'), 'LibreOffice recomputes a PAGEREF result on import and ignores revisions inside it'),
    'redline-comment-straddles-sdt': (('accepted', 'rejected'), 'LibreOffice keeps a comment whose markers lie in resolved revisions and leaves an empty paragraph where a replaced wrapper copy is removed'),
    'redline-comment-straddles-customxml': (('accepted', 'rejected'), 'LibreOffice keeps a comment whose markers lie in resolved revisions and leaves an empty paragraph where a replaced wrapper copy is removed'),
    'redline-comment-para-id-collision': (('accepted', 'rejected'), 'LibreOffice keeps a comment whose markers lie in resolved revisions and leaves an empty paragraph where a replaced wrapper copy is removed'),
    'redline-wrapper-para-id-copies': (('accepted', 'rejected'), 'LibreOffice keeps a comment whose markers lie in resolved revisions and leaves an empty paragraph where a replaced wrapper copy is removed'),
    'redline-comment-para-id-control': (('accepted', 'rejected'), 'LibreOffice keeps a comment whose markers lie in resolved revisions and leaves an empty paragraph where a replaced wrapper copy is removed'),
    'redline-boundary-bookmark-compare-tbl': (('accepted', 'rejected'), 'LibreOffice has no tracked bookmark changes; the authored redline exposes zero revisions'),
    'redline-boundary-bookmark-compare-tr': (('accepted', 'rejected'), 'LibreOffice has no tracked bookmark changes; the authored redline exposes zero revisions'),
    'redline-header-bookmark-only': (('accepted', 'rejected'), 'LibreOffice has no tracked bookmark changes; the redline holds no revision it can see'),
    'redline-body-bookmark-only-control': (('accepted', 'rejected'), 'LibreOffice has no tracked bookmark changes; the redline holds no revision it can see'),
}


class Corpus:
    def __init__(self, root):
        self.root = root
        self.cases = []
        self.generator = {'path': 'bench/redline_fixtures.py', 'sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}

    def file(self, case_id, name, **document):
        path = self.root / 'fixtures' / 'redline' / case_id / (name + '.docx')
        package(path, **document)
        return {'path': str(path.relative_to(self.root)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def add(self, case_id, category, kind, issue, description, operation, inputs, expected, authored, assertions=()):
        ineligible, reason = LIBREOFFICE_INELIGIBLE.get(case_id, ((), None))
        libreoffice = {key: key not in ineligible for key in expected}
        if reason:
            libreoffice['note'] = reason
        self.cases.append({
            'id': case_id, 'version': 1, 'category': category, 'kind': kind, 'issue': issue,
            'description': description, 'operation': operation, 'inputs': inputs, 'expected': expected,
            'authored': authored, 'assertions': list(assertions), 'libreoffice': libreoffice,
            'rights': {'author': 'John Scrudato IV', 'license': 'MIT', 'origin': 'Authored by bench/redline_fixtures.py in this repository',
                       'assets': 'All text is generated here; no images or embedded font files'},
            'generator': self.generator})

    def compare(self, case_id, category, kind, issue, description, left, right, redline, assertions=()):
        """A two-way case: accept-all of a correct redline equals right, reject-all equals left."""
        a = self.file(case_id, 'left', **left)
        b = self.file(case_id, 'right', **right)
        c = self.file(case_id, 'authored-redline', **redline)
        self.add(case_id, category, kind, issue, description, 'compare',
                 [dict(a, role='left'), dict(b, role='right')], {'accepted': b, 'rejected': a}, c, assertions)


def untracked(*texts, story='body'):
    return {'type': 'untracked-text', 'version': 1, 'scope': 'redline', 'story': story, 'texts': list(texts)}


def paragraph_count(count, scope='redline'):
    return {'type': 'paragraph-count', 'version': 1, 'scope': scope, 'story': 'body', 'count': count}


def generate():
    corpus = Corpus(ROOT)
    fields(corpus)
    sdt_fields(corpus)
    comments(corpus)
    para_ids(corpus)
    header_bookmarks(corpus)
    folds(corpus)
    styles(corpus)
    rejects(corpus)
    consolidate(corpus)
    table_boundary_bookmarks(corpus)
    identity(corpus)
    registry = {'schema': 1, 'suite': dict(SUITE, cases=[c['id'] for c in corpus.cases]), 'cases': corpus.cases}
    target = ROOT / 'fixtures' / 'redline' / 'manifest.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(registry, indent=2) + '\n')
    return registry


# ---------------------------------------------------------------------------------------------
# Docxodus #1165: a field's characters where its result changes beside a boundary both sides share
# ---------------------------------------------------------------------------------------------

def fields(corpus):
    opening = p(t('Survey register for the north ridge.'))
    target = p(bookmark(True, 1, '_RefRidge') + t('Ridge station inspected.') + bookmark(False, 1))
    instruction = ' PAGEREF _RefRidge \\h '
    tab = '<w:r><w:tab/></w:r>'
    for name, before, after, kind, description in [
            ('redline-field-result-beside-edit', t('Alpha beta '), t('Alpha '), 'reproducer',
             'PAGEREF result changes from 1 to 7 while the word before the field is deleted'),
            ('redline-field-result-end-control', t('Alpha '), t('Alpha '), 'control',
             'PAGEREF result that ends its paragraph changes from 1 to 7; nothing else in the paragraph changes'),
            ('redline-field-result-tab-control', t('Alpha') + tab, t('Alpha') + tab, 'control',
             'PAGEREF result after a tab changes from 1 to 7; nothing else in the paragraph changes')]:
        def body(state, rev=None):
            if rev is not None:
                lead = before if before == after else t('Alpha ') + rev.dele(t('beta '))
                runs = rev.dele(t('1')) + rev.ins(t('7'))
            else:
                lead = before if state == 'left' else after
                runs = t('1' if state == 'left' else '7')
            return opening + target + p(lead + field(instruction, runs)) + p(t(CLOSING))
        corpus.compare(name, 'fields', kind, 'JSv4/Docxodus#1165', description,
                       {'body': body('left')}, {'body': body('right')}, {'body': body('right', Revisions())},
                       [untracked('Survey register for the north ridge.', 'Alpha', CLOSING)])
    # Table-of-contents entries end with a nested PAGEREF whose result is the entry's page number.
    headings = [('_Toc101', 'Ridge survey'), ('_Toc102', 'Valley survey')]
    def toc(pages, titles, rev=None, changed=()):
        def heading(title, revised):
            if rev is None or title == revised:
                return t(revised)
            a, b = title.split(' '), revised.split(' ')
            head = next(i for i in range(len(a) + 1) if i == len(a) or i == len(b) or a[i] != b[i])
            tail = next(i for i in range(len(a) + 1) if i == len(a) - head or i == len(b) - head or a[-1 - i] != b[-1 - i])
            before = ' '.join(a[:head]) + ' ' if head else ''
            after = ' ' + ' '.join(a[len(a) - tail:]) if tail else ''
            old, new = ' '.join(a[head:len(a) - tail]), ' '.join(b[head:len(b) - tail])
            middle = (rev.dele(t(old)) if old else '') + (rev.ins(t(new + (' ' if not old and after else ''))) if new else '')
            if not old and after:
                after = after[1:]
            return (t(before) if before else '') + middle + (t(after) if after else '')
        entries = []
        for index, ((name, title), page, revised) in enumerate(zip(headings, pages, titles)):
            if rev is not None and index in changed:
                old, new = page
                result = rev.dele(t(old)) + rev.ins(t(new))
            else:
                result = t(page if isinstance(page, str) else page[1])
            label = heading(title, revised)
            content = (field(' TOC \\o "1-1" \\h \\z \\u ', '', end=False) if index == 0 else '') + label + '<w:r><w:tab/></w:r>' + field(f' PAGEREF {name} \\h ', result)
            entries.append(p(content, '<w:pStyle w:val="TOC1"/><w:tabs><w:tab w:val="right" w:leader="dot" w:pos="9350"/></w:tabs>'))
        entries.append(p(field('', '', begin=False)))
        # Each bookmarked heading carries the title its entry shows.
        sections = ''.join(p(bookmark(True, 10 + i, name) + heading(title, revised) + bookmark(False, 10 + i)) + p(t(f'{title} notes are filed.'))
                           for i, ((name, title), revised) in enumerate(zip(headings, titles)))
        return ''.join(entries) + sections + p(t(CLOSING))
    styles = styles_part(STYLE_TOC)
    names = [title for _, title in headings]
    for name, left_pages, right_pages, right_titles, kind, description in [
            ('redline-field-toc-page-numbers', ['1', '2'], ['2', '3'], names, 'reproducer',
             'Table of contents whose two entry page numbers change from 1 and 2 to 2 and 3'),
            ('redline-field-toc-entry-retitled-control', ['1', '2'], ['1', '3'], ['Ridge survey', 'Valley ridge survey'], 'control',
             'A word is inserted inside the second heading, away from its bookmark ends; its table-of-contents entry changes both its title and its page number'),
            ('redline-field-toc-page-number-control', ['1', '2'], ['1', '3'], names, 'control',
             'Table of contents whose second entry page number alone changes from 2 to 3')]:
        changed = [i for i, (a, b) in enumerate(zip(left_pages, right_pages)) if a != b]
        redline_pages = [(a, b) if a != b else a for a, b in zip(left_pages, right_pages)]
        right_body = toc(right_pages, right_titles)
        corpus.compare(name, 'fields', kind, 'JSv4/Docxodus#1165', description,
                       {'body': toc(left_pages, names), 'styles': styles}, {'body': right_body, 'styles': styles},
                       {'body': toc(redline_pages, right_titles, Revisions(), changed), 'styles': styles},
                       [untracked('Ridge survey', 'Ridge survey notes are filed.', CLOSING)])
    # A field opens in one paragraph and closes in the next; text changes beside its end.
    quote = ' QUOTE "First line" '
    for name, before, after, description in [
            ('redline-field-shared-end-append', 'Second line', ' today', 'appends text before the shared field end'),
            ('redline-field-shared-end-trim', 'Second line extended', None, 'trims text before the shared field end'),
            ('redline-field-shared-end-control', 'Second line', 'opening', 'edits the opening paragraph away from the field end')]:
        def body(state, rev=None):
            if rev is not None:
                if after == 'opening':
                    p1, p2 = t('Opening line ') + rev.ins(t('now ')), t(before)
                elif after is None:
                    p1, p2 = t('Opening line '), t('Second line') + rev.dele(t(' extended'))
                else:
                    p1, p2 = t('Opening line '), t(before) + rev.ins(t(after))
            elif state == 'right':
                p1 = t('Opening line now ') if after == 'opening' else t('Opening line ')
                p2 = t('Second line') if after is None else t(before) if after == 'opening' else t(before + after)
            else:
                p1, p2 = t('Opening line '), t(before)
            return (p(t('Field register opening paragraph.')) + p(p1 + field(quote, t('First line'), end=False))
                    + p(field('', p2, begin=False)) + p(t(CLOSING)))
        kind = 'control' if name.endswith('control') else 'reproducer'
        corpus.compare(name, 'fields', kind, 'JSv4/Docxodus#1165', 'Field spanning two paragraphs; the revision ' + description,
                       {'body': body('left')}, {'body': body('right')}, {'body': body('right', Revisions())},
                       [untracked('Field register opening paragraph.', CLOSING)])


# ---------------------------------------------------------------------------------------------
# Docxodus #1166: a paragraph closing one field and opening another
# ---------------------------------------------------------------------------------------------

def sdt_fields(corpus):
    first, second = ' QUOTE "first result" ', ' QUOTE "second result" '
    for name, wrapped, split, description in [
            ('redline-field-close-open-sdt', True, False, 'inside a block content control, one paragraph closes the first field and opens the second'),
            ('redline-field-close-open-body', False, False, 'one body paragraph closes the first field and opens the second'),
            ('redline-field-close-open-sdt-control', True, True, 'inside a block content control, the first field closes and the second opens in separate paragraphs')]:
        def body(state, rev=None):
            middle = t(' middle ')
            if state == 'right':
                middle = t(' middle ') + (rev.ins(t('part ')) if rev else t('part '))
            lead = p(t('Lead ') + field(first, t('first result'), end=False))
            if split:
                inner = p(field('', t('first tail'), begin=False) + middle) + p(field(second, t('second result'), end=False))
            else:
                inner = p(field('', t('first tail'), begin=False) + middle + field(second, t('second result'), end=False))
            tail = p(field('', t('second tail'), begin=False) + t(' ending.'))
            return p(t('Register opening paragraph.')) + lead + (sdt(inner, 'FieldBlock') if wrapped else inner) + tail + p(t(CLOSING))
        corpus.compare(name, 'fields', 'control' if split else 'reproducer', 'JSv4/Docxodus#1166',
                       'Two paragraph-spanning fields where ' + description + '; text is inserted beside the closing field character',
                       {'body': body('left')}, {'body': body('right')}, {'body': body('right', Revisions())},
                       [untracked('Register opening paragraph.', 'Lead', 'ending.', CLOSING)])


# ---------------------------------------------------------------------------------------------
# Docxodus #1167: a comment opening before a wrapper the comparison replaces and closing inside it
# ---------------------------------------------------------------------------------------------

def comments(corpus):
    note = comment(1, 'Check the clause wording.')
    for wrapper in ('sdt', 'customxml'):
        wrap = (lambda blocks: sdt(blocks, 'Clause')) if wrapper == 'sdt' else (lambda blocks: custom_block(blocks, 'clause'))
        for straddle in (True, False):
            def body(state, rev=None):
                revised = t('Clause text first.')
                if state == 'right':
                    revised = t('Clause text first') + (rev.ins(t(', revised')) if rev else t(', revised')) + t('.')
                if straddle:
                    lead = p(t('Before the clause ') + comment_marks('rangeStart', 1) + t('the review begins.'))
                    inner = p(revised) + comment_marks('rangeEnd', 1) + p(t('Clause text second.') + comment_marks('reference', 1))
                else:
                    lead = p(t('Before the clause ') + comment_marks('rangeStart', 1) + t('the review begins.')
                             + comment_marks('rangeEnd', 1) + comment_marks('reference', 1))
                    inner = p(revised) + p(t('Clause text second.'))
                return lead + wrap(inner) + p(t(CLOSING))
            def replaced(rev):
                # The comparison replaces this wrapper whole. One shared range start cannot serve both
                # copies, so the authored redline splits the comment: the original for the deleted
                # copy and reject, a copy with its own start for the inserted copy and accept.
                lead = p(t('Before the clause ') + rev.dele(comment_marks('rangeStart', 1)) + rev.ins(comment_marks('rangeStart', 2)) + t('the review begins.'))
                def copy(kind, identifier, first):
                    wrap = rev.dele if kind == 'del' else rev.ins
                    return wrap_block(p(wrap(t(first)), mark=rev.mark(kind)) + wrap(comment_marks('rangeEnd', identifier))
                                      + p(wrap(t('Clause text second.')) + wrap(comment_marks('reference', identifier)), mark=rev.mark(kind)))
                return lead + copy('del', 1, 'Clause text first.') + copy('ins', 2, 'Clause text first, revised.') + p(t(CLOSING))
            wrap_block = wrap
            label = 'block content control' if wrapper == 'sdt' else 'block custom XML element'
            name = f'redline-comment-straddles-{wrapper}' + ('' if straddle else '-control')
            authored = ({'body': replaced(Revisions()), 'comments': note + comment(2, 'Check the clause wording.')} if straddle
                        else {'body': body('right', Revisions()), 'comments': note})
            corpus.compare(name, 'comments', 'reproducer' if straddle else 'control', 'JSv4/Docxodus#1167',
                           ('Comment opening before a ' + label + ' and ending between its paragraphs, with its reference inside it' if straddle
                            else 'Comment wholly before a ' + label) + '; text is inserted inside the wrapper',
                           {'body': body('left'), 'comments': note}, {'body': body('right'), 'comments': note}, authored,
                           [untracked('Before the clause', CLOSING)])


# ---------------------------------------------------------------------------------------------
# Docxodus #1170: paragraph ids in a redline stay unique across the package and in range
# ---------------------------------------------------------------------------------------------

def para_ids(corpus):
    for name, body_id, wrapped_ids, kind, description in [
            ('redline-comment-para-id-collision', '00000013', False, 'reproducer',
             'the first body paragraph id is one past the largest comment paragraph id'),
            ('redline-wrapper-para-id-copies', '00004000', True, 'reproducer',
             'every paragraph inside the content control carries a paragraph id'),
            ('redline-comment-para-id-control', '00004000', False, 'control',
             'only the paragraphs outside the content control carry ids, far from the comment ids')]:
        notes = comment(1, 'Inside the clause.', para_id='00000011') + comment(2, 'Spans the clause blocks.', para_id='00000012')
        def body(state, rev=None):
            second = t('Clause text second.')
            if state == 'right':
                second = t('Clause text second') + (rev.ins(t(', amended')) if rev else t(', amended')) + t('.')
            ids = ['00000020', '00000021', '00000022'] if wrapped_ids else [None, None, None]
            inner = (p(comment_marks('rangeStart', 1) + t('Clause text first.') + comment_marks('rangeEnd', 1) + comment_marks('reference', 1), para_id=ids[0])
                     + comment_marks('rangeStart', 2) + p(second, para_id=ids[1])
                     + p(t('Clause text third.') + comment_marks('rangeEnd', 2) + comment_marks('reference', 2), para_id=ids[2]))
            return p(t('Register opening paragraph.'), para_id=body_id) + sdt(inner, 'Clause') + p(t(CLOSING), para_id='00004001')
        def replaced(rev):
            # The authored redline replaces the content control whole, as the comparison does for a
            # comment range between its blocks: the deleted copy keeps the original comments and
            # paragraph ids, the inserted copy carries comment copies under fresh ids.
            def copy(kind, ids, first, second, text):
                wrap = rev.dele if kind == 'del' else rev.ins
                return sdt(p(wrap(comment_marks('rangeStart', first)) + wrap(t('Clause text first.')) + wrap(comment_marks('rangeEnd', first))
                             + wrap(comment_marks('reference', first)), mark=rev.mark(kind), para_id=ids[0])
                           + wrap(comment_marks('rangeStart', second)) + p(wrap(t(text)), mark=rev.mark(kind), para_id=ids[1])
                           + p(wrap(t('Clause text third.')) + wrap(comment_marks('rangeEnd', second)) + wrap(comment_marks('reference', second)),
                               mark=rev.mark(kind), para_id=ids[2]), 'Clause')
            old_ids = ['00000020', '00000021', '00000022'] if wrapped_ids else [None] * 3
            new_ids = ['00000023', '00000024', '00000025'] if wrapped_ids else [None] * 3
            return (p(t('Register opening paragraph.'), para_id=body_id) + copy('del', old_ids, 1, 2, 'Clause text second.')
                    + copy('ins', new_ids, 3, 4, 'Clause text second, amended.') + p(t(CLOSING), para_id='00004001'))
        copies = notes + comment(3, 'Inside the clause.', para_id='00000014') + comment(4, 'Spans the clause blocks.', para_id='00000015')
        corpus.compare(name, 'comments', kind, 'JSv4/Docxodus#1170',
                       'Comments inside a content control the comparison replaces whole; ' + description,
                       {'body': body('left'), 'comments': notes}, {'body': body('right'), 'comments': notes},
                       {'body': replaced(Revisions()), 'comments': copies},
                       [untracked('Register opening paragraph.', CLOSING), {'type': 'para-ids-valid', 'version': 1, 'scope': 'redline'}])


# ---------------------------------------------------------------------------------------------
# Docxodus #1174: a bookmark-only change in an otherwise unchanged header
# ---------------------------------------------------------------------------------------------

def header_bookmarks(corpus):
    for name, story in [('redline-header-bookmark-only', 'header'), ('redline-body-bookmark-only-control', 'body')]:
        def blocks(state, rev=None, prefix='Header'):
            first, second = p(t(f'{prefix} first line.')), p(t(f'{prefix} second line.'))
            if state == 'left':
                return first + second
            start, end = bookmark(True, 40, 'MarkedLine'), bookmark(False, 40)
            if rev is not None:
                start, end = rev.ins(start), rev.ins(end)
            return first + start + second + end
        def document(state, rev=None):
            if story == 'header':
                return {'body': p(t('Body text is unchanged.')) + p(t(CLOSING)), 'header': blocks(state, rev)}
            return {'body': blocks(state, rev, 'Body') + p(t(CLOSING)), 'header': p(t('Header first line.'))}
        corpus.compare(name, 'bookmarks', 'reproducer' if story == 'header' else 'control', 'JSv4/Docxodus#1174',
                       'The only difference is a bookmark around the second ' + story + ' paragraph',
                       document('left'), document('right'), document('right', Revisions()),
                       [untracked(f'{story.title()} first line.', f'{story.title()} second line.', story='headers' if story == 'header' else 'body')])


# ---------------------------------------------------------------------------------------------
# Docxodus #1183: a bookmark ending between blocks must not stop the paragraph fold
# ---------------------------------------------------------------------------------------------

def folds(corpus):
    rest = ['Budget review is scheduled for Monday.', 'Hiring plan is attached.']
    heading = 'Quarterly planning notes'
    cells = [['R1C1', 'R1C2'], ['R2C1', 'R2C2']]
    # Found while authoring this suite: replacing the last word of a bookmarked paragraph puts the
    # bookmark end before the deleted word on reject. The control inserts a word inside the range.
    for name, revised, kind in [('redline-bookmark-end-after-replaced-word', 'Valley study', 'reproducer'),
                                ('redline-bookmark-end-after-replaced-word-control', 'Valley ridge survey', 'control')]:
        def marked(content):
            return p(t('Opening line of the survey.')) + p(bookmark(True, 5, '_Toc5') + content + bookmark(False, 5)) + p(t(CLOSING))
        rev = Revisions()
        tracked = (t('Valley ') + rev.dele(t('survey')) + rev.ins(t('study'))) if kind == 'reproducer' else (t('Valley ') + rev.ins(t('ridge ')) + t('survey'))
        corpus.compare(name, 'bookmarks', kind, None,
                       'Bookmarked paragraph whose ' + ('last word is replaced' if kind == 'reproducer' else 'text gains a word inside the bookmark')
                       + '; no Docxodus issue yet',
                       {'body': marked(t('Valley survey'))}, {'body': marked(t(revised))}, {'body': marked(tracked)},
                       [untracked('Opening line of the survey.', 'Valley', CLOSING)])
    for name, between, right_kind in [('redline-bookmark-between-blocks-fold-text', True, 'text'),
                                      ('redline-bookmark-between-blocks-fold-text-control', False, 'text'),
                                      ('redline-bookmark-between-blocks-fold-table', True, 'table'),
                                      ('redline-bookmark-between-blocks-fold-table-control', False, 'table')]:
        def left_body():
            start, end = bookmark(True, 0, '_Toc1'), bookmark(False, 0)
            return p(start + t(heading) + ('' if between else end)) + (end if between else '') + ''.join(p(t(x)) for x in rest)
        def right_body():
            if right_kind == 'text':
                return p(t('Draft agenda for the offsite.'))
            return table([[p(t(c)) for c in row] for row in cells], (3000, 3000)) + p()
        def redline_body(rev):
            # The revised document's last paragraph folds into the deleted heading: one paragraph
            # mark is reused, the later deleted paragraphs merge into the final one.
            start, end = rev.dele(bookmark(True, 0, '_Toc1')), rev.dele(bookmark(False, 0))
            inserted = rev.ins(t('Draft agenda for the offsite.')) if right_kind == 'text' else ''
            # In the table case the right document's empty final paragraph is the original's final
            # mark, so the heading's mark is deleted too.
            first = p(start + inserted + rev.dele(t(heading)) + ('' if between else end),
                      mark=rev.mark('del') if right_kind == 'table' else '') + (end if between else '')
            gone = p(rev.dele(t(rest[0])), mark=rev.mark('del')) + p(rev.dele(t(rest[1])))
            lead = ''
            if right_kind == 'table':
                lead = table([[p(rev.ins(t(c)), mark=rev.mark('ins')) for c in row] for row in cells], (3000, 3000),
                             row_props=[rev.mark('ins'), rev.mark('ins')])
            return lead + first + gone
        expected = 3 + (4 if right_kind == 'table' else 0)
        corpus.compare(name, 'bookmarks', 'control' if name.endswith('control') else 'reproducer', 'JSv4/Docxodus#1183',
                       'Three paragraphs whose heading bookmark ends ' + ('between blocks' if between else 'inside the paragraph')
                       + ', replaced by ' + ('one paragraph' if right_kind == 'text' else 'a two-by-two table and an empty paragraph')
                       + '; the redline keeps the folded paragraph count',
                       {'body': left_body()}, {'body': right_body()}, {'body': redline_body(Revisions())},
                       [paragraph_count(expected)])


# ---------------------------------------------------------------------------------------------
# Docxodus #1184: one style id used for styles of different types
# ---------------------------------------------------------------------------------------------

def styles(corpus):
    paragraph_style = '<w:style w:type="paragraph" w:customStyle="1" w:styleId="DocID"><w:name w:val="DocID"/><w:basedOn w:val="Normal"/><w:rPr><w:sz w:val="16"/></w:rPr></w:style>'
    character_style = '<w:style w:type="character" w:customStyle="1" w:styleId="DocID"><w:name w:val="DocID"/><w:rPr><w:b w:val="0"/><w:sz w:val="16"/></w:rPr></w:style>'
    other_paragraph = '<w:style w:type="paragraph" w:customStyle="1" w:styleId="DocID"><w:name w:val="DocID"/><w:basedOn w:val="Normal"/><w:rPr><w:sz w:val="18"/></w:rPr></w:style>'
    for name, right_style in [('redline-style-id-cross-type', character_style), ('redline-style-id-same-type-control', other_paragraph)]:
        def body(word, rev=None):
            text = t('The ') + (rev.dele(t('original')) + rev.ins(t('revised')) if rev else t(word)) + t(' paragraph.')
            return p(text) + p(t(CLOSING))
        corpus.compare(name, 'styles', 'reproducer' if right_style is character_style else 'control', 'JSv4/Docxodus#1184',
                       'Unreferenced style id DocID is a paragraph style in the original and a '
                       + ('character' if right_style is character_style else 'different paragraph') + ' style in the revision',
                       {'body': body('original'), 'styles': styles_part(paragraph_style)},
                       {'body': body('revised'), 'styles': styles_part(right_style)},
                       {'body': body(None, Revisions()), 'styles': styles_part(paragraph_style)},
                       [untracked('The', 'paragraph.', CLOSING), {'type': 'style-ids-unique', 'version': 1, 'scope': 'redline'}])


# ---------------------------------------------------------------------------------------------
# Docxodus #1176: rejecting revisions held by an inline customXml, math or a ruby base
# ---------------------------------------------------------------------------------------------

def rejects(corpus):
    def math_run(text):
        return f'<m:r><m:t>{escape(text)}</m:t></m:r>'
    def holder(kind, inner):
        if kind == 'customxml':
            return f'<w:customXml w:element="term">{inner}</w:customXml>'
        if kind == 'math':
            return f'<m:oMath>{inner}</m:oMath>'
        if kind == 'ruby':
            return ('<w:r><w:ruby><w:rubyPr><w:rubyAlign w:val="center"/><w:hps w:val="11"/><w:hpsRaise w:val="20"/>'
                    '<w:hpsBaseText w:val="22"/><w:lid w:val="en-US"/></w:rubyPr>'
                    f'<w:rt>{t("gloss")}</w:rt><w:rubyBase>{inner}</w:rubyBase></w:ruby></w:r>')
        return inner
    for kind, label in [('customxml', 'an inline custom XML element'), ('math', 'an Office Math zone'),
                        ('ruby', 'a ruby base'), ('direct', 'the paragraph itself')]:
        def content(tracked, rev=None):
            if kind == 'math':
                middle = rev.ins(math_run('+y')) + rev.dele(math_run('-z')) if tracked else math_run('-z')
                return math_run('x') + middle + math_run('=w')
            middle = (rev.ins(t('added ')) + rev.dele(t('removed '))) if tracked else t('removed ')
            return t('alpha ') + middle + t('omega')
        def body(tracked, rev=None):
            return p(t('Ledger ') + holder(kind, content(tracked, rev)) + t(' closes.')) + p(t(CLOSING))
        name = 'redline-reject-' + kind + ('-control' if kind == 'direct' else '')
        original = corpus.file(name, 'original', body=body(False))
        tracked = corpus.file(name, 'tracked', body=body(True, Revisions()))
        corpus.add(name, 'revisions', 'control' if kind == 'direct' else 'reproducer', 'JSv4/Docxodus#1176',
                   'Rejecting one insertion and one deletion held by ' + label, 'reject',
                   [dict(tracked, role='input')], {'output': original}, original,
                   [{'type': 'revision-count', 'version': 1, 'scope': 'output', 'max': 0}])


# ---------------------------------------------------------------------------------------------
# Docxodus #1175: N-way consolidation keeps a reviewer's block-level bookmarks
# ---------------------------------------------------------------------------------------------

def consolidate(corpus):
    for name, change in [('redline-consolidate-cell-bookmark', 'bookmark'), ('redline-consolidate-cell-text-control', 'text')]:
        def body(first_edit, second_edit, rev=None):
            opening = t('Ledger opening')
            if second_edit:
                opening += rev.ins(t(' revised'), 'Reviewer2') if rev else t(' revised')
            first = p(t('Entry alpha first.'))
            second_text = t('Entry alpha second')
            if first_edit and change == 'text':
                second_text += rev.ins(t(', checked'), 'Reviewer1') if rev else t(', checked')
            second = p(second_text + t('.'))
            if first_edit and change == 'bookmark':
                start, end = bookmark(True, 60, 'ReviewedEntry'), bookmark(False, 60)
                if rev:
                    start, end = rev.ins(start, 'Reviewer1'), rev.ins(end, 'Reviewer1')
                second = start + second + end
            return p(opening + t('.')) + table([[first + second, p(t('Entry beta.'))]]) + p(t(CLOSING))
        files = {role: corpus.file(name, role, body=body(*edits)) for role, edits in
                 [('base', (False, False)), ('reviewer1', (True, False)), ('reviewer2', (False, True)), ('merged', (True, True))]}
        authored = corpus.file(name, 'authored-redline', body=body(True, True, Revisions()))
        label = {'bookmark': 'adds a bookmark around an entry', 'text': 'edits an entry'}[change]
        corpus.add(name, 'consolidate', 'control' if change == 'text' else 'reproducer', 'JSv4/Docxodus#1175',
                   'Two reviewers: the first ' + label + ' inside a table cell, the second edits the opening paragraph', 'consolidate',
                   [dict(files['base'], role='base'), dict(files['reviewer1'], role='reviewer', author='Reviewer1'),
                    dict(files['reviewer2'], role='reviewer', author='Reviewer2')],
                   {'accepted': files['merged'], 'rejected': files['base']}, authored,
                   [untracked('Ledger opening', 'Entry alpha first.', CLOSING)])


def table_boundary_bookmarks(corpus):
    for operation in ('compare', 'consolidate'):
        for level in ('tbl', 'tr', 'p'):
            name = 'redline-boundary-bookmark-' + operation + '-' + ('paragraph-control' if level == 'p' else level)
            def body(marked, edited, rev=None):
                start, end = (bookmark(True, 73, 'HazelBoundary'), bookmark(False, 73)) if marked and level != 'p' else ('', '')
                if marked and rev and level != 'p':
                    start, end = rev.ins(start, 'Reviewer1'), rev.ins(end, 'Reviewer1')
                value = t('Hazel lower') + ((rev.ins(t(' revised'), 'Reviewer2') if rev else t(' revised')) if edited else '')
                content = table([[p(t('Hazel upper')), p(t('Birch upper'))], [p(value), p(t('Birch lower'))]])
                if level == 'tbl':
                    content = content.replace('</w:tr><w:tr>', '</w:tr>' + start + '<w:tr>', 1).replace('</w:tbl>', end + '</w:tbl>')
                elif level == 'tr':
                    content = content.replace('</w:tc><w:tc>', '</w:tc>' + start + '<w:tc>', 1).replace('</w:tc></w:tr>', '</w:tc>' + end + '</w:tr>', 1)
                else:
                    content = content.replace(t('Birch upper'), start + t('Birch upper') +
                        ((rev.ins(t(' checked'), 'Reviewer1') if rev else t(' checked')) if marked else '') + end, 1)
                return p(t('Hazel boundary ledger')) + content + p(t(CLOSING))
            variants = [(False, False), (True, False)] + ([(False, True)] if operation == 'consolidate' else [])
            inputs = []
            for index, variant in enumerate(variants):
                record = corpus.file(name, 'source-' + str(index), body=body(*variant))
                role = ('left' if index == 0 else 'right') if operation == 'compare' else ('base' if index == 0 else 'reviewer')
                inputs.append(dict(record, role=role, **({'author': 'Reviewer' + str(index)} if role == 'reviewer' else {})))
            accepted = corpus.file(name, 'accepted', body=body(True, operation == 'consolidate'))
            authored = corpus.file(name, 'authored-redline', body=body(True, operation == 'consolidate', Revisions()))
            corpus.add(name, 'bookmarks', 'control' if level == 'p' else 'reproducer', 'JSv4/Docxodus#1190',
                       operation.title() + (' independent plain-text edits (control)' if level == 'p' else
                           ' a bookmark directly in ' + level + ', with an independent table edit for consolidation'),
                       operation, inputs, {'accepted': accepted, 'rejected': {k: inputs[0][k] for k in ('path', 'sha256')}}, authored,
                       [untracked('Hazel upper', 'Birch upper', CLOSING)])


# ---------------------------------------------------------------------------------------------
# Identity calibration: an exact package and a differently serialized equal document
# ---------------------------------------------------------------------------------------------

def identity(corpus):
    texts = ['Survey register for the north ridge.', 'The crew compares the notes and keeps the route open.', CLOSING]
    plain = ''.join(p(t(x)) for x in texts)
    left = corpus.file('redline-identity-bytes', 'left', body=plain)
    corpus.add('redline-identity-bytes', 'identity', 'identity', None, 'Byte-identical packages', 'compare',
               [dict(left, role='left'), dict(left, role='right')], {'accepted': left, 'rejected': left}, left,
               [{'type': 'revision-count', 'version': 1, 'scope': 'redline', 'max': 0}, untracked(*texts)])
    split = ''.join(p(''.join(t(word + ' ') for word in x.split(' ')[:-1]) + t(x.split(' ')[-1])).replace('<w:p>', f'<w:p w:rsidR="00A1B2C{i}" w:rsidRDefault="00A1B2C{i}">', 1)
                    for i, x in enumerate(texts))
    a = corpus.file('redline-identity-reserialized', 'left', body=plain)
    b = corpus.file('redline-identity-reserialized', 'right', body=split)
    corpus.add('redline-identity-reserialized', 'identity', 'identity', None,
               'Equal text, styles and structure serialized with different run splits and revision-save ids',
               'compare', [dict(a, role='left'), dict(b, role='right')], {'accepted': b, 'rejected': a}, a,
               [{'type': 'revision-count', 'version': 1, 'scope': 'redline', 'max': 0}, untracked(*texts)])


if __name__ == '__main__':
    print(f'Authored {len(generate()["cases"])} deterministic redline cases')
