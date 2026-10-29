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
from .fixtures import PACKAGE_LINK_TARGET, PACKAGE_SHAPES, package_shape, custom_xml_link, comment_view_cases, comment_view_mark, comment_view_note, comment_view_wrapper, duplicate_comment_cases, consolidated_field_cases, comment_identity_cases, removed_comment_cases, note_insertion_cases, bookmark_reviewer_cases, bookmark_review_container, bookmark_conflict_cases, complex_field as field

ROOT = Path(__file__).resolve().parents[1]
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
W15 = 'http://schemas.microsoft.com/office/word/2012/wordml'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
FONT = 'Liberation Serif'
AUTHOR = 'Bench'
DATE = '2026-01-01T00:00:00Z'
SUITE = {'id': 'redline-v18', 'version': 18}
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


def package(path, body, styles=None, header=None, comments=None, footnotes=None, settings_extra='', comments_extended=None, strict=False, people=None,
            relations_extra=(), content_types_extra='', extra_parts=None):
    """One minimal, valid WordprocessingML package. Optional story parts take literal XML.

    `relations_extra` appends main-document relationships as (id, type, target) or
    (id, type, target, 'External'); `content_types_extra` adds literal Default/Override elements;
    `extra_parts` adds literal parts. Package-shape cases use them to write deliberate defects."""
    relations = [('rStyles', 'styles', 'styles.xml'), ('rSettings', 'settings', 'settings.xml')]
    overrides = [('/word/document.xml', 'document.main'), ('/word/styles.xml', 'styles'), ('/word/settings.xml', 'settings')]
    refs = ''
    parts = {}
    if people is not None:
        parts['word/people.xml'] = f'<w15:people xmlns:w15="{W15}">{people}</w15:people>'
        relations.append(('rPeople', 'http://schemas.microsoft.com/office/2011/relationships/people', 'people.xml'))
        overrides.append(('/word/people.xml', 'people'))
    if header is not None:
        parts['word/header1.xml'] = f'<w:hdr {NAMESPACES}>{header}</w:hdr>'
        relations.append(('rHeader', 'header', 'header1.xml'))
        overrides.append(('/word/header1.xml', 'header'))
        refs = '<w:headerReference w:type="default" r:id="rHeader"/>'
    if comments is not None:
        parts['word/comments.xml'] = f'<w:comments {NAMESPACES}>{comments}</w:comments>'
        relations.append(('rComments', 'comments', 'comments.xml'))
        overrides.append(('/word/comments.xml', 'comments'))
    if comments_extended is not None:
        parts['word/commentsExtended.xml'] = f'<w15:commentsEx xmlns:w15="{W15}">{comments_extended}</w15:commentsEx>'
        relations.append(('rCommentsEx', 'http://schemas.microsoft.com/office/2011/relationships/commentsExtended', 'commentsExtended.xml'))
        overrides.append(('/word/commentsExtended.xml', 'commentsExtended'))
    if footnotes is not None:
        separators = ('<w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>'
                      '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>')
        parts['word/footnotes.xml'] = f'<w:footnotes {NAMESPACES}>{separators}{footnotes}</w:footnotes>'
        relations.append(('rFootnotes', 'footnotes', 'footnotes.xml'))
        overrides.append(('/word/footnotes.xml', 'footnotes'))
    relations.extend(relations_extra)
    parts.update(extra_parts or {})
    parts['word/document.xml'] = f'<w:document {NAMESPACES}><w:body>{body}{SECTION.format(refs=refs)}</w:body></w:document>'
    parts['word/styles.xml'] = styles if styles is not None else styles_part()
    parts['word/settings.xml'] = (f'<w:settings xmlns:w="{W}">{settings_extra}<w:compat><w:compatSetting w:name="compatibilityMode" '
                                  'w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat></w:settings>')
    parts['word/_rels/document.xml.rels'] = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                             + ''.join(f'<Relationship Id="{i}" Type="{k if "://" in k else R + "/" + k}" Target={quoteattr(target)}'
                                                       + ''.join(f' TargetMode="{m}"' for m in mode) + '/>' for i, k, target, *mode in relations)
                                             + '</Relationships>')
    parts['_rels/.rels'] = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                            f'<Relationship Id="rDocument" Type="{R}/officeDocument" Target="word/document.xml"/></Relationships>')
    parts['[Content_Types].xml'] = ('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                                    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                                    '<Default Extension="xml" ContentType="application/xml"/>' + content_types_extra
                                    + ''.join(f'<Override PartName="{n}" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.{k}+xml"/>' for n, k in overrides)
                                    + '</Types>')
    if strict:
        parts = {name: xml.replace(W, 'http://purl.oclc.org/ooxml/wordprocessingml/main')
                 .replace(R, 'http://purl.oclc.org/ooxml/officeDocument/relationships')
                 for name, xml in parts.items()}
    zip_write(path, parts)


# Comparisons LibreOffice 25.8.7.3 cannot make, established by running the authored redlines. A
# declared-ineligible comparison is not applied; the run fails as unmeasured if the calibration
# disagrees with this table in either direction.
LIBREOFFICE_INELIGIBLE = {
    **{'redline-revision-owner-' + name: (('accepted', 'rejected'),
       'LibreOffice 25.8.7.3 does not resolve the schema-valid authored insertion containing a deletion: accept retains and joins the proposal to the closing paragraph, and reject retains the proposal; raw insertion/deletion, people, schema and benchmark-markup round trips remain mandatory')
       for name in ('namesake-account', 'unattributed-name')},
    **{'redline-table-column-widths-' + shape: (('accepted', 'rejected'),
       'LibreOffice 25.8.7.3 exposes zero revisions in the schema-valid authored table-property-only width edit; independent resolved widths, registry count and schema checks remain mandatory')
       for shape in ('full', 'partial')},
    **{'redline-reviewer-bookmark-' + kind: (('accepted', 'rejected'),
       'LibreOffice exposes zero revisions for the authored bookmark-only removal/movement; semantic, reviewer and schema checks remain mandatory')
       for kind in ('move-and-remove', 'single-remove-control')},
    'redline-consolidated-note-prefix': (('rejected',),
        'LibreOffice leaves an empty first paragraph when rejecting the authored inserted paragraph; note contents and all other views calibrate'),
    'redline-removed-comment-body-edited': (('accepted',),
        'LibreOffice retains the removed comment after accepting its deletion markers'),
    'redline-removed-comment-body-unchanged-control': (('accepted', 'rejected'),
        'LibreOffice exposes zero revisions for comment-marker changes without a text edit'),
    **{'redline-comment-reply-' + kind: (('accepted', 'rejected'),
       'LibreOffice exposes zero revisions for an added reply whose markers are the only change, and keeps the reply on reject')
       for kind in ('id-less-root', 'renumbered-root', 'root-para-id-control')},
    **{'redline-comment-identity-' + kind:
       (('accepted', 'rejected') if kind == 'replaced-id' else ('rejected',),
        'LibreOffice retains comment definitions after their insertion/deletion markers are resolved; independent markup and schema checks remain required')
       for kind in ('reused-id', 'replaced-id', 'distinct-control', 'reviewer-collision', 'reviewer-identical', 'reviewer-control')},
    **{'redline-duplicate-comment-' + wrapper + suffix: (('accepted', 'rejected'),
       'LibreOffice retains both revision-scoped comments and an empty paragraph after resolving the replaced wrapper copies')
       for wrapper in ('sdt', 'customxml') for suffix in ('', '-control')},
    'redline-comment-add-customxml': (('accepted', 'rejected'), 'LibreOffice retains both revision-scoped comments and an empty paragraph after resolving the replaced paragraph/wrapper copies'),
    'redline-comment-remove-sdt': (('accepted', 'rejected'), 'LibreOffice retains both revision-scoped comments and an empty paragraph after resolving the replaced paragraph/wrapper copies'),
    'redline-reviewer-added-comment': (('rejected',), 'LibreOffice keeps the comment whose markers are in rejected insertion revisions'),
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

    def add(self, case_id, category, kind, issue, description, operation, inputs, expected, authored, assertions=(), assets=None):
        ineligible, reason = LIBREOFFICE_INELIGIBLE.get(case_id, ((), None))
        libreoffice = {key: key not in ineligible for key in expected}
        if reason:
            libreoffice['note'] = reason
        self.cases.append({
            'id': case_id, 'version': 1, 'category': category, 'kind': kind, 'issue': issue,
            'description': description, 'operation': operation, 'inputs': inputs, 'expected': expected,
            'authored': authored, 'assertions': list(assertions), 'libreoffice': libreoffice,
            'rights': {'author': 'John Scrudato IV', 'license': 'MIT', 'origin': 'Authored by bench/redline_fixtures.py in this repository',
                       'assets': assets or 'All text is generated here; no images or embedded font files'},
            'generator': self.generator})

    def compare(self, case_id, category, kind, issue, description, left, right, redline, assertions=(), assets=None):
        """A two-way case: accept-all of a correct redline equals right, reject-all equals left."""
        a = self.file(case_id, 'left', **left)
        b = self.file(case_id, 'right', **right)
        c = self.file(case_id, 'authored-redline', **redline)
        self.add(case_id, category, kind, issue, description, 'compare',
                 [dict(a, role='left'), dict(b, role='right')], {'accepted': b, 'rejected': a}, c, assertions, assets)


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
    inline_custom_xml(corpus)
    comment_views(corpus)
    duplicate_comments(corpus)
    consolidated_fields(corpus)
    comment_identities(corpus)
    removed_comments(corpus)
    inserted_notes(corpus)
    reviewer_bookmarks(corpus)
    bookmark_conflicts(corpus)
    reply_parents(corpus)
    semantic_limits(corpus)
    column_widths(corpus)
    pending_grid_columns(corpus)
    block_insertions(corpus)
    mixed_run_edits(corpus)
    tracked_column_gaps(corpus)
    revision_ownership(corpus)
    move_range_membership(corpus)
    external_links(corpus)
    package_shapes(corpus)
    registry = {'schema': 1, 'suite': dict(SUITE, cases=[c['id'] for c in corpus.cases]), 'cases': corpus.cases}
    target = ROOT / 'fixtures' / 'redline' / 'manifest.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(registry, indent=2) + '\n')
    return registry



def move_range_membership(corpus):
    """Ordinary runs inside named move ranges survive rejection, as native Word does."""
    def mark(tag, identifier, content='', name=None):
        attrs = f'w:id="{identifier}"' + (f' w:name="{name}"' if name else '')
        if tag in {'moveFrom', 'moveTo', 'moveFromRangeStart', 'moveToRangeStart'}:
            attrs += f' w:author="Alex" w:date="2026-05-01T09:00:00Z"'
        return f'<w:{tag} {attrs}>{content}</w:{tag}>' if content else f'<w:{tag} {attrs}/>'

    source = p(t('Old: ') + mark('moveFromRangeStart', 1, name='move1')
               + mark('moveFrom', 2, '<w:r><w:delText>amount</w:delText></w:r>')
               + mark('moveFromRangeEnd', 1) + t(' end'))
    for shape in ('unsplit-control', 'plain-tail-inside', 'plain-between-move-elements',
                  'split-destination', 'plain-outside-control', 'cross-paragraph-split'):
        start = mark('moveToRangeStart', 3, name='move1')
        end = mark('moveToRangeEnd', 3)
        if shape == 'unsplit-control':
            destination = p(t('Fee ') + start + mark('moveTo', 4, t('amount')) + end + t(' due'))
        elif shape == 'plain-tail-inside':
            destination = p(t('Fee ') + start + mark('moveTo', 4, t('amount')) + t('XY') + end + t(' due'))
        elif shape == 'plain-between-move-elements':
            destination = p(t('Fee ') + start + mark('moveTo', 4, t('amo')) + t('XY')
                            + mark('moveTo', 6, t('unt')) + end + t(' due'))
        elif shape == 'plain-outside-control':
            destination = p(t('Fee ') + start + mark('moveTo', 4, t('amount')) + end + t('XY due'))
        else:
            split = (mark('moveTo', 4, t('amo')) + end + t('XY')
                     + mark('moveToRangeStart', 5, name='move1') + mark('moveTo', 6, t('unt'))
                     + mark('moveToRangeEnd', 5) + t(' due'))
            destination = (p(t('Fee ') + start + split) if shape == 'split-destination'
                           else p(t('Fee ') + start) + p(split))
        case_id = 'redline-move-range-' + shape
        tracked = corpus.file(case_id, 'input', body=source + destination)
        # Authored explicitly from Word's observed endpoints, never from a candidate result.
        tails = (['Fee ', 'XY due'] if shape == 'cross-paragraph-split'
                 else ['Fee  due'] if shape == 'unsplit-control' else ['Fee XY due'])
        expected = corpus.file(case_id, 'expected', body=p(t('Old: amount end')) + ''.join(p(t(text)) for text in tails))
        corpus.add(case_id, 'revisions', 'control' if shape.endswith('control') else 'reproducer',
                   'JSv4/Docxodus#1340', 'Reject a named move: ' + shape.replace('-', ' '), 'reject',
                   [dict(tracked, role='input')], {'output': expected}, expected,
                   [{'type': 'revision-count', 'version': 1, 'scope': 'output', 'max': 0}])


def revision_ownership(corpus):
    actor = 'Taylor'
    account = 'S::taylor@summit.example::55555555-5555-5555-5555-555555555555'
    other = 'S::taylor@valley.example::66666666-6666-6666-6666-666666666666'
    identity = {'providerId': 'AD', 'userId': account}
    before, proposal, after = 'Summit opening.', 'Summit proposed clause.', 'Summit closing.'

    def people(author, user):
        return (f'<w15:person w15:author={quoteattr(author)}><w15:presenceInfo w15:providerId="AD" '
                f'w15:userId={quoteattr(user)}/></w15:person>') if user is not None else None

    def body(content=None, mark=''):
        return p(t(before)) + (p(content, mark=mark) if content is not None else '') + p(t(after))

    for suffix, author, user, own, configure in [
            ('namesake-account', actor, other, False, 'open'),
            ('unattributed-name', actor, None, False, 'operation'),
            ('upn-alias', 'Word Taylor', 'S::TAYLOR@SUMMIT.EXAMPLE::77777777-7777-7777-7777-777777777777', True, 'open'),
            ('object-id-alias', 'Word Taylor', 'S::old@summit.example::55555555-5555-5555-5555-555555555555', True, 'operation'),
            ('legacy-name-control', actor, other, True, 'open')]:
        case_id = 'redline-revision-owner-' + suffix
        rev = Revisions()
        source_doc = dict(body=body(rev.ins(t(proposal), author), rev.mark('ins', author)), people=people(author, user))
        source = corpus.file(case_id, 'source', **source_doc)
        red = Revisions()
        recorded = body() if own else body(red.ins(red.dele(t(proposal), actor), author), red.mark('ins', author) + red.mark('del', actor))
        authored = corpus.file(case_id, 'authored-redline', body=recorded, people=people(author, user))
        expected = corpus.file(case_id, 'resolved', body=body(), people=people(author, user))
        assertions = [untracked(before, after), paragraph_count(2 if own else 3),
                      {'type': 'people-identity', 'version': 1, 'scope': 'redline', 'author': author,
                       'identities': [] if user is None else [{'providerId': 'AD', 'userId': user}]}]
        if own:
            assertions.append({'type': 'revision-count', 'version': 1, 'scope': 'redline', 'max': 0})
        else:
            assertions.append({'type': 'pending-insertion-deletion', 'version': 1, 'scope': 'redline',
                               'author': author, 'deletedBy': actor, 'text': proposal})
        legacy = suffix == 'legacy-name-control'
        corpus.add(case_id, 'identity', 'control' if legacy else 'reproducer', 'JSv4/Docxodus#1317',
                   'Delete a pending paragraph: ' + suffix.replace('-', ' '), 'revision-ownership',
                   [dict(source, role='source')], {'accepted': expected, 'rejected': expected}, authored, assertions)
        corpus.cases[-1]['revisionOwnership'] = {'version': 1, 'author': actor, 'identities': None if legacy else [identity],
            'configure': configure, 'action': 'delete-block', 'paragraphIndex': 1, 'text': '', 'queryAuthor': None if legacy else author}
        if not legacy:
            corpus.cases[-1]['authorNameStatus'] = {'version': 1, 'before': 'own' if own else 'taken', 'after': 'own' if own else 'taken'}

    # A free name is registered only by the first attributed revision or comment. Expected
    # documents and markup are literal declarations, never copied from a candidate's output.
    comment_styles = styles_part(
        '<w:style w:type="paragraph" w:styleId="CommentText"><w:name w:val="annotation text"/><w:basedOn w:val="Normal"/></w:style>'
        '<w:style w:type="character" w:styleId="CommentReference"><w:name w:val="annotation reference"/></w:style>')
    for action, suffix in [('replace-text', 'first-revision'), ('add-comment', 'first-comment')]:
        case_id = 'redline-revision-owner-' + suffix
        plain = p(t(before)) + p(t(proposal)) + p(t(after))
        source = corpus.file(case_id, 'source', body=plain, styles=comment_styles)
        metadata = people(actor, account)
        if action == 'replace-text':
            rev = Revisions()
            recorded = p(rev.dele(t(before), actor) + rev.ins(t('Summit revised opening.'), actor)) + p(t(proposal)) + p(t(after))
            accepted_doc = dict(body=p(t('Summit revised opening.')) + p(t(proposal)) + p(t(after)))
            rejected_doc = dict(body=plain)
            authored_doc = dict(body=recorded)
            text = 'Summit revised opening.'
        else:
            text = 'Summit account note.'
            reference = '<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr><w:commentReference w:id="1"/></w:r>'
            marked = p(comment_marks('rangeStart', 1) + t(before) + comment_marks('rangeEnd', 1) + reference) + p(t(proposal)) + p(t(after))
            note = (f'<w:comment w:id="1" w:author="{actor}" w:date="{DATE}">'
                    + p('<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr><w:annotationRef/></w:r>' + t(text),
                        props='<w:pStyle w:val="CommentText"/>') + '</w:comment>')
            accepted_doc = rejected_doc = authored_doc = dict(body=marked, comments=note)
        accepted = corpus.file(case_id, 'accepted', **accepted_doc, styles=comment_styles, people=metadata)
        rejected = corpus.file(case_id, 'rejected', **rejected_doc, styles=comment_styles, people=metadata)
        authored = corpus.file(case_id, 'authored-redline', **authored_doc, styles=comment_styles, people=metadata)
        corpus.add(case_id, 'identity', 'reproducer', 'JSv4/Docxodus#1317',
                   'Register a free reviewer name on its ' + suffix.replace('-', ' '), 'revision-ownership',
                   [dict(source, role='source')], {'accepted': accepted, 'rejected': rejected}, authored,
                   [paragraph_count(3), {'type': 'people-identity', 'version': 1, 'scope': 'redline', 'author': actor, 'identities': [identity]}])
        corpus.cases[-1]['revisionOwnership'] = {'version': 1, 'author': actor, 'identities': [identity],
            'configure': 'operation' if action == 'add-comment' else 'open', 'action': action,
            'paragraphIndex': 0, 'text': text, 'queryAuthor': actor}
        corpus.cases[-1]['authorNameStatus'] = {'version': 1, 'before': 'free', 'after': 'own'}


def semantic_limits(corpus):
    body = p(t('Marsh station agreement.')) + p(t(' '.join(['Each survey crew records the water level.'] * 24))) + p(t(CLOSING))
    for strict, kind, suffix in [(True, 'reproducer', 'strict'), (False, 'control', 'transitional-control')]:
        case_id = 'redline-semantic-raw-limits-' + suffix
        left = corpus.file(case_id, 'left', body=body, strict=strict)
        right = corpus.file(case_id, 'right', body=body, strict=strict)
        expected = corpus.file(case_id, 'expected', body=body)
        authored = corpus.file(case_id, 'authored-redline', body=body)
        corpus.add(case_id, 'identity', kind, 'JSv4/Docxodus#1352',
                   'Identical ' + ('Strict' if strict else 'Transitional') + ' inputs remain comparable at their raw package limits',
                   'compare', [dict(left, role='left'), dict(right, role='right')],
                   {'accepted': expected, 'rejected': expected}, authored,
                   [untracked('Marsh station agreement.', CLOSING), paragraph_count(3)])
        corpus.cases[-1]['semanticPreflight'] = {'version': 1, 'limits': 'raw-boundaries', 'changeCount': 0}


def column_widths(corpus):
    original = [2400, 3200]

    def document(widths, tracked=False):
        revisions = Revisions()
        def properties(values):
            return f'<w:tblW w:w="{sum(values)}" w:type="dxa"/><w:tblLayout w:type="fixed"/>'
        def grid(values):
            return '<w:tblGrid>' + ''.join(f'<w:gridCol w:w="{v}"/>' for v in values) + '</w:tblGrid>'
        pr = properties(widths)
        if tracked and sum(widths) != sum(original):
            pr += f'<w:tblPrChange {revisions.attrs(AUTHOR)}><w:tblPr>{properties(original)}</w:tblPr></w:tblPrChange>'
        columns = grid(widths)
        if tracked:
            identifier = revisions.next
            revisions.next += 1
            columns = columns.replace('</w:tblGrid>', f'<w:tblGridChange w:id="{identifier}">{grid(original)}</w:tblGridChange></w:tblGrid>', 1)
        rows = ''
        for labels in [('North gauge', 'East gauge'), ('South gauge', 'West gauge')]:
            cells = ''
            for index, label in enumerate(labels):
                cell_pr = f'<w:tcW w:w="{widths[index]}" w:type="dxa"/>'
                if tracked and widths[index] != original[index]:
                    cell_pr += f'<w:tcPrChange {revisions.attrs(AUTHOR)}><w:tcPr><w:tcW w:w="{original[index]}" w:type="dxa"/></w:tcPr></w:tcPrChange>'
                cells += f'<w:tc><w:tcPr>{cell_pr}</w:tcPr>{p(t(label))}</w:tc>'
            rows += '<w:tr>' + cells + '</w:tr>'
        return {'body': p(t('Gauge register column widths.')) + f'<w:tbl><w:tblPr>{pr}</w:tblPr>{columns}{rows}</w:tbl>' + p(t(CLOSING))}

    def assertion(values, scope):
        return {'type': 'table-widths', 'version': 1, 'scope': scope, 'grid': values,
                'cells': [values, values], 'table': sum(values)}

    for suffix, values in [('full', [2600, 3000]), ('partial', [2400, 3000])]:
        for tracked, kind, tail in [(True, 'reproducer', ''), (False, 'control', '-untracked-control')]:
            case_id = 'redline-table-column-widths-' + suffix + tail
            source = corpus.file(case_id, 'source', **document(original))
            updated = corpus.file(case_id, 'updated', **document(values))
            authored = corpus.file(case_id, 'authored-redline', **document(values, tracked))
            corpus.add(case_id, 'tables', kind, 'JSv4/Docxodus#1322',
                       ('Tracked' if tracked else 'Untracked') + ' column widths change ' + ('both columns' if suffix == 'full' else 'only the second column'),
                       'table-widths', [dict(source, role='source')],
                       {'accepted': updated, 'rejected': source if tracked else updated}, authored,
                       [untracked('Gauge register column widths.', 'North gauge', 'East gauge', 'South gauge', 'West gauge', CLOSING),
                        assertion(values, 'accepted'), assertion(original if tracked else values, 'rejected')])
            corpus.cases[-1]['tableWidths'] = {'version': 1, 'widths': values, 'tracked': tracked}
            corpus.cases[-1]['revisionRegistry'] = {'version': 1, 'count': 1 if tracked else 0}


def tracked_column_gaps(corpus):
    def cell(text, width, span=1, fill=None):
        return {'text': text, 'span': span, 'width': width, 'type': 'dxa', 'fill': fill}
    def row(cells, before=0, after=0):
        return {'before': before, 'after': after, 'height': None, 'cells': cells}
    def document(grid, rows):
        body = '<w:tbl><w:tblPr/><w:tblGrid>' + ''.join(f'<w:gridCol w:w="{w}"/>' for w in grid) + '</w:tblGrid>'
        for r in rows:
            properties = ''.join(f'<w:{name} w:val="{r[key]}"/>' for name, key in [('gridBefore', 'before'), ('gridAfter', 'after')] if r[key])
            body += '<w:tr>' + (f'<w:trPr>{properties}</w:trPr>' if properties else '')
            for c in r['cells']:
                cp = f'<w:tcW w:w="{c["width"]}" w:type="dxa"/>'
                if c['span'] > 1: cp += f'<w:gridSpan w:val="{c["span"]}"/>'
                if c['fill'] is not None: cp += f'<w:shd w:val="clear" w:fill="{c["fill"]}"/>'
                body += '<w:tc><w:tcPr>' + cp + '</w:tcPr>' + p(t(c['text'])) + '</w:tc>'
            body += '</w:tr>'
        return p(t('Waterway inspection.')) + body + '</w:tbl>' + p(t('Inspection complete.'))
    for scenario, resolution in [('leading', 'reject-all'), ('trailing', 'accept-all'),
                                 ('merged-reject', 'reject-each'), ('merged-accept', 'accept-all')]:
        mixed = scenario.startswith('merged')
        if mixed:
            grid, expanded_grid = [2100, 1300, 2600], [2100, 2100, 1300, 2600]
            north, center, south = [cell(name, width) for name, width in [('North buoy', 2100), ('Central buoy', 1300), ('South buoy', 2600)]]
            rows = [row([north, center, south]), row([cell('Bridge reach', 6000, 3, 'D9EAD3')]),
                    row([south], before=2), row([north, center, south])]
            expanded = [row([north, cell('', 2100), center, south]), row([cell('Bridge reach', 8100, 4, 'D9EAD3')]),
                        row([south], before=3), row([north, cell('', 2100), center, south])]
            index, position = 0, 'after'
        else:
            a, b, c, d, e = [cell(name, width) for name, width in [('East marker', 2400), ('West marker', 1600),
                ('Center marker', 1600 if scenario == 'leading' else 2400), ('Upper marker', 2400), ('Lower marker', 1600)]]
            grid = [2400, 1600]
            if scenario == 'leading':
                rows = [row([a, b]), row([c], before=1), row([d, e])]
                expanded_grid = [2400, 2400, 1600]
                expanded = [row([cell('', 2400), a, b]), row([c], before=2), row([cell('', 2400), d, e])]
                index, position = 0, 'before'
            else:
                rows = [row([a, b]), row([c], after=1), row([d, e])]
                expanded_grid = [2400, 1600, 1600]
                expanded = [row([a, b, cell('', 1600)]), row([c], after=2), row([d, e, cell('', 1600)])]
                index, position = 1, 'after'
        for tracked, kind, suffix in [(True, 'reproducer', ''), (False, 'control', '-control')]:
            case_id = 'redline-column-gap-' + scenario + suffix
            source = corpus.file(case_id, 'source', body=document(grid, rows))
            accepted = not tracked or resolution == 'accept-all'
            resolved_grid, resolved_rows = (expanded_grid, expanded) if accepted else (grid, rows)
            expected = corpus.file(case_id, 'expected', body=document(resolved_grid, resolved_rows))
            authored = corpus.file(case_id, 'authored-output', body=document(resolved_grid, resolved_rows))
            state = {'grid': resolved_grid, 'rows': [dict(r, cells=[{k: v for k, v in c.items() if k != 'text'} for c in r['cells']]) for r in resolved_rows]}
            corpus.add(case_id, 'tables', kind, 'JSv4/Docxodus#1330',
                       f'{scenario} column insertion followed by {resolution}, ' + ('tracked' if tracked else 'direct control'),
                       'column-edit', [dict(source, role='source')], {'output': expected}, authored,
                       [{'type': 'table-state', 'version': 1, 'scope': 'output', 'state': state},
                        {'type': 'revision-count', 'version': 1, 'scope': 'output', 'max': 0}])
            corpus.cases[-1]['columnEdit'] = {'version': 2, 'tracked': tracked, 'action': 'insert',
                                             'cellIndex': index, 'position': position, 'resolution': resolution}
            corpus.cases[-1]['columnReview'] = {'version': 1, 'beforeCount': 1 if tracked else 0,
                                               'supported': True, 'resolutionSuccess': True}
            corpus.cases[-1]['revisionRegistry'] = {'version': 1, 'count': 0}


def mixed_run_edits(corpus):
    def document(content):
        return p(t('Marina register.')) + p(content) + p(t('Survey complete.'))
    for marker in ('tab', 'br'):
        mark = f'<w:r><w:{marker}/></w:r>'
        for tracked in (False, True):
            for cut in ('before', 'across'):
                for reproducer, kind, suffix in [(True, 'reproducer', ''), (False, 'control', '-control')]:
                    mode = 'tracked' if tracked else 'direct'
                    case_id = f'redline-mixed-run-{marker}-{mode}-{cut}{suffix}'
                    length = 1 if cut == 'before' else 2
                    replacement = ('' if tracked else 'o') if cut == 'before' else 'ur'
                    source_content = ('<w:r><w:t>ca</w:t>' + f'<w:{marker}/>' + '<w:t>ve</w:t></w:r>') if reproducer else t('cave') + mark
                    if reproducer:
                        accepted_content = t('c' + replacement) + mark + t('ve' if cut == 'before' else 'e')
                    else:
                        accepted_content = t('c' + replacement + ('ve' if cut == 'before' else 'e')) + mark
                    rev = Revisions()
                    if tracked:
                        if reproducer:
                            recorded = t('c') + rev.dele(t('a')) + (rev.ins(t(replacement)) if replacement else '') + mark
                            recorded += (t('ve') if cut == 'before' else rev.dele(t('v')) + t('e'))
                        else:
                            recorded = t('c') + rev.dele(t('a' if cut == 'before' else 'av'))
                            recorded += (rev.ins(t(replacement)) if replacement else '') + t('ve' if cut == 'before' else 'e') + mark
                    else:
                        recorded = accepted_content
                    source = corpus.file(case_id, 'source', body=document(source_content))
                    accepted = corpus.file(case_id, 'accepted', body=document(accepted_content))
                    rejected = corpus.file(case_id, 'rejected', body=document(source_content if tracked else accepted_content))
                    authored = corpus.file(case_id, 'authored-redline', body=document(recorded))
                    corpus.add(case_id, 'revisions', kind, 'JSv4/Docxodus#1337',
                        f'{mode} text edit {cut} a {marker}, ' + ('between two text nodes in one run' if reproducer else 'after the selected text'),
                        'replace-span', [dict(source, role='source')], {'accepted': accepted, 'rejected': rejected}, authored,
                        [{'type': 'paragraph-count', 'version': 1, 'scope': scope, 'story': 'body', 'count': 3} for scope in ('accepted', 'rejected')])
                    corpus.cases[-1]['spanEdit'] = {'version': 1, 'tracked': tracked, 'paragraphIndex': 1,
                        'start': 1, 'length': length, 'replacement': replacement}


def block_insertions(corpus):
    def table(text):
        return ('<w:tbl><w:tblPr/><w:tblGrid><w:gridCol w:w="2000"/></w:tblGrid><w:tr><w:tc>'
                '<w:tcPr><w:tcW w:w="2000" w:type="dxa"/><w:shd w:val="clear" w:fill="D9EAD3"/></w:tcPr>'
                + p(t(text)) + '</w:tc></w:tr></w:tbl>')
    opening, original, closing = p(t('Harbor opening.')), table('Harbor cell.'), p(t('Harbor closing.'))
    state = {'grid': [2000], 'rows': [{'before': 0, 'after': 0, 'height': None,
             'cells': [{'span': 1, 'width': 2000, 'type': 'dxa', 'fill': 'D9EAD3'}]}]}
    for operation in ('paragraph', 'rule', 'table'):
        for success, kind, suffix in [(False, 'reproducer', ''), (True, 'control', '-control')]:
            case_id = 'redline-block-insert-' + operation + suffix
            source = corpus.file(case_id, 'source', body=opening + original + closing)
            # The controls insert after the first body paragraph, before the existing table.
            extra = p(t('Harbor register note.')) if operation == 'paragraph' else p('') if operation == 'rule' else table('') + p('')
            body = opening + (extra if success else '') + original + closing
            expected = corpus.file(case_id, 'expected', body=body)
            authored = corpus.file(case_id, 'authored-output', body=body)
            assertions = [{'type': 'revision-count', 'version': 1, 'scope': 'output', 'max': 0},
                          {'type': 'paragraph-count', 'version': 1, 'scope': 'output', 'story': 'body', 'count': (5 if operation == 'table' else 4) if success else 3}]
            if not success:
                assertions.append({'type': 'table-state', 'version': 1, 'scope': 'output', 'state': state})
            corpus.add(case_id, 'tables', kind, 'JSv4/Docxodus#1331',
                       'Insert a ' + operation + ' beside ' + ('a valid body paragraph' if success else 'a cell anchor without block siblings'),
                       'block-insert', [dict(source, role='source')], {'output': expected}, authored, assertions)
            corpus.cases[-1]['blockInsert'] = {'version': 1, 'operation': operation,
                'anchorKind': 'p' if success else 'tc', 'position': 'after', 'markdown': 'Harbor register note.'}
            corpus.cases[-1]['editOutcome'] = {'success': success, 'errorCode': None if success else 'AnchorWrongKind',
                                             'versionDelta': 1 if success else 0, 'undoAvailable': success}


def pending_grid_columns(corpus):
    import copy

    def cell(text, width=2000, span=1, fill=None):
        return {'text': text, 'width': width, 'span': span, 'type': 'dxa', 'fill': fill}

    def row(cells, before=0, height=None):
        return {'before': before, 'after': 0, 'height': height, 'cells': cells}

    def document(grid, rows, previous_grid=None):
        rev = Revisions()
        def cell_properties(c):
            result = f'<w:tcW w:w="{c["width"]}" w:type="dxa"/>'
            if c['span'] > 1:
                result += f'<w:gridSpan w:val="{c["span"]}"/>'
            if c['fill'] is not None:
                result += f'<w:shd w:val="clear" w:fill="{c["fill"]}"/>'
            return result
        def row_properties(r):
            result = ''.join(f'<w:{name} w:val="{r[key]}"/>' for name, key in [('gridBefore', 'before'), ('gridAfter', 'after')] if r[key])
            return result + (f'<w:trHeight w:val="{r["height"]}"/>' if r['height'] is not None else '')
        def columns(values):
            return ''.join(f'<w:gridCol w:w="{v}"/>' for v in values)
        grid_xml = columns(grid)
        if previous_grid is not None:
            identifier = rev.next
            rev.next += 1
            grid_xml += f'<w:tblGridChange w:id="{identifier}"><w:tblGrid>{columns(previous_grid)}</w:tblGrid></w:tblGridChange>'
        row_xml = ''
        for r in rows:
            properties = row_properties(r)
            if 'previous' in r:
                properties += f'<w:trPrChange {rev.attrs("Prior Survey Reviewer")}><w:trPr>{row_properties(r["previous"])}</w:trPr></w:trPrChange>'
            cells = ''
            for c in r['cells']:
                cp = cell_properties(c)
                if 'previous' in c:
                    cp += f'<w:tcPrChange {rev.attrs("Prior Survey Reviewer")}><w:tcPr>{cell_properties(c["previous"])}</w:tcPr></w:tcPrChange>'
                cells += f'<w:tc><w:tcPr>{cp}</w:tcPr>{p(t(c["text"]))}</w:tc>'
            row_xml += '<w:tr>' + (f'<w:trPr>{properties}</w:trPr>' if properties else '') + cells + '</w:tr>'
        return {'body': p(t('Survey channel register.')) + f'<w:tbl><w:tblPr/><w:tblGrid>{grid_xml}</w:tblGrid>{row_xml}</w:tbl>' + p(t('Register closing remains.'))}

    for shape in ('plain', 'no-op', 'merged', 'omitted', 'merged-before', 'merged-after'):
        for action in (('insert',) if shape in {'merged-before', 'merged-after'} else ('insert', 'delete')):
            for pending, kind, suffix in [(True, 'reproducer', ''), (False, 'control', '-control')]:
                grid = [2000, 2000, 2000] if shape == 'omitted' else [2000, 2000]
                prior = grid if shape == 'no-op' else ([3000, 1000, 2000] if shape == 'omitted' else [3000, 1000])
                a, b, c, d, e = [cell(label) for label in ('Canal marker', 'Quay marker', 'Ridge marker', 'Jetty marker', 'Marsh marker')]
                rows = [row([a, b]), row([c, d])]
                index, position = 0, 'after'
                if shape.startswith('merged'):
                    merged = cell('Long reach marker', 4000, 2, 'D9EAD3')
                    if pending:
                        merged['previous'] = cell('Long reach marker', 4000, 2, 'FFF2CC')
                    rows = [row([merged]), row([a, b])]
                    index = 1 if shape == 'merged' else 0
                    position = 'before' if shape == 'merged-before' else 'after'
                elif shape == 'omitted':
                    rows = [row([a, b], 1, 480), row([c, d, e])]
                    if pending:
                        rows[0]['previous'] = row([], 1, 240)
                    index, position = 2, 'before'

                source = document(grid, copy.deepcopy(rows), prior if pending else None)
                expected_grid = prior if pending else grid
                if shape in {'plain', 'no-op'}:
                    if action == 'insert':
                        expected_grid = [expected_grid[0], expected_grid[0], expected_grid[1]]
                        expected_rows = [row([a, cell(''), b]), row([c, cell(''), d])]
                    else:
                        expected_grid = [expected_grid[1]]
                        expected_rows = [row([b]), row([d])]
                elif shape.startswith('merged'):
                    fill = 'FFF2CC' if pending else 'D9EAD3'
                    if action == 'insert':
                        if shape == 'merged-after':
                            previous_width = expected_grid[1]
                            expected_grid = [expected_grid[0], expected_grid[1], expected_grid[1]]
                            expected_rows = [row([cell('Long reach marker', 4000, 2, fill), cell('', previous_width, 1, fill)]), row([a, b, cell('')])]
                        elif shape == 'merged-before':
                            previous_width = expected_grid[0]
                            expected_grid = [expected_grid[0], expected_grid[0], expected_grid[1]]
                            expected_rows = [row([cell('', previous_width, 1, fill), cell('Long reach marker', 4000, 2, fill)]), row([cell(''), a, b])]
                        else:
                            expected_grid = [expected_grid[0], expected_grid[0], expected_grid[1]]
                            expected_rows = [row([cell('Long reach marker', 7000 if pending else 6000, 3, fill)]), row([a, cell(''), b])]
                    else:
                        expected_grid = [expected_grid[1]]
                        expected_rows = [row([cell('Long reach marker', 1000 if pending else 2000, 1, fill)]), row([b])]
                else:
                    height = 240 if pending else 480
                    if action == 'insert':
                        expected_grid = [expected_grid[0], expected_grid[0], expected_grid[1], expected_grid[2]]
                        expected_rows = [row([a, b], 2, height), row([cell(''), c, d, e])]
                    else:
                        expected_grid = expected_grid[1:]
                        expected_rows = [row([a, b], 0, height), row([d, e])]

                case_id = f'redline-pending-grid-{shape}-{action}{suffix}'
                input_record = corpus.file(case_id, 'source', **source)
                expected = corpus.file(case_id, 'expected', **document(expected_grid, expected_rows))
                authored = corpus.file(case_id, 'authored-output', **document(expected_grid, expected_rows))
                state = {'grid': expected_grid, 'rows': [dict(r, cells=[{k: value for k, value in item.items() if k != 'text'} for item in r['cells']]) for r in expected_rows]}
                corpus.add(case_id, 'tables', kind, 'JSv4/Docxodus#1342',
                           f'Untracked column {action}, {shape} rows, followed by resolving ' + ('pending formatting' if pending else 'a revision-free control'),
                           'column-edit', [dict(input_record, role='source')], {'output': expected}, authored,
                           [{'type': 'table-state', 'version': 1, 'scope': 'output', 'state': state},
                            {'type': 'revision-count', 'version': 1, 'scope': 'output', 'max': 0}])
                resolution = 'reject-each' if (action == 'delete') != (shape == 'merged') else 'reject-all'
                corpus.cases[-1]['columnEdit'] = {'version': 1, 'action': action, 'position': position,
                                                  'cellIndex': index, 'resolution': resolution}
                corpus.cases[-1]['revisionRegistry'] = {'version': 1, 'count': 0}


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
        corpus.compare(name, 'bookmarks', kind, 'JSv4/Docxodus#1218',
                       'Bookmarked paragraph whose ' + ('last word is replaced' if kind == 'reproducer' else 'text gains a word inside the bookmark'),
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

def inline_custom_xml(corpus):
    for wrapped in (True, False):
        name = 'redline-inline-customxml' if wrapped else 'redline-inline-hyperlink-control'
        def body(content):
            return (p(t('MapleBefore ') + custom_xml_link(content, wrapped) + t(' MapleAfter'))
                    + p(bookmark(True, 91, 'BirchTarget') + t('BirchTarget.') + bookmark(False, 91)))
        rev = Revisions()
        corpus.compare(name, 'revisions', 'reproducer' if wrapped else 'control', 'JSv4/Docxodus#1188',
                       'Edited inline custom XML inside a hyperlink' if wrapped else 'The same edit inside a plain hyperlink',
                       {'body': body(t('OakOpened'))}, {'body': body(t('OakClosed'))},
                       {'body': body(rev.dele(t('OakOpened')) + rev.ins(t('OakClosed')))},
                       [untracked('MapleBefore', 'MapleAfter', 'BirchTarget.')])



def comment_views(corpus):
    for case in comment_view_cases():
        name = 'redline-' + case['id']
        def file(role, document):
            return corpus.file(name, role, body=document['body'], comments=document['comments_xml'])
        inputs = [file(str(i), document) for i, document in enumerate(case['sources'])]
        expected = {view: file(view, document) for view, document in zip(('accepted', 'rejected'), case['expected'])}
        rev = Revisions()
        if case['operation'] == 'compare':
            before, after = case['wrappers']
            if case['control']:
                body = case['sources'][0]['body']
                # Replace only the literal inner word, retaining one wrapper and one comment.
                from .fixtures import run
                body = body.replace(run('Cedar inner clause'), t('Cedar ') + rev.dele(t('inner')) + rev.ins(t('revised')) + t(' clause'))
                notes = comment_view_note()
            else:
                body = p(t('Maple opening') + rev.dele(comment_view_mark('RangeStart', 11))
                         + rev.ins(comment_view_mark('RangeStart', 12)))
                for wrapper, kind, identifier in [(before, 'del', 11), (after, 'ins', 12)]:
                    mark = rev.dele if kind == 'del' else rev.ins
                    body += comment_view_wrapper(wrapper, p(mark(t('Cedar inner clause'))
                        + mark(comment_view_mark('RangeEnd', identifier)) + mark(comment_view_mark('Reference', identifier)),
                        mark=rev.mark(kind)))
                body += p(t('Birch closing'))
                notes = comment_view_note(11) + comment_view_note(12)
            roles = [dict(inputs[0], role='left'), dict(inputs[1], role='right')]
        else:
            opening = t('Maple clause')
            if not case['control']:
                opening = (rev.ins(comment_view_mark('RangeStart'), 'Reviewer1') + opening
                           + rev.ins(comment_view_mark('RangeEnd'), 'Reviewer1')
                           + rev.ins(comment_view_mark('Reference'), 'Reviewer1'))
            body = p(opening) + p(t('Birch closing') + rev.ins(t(' revised'), 'Reviewer2'))
            notes = None if case['control'] else comment_view_note()
            roles = [dict(inputs[0], role='base')] + [dict(item, role='reviewer', author=f'Reviewer{i}')
                                                     for i, item in enumerate(inputs[1:], 1)]
        authored = corpus.file(name, 'authored-redline', body=body, comments=notes)
        corpus.add(name, 'comments', 'control' if case['control'] else 'reproducer', f"JSv4/Docxodus#{case['issue']}",
                   'Exact comment anchors across a one-sided wrapper' if case['operation'] == 'compare' else
                   'A reviewer adds a comment to unchanged text while another edits a separate paragraph',
                   case['operation'], roles, expected, authored)


def removed_comments(corpus):
    for case in removed_comment_cases():
        rev = Revisions()
        content = (rev.dele(comment_view_mark('RangeStart', 0)) + p(t('Dune clause'))
                   + rev.dele(comment_view_mark('RangeEnd', 0))
                   + p(t('Reed tail') + (rev.ins(t(' revised')) if case['edited'] else '')
                       + rev.dele(comment_view_mark('Reference', 0))))
        authored = dict(body=content, comments=comment_view_note(0, 'Check dune clause'))
        corpus.compare('redline-' + case['id'], 'comments', 'control' if case['control'] else 'reproducer',
                       'JSv4/Docxodus#1211', case['description'],
                       *[dict(body=s['body'], comments=s['comments_xml']) for s in case['sources']], authored)


def duplicate_comments(corpus):
    for case in duplicate_comment_cases():
        name = 'redline-' + case['id']
        def file(role, document):
            return corpus.file(name, role, body=document['body'], comments=document['comments_xml'])
        inputs = [dict(file(role, document), role=role)
                  for role, document in zip(('left', 'right'), case['sources'])]
        expected = {view: file(view, document) for view, document in zip(('accepted', 'rejected'), case['expected'])}
        rev = Revisions()
        body = p(t('Maple opening'))
        for tag, kind, identifier in [('Maple', 'del', 11), ('Birch', 'ins', 12)]:
            mark = rev.dele if kind == 'del' else rev.ins
            content = (mark(comment_view_mark('RangeStart', identifier)) + mark(t('Cedar clause' if tag == 'Maple' else 'Cedar revised clause'))
                       + mark(comment_view_mark('RangeEnd', identifier)) + mark(comment_view_mark('Reference', identifier)))
            body += comment_view_wrapper(case['wrapper'], p(content, mark=rev.mark(kind)), tag)
        body += p(t('Birch closing'))
        authored = corpus.file(name, 'authored-redline', body=body,
                               comments=comment_view_note(11) + comment_view_note(12))
        corpus.add(name, 'comments', 'control' if case['control'] else 'reproducer', 'JSv4/Docxodus#1197',
                   'One comment per resolved wrapper despite duplicate references in the source' if not case['control'] else
                   'The same wrapper replacement with one valid comment reference', 'compare', inputs, expected, authored)


def consolidated_fields(corpus):
    for case in consolidated_field_cases():
        name = 'redline-' + case['id']
        inputs = [dict(corpus.file(name, str(i), **document), role='base' if i == 0 else 'reviewer',
                       **({'author': f'Reviewer{i}'} if i else {}))
                  for i, document in enumerate(case['sources'])]
        expected = {view: corpus.file(name, view, **document)
                    for view, document in zip(('accepted', 'rejected'), case['expected'])}
        rev = Revisions()
        prefix = t('Alder ') + (rev.dele(t('birch '), 'Reviewer1') if case['kind'] == 'prefix-delete' else t('birch '))
        result = t('1') if case['kind'] == 'prefix-delete' else rev.dele(t('1'), 'Reviewer1') + rev.ins(t('7'), 'Reviewer1')
        content = result if case['control'] else field(' PAGE ', result)
        if case['kind'] == 'bookmark-added':
            content = rev.ins(bookmark(True, 5, 'CedarRange'), 'Reviewer1') + content + rev.ins(bookmark(False, 5), 'Reviewer1')
        authored = corpus.file(name, 'authored-redline', body=p(prefix + content + t(' tail') + rev.ins(t(' more'), 'Reviewer2')))
        corpus.add(name, 'fields', 'control' if case['control'] else 'reproducer', 'JSv4/Docxodus#1206',
                   case['description'] + ': ' + case['kind'], 'consolidate', inputs, expected, authored,
                   [untracked('Alder', 'tail')])


def comment_identities(corpus):
    for case in comment_identity_cases():
        name = 'redline-' + case['id']
        def file(role, document):
            return corpus.file(name, role, body=document['body'], comments=document['comments_xml'])
        inputs = [file(str(i), document) for i, document in enumerate(case['sources'])]
        expected = {view: file(view, document) for view, document in zip(('accepted', 'rejected'), case['expected'])}
        rev = Revisions()
        def annotated(content, identifier, mark=lambda value: value):
            return mark(comment_view_mark('RangeStart', identifier)) + content + mark(comment_view_mark('RangeEnd', identifier)) + mark(comment_view_mark('Reference', identifier))
        if case['operation'] == 'compare':
            opening = annotated(t('AlderFirst'), 2, rev.ins)
            previous = annotated(t('BirchSecond'), 0)
            if case['kind'] == 'replaced-id':
                previous = annotated(t('BirchSecond'), 0, rev.dele)
            body = p(opening + t(' ') + previous + t(' tail') + rev.ins(t(' revised')))
            notes = comment_view_note(0, 'Old cedar note') + comment_view_note(2, 'New willow note')
            roles = [dict(item, role=role) for item, role in zip(inputs, ('left', 'right'))]
        else:
            body, notes = '', ''
            for identifier, word in enumerate(('Alder', 'Birch')):
                author = f'Reviewer{identifier + 1}'
                body += p(annotated(t(word) + rev.ins(t(' revised'), author), identifier,
                                    lambda value: rev.ins(value, author)))
                notes += comment_view_note(identifier, 'Check clause' if case['kind'] == 'reviewer-identical' else 'Check ' + word.lower())
            roles = [dict(inputs[0], role='base')] + [dict(item, role='reviewer', author=f'Reviewer{i}')
                                                     for i, item in enumerate(inputs[1:], 1)]
        authored = corpus.file(name, 'authored-redline', body=body, comments=notes)
        corpus.add(name, 'comments', 'control' if case['control'] else 'reproducer', 'JSv4/Docxodus#1210',
                   case['description'] + ': ' + case['kind'], case['operation'], roles, expected, authored)


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


def inserted_notes(corpus):
    for case in note_insertion_cases():
        name = 'redline-' + case['id']
        def file(role, document):
            notes = ''.join(f'<w:footnote w:id="{i}">{xml}</w:footnote>' for i, xml in document['footnote_list'])
            return corpus.file(name, role, body=document['body'], footnotes=notes)
        inputs = [dict(file(str(i), document), role='base' if i == 0 else 'reviewer',
                       **({'author': f'Reviewer{i}'} if i else {})) for i, document in enumerate(case['sources'])]
        expected = {view: file(view, document) for view, document in zip(('accepted', 'rejected'), case['expected'])}
        rev = Revisions()
        # Author sequential ids in redline body order, independently of the candidate.
        first, second, added = (2, 3, 1) if case['before'] else (1, 2, 3)
        def ref(i):
            return f'<w:r><w:footnoteReference w:id="{i}"/></w:r>'
        body = p(t('Cedar lead')) + p(t('Dune citation') + rev.ins(t(' revised'), 'Reviewer2') + ref(first))
        body += p(t('Reed citation') + ref(second)) + p(t('Willow tail'))
        inserted = p(rev.ins(t('Birch inserted clause') + ref(added), 'Reviewer1'), mark=rev.mark('ins', 'Reviewer1'))
        body = inserted + body if case['before'] else body + inserted
        notes = []
        for identifier, text in ((first, 'Cobalt reference'), (second, 'Amber reference'), (added, 'Birch added reference')):
            content = '<w:r><w:footnoteRef/></w:r>' + t(' ' + text)
            content = p(rev.ins(content, 'Reviewer1'), mark=rev.mark('ins', 'Reviewer1')) if identifier == added else p(content)
            notes.append((identifier, f'<w:footnote w:id="{identifier}">{content}</w:footnote>'))
        authored = corpus.file(name, 'authored-redline', body=body, footnotes=''.join(xml for _, xml in sorted(notes)))
        corpus.add(name, 'consolidate', 'control' if case['control'] else 'reproducer', 'JSv4/Docxodus#1212',
                   case['description'], 'consolidate', inputs, expected, authored)


def reviewer_bookmarks(corpus):
    for case in bookmark_reviewer_cases():
        name = 'redline-' + case['id']
        inputs = [dict(corpus.file(name, str(i), **document), role='base' if i == 0 else 'reviewer',
                       **({'author': f'Reviewer{i}'} if i else {})) for i, document in enumerate(case['sources'])]
        expected = {view: corpus.file(name, view, **document)
                    for view, document in zip(('accepted', 'rejected'), case['expected'])}
        rev = Revisions()
        if 'container' in case:
            content = (rev.ins(bookmark(True, 7, 'CedarRange'), 'Reviewer1') if case['edited'] else bookmark(True, 7, 'CedarRange')) + t('Cedar ')
            content += rev.dele(t('grove'), 'Reviewer2') + rev.ins(t('meadow'), 'Reviewer2') if case['edited'] else t('grove')
            content += rev.ins(bookmark(False, 7), 'Reviewer1') if case['edited'] else bookmark(False, 7)
            body = bookmark_review_container(case['container'], p(content))
            body += p(t('Willow tail') + (rev.ins(t(' revised'), 'Reviewer2') if not case['edited'] else ''))
        else:
            def removed(marker):
                return rev.dele(rev.dele(marker, 'Reviewer2') if case['moved'] else marker, 'Reviewer1')
            body = removed(bookmark(True, 7, 'CedarRange')) + p(t('Cedar clause')) + removed(bookmark(False, 7))
            body += (rev.ins(bookmark(True, 9, 'CedarRange'), 'Reviewer2') if case['moved'] else '') + p(t('Dune clause'))
            body += (rev.ins(bookmark(False, 9), 'Reviewer2') if case['moved'] else '') + p(t('Willow tail'))
        authored = corpus.file(name, 'authored-redline', body=body)
        corpus.add(name, 'consolidate', 'control' if case['control'] else 'reproducer', 'JSv4/Docxodus#1212',
                   case['description'], 'consolidate', inputs, expected, authored)


def bookmark_conflicts(corpus):
    for case in bookmark_conflict_cases():
        name = 'redline-' + case['id']
        inputs = [dict(corpus.file(name, str(i), **document), role='base' if i == 0 else 'reviewer',
                       **({'author': f'Reviewer{i}'} if i else {})) for i, document in enumerate(case['sources'])]
        expected = {view: corpus.file(name, view, **document)
                    for view, document in zip(('accepted', 'rejected'), case['expected'])}
        rev = Revisions()
        body = (rev.ins(bookmark(True, 7, 'SharedRange'), 'Reviewer1') if case['control'] else '') + p(t('Cedar clause'))
        body += rev.ins(bookmark(False, 7), 'Reviewer1') if case['control'] else ''
        body += p(t('Dune clause')) + p(t('Reed tail') + rev.ins(t(' revised'), 'Reviewer2'))
        authored = corpus.file(name, 'authored-redline', body=body)
        corpus.add(name, 'consolidate', 'control' if case['control'] else 'reproducer', 'JSv4/Docxodus#1212',
                   case['description'], 'consolidate', inputs, expected, authored)
        # BaseWins removes both contested ranges. Consensus is credited to the first reviewer.
        corpus.cases[-1]['reviewerExpected'] = {
            'Reviewer1': corpus.file(name, 'reviewer1', **(case['sources'][1] if case['control'] else case['sources'][0])),
            'Reviewer2': corpus.file(name, 'reviewer2', body=p(t('Cedar clause')) + p(t('Dune clause')) + p(t('Reed tail revised'))),
        }


if __name__ == '__main__':
    print(f'Authored {len(generate()["cases"])} deterministic redline cases')


# ---------------------------------------------------------------------------------------------
# Docxodus #1312: a reply the revision adds to a comment the original numbers differently or not at all
# ---------------------------------------------------------------------------------------------

def reply_parents(corpus):
    root_text, reply_text = 'Check the delivery date.', 'Friday is confirmed.'
    def thread_entry(para_id, parent=None):
        return f'<w15:commentEx w15:paraId="{para_id}"' + (f' w15:paraIdParent="{parent}"' if parent else '') + ' w15:done="0"/>'
    def body(replied, rev=None):
        mark = rev.ins if rev else (lambda content: content)
        start = comment_marks('rangeStart', 1) + (mark(comment_marks('rangeStart', 2)) if replied else '')
        end = (comment_marks('rangeEnd', 1) + comment_marks('reference', 1)
               + (mark(comment_marks('rangeEnd', 2)) + mark(comment_marks('reference', 2)) if replied else ''))
        return p(t('Register opening paragraph.')) + p(start + t('The seller delivers the goods.') + end) + p(t(CLOSING))
    def document(root_id, reply_id=None, rev=None):
        notes = comment(1, root_text, para_id=root_id) + (comment(2, reply_text, para_id=reply_id) if reply_id else '')
        threads = None if root_id is None else thread_entry(root_id) + (thread_entry(reply_id, root_id) if reply_id else '')
        return {'body': body(reply_id is not None, rev), 'comments': notes, 'comments_extended': threads}
    for name, kind, original_id, revised_ids, redline_ids, description in [
            ('redline-comment-reply-id-less-root', 'reproducer', None, ('00000001', '00000002'), ('00000001', '00000002'),
             'the original root comment has no paragraph id and no commentsExtended part'),
            ('redline-comment-reply-renumbered-root', 'reproducer', '0000000A', ('0000000B', '0000000C'), ('0000000A', '0000000C'),
             'the revision numbers the root comment\'s paragraph id differently from the original'),
            ('redline-comment-reply-root-para-id-control', 'control', '00000001', ('00000001', '00000002'), ('00000001', '00000002'),
             'both documents give the root comment the same paragraph id')]:
        corpus.compare(name, 'comments', kind, 'JSv4/Docxodus#1312',
                       'The revision adds a threaded reply to an unchanged comment; ' + description,
                       document(original_id), document(*revised_ids), document(*redline_ids, rev=Revisions()),
                       [untracked('Register opening paragraph.', 'The seller delivers the goods.', CLOSING),
                        {'type': 'comment-threads', 'version': 1, 'scope': 'redline', 'threads': [[reply_text, root_text]]},
                        {'type': 'para-ids-valid', 'version': 1, 'scope': 'redline'}])



# ---------------------------------------------------------------------------------------------
# Package shapes: external targets System.Uri rejects (#1388) and parts the SDK refuses (#1384)
# ---------------------------------------------------------------------------------------------

INTRO = 'Intro: the notice terms below apply to every order.'
ADDED = 'Added paragraph: the revised draft keeps this new line.'


def link(rid, content):
    return f'<w:hyperlink r:id="{rid}" w:history="1">{content}</w:hyperlink>'


def link_paragraph(rid, rev=None):
    if rev is None:
        return p(t('Send notices to ') + link(rid, t('the notice desk')) + t('.'))
    return p(rev.ins(t('Send notices to ')) + link(rid, rev.ins(t('the notice desk'))) + rev.ins(t('.')), mark=rev.mark('ins'))


def hyperlink_targets(*targets):
    return {'type': 'hyperlink-targets', 'version': 1, 'scope': 'redline', 'targets': list(targets)}


def external_links(corpus):
    """A mailto target naming several recipients, which System.Uri cannot parse, on one or both sides."""
    for recipients, target in (('recipients', 'mailto:first@example.com;second@example.com'),
                               ('single', 'mailto:solo@example.com')):
        control = recipients == 'single'
        relation = [('rLink', 'hyperlink', target, 'External')]
        for inserted in (False, True):
            case_id = 'redline-hyperlink-mailto-' + recipients + ('-inserted' if inserted else '') + ('-control' if control else '')
            rev = Revisions()
            if inserted:
                left = dict(body=p(t(INTRO)) + p(t(CLOSING)))
                right = dict(body=p(t(INTRO)) + link_paragraph('rLink') + p(t(CLOSING)), relations_extra=relation)
                redline = dict(body=p(t(INTRO)) + link_paragraph('rLink', rev) + p(t(CLOSING)), relations_extra=relation)
                texts = (INTRO, CLOSING)
                change = 'a paragraph holding the link is inserted'
            else:
                shared = p(t(INTRO)) + link_paragraph('rLink')
                left = dict(body=shared + p(t(CLOSING)), relations_extra=relation)
                right = dict(body=shared + p(t(ADDED)) + p(t(CLOSING)), relations_extra=relation)
                redline = dict(body=shared + p(rev.ins(t(ADDED)), mark=rev.mark('ins')) + p(t(CLOSING)), relations_extra=relation)
                texts = (INTRO, 'Send notices to ', CLOSING)
                change = 'an unrelated paragraph is added beside the link'
            description = (('An external hyperlink to ' + ('one mailto recipient' if control else 'a mailto target naming two recipients, which System.Uri rejects'))
                           + '; ' + change + '. The redline keeps the target exactly as written.')
            corpus.compare(case_id, 'packages', 'control' if control else 'reproducer', 'JSv4/Docxodus#1388', description,
                           left, right, redline, [untracked(*texts), hyperlink_targets(target)])


def package_shapes(corpus):
    """Packages the Open XML SDK refuses at open; one unrelated paragraph is added."""
    descriptions = {
        'typed-parts-control': 'An embedded-font part typed by a ttf Default, a glossary document with its own Override and a hyperlink under its own relationship id',
        'untyped-font': 'The font table embeds a part that no Default or Override gives a content type',
        'generic-glossary': 'The glossary document is typed only by the generic application/xml Default',
        'shared-relationship-id': "An external hyperlink relationship reuses the settings relationship's id",
    }
    repaired = package_shape('typed-parts-control')
    for shape in PACKAGE_SHAPES:
        extras = package_shape(shape)
        def document(body, form=extras):
            return dict(body=body, relations_extra=form['relations'], content_types_extra=form['content_types'], extra_parts=form['parts'])
        shared = p(t(INTRO)) + link_paragraph(extras['link'])
        rev = Revisions()
        # The authored redline writes the repaired (control) package form; the expected documents are the inputs.
        redline = document(p(t(INTRO)) + link_paragraph(repaired['link']) + p(rev.ins(t(ADDED)), mark=rev.mark('ins')) + p(t(CLOSING)), repaired)
        control = shape == 'typed-parts-control'
        corpus.compare('redline-package-' + shape, 'packages', 'control' if control else 'reproducer', 'JSv4/Docxodus#1384',
                       descriptions[shape] + '; an unrelated paragraph is added.',
                       document(shared + p(t(CLOSING))), document(shared + p(t(ADDED)) + p(t(CLOSING))), redline,
                       [untracked(INTRO, 'Send notices to ', CLOSING), hyperlink_targets(PACKAGE_LINK_TARGET)],
                       assets=('All text is generated here; no images. word/fonts/ExampleSans-regular.ttf holds the '
                               'placeholder bytes declared in bench/common.py, which are not a font program'))
