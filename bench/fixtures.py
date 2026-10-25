"""Author the entire corpus from literal text and original OOXML.

No input documents, templates, images or generation helpers are imported.
"""
from __future__ import annotations

import hashlib
import re
import json
import struct
import zlib
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
FONT = 'Liberation Serif'


def png(width, height, rgb, alpha=False):
    def chunk(kind, value):
        return struct.pack('>I', len(value)) + kind + value + struct.pack('>I', zlib.crc32(kind + value) & 0xffffffff)
    rows = b''.join(b'\0' + b''.join(bytes(rgb(x, y)) for x in range(width)) for y in range(height))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6 if alpha else 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(rows, 9)) + chunk(b'IEND', b'')


def run(text, props=''):
    return f'<w:r><w:rPr>{props}</w:rPr><w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def para(text='', props='', runs=None):
    return f'<w:p><w:pPr>{props}</w:pPr>{run(text) if runs is None else runs}</w:p>'


def custom_xml_link(content, wrapped):
    """Original inline carrier shared by the PDF and redline comparison cases."""
    if wrapped:
        content = ('<w:customXml w:element="entry"><w:customXmlPr>'
                   '<w:attr w:name="key" w:val="cedar"/></w:customXmlPr>' + content + '</w:customXml>')
    return '<w:hyperlink w:anchor="BirchTarget">' + content + '</w:hyperlink>'



def comment_view_note(identifier=11, text='Review the cedar clause.'):
    return (f'<w:comment w:id="{identifier}" w:author="Cedar" w:initials="C" w:date="2026-01-01T00:00:00Z">'
            + para(text) + '</w:comment>')


def comment_view_mark(kind, identifier=11):
    marker = f'<w:comment{kind} w:id="{identifier}"/>'
    return '<w:r>' + marker + '</w:r>' if kind == 'Reference' else marker


def comment_view_wrapper(kind, content, tag='cedar'):
    if kind == 'sdt':
        return f'<w:sdt><w:sdtPr><w:tag w:val="{tag}"/><w:id w:val="4100"/></w:sdtPr><w:sdtContent>' + content + '</w:sdtContent></w:sdt>'
    if kind == 'customxml':
        return f'<w:customXml w:element="{tag}">' + content + '</w:customXml>'
    return content


def comment_view_cases():
    """Literal source/expected documents shared by PDF and independent redline fixtures."""
    cases = []
    for name, before, after in [('comment-add-customxml', '', 'customxml'),
                               ('comment-remove-sdt', 'sdt', ''),
                               ('comment-wrapper-control', 'sdt', 'sdt')]:
        documents = []
        for revised, wrapper in [(False, before), (True, after)]:
            word = 'revised' if revised and before == after else 'inner'
            body = (para(runs=run('Maple opening') + comment_view_mark('RangeStart'))
                    + comment_view_wrapper(wrapper, para(runs=run(f'Cedar {word} clause')
                        + comment_view_mark('RangeEnd') + comment_view_mark('Reference')))
                    + para('Birch closing'))
            documents.append({'body': body, 'comments_xml': comment_view_note()})
        cases.append({'id': name, 'operation': 'compare', 'issue': 1195, 'control': before == after,
                      'sources': documents, 'expected': [documents[1], documents[0]], 'wrappers': (before, after)})
    for added in (True, False):
        def document(commented, revised):
            opening = run('Maple clause')
            if commented:
                opening = comment_view_mark('RangeStart') + opening + comment_view_mark('RangeEnd') + comment_view_mark('Reference')
            return {'body': para(runs=opening) + para('Birch closing' + (' revised' if revised else '')),
                    'comments_xml': comment_view_note() if commented else None}
        sources = [document(False, False), document(added, False), document(False, True)]
        cases.append({'id': 'reviewer-added-comment' if added else 'reviewer-comment-control',
                      'operation': 'consolidate', 'issue': 1196, 'control': not added,
                      'sources': sources, 'expected': [document(added, True), sources[0]]})
    return cases


def duplicate_comment_cases():
    """Invalid duplicate references must not manufacture a second comment in either view."""
    cases = []
    for wrapper in ('sdt', 'customxml'):
        for duplicate in (True, False):
            def document(tag, extra):
                content = (comment_view_mark('RangeStart') + run('Cedar clause' if tag == 'Maple' else 'Cedar revised clause')
                           + comment_view_mark('RangeEnd') + comment_view_mark('Reference') * (2 if extra else 1))
                return {'body': para('Maple opening') + comment_view_wrapper(wrapper, para(runs=content), tag)
                        + para('Birch closing'), 'comments_xml': comment_view_note()}
            cases.append({'id': 'duplicate-comment-' + wrapper + ('' if duplicate else '-control'),
                          'operation': 'compare', 'issue': 1197, 'control': not duplicate, 'wrapper': wrapper,
                          'sources': [document('Maple', duplicate), document('Birch', duplicate)],
                          'expected': [document('Birch', False), document('Maple', False)]})
    return cases


def removed_comment_cases(stories=('body',)):
    """A removed comment's reference is in an edited or unchanged paragraph."""
    cases = []
    for story in stories:
        for edited in (True, False):
            def document(revised):
                content = (('' if revised else comment_view_mark('RangeStart', 0)) + para('Dune clause')
                           + ('' if revised else comment_view_mark('RangeEnd', 0))
                           + para(runs=run('Reed tail revised' if revised and edited else 'Reed tail')
                                  + ('' if revised else comment_view_mark('Reference', 0))))
                doc = dict(body=content, comments_xml=None if revised else comment_view_note(0, 'Check dune clause'))
                if story != 'body':
                    doc.update(body=para('Willow body'), story=(story, content),
                               final_section=section().replace('<w:sectPr>', f'<w:sectPr><w:{story}Reference w:type="default" r:id="rStory"/>'))
                return doc
            sources = [document(False), document(True)]
            cases.append(dict(id='removed-comment-' + story + ('-edited' if edited else '-unchanged-control'),
                              story=story, edited=edited, operation='compare', issue=1211, control=not edited,
                              description='Removed comment reference in a ' + story + ' paragraph',
                              sources=sources, expected=[sources[1], sources[0]]))
    return cases


def note_insertion_cases():
    """An inserted paragraph renumbers existing footnotes; a suffix is the control."""
    cases = []
    for before in (True, False):
        def document(inserted, edited):
            entries = [('Cedar lead', None), ('Dune citation' + (' revised' if edited else ''), 'Cobalt reference'),
                       ('Reed citation', 'Amber reference'), ('Willow tail', None)]
            if inserted:
                entries.insert(0 if before else len(entries), ('Birch inserted clause', 'Birch added reference'))
            body, notes = '', []
            for text, note in entries:
                content = run(text)
                if note:
                    identifier = len(notes) + 1
                    content += f'<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:footnoteReference w:id="{identifier}"/></w:r>'
                    notes.append((identifier, para(runs='<w:r><w:footnoteRef/></w:r>' + run(' ' + note))))
                body += para(runs=content)
            return dict(body=body, footnote_list=notes)
        sources = [document(False, False), document(True, False), document(False, True)]
        cases.append(dict(id='consolidated-note-' + ('prefix' if before else 'suffix-control'), before=before,
                          directory='note-views', category='notes', operation='consolidate', issue=1212,
                          control=not before, description='Inserted paragraph cites a footnote ' + ('before' if before else 'after') + ' existing notes',
                          sources=sources, expected=[document(True, True), sources[0]]))
    return cases


def bookmark_review_container(kind, content):
    if kind == 'sdt':
        return comment_view_wrapper('sdt', content)
    if kind == 'cell':
        return table([['<w:tc><w:tcPr/>' + content + '</w:tc>', cell('Birch register')]])
    return content


def bookmark_reviewer_cases():
    """Original paragraph, wrapper and cell cases plus independently selectable removals."""
    cases = []
    start = '<w:bookmarkStart w:id="7" w:name="CedarRange"/>'
    end = '<w:bookmarkEnd w:id="7"/>'
    for container in ('paragraph', 'sdt', 'cell'):
        for edited in (True, False):
            def document(marked, changed):
                word = 'meadow' if changed and edited else 'grove'
                content = (start if marked else '') + run('Cedar ' + word) + (end if marked else '')
                return dict(body=bookmark_review_container(container, para(runs=content))
                            + para('Willow tail' + (' revised' if changed and not edited else '')))
            sources = [document(not edited, False), document(True, False), document(not edited, True)]
            cases.append(dict(id='reviewer-bookmark-' + container + ('-edited' if edited else '-outside-control'),
                              container=container, edited=edited, directory='bookmark-reviewers', category='paragraphs',
                              operation='consolidate', issue=1212, control=not edited,
                              description='Reviewer bookmark with a text edit ' + ('inside ' if edited else 'outside ') + container,
                              sources=sources, expected=[document(True, True), sources[0]]))
    for moved in (True, False):
        def document(position):
            return dict(body=''.join((start if i == position else '') + para(text) + (end if i == position else '')
                                    for i, text in enumerate(('Cedar clause', 'Dune clause', 'Willow tail'))))
        sources = [document(0), document(-1), document(1 if moved else 0)]
        cases.append(dict(id='reviewer-bookmark-' + ('move-and-remove' if moved else 'single-remove-control'),
                          moved=moved, directory='bookmark-reviewers', category='paragraphs', operation='consolidate',
                          issue=1212, control=not moved, description='Independent reviewer decisions for a shared bookmark',
                          sources=sources, expected=[document(1 if moved else -1), sources[0]]))
    return cases


def bookmark_conflict_cases():
    """Competing names resolve against the base while an independent text edit survives."""
    cases = []
    start = '<w:bookmarkStart w:id="7" w:name="SharedRange"/>'
    end = '<w:bookmarkEnd w:id="7"/>'
    def document(position=-1, inline=False, extent=None, revised=False):
        body = ''
        for i, text in enumerate(('Cedar clause', 'Dune clause', 'Reed tail' + (' revised' if revised else ''))):
            content = run(text)
            if i == position and inline:
                length = len(text) if extent is None else extent
                content = start + run(text[:length]) + end + (run(text[length:]) if length < len(text) else '')
            body += (start if i == position and not inline else '') + para(runs=content)
            body += end if i == position and not inline else ''
        return dict(body=body)
    for kind in ('block-position', 'mixed-position', 'inline-extent', 'consensus-control'):
        control = kind == 'consensus-control'
        first_inline = kind == 'inline-extent'
        sources = [document(), document(0, first_inline),
                   document(0 if control or first_inline else 1, kind in ('mixed-position', 'inline-extent'),
                            5 if first_inline else None, revised=True)]
        cases.append(dict(id='bookmark-name-' + kind, directory='bookmark-name-conflicts', category='paragraphs',
                          operation='consolidate', issue=1212, control=control,
                          description='Same-name reviewer bookmarks with ' + kind.replace('-', ' '),
                          sources=sources, expected=[document(0 if control else -1, revised=True), sources[0]]))
    return cases


def complex_field(instruction, result_runs, begin=True, end=True):
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


def comment_identity_cases():
    """Package-local ids cannot identify different notes or independent reviewer additions."""
    def marked(text, identifier):
        content = run(text)
        return content if identifier is None else (comment_view_mark('RangeStart', identifier) + content
                + comment_view_mark('RangeEnd', identifier) + comment_view_mark('Reference', identifier))
    cases = []
    for kind in ('reused-id', 'replaced-id', 'distinct-control'):
        def document(revised):
            old = 1 if revised and kind != 'distinct-control' else 0
            new = 2 if kind == 'distinct-control' else 0
            keep = not revised or kind != 'replaced-id'
            return {'body': para(runs=marked('AlderFirst', new if revised else None) + run(' ')
                    + marked('BirchSecond', old if keep else None)
                    + run(' tail revised' if revised else ' tail')),
                    'comments_xml': (comment_view_note(old, 'Old cedar note') if keep else '')
                        + (comment_view_note(new, 'New willow note') if revised else '')}
        sources = [document(False), document(True)]
        cases.append({'id': 'comment-identity-' + kind, 'kind': kind, 'operation': 'compare',
                      'sources': sources, 'expected': [sources[1], sources[0]]})
    for kind in ('reviewer-collision', 'reviewer-identical', 'reviewer-control'):
        def document(first, second):
            body, notes = '', ''
            for index, (word, changed) in enumerate((('Alder', first), ('Birch', second))):
                identifier = index if kind == 'reviewer-control' or (first and second) else 0
                body += para(runs=marked(word + (' revised' if changed else ''), identifier if changed else None))
                if changed:
                    notes += comment_view_note(identifier, 'Check clause' if kind == 'reviewer-identical' else 'Check ' + word.lower())
            return {'body': body, 'comments_xml': notes or None}
        sources = [document(False, False), document(True, False), document(False, True)]
        cases.append({'id': 'comment-identity-' + kind, 'kind': kind, 'operation': 'consolidate',
                      'sources': sources, 'expected': [document(True, True), sources[0]]})
    return [dict(case, issue=1210, control=case['kind'].endswith('control'),
                 description='Comment definition identity across reused ids') for case in cases]


def consolidated_field_cases():
    """Independent field-envelope and ordinary-text consolidation documents."""
    cases = []
    for kind in ('result-edit', 'prefix-delete', 'bookmark-added', 'plain-control'):
        def document(reviewer, final=False):
            edited = reviewer == 1 or final
            prefix = 'Alder ' if edited and kind == 'prefix-delete' else 'Alder birch '
            result = '7' if edited and kind != 'prefix-delete' else '1'
            content = run(result) if kind == 'plain-control' else complex_field(' PAGE ', run(result))
            if edited and kind == 'bookmark-added':
                content = '<w:bookmarkStart w:id="5" w:name="CedarRange"/>' + content + '<w:bookmarkEnd w:id="5"/>'
            suffix = ' tail more' if reviewer == 2 or final else ' tail'
            return {'body': para(runs=run(prefix) + content + run(suffix))}
        sources = [document(i) for i in range(3)]
        cases.append({'id': 'consolidated-field-' + kind, 'kind': kind, 'operation': 'consolidate',
                      'issue': 1206, 'control': kind == 'plain-control', 'directory': 'field-views',
                      'description': 'Complex field boundaries across independent reviewer edits',
                      'sources': sources, 'expected': [document(0, True), sources[0]]})
    return cases


def bookmark_boundary_cases():
    """PDF views complement the redline track's bookmark-extent checks."""
    def document(text):
        return {'body': para(runs='<w:bookmarkStart w:id="5" w:name="AlderRange"/>' + run(text)
                             + '<w:bookmarkEnd w:id="5"/>') + para('Cedar closing ledger.')}
    return [dict(id='bookmark-boundary-' + kind, operation='compare', issue=1218,
                 control=kind == 'insertion-control', directory='bookmark-views',
                 description='Bookmark extent when editing its enclosed text',
                 sources=[document('Alder survey'), document(revised)],
                 expected=[document(revised), document('Alder survey')])
            for kind, revised in [('replacement', 'Alder study'), ('insertion-control', 'Alder ridge survey')]]


def section(cols=1, kind=None):
    mode = f'<w:type w:val="{kind}"/>' if kind else ''
    return f'<w:sectPr>{mode}<w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720"/><w:cols w:num="{cols}" w:space="480"/></w:sectPr>'


def cell(text, extra='', nested=''):
    return '<w:tc><w:tcPr>' + extra + '</w:tcPr>' + para(text) + nested + (para() if nested else '') + '</w:tc>'


def table(rows, props='', width=9360):
    borders = '<w:tblBorders>' + ''.join(f'<w:{side} w:val="single" w:sz="6" w:color="444444"/>' for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV')) + '</w:tblBorders>'
    return f'<w:tbl><w:tblPr><w:tblW w:w="{width}" w:type="dxa"/>{borders}{props}</w:tblPr><w:tblGrid><w:gridCol w:w="{width//2}"/><w:gridCol w:w="{width//2}"/></w:tblGrid>' + ''.join('<w:tr>' + ''.join(row) + '</w:tr>' for row in rows) + '</w:tbl>'


def drawing(wrap):
    polygon = '<wp:wrapPolygon edited="0"><wp:start x="10800" y="0"/><wp:lineTo x="21600" y="10800"/><wp:lineTo x="10800" y="21600"/><wp:lineTo x="0" y="10800"/><wp:lineTo x="10800" y="0"/></wp:wrapPolygon>'
    wrap_xml = '<wp:wrapSquare wrapText="bothSides"/>' if wrap == 'square' else '<wp:wrapTight wrapText="bothSides">' + polygon + '</wp:wrapTight>'
    return f'''<w:r><w:drawing><wp:anchor distT="0" distB="0" distL="91440" distR="91440" simplePos="0" relativeHeight="1" behindDoc="0" locked="0" layoutInCell="1" allowOverlap="1">
    <wp:simplePos x="0" y="0"/><wp:positionH relativeFrom="column"><wp:posOffset>0</wp:posOffset></wp:positionH><wp:positionV relativeFrom="paragraph"><wp:posOffset>0</wp:posOffset></wp:positionV>
    <wp:extent cx="1371600" cy="1371600"/><wp:effectExtent l="0" t="0" r="0" b="0"/>{wrap_xml}<wp:docPr id="1" name="Authored diamond" descr="Black diamond generated by this repository"/><wp:cNvGraphicFramePr/>
    <a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr><pic:cNvPr id="1" name="diamond.png"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="rImage"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="1371600" cy="1371600"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic>
    </wp:anchor></w:drawing></w:r>'''


def zip_write(path, parts):
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name, payload in sorted(parts.items()):
            item = ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            item.compress_type = ZIP_DEFLATED
            item.external_attr = 0o100644 << 16
            archive.writestr(item, payload.encode() if isinstance(payload, str) else payload)


# The settings every package carries; a case that needs one more setting prepends it (schema order).
SETTINGS_BODY = '<w:footnotePr><w:numFmt w:val="decimal"/></w:footnotePr><w:endnotePr><w:numFmt w:val="lowerRoman"/></w:endnotePr><w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat>'

def package(path, body, final_section=None, notes=None, image=False, namespaces_extra='', styles_xml=None, story=None, notes_xml=None, stories=None, extra_parts=None, footnote_list=None, numbering_xml=None, comments_xml=None, comments_extended_xml=None, comments_ids_xml=None, comments_extensible_xml=None, font=FONT):
    namespaces = f'xmlns:w="{W}" xmlns:r="{R}" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"'
    namespaces += namespaces_extra
    styles = f'''<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:eastAsia="{font}" w:cs="{font}"/><w:sz w:val="22"/><w:color w:val="000000"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/><w:widowControl/></w:pPr></w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style><w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:after="240"/></w:pPr><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style></w:styles>'''
    if styles_xml is not None:
        styles = styles_xml
    relations = [('rStyles', 'styles', 'styles.xml'), ('rSettings', 'settings', 'settings.xml')]
    overrides = [('document', 'document.main'), ('styles', 'styles'), ('settings', 'settings')]
    parts = {'word/document.xml': f'<w:document {namespaces}><w:body>{body}{final_section or section()}</w:body></w:document>', 'word/styles.xml': styles, 'word/settings.xml': f'<w:settings xmlns:w="{W}">{SETTINGS_BODY}</w:settings>'}
    for index, (kind, content) in enumerate(([story] if story else []) + (stories or [])):
        root = 'hdr' if kind == 'header' else 'ftr'
        parts[f'word/{kind}1.xml'] = f'<w:{root} xmlns:w="{W}">{content}</w:{root}>'
        relations.append(('rStory' if index == 0 else f'rStory{index}', kind, kind + '1.xml'))
        overrides.append((kind + '1', kind))
    if notes:
        kind, text = notes
        content = notes_xml if notes_xml is not None else para(runs=f"<w:r><w:{kind}Ref/></w:r>" + run(" " + text))
        parts[f'word/{kind}s.xml'] = f'<w:{kind}s xmlns:w="{W}"><w:{kind} w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:{kind}><w:{kind} w:type="continuationSeparator" w:id="0"><w:p><w:r><w:continuationSeparator/></w:r></w:p></w:{kind}><w:{kind} w:id="1">{content}</w:{kind}></w:{kind}s>'
        relations.append(('rNotes', kind + 's', kind + 's.xml'))
        overrides.append((kind + 's', kind + 's'))
    if comments_xml is not None:
        parts['word/comments.xml'] = f'<w:comments xmlns:w="{W}">{comments_xml}</w:comments>'
        relations.append(('rComments', 'comments', 'comments.xml'))
        overrides.append(('comments', 'comments'))
    if comments_extended_xml is not None:
        parts['word/commentsExtended.xml'] = comments_extended_xml
        relations.append(('rCommentTopology', 'http://schemas.microsoft.com/office/2011/relationships/commentsExtended', 'commentsExtended.xml'))
        overrides.append(('commentsExtended', 'commentsExtended'))
    for name, payload, relation in [
            ('commentsIds', comments_ids_xml, 'http://schemas.microsoft.com/office/2016/09/relationships/commentsIds'),
            ('commentsExtensible', comments_extensible_xml, 'http://schemas.microsoft.com/office/2018/08/relationships/commentsExtensible')]:
        if payload is not None:
            parts[f'word/{name}.xml'] = payload
            relations.append(('r' + name, relation, name + '.xml'))
            overrides.append((name, name))
    if numbering_xml is not None:
        parts['word/numbering.xml'] = numbering_xml
        relations.append(('rNumbering', 'numbering', 'numbering.xml'))
        overrides.append(('numbering', 'numbering'))
    if footnote_list:
        assert not notes, 'Use either one note or a list of footnotes'
        # Several numbered footnotes, each given as (id, literal note content).
        separators = '<w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote><w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>'
        parts['word/footnotes.xml'] = f'<w:footnotes xmlns:w="{W}">{separators}' + ''.join(f'<w:footnote w:id="{i}">{c}</w:footnote>' for i, c in footnote_list) + '</w:footnotes>'
        relations.append(('rNotes', 'footnotes', 'footnotes.xml'))
        overrides.append(('footnotes', 'footnotes'))
    if image:
        parts['word/media/diamond.png'] = png(160, 160, lambda x, y: (0, 0, 0, 255) if abs(x - 79.5) + abs(y - 79.5) < 75 else (255, 255, 255, 0), alpha=True)
        relations.append(('rImage', 'image', 'media/diamond.png'))
    parts['word/_rels/document.xml.rels'] = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + ''.join(f'<Relationship Id="{i}" Type="{kind if kind.startswith("http") else R + "/" + kind}" Target="{target}"/>' for i, kind, target in relations) + '</Relationships>'
    parts['_rels/.rels'] = f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rDocument" Type="{R}/officeDocument" Target="word/document.xml"/></Relationships>'
    parts['[Content_Types].xml'] = '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>' + ''.join(f'<Override PartName="/word/{name}.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.{kind}+xml"/>' for name, kind in overrides) + '</Types>'
    if extra_parts:
        parts.update(extra_parts)
    zip_write(path, parts)


def kept_note_parts(body, notes):
    pkg = 'http://schemas.openxmlformats.org/package/2006/relationships'
    content_types = ''.join(
        f'<Override PartName="/word/{part}.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.{kind}+xml"/>'
        for part, kind in [('document', 'document.main'), ('styles', 'styles'), ('footnotes', 'footnotes')])
    return {
        '[Content_Types].xml': f'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>{content_types}</Types>',
        '_rels/.rels': f'<Relationships xmlns="{pkg}"><Relationship Id="rId1" Type="{R}/officeDocument" Target="word/document.xml"/></Relationships>',
        'word/_rels/document.xml.rels': f'<Relationships xmlns="{pkg}"><Relationship Id="rId1" Type="{R}/styles" Target="styles.xml"/><Relationship Id="rId2" Type="{R}/footnotes" Target="footnotes.xml"/></Relationships>',
        'word/styles.xml': f'<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/><w:sz w:val="22"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:before="0" w:after="0" w:line="300" w:lineRule="exact"/></w:pPr></w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style></w:styles>',
        'word/footnotes.xml': f'<w:footnotes xmlns:w="{W}">{notes}</w:footnotes>',
        'word/document.xml': f'<w:document xmlns:w="{W}"><w:body>{body}<w:sectPr><w:pgSz w:w="8000" w:h="6400"/><w:pgMar w:top="200" w:right="200" w:bottom="200" w:left="200" w:header="0" w:footer="0" w:gutter="0"/></w:sectPr></w:body></w:document>',
    }


def kept_note_flow_cases():
    """Reproduce the original #1217 Word inputs, including omitted package defaults.

    These literal six-part packages deliberately carry no settings part. Their original
    run/paragraph spelling and implicit separators must survive deterministic regeneration.
    Page arrays are native Word observations, not renderer-derived expectations.
    """
    def paragraph(text, pitch=15, keep_next=False, keep_lines=False, note_id=None,
                  lines=1, definition=False, widow=None):
        props = ('<w:keepNext/>' if keep_next else '') + ('<w:keepLines/>' if keep_lines else '')
        if widow is not None:
            props += '<w:widowControl/>' if widow else '<w:widowControl w:val="0"/>'
        props += f'<w:spacing w:before="0" w:after="0" w:line="{pitch * 20}" w:lineRule="exact"/>'
        content = '<w:r><w:footnoteRef/></w:r>' if definition else ''
        content += '<w:r><w:br/></w:r>'.join(
            f'<w:r><w:t>{text}{i:02d}</w:t></w:r>' for i in range(1, lines + 1))
        if note_id is not None:
            content += f'<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:footnoteReference w:id="{note_id}"/></w:r>'
        return f'<w:p><w:pPr>{props}</w:pPr>{content}</w:p>'

    def note(note_id, pitch):
        return f'<w:footnote w:id="{note_id}">' + ''.join(
            paragraph(f'WillowNote{note_id:02d}Part{part:02d}', pitch=pitch, definition=part == 1)
            for part in range(1, 4)) + '</w:footnote>'


    # pitch, keepNext, variant, heading page, all 17 citation-line pages, three note pages, tail.
    heading_layouts = [
        (20, False, '', 1, [2] * 17, [2, 3, 3], 3),
        (20, True, '', 2, [3] * 17, [3, 4, 4], 4),
        (40, False, '', 1, [2] * 15 + [3, 3], [3, 3, 3], 3),
        (40, True, '', 2, [3] * 15 + [4, 4], [4, 4, 4], 4),
        (20, True, 'no-keep-lines', 1, [1] * 13 + [2] * 4, [2, 2, 2], 2),
        (20, True, 'separator-15pt', 2, [3] * 17, [3, 4, 4], 4),
        (20, True, 'separator-one-twip', 2, [3] * 17, [3, 4, 4], 4),
        (40, True, 'no-keep-lines', 1, [1] * 13 + [2] * 4, [2, 2, 2], 2),
        (40, True, 'separator-15pt', 2, [3] * 15 + [4, 4], [4, 4, 4], 4),
        (40, True, 'separator-one-twip', 2, [3] * 15 + [4, 4], [4, 4, 4], 4),
        (40, True, 'widow-off', 2, [3] * 16 + [4], [4, 4, 4], 4),
        (40, True, 'widow-on', 2, [3] * 15 + [4, 4], [4, 4, 4], 4),
    ]
    for pitch, kept, variant, heading_page, cite_pages, note_pages, tail_page in heading_layouts:
        body = ''.join(paragraph(f'WillowLead{i:02d}') for i in range(1, 7))
        body += paragraph('WillowHeading', keep_next=kept)
        body += paragraph('WillowCite', keep_lines=variant != 'no-keep-lines', note_id=1, lines=17,
                          widow=(variant == 'widow-on') if variant.startswith('widow-') else None)
        body += paragraph('WillowTail')
        notes = note(1, pitch)
        if variant.startswith('separator-'):
            line = 300 if variant == 'separator-15pt' else 1
            notes = ''.join(
                f'<w:footnote w:type="{kind}" w:id="{i}"><w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="{line}" w:lineRule="exact"/></w:pPr><w:r><w:{mark}/></w:r></w:p></w:footnote>'
                for kind, i, mark in [('separator', -1, 'separator'), ('continuationSeparator', 0, 'continuationSeparator')]) + notes
        pages = {f'WillowLead{i:02d}01': 1 for i in range(1, 7)}
        pages['WillowHeading01'] = heading_page
        pages.update({f'WillowCite{i:02d}': p for i, p in enumerate(cite_pages, 1)})
        pages['WillowTail01'] = tail_page
        pages.update({('1' if i == 1 else '') + f'WillowNote01Part{i:02d}01': p
                      for i, p in enumerate(note_pages, 1)})
        cid = (f'heading-policy-note-{pitch}pt-{variant}' if variant
               else f'heading-note-{pitch}pt-keep-{str(kept).lower()}') + '-times-new-roman'
        yield cid, (f'300pt band; six lead paragraphs; heading keepNext={kept}; '
                    f'17-line citing paragraph; three {pitch}pt note paragraphs'
                    + (f'; {variant} control' if variant else '') + ' (Docxodus #1217)'), kept_note_parts(body, notes), pages, ['1']

    # pitch: eight heading pages, eight citing pages, all 24 note-paragraph pages, tail.
    dense_layouts = {
        20: ([1, 1, 1, 2, 2, 2, 3, 3], [1, 1, 1, 2, 2, 2, 3, 3],
             [1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3], 3),
        39: ([1, 1, 2, 2, 3, 3, 4, 5], [1, 1, 2, 2, 3, 3, 4, 5],
             [1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 5, 5, 5], 5),
        40: ([1, 1, 2, 2, 3, 3, 4, 5], [1, 1, 2, 2, 3, 3, 4, 5],
             [1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 5, 5, 5], 5),
        41: ([1, 1, 2, 2, 3, 3, 4, 5], [1, 1, 2, 2, 3, 3, 4, 5],
             [1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 5, 5, 5], 5),
        89: ([1, 2, 3, 5, 6, 7, 9, 10], [1, 2, 4, 5, 6, 8, 9, 10],
             [1, 1, 2, 2, 3, 3, 4, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 8, 9, 9, 10, 10, 11, 11], 11),
        90: ([1, 2, 3, 5, 6, 7, 9, 10], [1, 2, 4, 5, 6, 8, 9, 10],
             [1, 1, 2, 2, 3, 3, 4, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 8, 9, 9, 10, 10, 11, 11], 11),
        91: ([1, 2, 3, 5, 6, 8, 9, 11], [1, 2, 4, 5, 7, 8, 10, 11],
             [1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12], 12),
    }
    for pitch, (heading_pages, cite_pages, note_pages, tail_page) in dense_layouts.items():
        body = ''.join(paragraph(f'WillowHeading{i:02d}', keep_next=True)
                       + paragraph(f'WillowCite{i:02d}', keep_lines=True, note_id=i) for i in range(1, 9))
        body += paragraph('WillowTail')
        pages = {}
        for i in range(1, 9):
            pages[f'WillowHeading{i:02d}01'] = heading_pages[i - 1]
            pages[f'WillowCite{i:02d}01'] = cite_pages[i - 1]
            for part in range(1, 4):
                pages[(str(i) if part == 1 else '') + f'WillowNote{i:02d}Part{part:02d}01'] = note_pages[(i - 1) * 3 + part - 1]
        pages['WillowTail01'] = tail_page
        yield f'dense-chain-note-{pitch}pt-times-new-roman', (
            f'300pt band; eight 30pt kept heading/citation pairs; each cites three {pitch}pt note paragraphs '
            '(Docxodus #1217)'), kept_note_parts(body, ''.join(note(i, pitch) for i in range(1, 9))), pages, [str(i) for i in range(1, 9)]


def kept_note_paragraph_inputs():
    """Original literal mode/widow controls and long notes with unbreakable line labels.

    The source shapes preserve the separately captured Word input hashes. In particular,
    settings are omitted in the legacy controls and modes 14/15 differ only in settings.
    """
    spacing = '<w:spacing w:before="0" w:after="0" w:line="300" w:lineRule="exact"/>'
    body = (f'<w:p><w:pPr>{spacing}</w:pPr><w:r><w:t>SpruceCite01</w:t></w:r>'
            '<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:footnoteReference w:id="1"/></w:r></w:p>'
            f'<w:p><w:pPr>{spacing}</w:pPr><w:r><w:t>SpruceTail01</w:t></w:r></w:p>')
    variants = [(20, 'widow-default', None), (20, 'widow-off', None), (20, 'widow-on', None),
                (18, 'fitting', None), (19, 'deferred', None), (21, 'widow-default', None),
                (19, 'widow-off', None), (19, 'widow-on', None),
                (21, 'widow-default', 14), (21, 'widow-default', 15)]
    settings = lambda mode: (f'<w:settings xmlns:w="{W}"><w:compat><w:compatSetting '
                            'w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" '
                            f'w:val="{mode}"/></w:compat></w:settings>')
    for count, variant, mode in variants:
        widow = '<w:widowControl w:val="0"/>' if variant == 'widow-off' else '<w:widowControl/>' if variant == 'widow-on' else ''
        content = '<w:r><w:footnoteRef/></w:r>' + '<w:r><w:br/></w:r>'.join(
            f'<w:r><w:t>SpruceNoteLine{i:02d}</w:t></w:r>' for i in range(1, count + 1))
        note = f'<w:footnote w:id="1"><w:p><w:pPr><w:keepLines/>{widow}{spacing}</w:pPr>{content}</w:p></w:footnote>'
        parts = kept_note_parts(body, note)
        if mode is not None:
            parts['word/settings.xml'] = settings(mode)
            parts['word/_rels/document.xml.rels'] = parts['word/_rels/document.xml.rels'].replace('</Relationships>',
                f'<Relationship Id="rIdFixtureSettings" Type="{R}/settings" Target="settings.xml"/></Relationships>')
            parts['[Content_Types].xml'] = parts['[Content_Types].xml'].replace('</Types>',
                '<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/></Types>')
        cid = (f'kept-note-mechanism-normal-mode{mode}-opc-default-ns-times-new-roman' if mode is not None
               else f'kept-note-{count}-lines-{variant}-times-new-roman')
        yield cid, f'One kept {count}-line note; widow {variant}; compatibility {mode or "omitted"} (Docxodus #1217)', parts, 'short', count, variant, mode

    # These static package declarations/styles are literal source, not a loaded template.
    long_parts = {'[Content_Types].xml': '<?xml version="1.0" encoding="utf-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n  <Default Extension="xml" ContentType="application/xml"/>\n  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>\n  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>\n  <Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>\n<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/></Types>', '_rels/.rels': '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>\n</Relationships>', 'word/_rels/document.xml.rels': '<?xml version="1.0" encoding="utf-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>\n  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes" Target="footnotes.xml"/>\n<Relationship Id="rFixtureSettings" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/></Relationships>', 'word/styles.xml': '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n  <w:docDefaults><w:rPrDefault><w:rPr>\n    <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>\n    <w:sz w:val="24"/><w:szCs w:val="24"/>\n  </w:rPr></w:rPrDefault></w:docDefaults>\n  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>\n  <w:style w:type="paragraph" w:styleId="FootnoteText"><w:name w:val="footnote text"/>\n    <w:basedOn w:val="Normal"/>\n    <w:pPr><w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>\n    <w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>\n  </w:style>\n  <w:style w:type="character" w:styleId="FootnoteReference"><w:name w:val="footnote reference"/>\n    <w:rPr><w:vertAlign w:val="superscript"/></w:rPr>\n  </w:style>\n</w:styles>'}
    for cite, mode in [(1, 15), (1, 14), (16, 15), (16, 14)]:
        body = ''.join(
            '<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
            f'<w:r><w:t xml:space="preserve">SpruceBody{i:02d}</w:t></w:r>'
            + ('<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr><w:footnoteReference w:id="1"/></w:r>' if i == cite else '')
            + '</w:p>' for i in range(1, 31))
        content = '<w:t xml:space="preserve"> SpruceLongNote001</w:t>' + ''.join(
            f'<w:br/><w:t>SpruceLongNote{i:03d}</w:t>' for i in range(2, 121))
        parts = dict(long_parts)
        parts['word/document.xml'] = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body>\n  ' + body + '\n  <w:sectPr>\n    <w:pgSz w:w="12240" w:h="15840"/>\n    <w:pgMar w:top="1440" w:right="1440"\n      w:bottom="1440" w:left="1440"\n      w:header="720" w:footer="720" w:gutter="0"/>\n    <w:cols w:space="720"/>\n  </w:sectPr>\n</w:body></w:document>'
        parts['word/footnotes.xml'] = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n  <w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>\n  <w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>\n  <w:footnote w:id="1"><w:p><w:pPr><w:pStyle w:val="FootnoteText"/><w:keepLines/></w:pPr><w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr><w:footnoteRef/></w:r><w:r>' + content + '</w:r></w:p></w:footnote>\n</w:footnotes>'
        if cite == 16:
            parts['word/document.xml'] = parts['word/document.xml'].replace(
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n',
                '<?xml version="1.0" encoding="utf-8"?>').replace(
                '<w:pgMar w:top="1440" w:right="1440"\n      w:bottom="1440" w:left="1440"\n      w:header="720" w:footer="720" w:gutter="0"/>',
                '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>')
        parts['word/settings.xml'] = settings(mode)
        cid = f'kept-note-120-lines-citation-{cite}-mode-{mode}-times-new-roman'
        yield cid, f'120 explicit note lines; body citation {cite}; compatibility {mode} (Docxodus #1217)', parts, 'long', 120, cite, mode


def generate():
    cases = []
    def add(case_id, category, description, text, body, sect=None, notes=None, image=False, assertions=None, namespaces_extra='', styles_xml=None, story=None, notes_xml=None, stories=None, extra_parts=None, footnote_list=None, numbering_xml=None, comments_xml=None, comments_extended_xml=None, comments_ids_xml=None, comments_extensible_xml=None, font=FONT, literal_parts=None):
        assertions = assertions or []
        for assertion in assertions:
            if assertion['type'] == 'marker-region':
                assertion.update(version=2, tolerancePt=0.0001)
        path = ROOT / 'fixtures' / (case_id + '.docx')
        if literal_parts is None:
            package(path, body, sect, notes, image, namespaces_extra, styles_xml, story, notes_xml, stories, extra_parts, footnote_list, numbering_xml, comments_xml, comments_extended_xml, comments_ids_xml, comments_extensible_xml, font=font)
        else:
            zip_write(path, literal_parts)
        inventory = dict(sorted(Counter(' '.join(text).split()).items()))
        cases.append({'id': case_id, 'version': 2 if any(a['type'] == 'marker-region' for a in assertions) else 1, 'category': category, 'description': description, 'input': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'rights': {'author': 'John Scrudato IV', 'license': 'MIT', 'origin': 'Authored by bench/fixtures.py in this repository', 'assets': 'All text and graphics are generated here; no embedded font files'}, 'profile': {'review': 'final', 'comments': 'hidden'}, 'fonts': [font], 'tokens': inventory, 'assertions': assertions, 'generator': {'path': 'bench/fixtures.py', 'sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}})
    prose = 'The survey team records the height of each tower before the evening check. The next crew compares the notes and keeps the route open for the morning visit.'
    for case_id, ending in [('columns-continuous', 'continuous'), ('columns-balanced', 'balanced ending'), ('columns-break', 'continuous')]:
        title = case_id.replace('-', ' ').title()
        texts = [title]
        body = para(title, '<w:pStyle w:val="Title"/>' + section())
        for i in range(1, 13):
            text = f'C{i:02d} {prose}'
            texts.append(text)
            props = '<w:keepLines/>'
            if case_id == 'columns-balanced' and i == 12:
                props += section(2, 'continuous')
            prefix = '<w:r><w:br w:type="column"/></w:r>' if case_id == 'columns-break' and i == 7 else ''
            body += para(props=props, runs=prefix + run(text))
        assertions = [{'type': 'marker-region', 'version': 1, 'marker': 'C01', 'occurrence': 1, 'page': 'reference', 'rect': [72, 60, 300, 720]}]
        if case_id in ('columns-break', 'columns-balanced'):
            assertions.append({'type': 'marker-region', 'version': 1, 'marker': 'C07', 'occurrence': 1, 'page': 'reference', 'rect': [318, 60, 540, 720]})
        if case_id == 'columns-balanced':
            after = 'AfterColumns The two columns end before this full width paragraph.'
            texts.append(after)
            body += para(after)
        final = section(1, 'continuous') if case_id == 'columns-balanced' else section(2, 'continuous')
        add(case_id, 'columns', 'Two columns with ' + ending + ' section behavior', texts, body, final, assertions=assertions)
    title = 'Service agreement layout'
    texts = [title]
    body = para(title, '<w:pStyle w:val="Title"/>')
    for i in range(1, 25):
        text = f'Clause{i:02d} The parties will inspect the sample, record the agreed date, and send the written schedule to the project office. Each report includes the measured quantity and the name of the person responsible for the next review.'
        texts.append(text)
        body += para(text, '<w:jc w:val="both"/>')
    add('paragraph-contract', 'paragraphs', 'Authored agreement with justified multi-page flow', texts, body)
    # Keep the original Liberation Serif baseline byte-identical. Word Online can
    # export this explicitly requested family without substituting its font.
    add('paragraph-contract-times-new-roman', 'paragraphs',
        'The same justified agreement in Times New Roman for Word adjudication (bench #33)',
        texts, body, font='Times New Roman')
    texts = ['First page', 'The first page contains a short introduction.', 'HeadingMarker', prose]
    body = para(texts[0], '<w:pStyle w:val="Title"/>') + para(texts[1]) + para(texts[2], '<w:pageBreakBefore/><w:keepNext/><w:spacing w:before="360" w:after="120"/>') + para(texts[3])
    add('paragraph-heading', 'paragraphs', 'Space before a heading at a page start', texts, body, assertions=[{'type': 'marker-region', 'version': 1, 'marker': 'HeadingMarker', 'occurrence': 1, 'page': 2, 'rect': [72, 60, 540, 160]}])
    texts = ['Kept heading and paragraph']
    body = para(texts[0], '<w:pStyle w:val="Title"/>')
    for i in range(30):
        text = f'Row{i:02d} A short line establishes the available page band.'
        texts.append(text)
        body += para(text, '<w:spacing w:after="100"/>')
    texts += ['KeepHeading', 'KeepBody ' + prose]
    body += para(texts[-2], '<w:keepNext/><w:spacing w:before="240"/>') + para(texts[-1], '<w:keepLines/>')
    add('paragraph-keep', 'paragraphs', 'Heading and paragraph keep behavior near a page boundary', texts, body, assertions=[{'type': 'same-page', 'version': 1, 'markers': ['KeepHeading', 'KeepBody']}])
    for kind in ('footnote', 'endnote'):
        title, first, note = kind.title() + ' placement', 'NoteAnchor The route is checked before departure.', 'NoteText The recorded distance is five miles.'
        marker = 'i' if kind == 'endnote' else '1'
        texts = [title, first, marker, marker, note, prose]
        body = para(title, '<w:pStyle w:val="Title"/>') + para(runs=run(first + ' ') + f'<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:{kind}Reference w:id="1"/></w:r>') + para(prose)
        assertion = {'type': 'marker-region', 'version': 1, 'marker': 'NoteText', 'occurrence': 1, 'page': 'reference', 'rect': [60, 650, 552, 750]} if kind == 'footnote' else {'type': 'marker-reference-position', 'version': 1, 'marker': 'NoteText', 'tolerancePt': 0.5}
        add('notes-' + kind, 'notes', kind.title() + ' body and automatic marker', texts, body, notes=(kind, note), assertions=[assertion])
        if kind == 'endnote':
            cases[-1]['version'] = 2
    # Docxodus #1314: a tracked section-property change (w:sectPrChange) stores the section's
    # earlier properties as a nested w:sectPr. Here those earlier properties numbered endnotes in
    # decimal and the current section declares no endnote format, so settings' lowerRoman applies
    # and both the citation and the note read "i". A renderer that reads the stored earlier copy as
    # the section's own format prints "1" instead. Shown in markup, where the change is pending.
    # The control is the same section with no pending change.
    change_texts = ['Ledger endnote format', 'ChangeAnchor The survey closes at the eastern gate.', 'i', 'i',
                    'ChangeNote The gate log is kept at the depot.', prose]
    change_body = (para(change_texts[0], '<w:pStyle w:val="Title"/>')
                   + para(runs=run(change_texts[1] + ' ') + '<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:endnoteReference w:id="1"/></w:r>')
                   + para(prose))
    earlier_format = ('<w:sectPrChange w:id="41" w:author="Rowan Reviewer" w:date="2026-09-12T10:00:00Z"><w:sectPr>'
                      '<w:endnotePr><w:numFmt w:val="decimal"/></w:endnotePr></w:sectPr></w:sectPrChange>')
    for case_id, pending in [('notes-endnote-format-section-change', True), ('notes-endnote-format-section-change-control', False)]:
        change_sect = section().replace('</w:sectPr>', earlier_format + '</w:sectPr>') if pending else section()
        add(case_id, 'notes',
            'Endnote markers under a section ' + ('whose pending property change stored an earlier decimal format, shown in markup (Docxodus #1314)'
                                                   if pending else 'with no pending property change, shown in markup (control)'),
            change_texts, change_body, change_sect, notes=('endnote', change_texts[4]))
        cases[-1]['profile'] = {'review': 'markup', 'comments': 'hidden'}
    title = 'Nested table spacing'
    texts = [title, 'OuterLeft', 'OuterRight', 'InnerLeft', 'InnerRight', 'AfterTable']
    inner = table([[cell(texts[3]), cell(texts[4])]], width=4200)
    body = para(title, '<w:pStyle w:val="Title"/>') + table([[cell(texts[1], nested=inner), cell(texts[2])]]) + para(texts[-1])
    # Native Word margins for Docxodus #1219; LibreOffice retains implicit 5.4pt padding.
    # Raw Word boxes and font/schema qualifications are retained with the case evidence.
    add('tables-nested', 'tables', 'Nested table with visible outer and inner cells', texts, body,
        assertions=[{'type': 'marker-region', 'version': 2, 'marker': 'OuterLeft', 'occurrence': 1, 'page': 1, 'rect': [72.525, 105.999, 117.041, 119.176], 'adjudicated': 'word'}, {'type': 'marker-region', 'version': 2, 'marker': 'InnerLeft', 'occurrence': 1, 'page': 1, 'rect': [73.275, 127.249, 116.042, 140.426], 'adjudicated': 'word'}])
    cases[-1]['version'] = 2
    title = 'Inherited cell margins'
    texts = [title, 'CellLeft', 'CellRight', 'SecondLeft', 'SecondRight', 'AfterMargins']
    margins = '<w:tblCellMar>' + ''.join(f'<w:{s} w:w="240" w:type="dxa"/>' for s in ('top', 'left', 'bottom', 'right')) + '</w:tblCellMar>'
    body = para(title, '<w:pStyle w:val="Title"/>') + table([[cell(texts[1]), cell(texts[2])], [cell(texts[3]), cell(texts[4])]], margins) + para(texts[-1])
    add('tables-margins', 'tables', 'Table-level cell margins inherited by each cell', texts, body)
    for wrap in ('square', 'tight'):
        title = wrap.title() + ' image wrapping'
        texts = [title]
        body = para(title, '<w:pStyle w:val="Title"/>')
        for i in range(8):
            text = f'Wrap{i:02d} {prose}'
            texts.append(text)
            body += para(runs=(drawing(wrap) if i == 0 else '') + run(text))
        add('images-' + wrap, 'images', wrap.title() + ' wrapping around an authored diamond', texts, body, image=True)
    # Docxodus #1314: a one-inch picture anchored 264pt from the page's left edge, square-wrapped on
    # both sides, in an A4 section whose pending property change (w:sectPrChange) stored earlier
    # Letter properties. Its centre (300pt) is right of the A4 page centre (297.6pt) but left of the
    # Letter centre (306pt), so a renderer that lays the last section out on the stored Letter page
    # moves the picture to the other side of the text. Either way the paragraph's first word must
    # start at the left margin, beside the picture. The paragraph carries its own properties, which
    # is what exposed the defect: the converter then saw the stored copy before the paragraph's runs.
    # Shown in markup, where the change is pending. The control has no pending change.
    float_text = 'FloatLead Alder survey notes run beside the anchored picture and continue across the column.'
    float_picture = drawing('square').replace(
        '<wp:positionH relativeFrom="column"><wp:posOffset>0</wp:posOffset>',
        '<wp:positionH relativeFrom="page"><wp:posOffset>3352800</wp:posOffset>').replace('1371600', '914400')
    float_margins = '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720"/><w:cols w:num="1" w:space="480"/>'
    float_letter = ('<w:sectPrChange w:id="42" w:author="Rowan Reviewer" w:date="2026-09-12T10:00:00Z"><w:sectPr>'
                    '<w:pgSz w:w="12240" w:h="15840"/>' + float_margins + '</w:sectPr></w:sectPrChange>')
    for case_id, pending in [('images-float-side-section-change', True), ('images-float-side-section-change-control', False)]:
        float_sect = '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>' + float_margins + (float_letter if pending else '') + '</w:sectPr>'
        add(case_id, 'images',
            'Page-anchored picture in an A4 section ' + ('whose pending property change stored earlier Letter properties, shown in markup (Docxodus #1314)'
                                                         if pending else 'with no pending property change, shown in markup (control)'),
            [float_text], para(props='<w:jc w:val="left"/>', runs=float_picture + run(float_text)), float_sect, image=True,
            assertions=[{'type': 'marker-region', 'version': 2, 'marker': 'FloatLead', 'occurrence': 1, 'page': 1, 'rect': [66, 60, 150, 200]}])
        cases[-1]['profile'] = {'review': 'markup', 'comments': 'hidden'}
    # Independent textbox pair for Docxodus #1076. No renderer fixture/helper is imported.
    # The body and following line remain away from the page-positioned textbox.
    texts = ['Drawing register begins.', 'TextboxLabel Cedar sample tray.',
             'FollowingMarker The tray is ready.']
    textbox_styles = f'''<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr>
      <w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:eastAsia="{FONT}" w:cs="{FONT}"/>
      <w:color w:val="000000"/><w:sz w:val="22"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>
      <w:widowControl/><w:spacing w:after="120" w:line="276" w:lineRule="auto"/>
      </w:pPr></w:pPrDefault></w:docDefaults>
      <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style></w:styles>'''
    for relative_zero in (False, True):
        relative = ('<wp14:sizeRelH relativeFrom="margin"><wp14:pctWidth>0</wp14:pctWidth></wp14:sizeRelH>'
                    '<wp14:sizeRelV relativeFrom="margin"><wp14:pctHeight>0</wp14:pctHeight></wp14:sizeRelV>') if relative_zero else ''
        box = f'''<w:r><w:drawing><wp:anchor distT="0" distB="0" distL="0" distR="0"
          simplePos="0" relativeHeight="1" behindDoc="0" locked="0" layoutInCell="1" allowOverlap="1">
          <wp:simplePos x="0" y="0"/><wp:positionH relativeFrom="page"><wp:posOffset>1828800</wp:posOffset></wp:positionH>
          <wp:positionV relativeFrom="page"><wp:posOffset>1828800</wp:posOffset></wp:positionV>
          <wp:extent cx="2743200" cy="914400"/><wp:wrapNone/><wp:docPr id="1" name="Authored tray label"/>
          <wp:cNvGraphicFramePr/><a:graphic><a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">
          <wps:wsp><wps:cNvSpPr txBox="1"/><wps:spPr><a:xfrm><a:off x="0" y="0"/>
          <a:ext cx="2743200" cy="914400"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/>
          <a:ln w="12700"><a:solidFill><a:srgbClr val="000000"/></a:solidFill></a:ln></wps:spPr>
          <wps:txbx><w:txbxContent>{para(texts[1])}</w:txbxContent></wps:txbx>
          <wps:bodyPr lIns="0" tIns="0" rIns="0" bIns="0"><a:noAutofit/></wps:bodyPr></wps:wsp>
          </a:graphicData></a:graphic>{relative}</wp:anchor></w:drawing></w:r>'''
        cid = 'drawings-textbox-zero-relative' if relative_zero else 'drawings-textbox-absolute'
        add(cid, 'images', 'Page-positioned 216 by 72pt textbox with ' + ('zero relative dimensions' if relative_zero else 'absolute extent'),
            texts, para(runs=run(texts[0]) + box) + para(texts[2]),
            styles_xml=textbox_styles,
            namespaces_extra=' xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"',
            assertions=[{'type': 'marker-region', 'version': 2, 'marker': 'TextboxLabel', 'occurrence': 1,
                         'page': 1, 'rect': [144, 144, 360, 216]},
                        {'type': 'same-page', 'version': 1, 'markers': ['TextboxLabel', 'FollowingMarker']}])
        if not relative_zero:
            add('drawings-textbox-empty-host', 'images',
                'Absolute textbox promoted out of a host paragraph containing only the drawing',
                texts[1:], para(runs=box) + para(texts[2]), styles_xml=textbox_styles,
                namespaces_extra=' xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"',
                assertions=[{'type': 'marker-region', 'version': 2, 'marker': 'TextboxLabel', 'occurrence': 1,
                             'page': 1, 'rect': [144, 144, 360, 216]},
                            {'type': 'same-page', 'version': 1, 'markers': ['TextboxLabel', 'FollowingMarker']}])
    # Original inline-drawing set for Docxodus #1270: a 144 by 72pt teal rectangle that is a plain
    # DrawingML shape (not a text box), the same rectangle as the only child of a group, each also
    # inside a tracked deletion viewed in markup, and an inline teal picture of the same extent as
    # the control. The rectangle is the only ink between two text paragraphs; the following
    # paragraph's position records the extent it occupies.
    teal_shape = ('<wps:wsp><wps:cNvSpPr/><wps:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="1828800" cy="914400"/></a:xfrm>'
                  '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="19647E"/></a:solidFill>'
                  '</wps:spPr><wps:bodyPr/></wps:wsp>')
    teal_picture = ('<pic:pic><pic:nvPicPr><pic:cNvPr id="1" name="teal.png"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill>'
                    '<a:blip r:embed="rImage"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm>'
                    '<a:off x="0" y="0"/><a:ext cx="1828800" cy="914400"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/>'
                    '</a:prstGeom></pic:spPr></pic:pic>')
    drawing_uris = {'shape': 'http://schemas.microsoft.com/office/word/2010/wordprocessingShape',
                    'group': 'http://schemas.microsoft.com/office/word/2010/wordprocessingGroup',
                    'picture': 'http://schemas.openxmlformats.org/drawingml/2006/picture'}
    drawing_payloads = {'shape': teal_shape, 'picture': teal_picture,
                        'group': ('<wpg:wgp><wpg:cNvGrpSpPr/><wpg:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="1828800" cy="914400"/>'
                                  '<a:chOff x="0" y="0"/><a:chExt cx="1828800" cy="914400"/></a:xfrm></wpg:grpSpPr>'
                                  + teal_shape + '</wpg:wgp>')}
    for kind, deleted in [('shape', False), ('shape', True), ('group', False), ('group', True), ('picture', False)]:
        texts = ['PanelBefore Optical panel.', 'PanelAfter End of inspection.']
        inline = (f'<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="1828800" cy="914400"/>'
                  f'<wp:docPr id="7" name="Teal inspection panel"/><a:graphic><a:graphicData uri="{drawing_uris[kind]}">'
                  f'{drawing_payloads[kind]}</a:graphicData></a:graphic></wp:inline></w:drawing></w:r>')
        if deleted:
            inline = '<w:del w:id="31" w:author="Review Example" w:date="2026-09-12T10:00:00Z">' + inline + '</w:del>'
        cid = 'drawings-inline-' + kind + ('-deleted' if deleted else '') + ('-control' if kind == 'picture' else '')
        description = ('Inline teal picture control for the shape and group cases' if kind == 'picture' else
                       'Inline teal ' + ('rectangle shape' if kind == 'shape' else 'rectangle as the only child of a group')
                       + (' inside a tracked deletion' if deleted else '') + ' (Docxodus #1270)')
        add(cid, 'images', description, texts, para(texts[0]) + para(runs=inline) + para(texts[1]),
            image=kind == 'picture',
            # The picture control reuses the package's one image relationship with a teal raster.
            extra_parts={'word/media/diamond.png': png(192, 96, lambda x, y: (0x19, 0x64, 0x7E))} if kind == 'picture' else None,
            namespaces_extra=' xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup"',
            assertions=[{'type': 'marker-region', 'version': 2, 'marker': 'PanelAfter', 'occurrence': 1,
                         'page': 1, 'rect': [72, 150, 540, 210]}])
        if deleted:
            cases[-1]['profile'] = {'review': 'markup', 'comments': 'hidden'}
    # Original floating-shape set for Docxodus #1346. Reuse the authored primitive above;
    # positioning, wrapping and paint order are explicit, rather than taken from a template.
    floating_styles = f'''<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr>
      <w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}"/><w:sz w:val="22"/></w:rPr></w:rPrDefault>
      <w:pPrDefault><w:pPr><w:spacing w:before="0" w:after="0" w:line="320" w:lineRule="atLeast"/>
      </w:pPr></w:pPrDefault></w:docDefaults></w:styles>'''
    def floating_panel(kind='shape', wrap='top-bottom', order=10, behind=False, identifier=7, fill='19647E', unsupported=False):
        payload = drawing_payloads[kind].replace('19647E', fill)
        if unsupported:
            payload = payload.replace('prst="rect"', 'prst="hexagon"')
        polygon = ('<wp:wrapPolygon edited="0"><wp:start x="0" y="0"/><wp:lineTo x="21600" y="10800"/>'
                   '<wp:lineTo x="0" y="21600"/><wp:lineTo x="0" y="0"/></wp:wrapPolygon>')
        wrapping = ('<wp:wrapTopAndBottom/>' if wrap == 'top-bottom' else '<wp:wrapNone/>' if wrap == 'none'
                    else '<wp:wrapSquare wrapText="bothSides"/>' if wrap == 'square'
                    else f'<wp:wrap{wrap.title()} wrapText="bothSides">{polygon}</wp:wrap{wrap.title()}>')
        return (f'<w:r><w:drawing><wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" '
                f'relativeHeight="{order}" behindDoc="{int(behind)}" locked="0" layoutInCell="1" allowOverlap="1">'
                '<wp:simplePos x="0" y="0"/><wp:positionH relativeFrom="column"><wp:posOffset>0</wp:posOffset></wp:positionH>'
                '<wp:positionV relativeFrom="paragraph"><wp:posOffset>0</wp:posOffset></wp:positionV>'
                f'<wp:extent cx="1828800" cy="914400"/>{wrapping}<wp:docPr id="{identifier}" name="Harbor panel {identifier}"/>'
                f'<a:graphic><a:graphicData uri="{drawing_uris[kind]}">{payload}</a:graphicData></a:graphic></wp:anchor></w:drawing></w:r>')
    floating_cases = [
        ('shape-top-bottom', floating_panel(), False, True, 'Floating rectangle reserves top/bottom clearance'),
        ('group-top-bottom', floating_panel('group'), False, True, 'Floating group reserves top/bottom clearance'),
        ('shape-mixed-top-bottom', floating_panel(), True, True, 'Floating rectangle clears text in its own paragraph'),
        ('shape-no-wrap-control', floating_panel(wrap='none'), False, False, 'No-wrap rectangle leaves body line spacing intact'),
        ('shape-behind-text', floating_panel(wrap='none', behind=True), True, False, 'Background rectangle remains behind body text'),
        ('shape-relative-height', floating_panel(wrap='none', order=4294967295)
         + floating_panel(wrap='none', order=2147483648, identifier=8, fill='FF9900'), False, False,
         'Relative height orders overlapping rectangles independently of source order'),
        *[(f'shape-{wrap}', floating_panel(wrap=wrap), False, False,
           f'Column-edge rectangle with {wrap} text wrapping') for wrap in ('square', 'tight', 'through')],
        ('shape-unsupported', floating_panel(unsupported=True), False, True, 'Previously undrawn floating hexagon keeps its six-sided geometry'),
        ('vml-plain', '<w:r><w:pict><v:rect style="width:144pt;height:72pt" fillcolor="#19647E"/></w:pict></w:r>',
         False, True, 'Plain VML rectangle keeps its fill and outline'),
    ]
    for suffix, panel_xml, mixed, clears, description in floating_cases:
        texts = ['HarborBefore The inspection begins.', 'HarborAfter The inspection ends.']
        if mixed:
            texts.insert(1, 'HarborAnchor')
        after_region = ([72, 160, 540, 220] if clears else
                        [216, 100, 540, 140] if suffix == 'shape-square' else
                        [180, 100, 540, 140] if suffix in ('shape-tight', 'shape-through') else
                        [72, 100, 540, 140])
        add('drawings-floating-' + suffix, 'images', description + ' (Docxodus #1346)', texts,
            para(texts[0]) + para(runs=panel_xml + (run('HarborAnchor') if mixed else '')) + para(texts[-1]),
            styles_xml=floating_styles,
            namespaces_extra=' xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup" xmlns:v="urn:schemas-microsoft-com:vml"',
            assertions=[{'type': 'marker-region', 'version': 2, 'marker': 'HarborAfter', 'occurrence': 1,
                         'page': 1, 'rect': after_region}])

    # Independent hidden-header pair for Docxodus #1077. The empty first paragraph
    # is the passing control; the visible second line exposes paragraph-mark flow.
    header_styles = f'''<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr>
      <w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:eastAsia="{FONT}" w:cs="{FONT}"/>
      <w:color w:val="000000"/><w:sz w:val="22"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>
      <w:spacing w:after="0" w:line="240" w:lineRule="auto"/>
      </w:pPr></w:pPrDefault></w:docDefaults></w:styles>'''
    texts = ['HeaderMarker Night archive register.', 'BodyMarker The cedar drawer is ready.']
    header_section = section().replace('<w:sectPr>', '<w:sectPr><w:headerReference w:type="default" r:id="rStory"/>')
    for hidden in (False, True):
        first = para(runs=run('SecretMarker Concealed archive note.', '<w:vanish/>')) if hidden else para(runs='')
        cid = 'paragraphs-header-hidden' if hidden else 'paragraphs-header-empty'
        add(cid, 'paragraphs', 'Header with ' + ('hidden-only' if hidden else 'empty') + ' first paragraph and visible following line',
            texts, para(texts[1]), sect=header_section, styles_xml=header_styles,
            story=('header', first + para(texts[0])),
            assertions=[{'type': 'marker-region', 'version': 2, 'marker': 'HeaderMarker', 'occurrence': 1,
                         'page': 1, 'rect': [72, 45, 540, 80]}])
    # An original one-glyph pair isolates print measurement from word wrapping.
    # The available paragraph width is negative; its visible inline glyph remains measurable.
    overindent = '<w:ind w:left="5000" w:right="5000"/>'
    for indented in (False, True):
        cid = 'paragraphs-zero-width' if indented else 'paragraphs-inline-control'
        left = 320 if indented else 70
        add(cid, 'paragraphs', 'Visible inline glyph in ' + ('a zero-width' if indented else 'an ordinary') + ' paragraph',
            ['Z'], para('Z', overindent if indented else ''), styles_xml=header_styles,
            assertions=[{'type': 'marker-region', 'version': 2, 'marker': 'Z', 'occurrence': 1,
                         'page': 1, 'rect': [left, 60, left + 35, 105]}])
    # A whole word also wraps into three single-letter lines when its paragraph has no
    # available width. The reference PDF's visible-word inventory and final glyph region
    # ensure that accepting measurable descendants preserves every painted letter.
    add('paragraphs-overindented-word', 'paragraphs',
        'Overindented ABC word with reference letter wrapping and measurable inline descendants',
        ['A B C'], para('ABC', overindent), styles_xml=header_styles,
        assertions=[{'type': 'same-page', 'version': 1, 'markers': ['A', 'B', 'C']},
                    {'type': 'marker-region', 'version': 2, 'marker': 'C', 'occurrence': 1,
                     'page': 1, 'rect': [320, 85, 355, 130]}])
    # Original delivery ledger for Docxodus #1079. Whole rows fit on a page;
    # each pair differs only in the vertical merge elements. Continuations have
    # no visible text, so the pairs declare identical complete token inventories.
    ledger_styles = f'''<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr>
      <w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}"/><w:sz w:val="22"/>
      </w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/>
      </w:pPr></w:pPrDefault></w:docDefaults></w:styles>'''
    def ledger(location, first, span, merged, kept=False):
        texts, rows = [], []
        for index in range(1, 21):
            continuing = first < index < first + span
            left = '' if continuing else f'Lot{index:02d} Birch sample.'
            right = f'Entry{index:02d} Delivery ledger.'
            if left:
                texts.append(left)
            texts.append(right)
            merge = ('<w:vMerge w:val="restart"/>' if index == first else '<w:vMerge/>' if continuing else '') if merged else ''
            # The kept control holds each merged row with the next one, the declared intact merge.
            keep = '<w:keepNext/>' if kept and first <= index < first + span - 1 else ''
            cells = '<w:tc><w:tcPr><w:tcW w:w="4680" w:type="dxa"/>' + merge + '</w:tcPr>' + para(left, keep) + '</w:tc>'
            cells += '<w:tc><w:tcPr><w:tcW w:w="4680" w:type="dxa"/></w:tcPr>' + para(right, keep) + '</w:tc>'
            rows.append('<w:tr><w:trPr><w:trHeight w:val="1100" w:hRule="atLeast"/><w:cantSplit/></w:trPr>' + cells + '</w:tr>')
        body = '<w:tbl><w:tblPr><w:tblW w:w="9360" w:type="dxa"/><w:tblLayout w:type="fixed"/></w:tblPr>'
        body += '<w:tblGrid><w:gridCol w:w="4680"/><w:gridCol w:w="4680"/></w:tblGrid>' + ''.join(rows) + '</w:tbl>'
        cid = 'tables-vmerge-' + location + ('-merged' if merged else '-control') + ('-kept' if kept else '')
        assertions = [{'type': 'marker-region', 'version': 2, 'marker': 'Entry20', 'occurrence': 1,
                       'page': 2, 'rect': [305, 60, 540, 720]}]
        if merged:
            assertions.append({'type': 'same-page', 'version': 1,
                               'markers': [f'Entry{n:02d}' for n in range(first, first + span)]})
        add(cid, 'tables', 'Twenty-row ledger with ' + ('an intact' if merged else 'no') + ' vertical merge at ' + location
            + (', each merged row kept with the next' if kept else ''),
            texts, body, styles_xml=ledger_styles, assertions=assertions)
    for location, first, span in [('early', 1, 2), ('boundary', 11, 3)]:
        for merged in (False, True):
            ledger(location, first, span, merged)
    # Original archive register for Docxodus #1080. Ninety short lines occupy
    # three pages. The control uses separate paragraphs; the reproduction uses
    # one paragraph with text-wrapping breaks. Blank variants also test consecutive
    # breaks near page boundaries. No product fixture or helper is imported.
    line_properties = '<w:widowControl w:val="0"/><w:spacing w:before="0" w:after="0" w:line="400" w:lineRule="exact"/>'
    for blanks in (False, True):
        texts = [f'Record{index:03d} Elm archive checked.' for index in range(1, 91)]
        blocks = []
        for index, text in enumerate(texts, 1):
            blocks.append(run(text))
            if blanks and index in (32, 64):
                blocks.append('')
        for hard_breaks in (False, True):
            body = para(props=line_properties, runs='<w:r><w:br/></w:r>'.join(blocks)) if hard_breaks else ''.join(
                para(props=line_properties, runs=block) for block in blocks)
            cid = 'paragraphs-line-breaks-' + ('blanks-' if blanks else 'plain-') + ('breaks' if hard_breaks else 'control')
            add(cid, 'paragraphs', 'Three-page archive register using ' + ('explicit line breaks' if hard_breaks else 'individual paragraphs')
                + (' with two empty lines' if blanks else ''), texts, body, styles_xml=ledger_styles,
                assertions=[{'type': 'marker-region', 'version': 2, 'marker': 'Record001', 'occurrence': 1,
                             'page': 1, 'rect': [72, 72, 540, 105]},
                            {'type': 'marker-region', 'version': 2, 'marker': 'Record090', 'occurrence': 1,
                             'page': 3, 'rect': [72, 60, 540, 720]}])
    # Original archive cards for Docxodus #1081. A half-point height/width
    # exposes Chromium PDF size quantization. Controls change only that axis
    # to an integral point. Strict benchmark physical-geometry checks remain.
    for axis, integral in [('height', (606, 878)), ('width', (626, 852))]:
        for fractional in (False, True):
            width, height = integral
            if fractional:
                if axis == 'height':
                    height += 0.5
                else:
                    width += 0.5
            sect = section().replace('w:w="12240" w:h="15840"', f'w:w="{int(width * 20)}" w:h="{int(height * 20)}"')
            cid = f'paragraphs-page-size-{axis}-' + ('fractional' if fractional else 'control')
            text = 'PageBoxMarker Alder archive card.'
            add(cid, 'paragraphs', 'Archive card with ' + ('a half-point' if fractional else 'an integral') + ' page ' + axis,
                [text], para(text), sect=sect, styles_xml=ledger_styles,
                assertions=[{'type': 'marker-region', 'version': 2, 'marker': 'PageBoxMarker', 'occurrence': 1,
                             'page': 1, 'rect': [72, 60, 540, 105]}])
    # Original running-story number pair for Docxodus #1082. Legacy pgNum
    # blocks must remain decimal even when the section asks for Roman numbering.
    # Complex PAGE controls have an explicit Arabic switch. Simple fields also
    # record the independently discovered cached-result rendering gap.
    for restarted in (False, True):
        for kind in ('field', 'simple-field', 'legacy'):
            start = 12 if restarted else 1
            body_texts = [f'Archive{index:02d} Maple register inspected.' for index in range(1, 4)]
            body = ''.join(para(text, '<w:pageBreakBefore/>' if index else '') for index, text in enumerate(body_texts))
            numbering = f'<w:pgNumType w:fmt="{"upperRoman" if restarted else "decimal"}" w:start="{start}"/>'
            sect = section().replace('<w:sectPr>', '<w:sectPr><w:headerReference w:type="default" r:id="rStory"/>')
            sect = sect.replace('<w:cols ', numbering + '<w:cols ')
            header_run = '<w:r><w:rPr><w:i/><w:sz w:val="24"/></w:rPr>'
            result = header_run + '<w:t>1</w:t></w:r>'
            if kind == 'legacy':
                header = header_run + '<w:pgNum/></w:r>'
            elif kind == 'simple-field':
                header = '<w:fldSimple w:instr=" PAGE \\* Arabic ">' + result + '</w:fldSimple>'
            else:
                header = '<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> PAGE \\* Arabic </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r>' + result + '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
            cid = 'paragraphs-page-number-' + ('restarted-' if restarted else 'ordinary-') + kind
            texts = body_texts + [str(start + index) for index in range(3)]
            add(cid, 'paragraphs', 'Three-page running story with ' + {'legacy': 'legacy pgNum', 'field': 'equivalent complex decimal PAGE field', 'simple-field': 'equivalent simple decimal PAGE field'}[kind]
                + (' and a Roman-numbered section restarted at twelve' if restarted else ''),
                texts, body, sect=sect, styles_xml=ledger_styles,
                story=('header', para(runs=header, props='<w:spacing w:after="0"/>')),
                assertions=[{'type': 'marker-region', 'version': 2, 'marker': str(start + index), 'occurrence': 1,
                             'page': index + 1, 'rect': [72, 30, 540, 65]} for index in range(3)])
    # Independently authored long footnote ledgers for Docxodus #1083.
    for blanks in (False, True):
        texts = [f'Ledger{index:03d} Willow inventory counted.' for index in range(1, 91)]
        line_runs = []
        for index, text in enumerate(texts):
            line_runs.append(run((' ' if index == 0 else '') + text))
            if blanks and (index + 1) % 25 == 0:
                line_runs.extend(['', ''])
        props = '<w:widowControl w:val="0"/><w:spacing w:before="0" w:after="0" w:line="360" w:lineRule="exact"/>'
        marker = '<w:r><w:footnoteRef/></w:r>'
        body_text = 'CiteMarker The Willow inventory has one detailed note.'
        body = para(runs=run(body_text + ' ') + '<w:r><w:footnoteReference w:id="1"/></w:r>')
        for paragraphs in (True, False):
            note = ''.join(para(props=props, runs=(marker if index == 0 else '') + line)
                           for index, line in enumerate(line_runs)) if paragraphs else para(
                               props=props, runs=marker + '<w:r><w:br/></w:r>'.join(line_runs))
            cid = 'notes-explicit-breaks-' + ('blanks-' if blanks else '') + ('paragraph-control' if paragraphs else 'breaks')
            add(cid, 'notes', 'Ninety-line original footnote inventory with ' + ('paragraph boundaries' if paragraphs else 'explicit text-wrapping breaks')
                + (' and two empty lines after each twenty-five entries' if blanks else ''),
                [body_text, '1', '1'] + texts, body, notes=('footnote', ''), notes_xml=note, styles_xml=ledger_styles,
                assertions=[{'type': 'marker-region', 'version': 2, 'marker': 'CiteMarker', 'occurrence': 1,
                             'page': 1, 'rect': [72, 60, 540, 130]},
                            {'type': 'marker-region', 'version': 2, 'marker': 'Ledger090', 'occurrence': 1,
                             'page': 'reference', 'rect': [72, 60, 540, 725]},
                            {'type': 'marker-reference-position', 'version': 1, 'marker': 'Ledger002', 'tolerancePt': 0.5},
                            {'type': 'marker-reference-position', 'version': 1, 'marker': 'Ledger045', 'tolerancePt': 0.5}])
    # Original paragraph-border cards for Docxodus #1084. The optional size
    # has an application-defined default; explicit zero supplies the policy
    # control, and explicit two preserves the thin-border fidelity gap.
    for border_style in ('single', 'dashed'):
        for size in (None, '0', '2'):
            size_attr = '' if size is None else f' w:sz="{size}"'
            borders = ''.join(f'<w:{side} w:val="{border_style}" w:color="246B7D" w:space="4"{size_attr}/>'
                              for side in ('top', 'left', 'bottom', 'right'))
            text = 'BorderCard Juniper register inspected.'
            body = para(text, '<w:pBdr>' + borders + '</w:pBdr><w:spacing w:before="0" w:after="0"/>')
            add('paragraphs-border-size-' + border_style + '-' + ('omitted' if size is None else 'zero' if size == '0' else 'thin'),
                'paragraphs', 'Original border card with ' + border_style + ' borders and ' + ('omitted application-defined size' if size is None else 'explicit size ' + size),
                [text], body, styles_xml=ledger_styles,
                assertions=[{'type': 'marker-region', 'version': 2, 'marker': 'BorderCard', 'occurrence': 1,
                             'page': 1, 'rect': [72, 60, 540, 130]}])
    # Original Elm inventories for Docxodus #1085. Six universal-unit forms
    # share an exact 720-twip control; the original 12pt trigger has its own
    # 240-twip control. Each package exercises physical/logical edges and a
    # bordered hanging paragraph, whose wrapper has a separate indent path.
    indent_styles = ledger_styles.replace(f'w:hAnsi="{FONT}"', f'w:hAnsi="{FONT}" w:cs="{FONT}"')
    # Reference controls for bench #18 omit the conflicting legacy aliases on the logical paragraph.
    indentation_forms = [('pt', '36pt'), ('in', '0.5in'), ('cm', '1.27cm'), ('mm', '12.7mm'),
                         ('pc', '3pc'), ('pi', '3pi'), ('twips', '720'), ('small-pt', '12pt'), ('small-twips', '240')]
    for name, value in indentation_forms + [('twips-logical-only', '720'), ('small-twips-logical-only', '240')]:
        words = 'Elm archive entries remain in order while the register is inspected. '
        texts = [marker + ' ' + (words * 3).strip() for marker in ('InsetMarker', 'LogicalMarker', 'FirstMarker', 'BoxMarker')]
        # Avoid detached bidi punctuation in Poppler's whole-word inventory.
        texts[1] = texts[1].replace('.', '')
        aliases = '' if name.endswith('logical-only') else ' w:left="1440" w:right="1440"'
        props = [f'<w:ind w:left="{value}" w:right="{value}"/>',
                 f'<w:bidi/><w:ind w:start="{value}" w:end="{value}"{aliases}/>',
                 f'<w:ind w:left="{value}" w:firstLine="{value}"/>',
                 f'<w:pBdr><w:bottom w:val="single" w:sz="8" w:color="246B7D"/></w:pBdr><w:ind w:left="{value}" w:hanging="{value}"/>']
        body = ''.join(para(text, prop) for text, prop in zip(texts, props))
        assertions = [{'type': 'marker-region', 'version': 2, 'marker': marker, 'occurrence': 1,
                       'page': 1, 'rect': [72, 60, 540, 400]} for marker in ('InsetMarker', 'LogicalMarker', 'FirstMarker', 'BoxMarker')]
        assertions.append({'type': 'marker-reference-position', 'version': 1, 'marker': 'InsetMarker', 'tolerancePt': 0.5})
        add('paragraphs-indentation-' + name, 'paragraphs', 'Original Elm indentation inventory in ' + value
            + (' without conflicting legacy aliases on the logical paragraph' if not aliases else ''),
            texts, body, styles_xml=indent_styles, assertions=assertions)
    margin_styles = f'<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:cs="{FONT}"/><w:sz w:val="22"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:widowControl/><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style></w:styles>'
    margin_units = [('pt', '54pt', '18pt'), ('in', '0.75in', '0.25in'),
                    ('cm', '1.905cm', '0.635cm'), ('mm', '19.05mm', '6.35mm'),
                    ('pc', '4.5pc', '1.5pc'), ('pi', '4.5pi', '1.5pi'), ('twips', '1080', '360')]
    for name, edge, band in margin_units + [('multipage-pt', '54pt', '18pt'), ('multipage-twips', '1080', '360')]:
        count = 80 if name.startswith('multipage') else 16
        pages = 2 if name.startswith('multipage') else 1
        texts = ['MarginTop Chestnut margin records begin here.',
                 'MarginWide ' + ('The archive crew measures the page before numbering each entry. ' * 5).strip()]
        texts += [f'Chestnut{i:03d} The margin register retains this original line.' for i in range(1, count + 1)]
        texts += ['MarginEnd Chestnut margin records end here.']
        body = ''.join(para(text, '<w:spacing w:after="0" w:line="240" w:lineRule="auto"/>') for text in texts)
        sect = f'<w:sectPr><w:headerReference w:type="default" r:id="rStory"/><w:footerReference w:type="default" r:id="rStory1"/><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="{edge}" w:right="{edge}" w:bottom="{edge}" w:left="{edge}" w:header="{band}" w:footer="{band}" w:gutter="0"/></w:sectPr>'
        header, footer = 'MarginHead Chestnut running header.', 'MarginFoot Chestnut running footer.'
        assertions = [{'type': 'marker-region', 'version': 2, 'marker': 'MarginTop', 'occurrence': 1,
                       'page': 1, 'rect': [54, 54, 558, 738]},
                      {'type': 'marker-reference-position', 'version': 1, 'marker': 'MarginTop', 'tolerancePt': 0.5},
                      {'type': 'marker-region', 'version': 2, 'marker': 'MarginEnd', 'occurrence': 1,
                       'page': pages, 'rect': [54, 54, 558, 738]}]
        if pages == 1:
            assertions += [{'type': 'marker-region', 'version': 2, 'marker': marker, 'occurrence': 1,
                            'page': 1, 'rect': rect} for marker, rect in
                           [('MarginHead', [54, 0, 558, 54]), ('MarginFoot', [54, 738, 558, 792])]]
        add('paragraphs-page-margins-' + name, 'paragraphs', 'Original Chestnut page and story margins in ' + edge,
            texts + [header, footer] * pages, body, sect, assertions=assertions,
            story=('header', para(header)), stories=[('footer', para(footer))], styles_xml=margin_styles)
    for name, value in [('small-mm', '25mm'), ('small-twips', '1417')]:
        text = 'MarginMillimeters Chestnut documents a millimeter left margin.'
        sect = f'<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="{value}" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>'
        add('paragraphs-page-margins-' + name, 'paragraphs', 'Original Chestnut millimeter margin and rounded twip control',
            [text], para(text), sect, styles_xml=margin_styles, assertions=[{'type': 'marker-reference-position', 'version': 1,
                                                   'marker': 'MarginMillimeters', 'tolerancePt': 0.5}])
    row_styles = f'<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:cs="{FONT}"/><w:sz w:val="22"/></w:rPr></w:rPrDefault></w:docDefaults></w:styles>'
    row_units = [('pt', '36pt'), ('in', '0.5in'), ('cm', '1.27cm'), ('mm', '12.7mm'),
                 ('pc', '3pc'), ('pi', '3pi'), ('twips', '720'), ('fractional-pt', '25.075pt'),
                 ('fractional-twips', '502'), ('multipage-pt', '36pt'), ('multipage-twips', '720'),
                 ('exact-pt', '36pt'), ('exact-twips', '720')]
    for name, value in row_units:
        count = 30 if name.startswith('multipage') else 3
        rule = 'exact' if name.startswith('exact') else 'atLeast'
        texts = []
        rows = []
        for index in range(1, count + 1):
            left = f'Birch{index:02d} Original height record.'
            right = f'Entry{index:02d} Complete second cell.'
            texts += [left, right]
            cells = ''.join('<w:tc><w:tcPr><w:tcW w:w="3600" w:type="dxa"/></w:tcPr>'
                            + para(text, '<w:spacing w:after="0"/>') + '</w:tc>' for text in (left, right))
            rows.append(f'<w:tr><w:trPr><w:trHeight w:val="{value}" w:hRule="{rule}"/></w:trPr>{cells}</w:tr>')
        borders = '<w:tblBorders>' + ''.join(f'<w:{side} w:val="single" w:sz="6" w:color="444444"/>'
                    for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV')) + '</w:tblBorders>'
        body = '<w:tbl><w:tblPr><w:tblW w:w="7200" w:type="dxa"/>' + borders + '<w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid><w:gridCol w:w="3600"/><w:gridCol w:w="3600"/></w:tblGrid>' + ''.join(rows) + '</w:tbl>'
        assertions = [{'type': 'marker-region', 'version': 2, 'marker': 'Birch01', 'occurrence': 1,
                       'page': 1, 'rect': [72, 60, 540, 720]},
                      {'type': 'marker-region', 'version': 2, 'marker': f'Birch{count:02d}', 'occurrence': 1,
                       'page': 'reference', 'rect': [72, 60, 540, 720]}]
        assertions.append({'type': 'marker-reference-position', 'version': 1,
                           'marker': f'Birch{count:02d}', 'tolerancePt': 0.5})
        add('tables-row-height-' + name, 'tables', 'Original Birch ledger row height in ' + value + ' with ' + rule,
            texts, body, sect=section().replace('w:footer="720"', 'w:footer="720" w:gutter="0"'), styles_xml=row_styles, assertions=assertions)
    for name, entry in [('control', None), ('zero', '[trash]/0000.dat'),
                        ('upper', '[trash]/ABCD.dat'), ('lower', '[trash]/00af.dat')]:
        text = 'ResourceTop Acacia records retain every original entry.'
        extras = {entry: b'<obsolete>Discarded independent Acacia fragment'} if entry else None
        add('paragraphs-standard-trash-' + name, 'paragraphs', 'Original Acacia ledger with ' + (entry or 'no trash item'),
            [text], para(text), sect=section().replace('w:footer="720"', 'w:footer="720" w:gutter="0"'),
            styles_xml=row_styles, extra_parts=extras, assertions=[
                {'type': 'marker-region', 'version': 2, 'marker': 'ResourceTop', 'occurrence': 1,
                 'page': 1, 'rect': [72, 60, 540, 720]},
                {'type': 'marker-reference-position', 'version': 1, 'marker': 'ResourceTop', 'tolerancePt': 0.5}])
    # Reference control for bench #17: LibreOffice splits the boundary merge across pages,
    # violating the original same-page declaration. Keep-with-next on the merged rows states
    # the same intact merge in markup both Word and LibreOffice honor; see REFERENCE_CONTROLS.md.
    ledger('boundary', 11, 3, True, kept=True)
    # Regression coverage for Docxodus #1122: an exact row keeps its declared height when its
    # content needs more. The second row's cell ends with an empty 36pt paragraph mark in an 18pt
    # exact row; the third row's position shows whether the height rule was honored rather than
    # grown to fit. The excess is a paragraph mark, not text, so the visible-token inventory does
    # not depend on how a provider writes clipped glyphs into the PDF text layer.
    overflow_rows = []
    overflow_texts = []
    for index in range(1, 4):
        left = f'Birch{index:02d} Exact record.'
        right = f'Entry{index:02d} Exact cell.'
        overflow_texts += [left, right]
        tall_mark = para(props='<w:spacing w:after="0"/><w:rPr><w:sz w:val="72"/></w:rPr>', runs='') if index == 2 else ''
        cells = ('<w:tc><w:tcPr><w:tcW w:w="3600" w:type="dxa"/></w:tcPr>' + para(left, '<w:spacing w:after="0"/>') + tall_mark + '</w:tc>'
                 + '<w:tc><w:tcPr><w:tcW w:w="3600" w:type="dxa"/></w:tcPr>' + para(right, '<w:spacing w:after="0"/>') + '</w:tc>')
        overflow_rows.append(f'<w:tr><w:trPr><w:trHeight w:val="360" w:hRule="exact"/></w:trPr>{cells}</w:tr>')
    overflow_borders = '<w:tblBorders>' + ''.join(f'<w:{side} w:val="single" w:sz="6" w:color="444444"/>'
                                                 for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV')) + '</w:tblBorders>'
    overflow_body = ('<w:tbl><w:tblPr><w:tblW w:w="7200" w:type="dxa"/>' + overflow_borders + '<w:tblLayout w:type="fixed"/></w:tblPr>'
                     '<w:tblGrid><w:gridCol w:w="3600"/><w:gridCol w:w="3600"/></w:tblGrid>' + ''.join(overflow_rows) + '</w:tbl>')
    add('tables-row-height-exact-overflow', 'tables', 'Birch ledger with an exact 18pt row whose cell content needs more height',
        overflow_texts, overflow_body, sect=section().replace('w:footer="720"', 'w:footer="720" w:gutter="0"'), styles_xml=row_styles,
        assertions=[{'type': 'marker-reference-position', 'version': 1, 'marker': marker, 'tolerancePt': 0.5}
                    for marker in ('Birch01', 'Birch03')])
    # Regression coverage for Docxodus #1115: simple PAGE and NUMPAGES fields in one header.
    # Each page reads "Leaf N of 3": pages 1 and 2 have unique number markers, and the complete
    # inventory requires four 3s, so a cached NUMPAGES or PAGE result fails it.
    folio_texts = [f'Folio{index:02d} Maple register inspected.' for index in range(1, 4)]
    folio_body = ''.join(para(text, '<w:pageBreakBefore/>' if index else '') for index, text in enumerate(folio_texts))
    folio_run = '<w:r><w:rPr><w:i/><w:sz w:val="24"/></w:rPr><w:t>{}</w:t></w:r>'
    folio_run = folio_run.replace('<w:t>', '<w:t xml:space="preserve">')
    folio_header = (folio_run.format('Leaf ') + '<w:fldSimple w:instr=" PAGE ">' + folio_run.format('1') + '</w:fldSimple>'
                    + folio_run.format(' of ') + '<w:fldSimple w:instr=" NUMPAGES ">' + folio_run.format('1') + '</w:fldSimple>')
    folio_sect = section().replace('<w:sectPr>', '<w:sectPr><w:headerReference w:type="default" r:id="rStory"/>')
    add('paragraphs-page-number-numpages-simple-field', 'paragraphs',
        'Three-page running story with simple PAGE and NUMPAGES fields in one italic header line',
        folio_texts + [f'Leaf {index} of 3' for index in range(1, 4)], folio_body, sect=folio_sect, styles_xml=ledger_styles,
        story=('header', para(runs=folio_header, props='<w:spacing w:after="0"/>')),
        assertions=[{'type': 'marker-region', 'version': 2, 'marker': str(index + 1), 'occurrence': 1,
                     'page': index + 1, 'rect': [72, 30, 540, 65]} for index in range(2)])
    # Docxodus #1272: complex PAGE and NUMPAGES fields in a footer line that is wholly a tracked
    # deletion, so both instructions are w:delInstrText. Markup view still shows the struck line,
    # "Sheet N of 3", on every page. Both cached results are 1, so the inventory (one 1, one 2,
    # four 3s) fails a cached PAGE or NUMPAGES. The control is the same footer left undeleted.
    sheet_texts = [f'Rowan{index:02d} tally ledger audited.' for index in range(1, 4)]
    sheet_body = ''.join(para(text, '<w:pageBreakBefore/>' if index else '') for index, text in enumerate(sheet_texts))
    sheet_sect = section().replace('<w:sectPr>', '<w:sectPr><w:footerReference w:type="default" r:id="rStory"/>')
    for case_id, deleted in [('paragraphs-page-number-deleted-field', True), ('paragraphs-page-number-deleted-field-control', False)]:
        text_tag, instruction_tag = ('delText', 'delInstrText') if deleted else ('t', 'instrText')
        sheet_run = '<w:r><w:rPr><w:i/><w:sz w:val="24"/></w:rPr>{}</w:r>'
        def sheet_text(content, tag=text_tag):
            return sheet_run.format(f'<w:{tag} xml:space="preserve">{content}</w:{tag}>')
        def sheet_field(instruction):
            return (sheet_run.format('<w:fldChar w:fldCharType="begin"/>') + sheet_text(instruction, instruction_tag)
                    + sheet_run.format('<w:fldChar w:fldCharType="separate"/>') + sheet_text('1')
                    + sheet_run.format('<w:fldChar w:fldCharType="end"/>'))
        sheet_footer = sheet_text('Sheet ') + sheet_field(' PAGE ') + sheet_text(' of ') + sheet_field(' NUMPAGES ')
        if deleted:
            sheet_footer = '<w:del w:id="31" w:author="Rowan Reviewer" w:date="2026-09-12T10:00:00Z">' + sheet_footer + '</w:del>'
        add(case_id, 'paragraphs',
            'Three-page running story whose footer PAGE and NUMPAGES fields ' + ('sit inside a tracked deletion, shown in markup (Docxodus #1272)'
                                                                                 if deleted else 'are not deleted, shown in markup (control)'),
            sheet_texts + [f'Sheet {index} of 3' for index in range(1, 4)], sheet_body, sect=sheet_sect, styles_xml=ledger_styles,
            story=('footer', para(runs=sheet_footer, props='<w:spacing w:after="0"/>')),
            assertions=[{'type': 'marker-region', 'version': 2, 'marker': str(index + 1), 'occurrence': 1,
                         'page': index + 1, 'rect': [72, 720, 540, 780]} for index in range(2)])
        cases[-1]['profile'] = {'review': 'markup', 'comments': 'hidden'}
    # Regression coverage for Docxodus #1126: horizontal border spacing on indented, hanging and
    # adjacent grouped paragraphs. Text keeps its indentation; borders sit outside it.
    spacing_texts = ['SpacingPlain Juniper card keeps its text at the margin.',
                     'SpacingIndent Juniper card keeps its text at the left indent.',
                     'SpacingGroupOne ' + ('Juniper grouped card wraps across the full measure of its text band. ' * 2).strip(),
                     'SpacingGroupTwo Juniper grouped card shares the same border.',
                     'SpacingHanging ' + ('Juniper hanging card wraps beneath its hanging indent. ' * 3).strip()]
    def spaced_border(space, size='8'):
        return '<w:pBdr>' + ''.join(f'<w:{side} w:val="single" w:sz="{size}" w:space="{space}" w:color="246B7D"/>'
                                    for side in ('top', 'left', 'bottom', 'right')) + '</w:pBdr>'
    spacing_props = [spaced_border('4'),
                     spaced_border('12') + '<w:ind w:left="1440" w:right="720"/>',
                     spaced_border('8') + '<w:ind w:left="720"/>',
                     spaced_border('8') + '<w:ind w:left="720"/>',
                     spaced_border('6', '4') + '<w:ind w:left="1440" w:hanging="720"/>']
    spacing_body = ''.join(para(text, props + '<w:spacing w:before="240" w:after="0"/>' if index in (0, 1, 2, 4) else props + '<w:spacing w:after="0"/>')
                           for index, (text, props) in enumerate(zip(spacing_texts, spacing_props)))
    add('paragraphs-border-spacing-indented', 'paragraphs',
        'Bordered Juniper cards with positive spacing, indents, a grouped pair and a hanging indent',
        spacing_texts, spacing_body, styles_xml=ledger_styles,
        assertions=[{'type': 'marker-reference-position', 'version': 1, 'marker': marker, 'tolerancePt': 0.5}
                    for marker in ('SpacingPlain', 'SpacingIndent', 'SpacingGroupOne', 'SpacingGroupTwo', 'SpacingHanging')])
    # Regression coverage for Docxodus #1125: half-point width and height together, with ink
    # placed near every page edge by small margins.
    edge_texts = ['EdgeTop Rowan card begins near the upper edge.'] + [f'Rowan{index:02d} edge register line.' for index in range(1, 65)] + ['EdgeEnd Rowan card ends near the lower edge.']
    edge_sect = ('<w:sectPr><w:pgSz w:w="12130" w:h="17570"/><w:pgMar w:top="360" w:right="360" w:bottom="360" w:left="360" '
                 'w:header="180" w:footer="180" w:gutter="0"/><w:cols w:num="1" w:space="480"/></w:sectPr>')
    edge_body = ''.join(para(text, '<w:jc w:val="right"/>' if index % 2 else '') for index, text in enumerate(edge_texts))
    add('paragraphs-page-size-edge-ink', 'paragraphs', 'Rowan card with half-point width and height and ink near every edge',
        edge_texts, edge_body, sect=edge_sect, styles_xml=ledger_styles,
        assertions=[{'type': 'marker-reference-position', 'version': 1, 'marker': marker, 'tolerancePt': 0.5}
                    for marker in ('EdgeTop', 'Rowan63', 'EdgeEnd')])
    # core-v18: rendering regressions from Docxodus #1164, #1168, #1171 and #1178-#1182. Lines use
    # exact spacing so each page band holds a known number of lines.
    def exact(twips):
        return f'<w:widowControl w:val="0"/><w:spacing w:before="0" w:after="0" w:line="{twips}" w:lineRule="exact"/>'
    # Docxodus #1164: A4 with 1417-twip (70.85pt) margins around a 14004-twip body band. Twelve exact
    # lines one twip short of the band must stay on page 1; one twip over, the last line moves to page 2.
    # The one-twip margins keep a correct paginator off floating-point ties. Controls use 1416/1418 twips
    # (70.8pt/70.9pt), which have the same band but no fractional tenth of a point.
    for name, margins in [('1417', (1417, 1417, 1417, 1417)), ('1417-control', (1416, 1418, 1418, 1416))]:
        for fill, last, page in [('underfull', 1166, 1), ('overfull', 1168, 2)]:
            top, right, bottom, left = margins
            sect = (f'<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="{top}" w:right="{right}" w:bottom="{bottom}" '
                    f'w:left="{left}" w:header="709" w:footer="709" w:gutter="0"/><w:cols w:space="708"/></w:sectPr>')
            texts = [f'Geometry{i:02d} Fir margin register entry.' for i in range(1, 13)]
            body = ''.join(para(text, exact(last if i == 12 else 1167)) for i, text in enumerate(texts, 1))
            fill_label = 'fall one twip short of' if fill == 'underfull' else 'overfill by one twip'
            add(f'paragraphs-page-margins-{name}-{fill}', 'paragraphs',
                f'A4 page with {"1417-twip" if name == "1417" else "1416/1418-twip control"} margins; twelve exact lines {fill_label} the body band',
                texts, body, sect=sect, styles_xml=ledger_styles,
                assertions=[{'type': 'marker-region', 'version': 2, 'marker': 'Geometry12', 'occurrence': 1, 'page': page,
                             'rect': [60, 60, 540, 790]},
                            {'type': 'marker-reference-position', 'version': 1, 'marker': 'Geometry01', 'tolerancePt': 0.5},
                            {'type': 'marker-reference-position', 'version': 1, 'marker': 'Geometry12', 'tolerancePt': 0.5}])
    # Positive exact heights keep #1168's clipping. The unchanged exact-zero inputs below use
    # Word's content-height behavior (#1339); their marker positions are checked against references.
    exact_borders = '<w:tblBorders>' + ''.join(f'<w:{side} w:val="single" w:sz="6" w:color="444444"/>' for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV')) + '</w:tblBorders>'
    def exact_table(rows, borders=exact_borders):
        return ('<w:tbl><w:tblPr><w:tblW w:w="7200" w:type="dxa"/>' + borders + '<w:tblLayout w:type="fixed"/></w:tblPr>'
                '<w:tblGrid><w:gridCol w:w="3600"/><w:gridCol w:w="3600"/></w:tblGrid>' + ''.join(rows) + '</w:tbl>')
    def exact_row(height, cells, rule='exact', header=False):
        props = ('<w:tblHeader/>' if header else '') + f'<w:trHeight w:val="{height}" w:hRule="{rule}"/>'
        return '<w:tr><w:trPr>' + props + '</w:trPr>' + ''.join(f'<w:tc><w:tcPr><w:tcW w:w="3600" w:type="dxa"/></w:tcPr>{c}</w:tc>' for c in cells) + '</w:tr>'
    blank = para(runs=run('     '), props='<w:spacing w:after="0"/>')
    tight = '<w:spacing w:after="0"/>'
    for name, hidden in [('exact-hidden-paragraph', True), ('exact-hidden-control', False)]:
        texts, rows = [], []
        for index in range(1, 4):
            left, right = f'Hidden{index:02d} Birch record.', f'Entry{index:02d} Exact cell.'
            texts += [left, right]
            cell_xml = para(left, tight) + (para(props=tight, runs='') + blank if index == 2 and hidden else para(props=tight, runs='') if index == 2 else '')
            rows.append(exact_row(300, [cell_xml, para(right, tight)]))
        texts.append('HiddenAfter The ledger continues below the table.')
        add('tables-row-height-' + name, 'tables',
            'Exact 15pt rows; the second row cell ' + ('holds three paragraphs, the third wholly hidden by the row height' if hidden else 'holds two paragraphs, the second partly hidden'),
            texts, exact_table(rows) + para(texts[-1], tight), sect=section().replace('w:footer="720"', 'w:footer="720" w:gutter="0"'), styles_xml=row_styles,
            assertions=[{'type': 'marker-reference-position', 'version': 1, 'marker': marker, 'tolerancePt': 0.5} for marker in ('Hidden03', 'HiddenAfter')])
    for name, only in [('exact-zero-borderless', False), ('exact-zero-only', True)]:
        texts = ['ZeroBefore The register opens above the table.']
        rows = []
        for index in range(1, 4):
            if only or index == 2:
                rows.append(exact_row(0, [blank, blank]))
            else:
                left, right = f'Zero{index:02d} Rowan record.', f'Entry{index:02d} Visible cell.'
                texts += [left, right]
                rows.append(exact_row(360, [para(left, tight), para(right, tight)], rule='atLeast'))
        texts.append('ZeroAfter The register continues below the table.')
        body = para(texts[0], tight) + exact_table(rows, '<w:tblBorders>' + ''.join(f'<w:{side} w:val="nil"/>' for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV')) + '</w:tblBorders>') + para(texts[-1], tight)
        add('tables-row-height-' + name, 'tables',
            'Borderless table ' + ('made only of exact zero-height rows' if only else 'with one exact zero-height row between two visible rows'),
            texts, body, sect=section().replace('w:footer="720"', 'w:footer="720" w:gutter="0"'), styles_xml=row_styles,
            assertions=[{'type': 'marker-reference-position', 'version': 1, 'marker': 'ZeroAfter', 'tolerancePt': 0.5}]
            + ([] if only else [{'type': 'marker-reference-position', 'version': 1, 'marker': 'Zero03', 'tolerancePt': 0.5}]))
    # Docxodus #1339: reuse the original Word-adjudicated row fixtures from 7851026. Times
    # New Roman throughout, so a Word capture keeps the declared family and can be eligible.
    rg_font = 'Times New Roman'
    rg_styles = (f'<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="{rg_font}" w:hAnsi="{rg_font}" w:cs="{rg_font}"/>'
                 '<w:sz w:val="22"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:widowControl w:val="0"/><w:spacing w:before="0" w:after="0" w:line="320" w:lineRule="exact"/>'
                 '</w:pPr></w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style></w:styles>')
    rg_sect = section().replace('w:footer="720"', 'w:footer="720" w:gutter="0"')
    def rg_borders(on):
        sides = ('top', 'left', 'bottom', 'right', 'insideH', 'insideV')
        if on:
            return '<w:tblBorders>' + ''.join(f'<w:{s} w:val="single" w:sz="8" w:space="0" w:color="000000"/>' for s in sides) + '</w:tblBorders>'
        return '<w:tblBorders>' + ''.join(f'<w:{s} w:val="nil"/>' for s in sides) + '</w:tblBorders>'
    def rg_cell(body, width):
        return f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/></w:tcPr>{body}</w:tc>'
    def rg_row(cells, height=None, rule='exact', header=False):
        props = '' if height is None else (f'<w:trHeight w:hRule="{rule}"/>' if height == 'absent' else f'<w:trHeight w:val="{height}" w:hRule="{rule}"/>')
        props += '<w:tblHeader/>' if header else ''
        return '<w:tr>' + ('<w:trPr>' + props + '</w:trPr>' if props else '') + ''.join(cells) + '</w:tr>'
    def rg_table(rows, widths, bordered, margins):
        return (f'<w:tbl><w:tblPr><w:tblW w:w="{sum(widths)}" w:type="dxa"/>{rg_borders(bordered)}<w:tblLayout w:type="fixed"/>'
                '<w:tblCellMar>' + ''.join(f'<w:{s} w:w="{m}" w:type="dxa"/>' for s, m in zip(('top', 'left', 'bottom', 'right'), margins)) + '</w:tblCellMar>'
                '</w:tblPr><w:tblGrid>' + ''.join(f'<w:gridCol w:w="{w}"/>' for w in widths) + '</w:tblGrid>' + ''.join(rows) + '</w:tbl>')
    side_margins, no_margins = ('0', '108', '0', '108'), ('0', '0', '0', '0')
    def rg_add(case_id, description, texts, body, sect=rg_sect, clipped=None):
        markers = [t.split()[0] for t in texts]
        add(case_id, 'tables', description, texts, body, sect=sect, styles_xml=rg_styles, font=rg_font,
            assertions=[{'type': 'marker-reference-position', 'version': 1, 'marker': m, 'tolerancePt': 0.5} for m in markers])
        if clipped:
            cases[-1]['clippedTokens'] = clipped
    # #1339: an exact row of height 0 (or with no height stated) is laid out at its content height;
    # the control's positive exact heights, down to one twip, still clip.
    def zero_case(case_id, description, variants):
        texts, body, clipped = [], '', {}
        for label, height, bordered, lines, hidden in variants:
            def two(prefix, count, line=None):
                cells = []
                for side in ('L', 'R'):
                    words = [f'{label}{prefix}{i}{side}' for i in range(1, count + 1)]
                    content = ''.join(para(w, exact(line)) if line else para(w) for w in words) if count else para(runs=run(' '))
                    cells.append(rg_cell(content, 4000))
                    texts.extend(words[:1] if hidden else words)
                    if hidden:
                        clipped.update({w: 1 for w in words[1:]})
                return cells
            texts.append(f'{label}Before')
            rows = [rg_row(two('Top', 1), 360, 'atLeast'), rg_row(two('Mid', lines, 320 if hidden else None), height),
                    rg_row(two('Bot', 1), 360, 'atLeast')]
            texts.append(f'{label}After')
            body += para(f'{label}Before') + rg_table(rows, [4000, 4000], bordered, side_margins) + para(f'{label}After')
        rg_add(case_id, description, texts, body, clipped=clipped or None)
    zero_case('tables-row-height-exact-zero-content-times-new-roman',
              'Exact rows of height 0 or with no height, one and three lines, borderless and bordered, between atLeast rows (Docxodus #1339)',
              [('Alpha', 0, False, 1, False), ('Bravo', 0, True, 1, False), ('Charlie', 0, False, 3, False), ('Kilo', 'absent', True, 1, False)])
    zero_case('tables-row-height-exact-tiny-control-times-new-roman',
              'Control: exact rows of one twip (empty) and eight points (three lines, two hidden) clip to their height (Docxodus #1339)',
              [('Echo', 1, False, 0, False), ('Foxtrot', 1, True, 0, False), ('Lima', 160, True, 3, True)])
    # #1201: a zero-width first grid column (zero tcW, zero cell margins, fixed layout). Its cells
    # hold empty paragraphs, so the case asserts the layout and the export, not clipped glyphs.
    for case_id, width, description in [('tables-zero-width-column-times-new-roman', 0, 'A zero-width first column'),
                                        ('tables-zero-width-column-control-times-new-roman', 480, 'Control: a 24pt first column')]:
        texts, body = [], ''
        for label, height, rule, bordered in [('Alder', 360, 'exact', False), ('Birch', 360, 'atLeast', False), ('Dogwood', 360, 'exact', True)]:
            texts += [f'{label}Before table.', f'{label}Wide cell.', f'{label}After table.']
            body += para(texts[-3]) + rg_table([rg_row([rg_cell(para(runs=''), width), rg_cell(para(texts[-2]), 5400 - width)], height, rule)],
                                               [width, 5400 - width], bordered, no_margins) + para(texts[-1])
        rg_add(case_id, description + ' in exact and atLeast 18pt rows, borderless and bordered (Docxodus #1201)', texts, body)
    # Docxodus #1171: a repeated header row with exact and atLeast rules, and a bordered paragraph
    # inside an exact row. Header text repeats once per page, so it is counted, not used as a marker.
    for rule in ('exact', 'atLeast'):
        texts, rows = [], [exact_row(400, [para('HeaderLeft Ledger column.', tight), para('HeaderRight Entry column.', tight)], rule=rule, header=True)]
        for index in range(1, 61):
            left, right = f'Cedar{index:02d} Repeated ledger.', f'Entry{index:02d} Header table.'
            texts += [left, right]
            rows.append(exact_row(360, [para(left, tight), para(right, tight)]))
        texts += ['HeaderLeft Ledger column.', 'HeaderRight Entry column.'] * 2
        add('tables-header-repeat-' + rule.lower(), 'tables', f'Sixty exact rows under a repeated {rule} header row across two pages',
            texts, exact_table(rows), sect=section().replace('w:footer="720"', 'w:footer="720" w:gutter="0"'), styles_xml=row_styles,
            assertions=[{'type': 'marker-reference-position', 'version': 1, 'marker': marker, 'tolerancePt': 0.5} for marker in ('Cedar01', 'Cedar35', 'Cedar60')])
    for rule in ('exact', 'atLeast'):
        boxed = '<w:pBdr>' + ''.join(f'<w:{side} w:val="single" w:sz="12" w:space="2" w:color="246B7D"/>' for side in ('top', 'left', 'bottom', 'right')) + '</w:pBdr><w:spacing w:after="0"/>'
        texts = ['BoxClip Juniper card.', 'BoxCell Neighbour cell.', 'BoxAfter The card register continues.']
        cell_xml = para(props=boxed, runs=run(texts[0] + ' ') + '<w:r><w:br/></w:r><w:r><w:br/></w:r>' + run('   '))
        body = exact_table([exact_row(360, [cell_xml, para(texts[1], tight)], rule=rule)]) + para(texts[2], tight)
        add('tables-row-height-' + ('exact' if rule == 'exact' else 'atleast') + '-border-clip', 'tables',
            f'Three-line bordered paragraph in an 18pt {rule} row' + (', clipped by the row height with side borders kept; border clipping is measured by the raster score only' if rule == 'exact' else ' (control: the row grows)'),
            texts, body, sect=section().replace('w:footer="720"', 'w:footer="720" w:gutter="0"'), styles_xml=row_styles,
            assertions=[{'type': 'marker-reference-position', 'version': 1, 'marker': marker, 'tolerancePt': 0.5} for marker in ('BoxClip', 'BoxAfter')])
    # Docxodus #1178-#1182: footnote layout around long and carried notes. Every body and note line
    # is an exact 18pt line, so a 648pt body band holds 36 lines.
    note_props = exact(360)
    def reference(number):
        return ' <w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:footnoteReference w:id="' + str(number) + '"/></w:r>'
    def note(prefix, count, keep=False):
        lines = [f'{prefix}{i:03d} Spruce note line.' for i in range(1, count + 1)]
        props = note_props + ('<w:keepLines/>' if keep else '')
        if keep:
            content = para(props=props, runs='<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:footnoteRef/></w:r>' + run(' ') + '<w:r><w:br/></w:r>'.join(run(x) for x in lines))
        else:
            content = ''.join(para(props=props, runs=('<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:footnoteRef/></w:r>' + run(' ') if i == 0 else '') + run(x)) for i, x in enumerate(lines))
        return lines, content
    def cite(text, number):
        return para(props=note_props, runs=run(text + ' ').replace('</w:t></w:r>', '</w:t></w:r>', 1).rstrip() + reference(number).strip())
    def body_lines(prefix, count):
        lines = [f'{prefix}{i:02d} Spruce body line.' for i in range(1, count + 1)]
        return lines, ''.join(para(x, note_props) for x in lines)
    note_section = section().replace('w:footer="720"', 'w:footer="720" w:gutter="0"')
    # #1217: the mandatory empty paragraph after a nested table is structural. A synthetic
    # full-size blank run there used to protrude from an otherwise fitting footnote's band.
    body_text = [f'WillowBody{i:02d} Reed ledger line.' for i in range(1, 62)]
    note_text = [f'WillowNote{i:02d} Reed note row.' for i in range(1, 4)]
    note_rows = [para(props=note_props, runs=(
        '<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:footnoteRef/></w:r>'
        + run(' ') if i == 0 else '') + run(text)) for i, text in enumerate(note_text)]
    def note_table(contents, columns=1):
        width = 4320 // columns
        return ('<w:tbl><w:tblPr><w:tblW w:w="4320" w:type="dxa"/>'
                '<w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid>' + f'<w:gridCol w:w="{width}"/>' * columns
                + '</w:tblGrid>' + ''.join('<w:tr>' + ''.join(
                    f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/></w:tcPr>' + cell + '</w:tc>'
                    for cell in ([content] if isinstance(content, str) else content))
                    + '</w:tr>' for content in contents) + '</w:tbl>')
    # The reference importer needs a paragraph after a footnote table. Its one-twip line
    # avoids padding away the nested cell's overflowing synthetic blank on unfixed renderers.
    note_table_tail = '<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="1" w:lineRule="exact"/><w:rPr><w:sz w:val="2"/></w:rPr></w:pPr></w:p>'
    for nested in (False, True):
        content = note_table(note_rows)
        if nested:
            content = note_table([content + '<w:p/>'])
        add('notes-fitting-' + ('nested-table' if nested else 'table-control'), 'notes',
            'Three-row footnote table' + (' nested in a cell with an unformatted structural tail paragraph'
                                         if nested else ' without an enclosing table (control)'),
            body_text + ['1', '1'] + note_text,
            cite(body_text[0], 1) + ''.join(para(text, note_props) for text in body_text[1:]),
            sect=note_section, styles_xml=ledger_styles, footnote_list=[(1, content + note_table_tail)],
            assertions=[{'type': 'same-page', 'version': 1,
                         'markers': ['WillowBody01', 'WillowNote01', 'WillowNote03']}])
    # Whole rows are the control for nesting, and three lines control each oversized cell shape.
    for name, count, nested, packed, columns, wrapped in [
            ('nested', 80, True, False, 1, False), ('rows-control', 80, False, False, 1, False),
            ('tall-row', 80, False, True, 1, False), ('tall-row-control', 3, False, True, 1, False),
            ('nested-wrapped', 80, True, True, 2, True), ('nested-wrapped-control', 3, True, True, 2, True),
            ('row-wrapped', 80, False, True, 2, True), ('row-wrapped-control', 3, False, True, 2, True)]:
        lines = [[f'Pine{col + 1}N{i:03d} Row.' for i in range(1, count + 1)] for col in range(columns)]
        paragraphs = []
        for col, labels in enumerate(lines):
            ref = ('<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:footnoteRef/></w:r>'
                   + run(' ') if col == 0 else '')
            paragraphs.append([para(props=note_props, runs=ref + '<w:r><w:br/></w:r>'.join(run(x) for x in labels))]
                              if wrapped else [para(props=note_props, runs=(ref if i == 0 else '') + run(text))
                                               for i, text in enumerate(labels)])
        contents = [[''.join(items) for items in paragraphs]] if packed else list(zip(*paragraphs))
        content = note_table(contents, columns)
        if nested:
            content = note_table([content + '<w:p/>'])
        # Literal page membership from the independently captured Word inputs. All body and
        # note markers bind candidates; the existing adjudication policy keeps LO calibration
        # distinct from Word layout rather than changing any scorer or tolerance.
        word_pages = {f'WillowBody{i:02d}': (1 if i == 1 else 3 if i <= 25 else 4)
                      if count == 80 else (1 if i <= 32 else 2) for i in range(1, 62)}
        word_pages.update({f'Pine{col + 1}N{i:03d}': (1 if i <= 34 else 2 if i <= 69 else 3)
                           if count == 80 else 1 for col in range(columns) for i in range(1, count + 1)})
        add('notes-table-flow-' + name + '-times-new-roman', 'notes',
            f'{count} lines in a {columns}-cell footnote table with '
            + ('one wrapped paragraph per cell' if wrapped else 'separate paragraphs')
            + (' inside a nested table' if nested else '') + (' (control)' if 'control' in name else ''),
            body_text + ['1', '1'] + [text for labels in lines for text in labels],
            cite(body_text[0], 1) + ''.join(para(text, note_props) for text in body_text[1:]),
            sect=note_section, styles_xml=ledger_styles.replace(FONT, 'Times New Roman'),
            font='Times New Roman', footnote_list=[(1, content + note_table_tail)],
            assertions=[{'type': 'same-page', 'version': 1,
                         'markers': ['WillowBody01'] + [labels[0].split()[0] for labels in lines]}]
                + [{'type': 'marker-region', 'version': 2, 'marker': marker, 'occurrence': 1,
                    'page': page, 'rect': [60, 60, 552, 732], 'adjudicated': 'word'}
                   for marker, page in word_pages.items()])
    # #1178: a note that fills nearly a whole page under its citing line, cited first and mid-page.
    for name, before in [('notes-tall-note-first-line', 0), ('notes-tall-note-mid-page', 10)]:
        lead, lead_xml = body_lines('TallLead', before)
        tall, tall_xml = note('TallNote', 70)
        after, after_xml = body_lines('TallBody', 30)
        texts = lead + ['TallCite Spruce register cites the tall note.', '1', '1'] + tall + after
        body = lead_xml + cite('TallCite Spruce register cites the tall note.', 1) + after_xml
        keep_line = 30 if before == 0 else 23
        add(name, 'notes', f'Seventy-line footnote cited on body line {before + 1}; the note fills nearly all of the rest of page 1',
            texts, body, sect=note_section, styles_xml=ledger_styles, footnote_list=[(1, tall_xml)],
            assertions=[{'type': 'marker-region', 'version': 2, 'marker': f'TallNote{keep_line:03d}', 'occurrence': 1, 'page': 1, 'rect': [60, 60, 552, 760]},
                        {'type': 'marker-reference-position', 'version': 1, 'marker': 'TallBody01', 'tolerancePt': 0.5},
                        {'type': 'marker-reference-position', 'version': 1, 'marker': 'TallNote070', 'tolerancePt': 0.5}])
    # Note text markers are taken from a note's second or later line: the first line begins with the
    # note number, whose superscript width differs between providers.
    # #1179: once a note continues onto the next page, no later note starts below it on its page.
    for name, long_count in [('notes-continued-note-last', 30), ('notes-continued-note-last-control', 4)]:
        lead, lead_xml = body_lines('SplitLead', 20)
        a_lines, a_xml = note('SplitNoteA', long_count)
        b_lines, b_xml = note('ShortNoteB', 2)
        after, after_xml = body_lines('SplitBody', 30)
        texts = lead + ['SplitCiteA Spruce register cites the long note.', '1', '1', 'SplitCiteB Spruce register cites the short note.', '2', '2'] + a_lines + b_lines + after
        body = lead_xml + cite('SplitCiteA Spruce register cites the long note.', 1) + cite('SplitCiteB Spruce register cites the short note.', 2) + after_xml
        last = a_lines[-1].split()[0]
        assertions = [{'type': 'marker-reference-position', 'version': 1, 'marker': marker, 'tolerancePt': 0.5} for marker in ('SplitCiteB', 'ShortNoteB002', last, 'SplitBody01')]
        if long_count > 4:
            assertions.append({'type': 'same-page', 'version': 1, 'markers': [last, 'ShortNoteB002']})
        add(name, 'notes', 'Two citations on page 1: a ' + ('thirty-line note that continues onto page 2' if long_count > 4 else 'four-line note that fits') + ', then a two-line note',
            texts, body, sect=note_section, styles_xml=ledger_styles, footnote_list=[(1, a_xml), (2, b_xml)], assertions=assertions)
    # #1182: a carried note that does not end on a page; later citations wait for its end.
    a_lines, a_xml = note('CarriedNote', 90)
    b_lines, b_xml = note('DeferredNoteB', 2)
    c_lines, c_xml = note('DeferredNoteC', 2)
    after, after_xml = body_lines('CarriedBody', 12)
    texts = ['CarriedCite Spruce register cites the carried note.', '1', '1', 'DeferredCiteB Spruce register cites a deferred note.', '2', '2',
             'DeferredCiteC Spruce register cites another deferred note.', '3', '3'] + a_lines + b_lines + c_lines + after
    body = (cite('CarriedCite Spruce register cites the carried note.', 1) + cite('DeferredCiteB Spruce register cites a deferred note.', 2)
            + cite('DeferredCiteC Spruce register cites another deferred note.', 3) + after_xml)
    # In Word reference PDFs, the citing paragraphs after a carried note start, with their notes, on
    # the page where the carried note ends; the page between holds only the continuation. LibreOffice
    # 25.8.7.3 places the first deferred citation beside the running continuation instead.
    word = {'adjudicated': 'word'}
    add('notes-carried-note-defers-citations', 'notes', 'Ninety-line note carried across pages; two later citations and their two-line notes follow it where the carried note ends (Word-adjudicated)',
        texts, body, sect=note_section, styles_xml=ledger_styles, footnote_list=[(1, a_xml), (2, b_xml), (3, c_xml)],
        assertions=[{'type': 'marker-region', 'version': 2, 'marker': 'CarriedCite', 'occurrence': 1, 'page': 1, 'rect': [60, 60, 552, 760]},
                    dict({'type': 'same-page', 'version': 1, 'markers': ['CarriedNote090', 'DeferredCiteB', 'DeferredNoteB002']}, **word),
                    {'type': 'same-page', 'version': 1, 'markers': ['DeferredCiteC', 'DeferredNoteC002']},
                    dict({'type': 'marker-region', 'version': 2, 'marker': 'DeferredCiteB', 'occurrence': 1, 'page': 3, 'rect': [60, 60, 552, 760]}, **word)])
    # #1180: a keep-with-next heading and the paragraph it keeps, near the foot of a page whose note
    # continues onto the next one. The kept pair must share a page.
    note_count, chain_lines = 30, 1
    lead, lead_xml = body_lines('KeepLead', 30)
    a_lines, a_xml = note('KeepCarried', note_count)
    b_lines, b_xml = note('KeepNoteTwo', 2)
    after, after_xml = body_lines('KeepTail', 40)
    heading = 'KeepHeading Spruce section heading.'
    chain = [f'KeepFollow{i:02d} Spruce kept paragraph line.' for i in range(1, chain_lines + 1)]
    texts = lead + ['KeepCite Spruce register cites the carried note.', '1', '1', heading] + chain + ['2', '2'] + a_lines + b_lines + after
    chain_xml = para(props=note_props + '<w:keepLines/>', runs='<w:r><w:br/></w:r>'.join(run(x) for x in chain) + reference(2))
    body = lead_xml + cite('KeepCite Spruce register cites the carried note.', 1) + para(heading, note_props + '<w:keepNext/>') + chain_xml + after_xml
    add('notes-keep-next-beside-continuation', 'notes', 'Keep-with-next heading and a one-line kept paragraph citing a two-line note after a thirty-line note cited on line 31',
        texts, body, sect=note_section, styles_xml=ledger_styles, footnote_list=[(1, a_xml), (2, b_xml)],
        assertions=[{'type': 'same-page', 'version': 1, 'markers': ['KeepHeading', 'KeepFollow01']}]
        + [{'type': 'marker-reference-position', 'version': 1, 'marker': marker, 'tolerancePt': 0.5} for marker in ('KeepHeading', 'KeepNoteTwo002', 'KeepTail01')])
    # A table row citing a keep-lines note too tall for the rest of the page.
    lead, lead_xml = body_lines('TableLead', 30)
    after, after_xml = body_lines('TableTail', 8)
    cell_xml = cite('TableCite Spruce row cites a kept note.', 1)
    table_xml = ('<w:tbl><w:tblPr><w:tblW w:w="9360" w:type="dxa"/>' + exact_borders + '<w:tblLayout w:type="fixed"/></w:tblPr>'
                 '<w:tblGrid><w:gridCol w:w="9360"/></w:tblGrid><w:tr><w:tc><w:tcPr><w:tcW w:w="9360" w:type="dxa"/></w:tcPr>' + cell_xml + '</w:tc></w:tr></w:tbl>')
    # Word reference PDFs move the citing row to the next page with its kept note; LibreOffice keeps
    # the row on page 1 and sends the note on alone.
    for count, name in [(12, 'notes-keep-lines-note-in-table'), (2, 'notes-keep-lines-table-fitting-control')]:
        a_lines, a_xml = note('TableKeepNote', count, keep=True)
        texts = lead + ['TableCite Spruce row cites a kept note.', '1', '1'] + a_lines + after
        pairing = {'type': 'same-page', 'version': 1, 'markers': ['TableCite', 'TableKeepNote002', 'TableTail01']}
        if count == 12:
            pairing['adjudicated'] = 'word'
        control_page = [] if count == 12 else [
            {'type': 'marker-region', 'version': 2, 'marker': 'TableCite', 'occurrence': 1, 'page': 1, 'rect': [60, 60, 552, 760]}]
        add(name, 'notes', ('Table row on body line 31 citing a twelve-line keep-lines note that does not fit below it; the row moves to the note\'s page (Word-adjudicated)' if count == 12 else
                           'Control for Docxodus #1217: the table row and its two-line kept note fit together on page 1'),
            texts, lead_xml + table_xml + after_xml, sect=note_section, styles_xml=ledger_styles, footnote_list=[(1, a_xml)],
            assertions=[{'type': 'same-page', 'version': 1, 'markers': ['TableKeepNote001', f'TableKeepNote{count:03d}']},
                        {'type': 'marker-region', 'version': 2, 'marker': 'TableLead30', 'occurrence': 1, 'page': 1, 'rect': [60, 60, 552, 760]}, pairing] + control_page)
    # Original decoration pairs for Docxodus #1220. Raster measurements, rather than text
    # inventories, distinguish line count, pattern and color; each reproducer has a simple control.
    decoration_styles = f'<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}"/><w:color w:val="000000"/><w:sz w:val="40"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:widowControl/><w:spacing w:after="120"/></w:pPr></w:pPrDefault></w:docDefaults></w:styles>'
    decoration_pairs = [
        ('double-underline', '<w:u w:val="double"/>', '<w:u w:val="single"/>'),
        ('double-strike', '<w:dstrike/>', '<w:strike/>'),
        ('underline-and-strike', '<w:strike/><w:u w:val="single"/>', '<w:u w:val="single"/>'),
        ('dotted-blue-underline', '<w:u w:val="dotted" w:color="0000FF"/>', '<w:u w:val="single" w:color="0000FF"/>'),
    ]
    for label, repro, control in decoration_pairs:
        for suffix, properties in [('', repro), ('-control', control)]:
            texts = ['CedarRule The archive crew labels each cedar tray.',
                     'PlainRule The next tray awaits inspection.']
            body = para(runs=run(texts[0], properties)) + para(texts[1])
            add('decoration-' + label + suffix, 'paragraphs',
                label.replace('-', ' ').title() + (' simpler control' if suffix else ' reproduction (Docxodus #1220)'),
                texts, body, styles_xml=decoration_styles)
    # Word-style revision bars use the text column as their origin, including zero indent.
    change_bar_styles = f'<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}"/><w:color w:val="000000"/><w:sz w:val="22"/></w:rPr></w:rPrDefault></w:docDefaults></w:styles>'
    for case_id, indent in [('revision-change-bar-zero-indent', 0), ('revision-change-bar-indented-control', 720)]:
        original, inserted = 'CedarBar The crew ', 'updates the cedar ledger.'
        insertion = '<w:ins w:id="1" w:author="Cedar Reviewer" w:date="2026-09-10T12:00:00Z">' + run(inserted) + '</w:ins>'
        body = para(props=f'<w:ind w:left="{indent}"/>', runs=run(original) + insertion)
        add(case_id, 'paragraphs', 'Word-style revision bar with ' + ('zero indent (Docxodus #1221)' if indent == 0 else 'half-inch indent control'),
            [original + inserted], body, styles_xml=change_bar_styles)
        cases[-1]['profile'] = {'review': 'markup', 'comments': 'hidden', 'markupPresentation': 'word'}
    # The bold-only revision inherits its font/size; the control states the same values explicitly.
    format_styles = f'<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}"/><w:sz w:val="24"/></w:rPr></w:rPrDefault></w:docDefaults></w:styles>'
    fonts = f'<w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}"/>'
    size = '<w:sz w:val="24"/>'
    for case_id, explicit in [('revision-label-inherited-font', False), ('revision-label-explicit-font-control', True)]:
        text = 'FormatLabel The cedar ledger is ready.'
        current = fonts + '<w:b/>' + size if explicit else '<w:b/>'
        previous = fonts + size if explicit else ''
        revision = '<w:rPrChange w:id="1" w:author="Cedar Reviewer" w:date="2026-09-10T12:00:00Z"><w:rPr>' + previous + '</w:rPr></w:rPrChange>'
        add(case_id, 'paragraphs', 'Bold-only formatting revision with ' + ('explicit matching font and size control' if explicit else 'inherited font and size (Docxodus #1222)'),
            [text], para(runs=run(text, current + revision)), styles_xml=format_styles)
        cases[-1]['profile'] = {'review': 'markup', 'comments': 'hidden'}
        cases[-1]['htmlAssertions'] = [{'type': 'marker-attribute', 'version': 1, 'marker': 'FormatLabel', 'attribute': 'title', 'equals': 'Bold added'}]
    # Docxodus #1271: one 10pt footnote line whose only run carries a pending formatting revision,
    # measured in markup view, and a control without the w:rPrChange. Docxodus underlines the
    # revised run with a border that hung below the note band, and its export refused the
    # document as clipped. Both notes must appear in full in the footnote area of page 1.
    note_run_props = f'<w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}"/><w:sz w:val="20"/>'
    for case_id, revised in [('notes-format-revision-markup', True), ('notes-format-revision-markup-control', False)]:
        cite_text, note_text = 'NoteCite Receiver maintenance', 'NoteQuartz A spare quartz plate remains in the cabinet.'
        revision = '<w:rPrChange w:id="31" w:author="Cedar Reviewer" w:date="2026-09-12T10:00:00Z"><w:rPr><w:i/></w:rPr></w:rPrChange>' if revised else ''
        note_xml = para(props='<w:spacing w:after="0" w:line="240" w:lineRule="auto"/>',
                        runs=f'<w:r><w:rPr>{note_run_props}<w:vertAlign w:val="superscript"/></w:rPr><w:footnoteRef/></w:r>' + run(' ' + note_text, note_run_props + revision))
        body = para(runs=run(cite_text) + '<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:footnoteReference w:id="1"/></w:r>')
        add(case_id, 'notes', ('One-line footnote whose run carries a formatting revision, in markup view (Docxodus #1271)' if revised else
                               'Control: the same one-line footnote without the formatting revision, in markup view'),
            [cite_text, '1', '1', note_text], body, notes=('footnote', note_text), notes_xml=note_xml,
            assertions=[{'type': 'marker-region', 'version': 1, 'marker': 'NoteQuartz', 'occurrence': 1, 'page': 1, 'rect': [60, 650, 552, 750]},
                        {'type': 'same-page', 'version': 1, 'markers': ['NoteCite', 'NoteQuartz']}])
        cases[-1]['profile'] = {'review': 'markup', 'comments': 'hidden'}
    # Original numbered heading with a hidden paragraph mark, and visible-mark control.
    mark_styles = f'<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}"/><w:sz w:val="24"/></w:rPr></w:rPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style><w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/></w:rPr></w:style></w:styles>'
    mark_numbering = f'<w:numbering xmlns:w="{W}"><w:abstractNum w:abstractNumId="1"><w:multiLevelType w:val="singleLevel"/><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:suff w:val="space"/><w:lvlText w:val="%1."/></w:lvl></w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="1"/></w:num></w:numbering>'
    for case_id, hidden in [('paragraph-mark-hidden-numbered-heading', True), ('paragraph-mark-visible-numbered-control', False)]:
        heading, following = 'CedarHeading.', 'CedarBody Return the archive folder before dusk.'
        props = '<w:pStyle w:val="Heading2"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr><w:rPr><w:vanish w:val="' + ('1' if hidden else '0') + '"/></w:rPr>'
        add(case_id, 'paragraphs', 'Numbered heading with ' + ('hidden paragraph mark (Docxodus #1223)' if hidden else 'explicitly visible paragraph mark control'),
            ['1.', heading, following], para(heading, props) + para(' ' + following), styles_xml=mark_styles, numbering_xml=mark_numbering,
            assertions=[{'type': 'marker-reference-position', 'version': 1, 'marker': marker, 'tolerancePt': 0.5} for marker in ('CedarHeading.', 'CedarBody')])
    # Docxodus #1294: three run-in sections, each a heading whose hidden paragraph mark joins it to
    # the body paragraph after it. The heading carries keepNext and keepLines; the closing body
    # paragraph keeps its lines but not its block with the next one. Each section is three lines (the
    # heading shares the first) and 26 lead lines leave room for exactly two. The layout asserted is
    # the one Docxodus #1294 specifies: the closing paragraph's properties govern the joined block, so
    # two sections stay on page 1 and the third starts page 2. LibreOffice 25.8.7.3 applies the
    # heading's keepNext to the block and chains all three onto page 2; Word adjudication is pending.
    # The control gives the headings no keep properties, so the same split holds under either reading.
    run_in_lead = [f'AlderLead{i:02d} register retained.' for i in range(1, 27)]
    run_in_names = ['RunInAlder', 'RunInBirch', 'RunInCedar']
    for case_id, trigger in [('paragraph-mark-hidden-run-in-keep', True), ('paragraph-mark-hidden-run-in-keep-control', False)]:
        heading_keep = '<w:keepNext/><w:keepLines/>' if trigger else ''
        body = para(props=line_properties, runs='<w:r><w:br/></w:r>'.join(run(t) for t in run_in_lead))
        texts = list(run_in_lead)
        for name in run_in_names:
            lines = [f' {name}Body{i} clause text retained.' for i in range(1, 4)]
            body += para(f'{name}.', heading_keep + line_properties + '<w:rPr><w:b/><w:vanish/></w:rPr>')
            body += para(props='<w:keepLines/>' + line_properties, runs='<w:r><w:br/></w:r>'.join(run(t) for t in lines))
            texts += [f'{name}.'] + lines
        body += para('RunInClose', line_properties)
        add(case_id, 'paragraphs',
            'Run-in sections joined by hidden paragraph marks; ' + ('headings carry keepNext and keepLines, the closing paragraphs govern the block (behaviour specified by Docxodus #1294)'
                                                                       if trigger else 'headings without keep properties (control)'),
            texts + ['RunInClose'], body,
            assertions=[{'type': 'marker-region', 'version': 2, 'marker': marker, 'occurrence': 1,
                         'page': page, 'rect': [72, 60, 540, 720]}
                        for marker, page in [('RunInAlder.', 1), ('RunInBirchBody3', 1), ('RunInCedar.', 2)]])
    # Original manual labels with a hanging indent and two stops, plus a narrow left-tab control.
    tab_styles = f'<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}"/><w:sz w:val="24"/></w:rPr></w:rPrDefault></w:docDefaults></w:styles>'
    tab_entries = [('3.2.', 'CedarTitle01 Sample inventory', '7'),
                   ('3.12.', 'CedarTitle02 Storage schedule', '18'),
                   ('3.13.', 'CedarTitle03 Map register', '104')]
    for case_id, control in [('tabs-hanging-manual-labels', False), ('tabs-left-narrow-label-control', True)]:
        entries = tab_entries[:1] if control else tab_entries
        texts, body, markers = [], '', []
        for label, title, page in entries:
            stops = '<w:tab w:val="left" w:pos="1800"/>'
            if not control: stops += '<w:tab w:val="right" w:leader="dot" w:pos="9000"/>'
            props = '<w:tabs>' + stops + '</w:tabs><w:spacing w:after="0" w:line="240" w:lineRule="exact"/><w:ind w:left="1800" w:hanging="720"/>'
            content = run(label) + '<w:r><w:tab/></w:r>' + run(title + ' ')
            if not control: content += '<w:r><w:tab/></w:r>' + run(' ' + page)
            body += para(props=props, runs=content)
            texts += [label, title] + ([] if control else [page])
            markers += [title.split()[0]] + ([] if control else [page])
        add(case_id, 'paragraphs', 'Narrow manual label with a single left title tab control' if control else
            'Three manual labels with hanging indentation, a left title stop and right page-number stop with dot leader (Docxodus #1224)',
            texts, body, styles_xml=tab_styles,
            assertions=[{'type': 'marker-reference-position', 'version': 1, 'marker': marker,
                         'tolerancePt': 0.5} for marker in markers])
        if not control: cases[-1]['pdfTextNormalization'] = 'isolated-dot-leaders-v1'
    # Docxodus #1269: one paragraph whose three tabs fall on automatic stops, under a 12-twip or a
    # zero w:defaultTabStop, and a 720-twip control; the cases differ only in that value. The lead text
    # runs past 1,200 twips, the hundredth 12-twip stop. A space before each tab keeps the words
    # separate in PDF text extraction when a 12-twip stop leaves almost no gap.
    interval_runs = run('TabLead observatory inventory ') + '<w:r><w:tab/></w:r>' + run('TabNorth ') + '<w:r><w:tab/></w:r>' + run('TabEast ') + '<w:r><w:tab/></w:r>' + run('TabSouth ') + run('Copper lens.')
    interval_texts = ['TabLead observatory inventory', 'TabNorth', 'TabEast', 'TabSouth', 'Copper lens.']
    # A correct 12-twip tab advances under 0.6pt, so position cannot tell it from a dropped one; that
    # case catches a conversion failure and a half-inch fallback: each word must end before it would
    # on the half-inch grid, and start no more than 3pt left of the reference. A zero interval has no
    # automatic stops: Word for the web gives each tab no width (docs/results/default-tab-interval-word.md),
    # while LibreOffice uses its 1.25cm default. The Word-adjudicated zero case requires each word to
    # start no more than 3pt left of its zero-width position and at least 4pt before LibreOffice's
    # 1.25cm stop (half-inch stops lie further right). Where on the fine grid, or how close to the
    # preceding word, a word lands depends on the renderer's text measurement, which the raster score
    # measures. The control follows the reference.
    def interval_assertions(interval):
        if interval == 720:
            return [{'type': 'marker-reference-position', 'version': 1, 'marker': marker, 'tolerancePt': 0.5}
                    for marker in ('TabNorth', 'TabEast', 'TabSouth')]
        if interval == 12:
            return [{'type': 'marker-region', 'version': 2, 'marker': marker, 'occurrence': 1, 'page': 1, 'rect': [left, 60, right, 100]}
                    for marker, left, right in [('TabNorth', 223, 297), ('TabEast', 273, 362), ('TabSouth', 316, 441)]]
        return [{'type': 'marker-region', 'version': 2, 'marker': marker, 'occurrence': 1, 'page': 1, 'rect': [left, 60, right, 100], 'adjudicated': 'word'}
                for marker, left, right in [('TabNorth', 223, 292), ('TabEast', 273, 355), ('TabSouth', 316, 433)]]
    for case_id, interval, description in [
            ('tabs-default-interval-12', 12, 'Three tabs on automatic stops with a 12-twip default tab interval (Docxodus #1269)'),
            ('tabs-default-interval-0', 0, 'Three tabs on automatic stops with a zero default tab interval (Docxodus #1269)'),
            ('tabs-default-interval-720-control', 720, 'Three tabs on automatic stops with the half-inch default tab interval (control)')]:
        add(case_id, 'paragraphs', description, interval_texts,
            para(props='<w:spacing w:after="0" w:line="240" w:lineRule="exact"/>', runs=interval_runs), styles_xml=tab_styles,
            extra_parts={'word/settings.xml': f'<w:settings xmlns:w="{W}"><w:defaultTabStop w:val="{interval}"/>{SETTINGS_BODY}</w:settings>'},
            assertions=interval_assertions(interval))
    # #1275: leader lines whose right stop lies inside the right indent, and leader lines whose
    # entries carry inert markup (empty bookmark, non-breaking hyphen, underlined or struck tab
    # runs). Both share one plain control with neither.
    lead_entries = [('2.1.', 'AlderTitle01 Quarry access roads', '3'),
                    ('2.2.', 'AlderTitle02 Spillway', '12'),
                    ('2.3.', 'AlderTitle03 Culvert inspection and annual load ratings', '27'),
                    ('2.4.', 'AlderTitle04 Riprap', '140')]
    for case_id, kind in [('tabs-right-stop-in-right-indent', 'indent'),
                          ('tabs-right-stop-inline-markup', 'markup'),
                          ('tabs-right-stop-plain-control', 'control')]:
        texts, body, markers = [], '', []
        for i, (label, title, page) in enumerate(lead_entries):
            right = ' w:right="864"' if kind == 'indent' else ''
            props = ('<w:tabs><w:tab w:val="left" w:pos="1296"/><w:tab w:val="right" w:leader="dot" w:pos="9360"/></w:tabs>'
                     '<w:spacing w:after="0" w:line="240" w:lineRule="exact"/>'
                     f'<w:ind w:left="1296"{right} w:hanging="648"/>')
            tab_props = ''
            content = run(label)
            if kind == 'markup':
                tab_props = {2: '<w:u w:val="single"/>', 3: '<w:strike/>'}.get(i, '')
                if i == 0:
                    content = f'<w:bookmarkStart w:id="{i}" w:name="_AlderEntry{i}"/><w:bookmarkEnd w:id="{i}"/>' + content
            tab = f'<w:r><w:rPr>{tab_props}</w:rPr><w:tab/></w:r>'
            content += tab + run(title)
            if kind == 'markup' and i == 1:
                content += '<w:r><w:noBreakHyphen/></w:r>' + run('West')
                title += '-West'
            content += run(' ') + tab + run(' ' + page)
            body += para(props=props, runs=content)
            texts += [label, title, page]
            markers += [title.split()[0], page]
        add(case_id, 'paragraphs', {
            'indent': 'Four leader lines whose right page-number stop lies inside an 864-twip right indent (Docxodus #1275)',
            'markup': 'Four leader lines with an empty bookmark, a non-breaking hyphen, an underlined and a struck tab run (Docxodus #1275)',
            'control': 'Four plain leader lines with no right indent and no inline markup (control)'}[kind],
            texts, body, styles_xml=tab_styles,
            assertions=[{'type': 'marker-reference-position', 'version': 1, 'marker': marker,
                         'tolerancePt': 0.5} for marker in markers])
        cases[-1]['pdfTextNormalization'] = 'isolated-dot-leaders-v1'
    # #1285: four more leader-line shapes, each with an 864-twip right indent as above. Every
    # reproducer has a control that differs from it only in the trigger, except the wrapped titles,
    # whose control is tabs-right-stop-in-right-indent (the same entries with titles that fit).
    def leader_case(case_id, description, entries, stops, number_runs=None, wrap=None, target_pages=False):
        texts, body, markers = [], '', []
        for i, (label, title, page, second) in enumerate(entries):
            props = (f'<w:tabs>{stops(i)}</w:tabs><w:spacing w:after="0" w:line="240" w:lineRule="exact"/>'
                     '<w:ind w:left="1296" w:right="864" w:hanging="648"/>')
            content = run(label) + '<w:r><w:tab/></w:r>' + run(title + ' ') + '<w:r><w:tab/></w:r>'
            content += number_runs(i, page) if number_runs else run(' ' + page)
            if second: content += '<w:r><w:tab/></w:r>' + run(second)
            body += para(props=props, runs=wrap(i, content) if wrap else content)
            texts += [label, title, page] + ([second] if second else [])
            markers += [title.split()[0], title.split()[-1], page] + ([second] if second else [])
        for i in range(len(entries) if target_pages else 0):
            target = f'BirchTarget{i + 1:02d}'
            body += para(props='<w:pageBreakBefore/>', runs=f'<w:bookmarkStart w:id="{20 + i}" w:name="_Birch{i}"/>' + run(target) + f'<w:bookmarkEnd w:id="{20 + i}"/>')
            texts.append(target)
        add(case_id, 'paragraphs', description, texts, body, styles_xml=tab_styles,
            assertions=[{'type': 'marker-reference-position', 'version': 1, 'marker': marker,
                         'tolerancePt': 0.5} for marker in dict.fromkeys(markers)])
        cases[-1]['pdfTextNormalization'] = 'isolated-dot-leaders-v1'
    leader_stops = lambda i: '<w:tab w:val="left" w:pos="1296"/><w:tab w:val="right" w:leader="dot" w:pos="9360"/>'
    birch = [('2.1.', 'BirchTitle01 Quarry access roads', '2', None), ('2.2.', 'BirchTitle02 Spillway', '3', None),
             ('2.3.', 'BirchTitle03 Culvert inspection and annual load ratings', '4', None), ('2.4.', 'BirchTitle04 Riprap', '5', None)]
    # LibreOffice recomputes the field's result, so the space before it is a run of its own.
    pageref = lambda i, page: run(' ') + ('<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
                               f'<w:r><w:instrText xml:space="preserve"> PAGEREF _Birch{i} \\h </w:instrText></w:r>'
                               '<w:r><w:fldChar w:fldCharType="separate"/></w:r>' + run(page) +
                               '<w:r><w:fldChar w:fldCharType="end"/></w:r>')
    leader_case('tabs-right-stop-pageref-field', 'Four leader lines whose page numbers are PAGEREF complex fields to bookmarks on pages 2-5 (Docxodus #1285)',
                birch, leader_stops, number_runs=pageref, target_pages=True)
    leader_case('tabs-right-stop-pageref-control', 'The same four leader lines with plain-text page numbers (control)',
                birch, leader_stops, number_runs=lambda i, page: run(' ') + run(page), target_pages=True)
    leader_case('tabs-right-stop-wrapped-title', 'Four leader lines whose titles wrap past the right indent, the last to three lines (Docxodus #1285)',
                [('2.1.', 'CedarTitle01 Culvert inspection, annual load ratings and scour monitoring for the northern spillway approach', '27', None),
                 ('2.2.', 'CedarTitle02 Quarry access roads, haul route maintenance and dust suppression along the eastern boundary', '31', None),
                 ('2.3.', 'CedarTitle03 Riprap placement, toe protection and settlement surveys at the downstream face of the main embankment and the auxiliary outlet', '140', None),
                 ('2.4.', 'CedarTitle04 Spillway gates', '152', None)], leader_stops)
    # The first right stop (8800) lies inside the right indent; the next is a right stop at the
    # column edge or a left stop at 8900. The control moves both before the line end (8496).
    elm = [('2.1.', 'ElmTitle01 Spillway', '12', '34'), ('2.2.', 'ElmTitle02 Riprap', '56', '78'),
           ('2.3.', 'ElmTitle03 Culverts', '90', 'Ra'), ('2.4.', 'ElmTitle04 Outlets', '91', 'Rb')]
    def second_stops(first, right_second, left_second):
        return lambda i: (f'<w:tab w:val="left" w:pos="1296"/><w:tab w:val="right" w:leader="dot" w:pos="{first}"/>' +
                          (f'<w:tab w:val="right" w:pos="{right_second}"/>' if i < 2 else f'<w:tab w:val="left" w:pos="{left_second}"/>'))
    leader_case('tabs-right-stop-second-stop-in-indent', 'Four leader lines with a second stop after a right stop inside the right indent (Docxodus #1285)',
                elm, second_stops(8800, 9360, 8900))
    leader_case('tabs-right-stop-second-stop-control', 'The same four leader lines with both stops before the line end (control)',
                elm, second_stops(8000, 8400, 8100))
    fir = [('2.1.', 'FirTitle01 Quarry access roads', '3', None), ('2.2.', 'FirTitle02 Spillway', '12', None),
           ('2.3.', 'FirTitle03 Culvert inspection and annual load ratings', '27', None), ('2.4.', 'FirTitle04 Riprap', '140', None)]
    linked = lambda bookmark: lambda i, content: (
        f'<w:hyperlink w:anchor="_FirTarget{i}">' +
        (f'<w:bookmarkStart w:id="{30 + i}" w:name="_FirEntry{i}"/><w:bookmarkEnd w:id="{30 + i}"/>' if bookmark else '') +
        content + '</w:hyperlink>')
    leader_case('tabs-right-stop-linked-bookmark', 'Four linked leader lines, each with its bookmark inside the link (Docxodus #1285)',
                fir, leader_stops, wrap=linked(True))
    leader_case('tabs-right-stop-linked-control', 'The same four linked leader lines without bookmarks (control)',
                fir, leader_stops, wrap=linked(False))
    # Completion review: a short suffix can remain beside the overhanging stop, but a long one
    # must wrap into the column instead of being forced past the page in one no-wrap box.
    for long_tail in (False, True):
        suffix = ' '.join(f'TailWord{i:02}' for i in range(24)) if long_tail else 'Oak'
        props = ('<w:tabs><w:tab w:val="left" w:pos="1296"/><w:tab w:val="right" w:pos="8800"/>'
                 '<w:tab w:val="left" w:pos="8900"/></w:tabs><w:spacing w:after="0" w:line="240" w:lineRule="exact"/>'
                 '<w:ind w:left="1296" w:right="864" w:hanging="648"/>')
        content = (run('2.1.') + '<w:r><w:tab/></w:r>' + run('Spillway ') + '<w:r><w:tab/></w:r>'
                   + run(' 12 ') + '<w:r><w:tab/></w:r>' + run(suffix))
        add('tabs-right-stop-' + ('long-tail' if long_tail else 'short-tail-control'), 'paragraphs',
            'Long text after an overhanging right stop and a final left tab stays inside the column (Docxodus #1285)' if long_tail else
            'A short suffix after the same stops stays beside them (control)',
            ['2.1.', 'Spillway', '12', suffix], para(props=props, runs=content), styles_xml=tab_styles,
            assertions=[{'type': 'marker-region', 'version': 2, 'marker': 'TailWord23' if long_tail else 'Oak',
                         'occurrence': 1, 'page': 1, 'rect': [72, 72, 540, 200] if long_tail else [515, 70, 540, 85]}])
    # Original page-anchored footer frame and otherwise identical ordinary-flow control.
    frame_styles = f'<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}"/><w:sz w:val="24"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="exact"/></w:pPr></w:pPrDefault></w:docDefaults></w:styles>'
    frame_section = section().replace('<w:sectPr>', '<w:sectPr><w:footerReference w:type="default" r:id="rStory"/>')
    for case_id, framed in [('footer-paragraph-text-frame', True), ('footer-paragraph-flow-control', False)]:
        body_text, frame_text, centered = 'CedarFrameBody Keep the archive tray clear.', 'CedarFrame01 Archive ledger.', 'CedarSheet01 Page control.'
        properties = '<w:framePr w:w="10080" w:hAnchor="page" w:vAnchor="text" w:x="840" w:y="20" w:wrap="auto"/>' if framed else ''
        footer = para(frame_text, properties) + para(centered, '<w:jc w:val="center"/>')
        add(case_id, 'paragraphs', 'Footer paragraph with a page-anchored text frame (Docxodus #1225)' if framed else
            'Identical footer paragraphs without frame properties, preserving ordinary flow',
            [body_text, frame_text, centered], para(body_text), sect=frame_section,
            styles_xml=frame_styles, story=('footer', footer),
            assertions=[{'type': 'marker-reference-position', 'version': 1, 'marker': marker,
                         'tolerancePt': 0.5} for marker in ('CedarFrameBody', 'CedarFrame01', 'CedarSheet01')])
    # A margin comment that exceeds its HTML viewport, and the same short-note control.
    # PDFs deliberately hide comments; interactive readability is measured in delivered HTML.
    comment_styles = f'<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}"/><w:color w:val="000000"/><w:sz w:val="22"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:widowControl/><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults></w:styles>'
    for case_id, count in [('comments-long-scrollable-margin', 240), ('comments-short-margin-control', 8)]:
        body_text = 'CedarCommentBody The archive crew checks the cedar ledger.'
        tokens = [f'CedarNote{i:03d}' for i in range(count)]
        comment = ('<w:comment w:id="0" w:author="Cedar Reviewer" w:initials="CR" w:date="2026-09-10T12:00:00Z">'
                   + para(' '.join(tokens)) + '</w:comment>')
        body = para(runs='<w:commentRangeStart w:id="0"/>' + run(body_text)
                    + '<w:commentRangeEnd w:id="0"/><w:r><w:commentReference w:id="0"/></w:r>')
        add(case_id, 'paragraphs', 'A 240-token margin comment extending beyond its HTML viewport (Docxodus #1226)' if count == 240 else
            'The same comment graph with an eight-token note that fits without scrolling',
            [body_text], body, styles_xml=comment_styles, comments_xml=comment)
        cases[-1]['htmlProfile'] = {'review': 'final', 'comments': 'margin'}
        cases[-1]['htmlAssertions'] = [{'type': 'marker-readable', 'version': 1, 'marker': tokens[-1], 'tokens': tokens}]
    # A three-level thread and three flat notes, with identical body and comment text.
    for case_id, threaded in [('comments-nested-reply-size', True), ('comments-flat-note-size-control', False)]:
        ids = ['00000010', '00000020', '00000030']
        body_text = 'CedarThreadBody The archive crew checks the cedar tray.'
        body = para(runs='<w:commentRangeStart w:id="0"/>' + run(body_text) + '<w:commentRangeEnd w:id="0"/>'
                    + ''.join(f'<w:r><w:commentReference w:id="{i}"/></w:r>' for i in range(3)))
        comments = ''.join(f'<w:comment w:id="{i}" w:author="Cedar ArchiveReviewerwithalongunbrokentoken" w:date="2026-09-10T12:00:00Z">'
                           + f'<w:p xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" w14:paraId="{pid}">'
                           + run(f'CedarThread{i} Check the tray.') + '</w:p></w:comment>' for i, pid in enumerate(ids))
        topology = '<w15:commentsEx xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml">' + ''.join(
            f'<w15:commentEx w15:paraId="{pid}"' + (f' w15:paraIdParent="{ids[i - 1]}"' if threaded and i else '') + '/>'
            for i, pid in enumerate(ids)) + '</w15:commentsEx>'
        add(case_id, 'paragraphs', 'Root, reply and nested reply with a long author (Docxodus #1227)' if threaded else
            'The same three comment bodies and authors without parent relationships',
            [body_text], body, sect=section().replace('w:right="1440"', 'w:right="2880"'),
            styles_xml=comment_styles, comments_xml=comments, comments_extended_xml=topology)
        cases[-1]['htmlProfile'] = {'review': 'final', 'comments': 'margin'}
        cases[-1]['htmlAssertions'] = [{'type': 'marker-computed-style', 'version': 1, 'marker': f'CedarThread{i}',
                                       'property': 'font-size', 'equals': '13.6px'} for i in range(3)]
    # Header containment is isolated from nesting: one long author and a short-author control.
    for case_id, author in [('comments-long-author-header', 'CedarArchivistwithalongunbrokentoken'),
                            ('comments-short-author-header-control', 'Cy')]:
        body_text = 'CedarHeaderBody The archive crew checks the tray.'
        body = para(runs='<w:commentRangeStart w:id="0"/>' + run(body_text)
                    + '<w:commentRangeEnd w:id="0"/><w:r><w:commentReference w:id="0"/></w:r>')
        # The literal trailing space separates the author's marker from adjacent date text in HTML.
        comment = f'<w:comment w:id="0" w:author="{author} " w:date="2026-09-10T12:00:00Z">' + para('CedarHeaderNote Review the tray.') + '</w:comment>'
        add(case_id, 'paragraphs', 'A long unbroken author in a one-inch review margin (Docxodus #1227)' if len(author) > 2 else
            'The same note and margin with a short author whose header fits',
            [body_text], body, styles_xml=comment_styles, comments_xml=comment)
        cases[-1]['htmlProfile'] = {'review': 'final', 'comments': 'margin'}
        cases[-1]['htmlAssertions'] = [{'type': 'marker-computed-style', 'version': 1, 'marker': author,
                                       'property': 'font-size', 'equals': '12.24px'}]
    # Original durable UTC timestamp and legacy-only control. PDF comments stay hidden;
    # the inline HTML attribute independently measures the instant, without caption formatting.
    date = '2027-01-02T04:30:00Z'
    cid = 'http://schemas.microsoft.com/office/word/2016/wordml/cid'
    cex = 'http://schemas.microsoft.com/office/word/2018/wordml/cex'
    w14 = 'http://schemas.microsoft.com/office/word/2010/wordml'
    for modern in [True, False]:
        case_id = 'comments-durable-utc-timestamp' if modern else 'comments-legacy-utc-control'
        anchor = 'BirchDateAnchor The crew verifies the timestamp.'
        body = para(runs='<w:commentRangeStart w:id="4"/>' + run(anchor) +
                    '<w:commentRangeEnd w:id="4"/><w:r><w:commentReference w:id="4"/></w:r>')
        stamp = '2027-01-01T23:30:00Z' if modern else date
        comment = (f'<w:comment w:id="4" w:author="Birch Reviewer" w:date="{stamp}">'
                   f'<w:p xmlns:w14="{w14}" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
                   'mc:Ignorable="w14" w14:paraId="00DD00DD">' + run('BirchDateNote Check the clock.') + '</w:p></w:comment>')
        ids = f'<c:commentsIds xmlns:c="{cid}"><c:commentId c:paraId="00DD00DD" c:durableId="03CC03CC"/></c:commentsIds>'
        extensible = f'<e:commentsExtensible xmlns:e="{cex}"><e:commentExtensible e:durableId="03CC03CC" e:dateUtc="{date}"/></e:commentsExtensible>'
        add(case_id, 'paragraphs', 'Modern durable timestamp overrides legacy date (Docxodus #1228)' if modern else
            'The same effective timestamp supplied only in the legacy attribute', [anchor], body,
            styles_xml=comment_styles, comments_xml=comment, comments_ids_xml=ids if modern else None,
            comments_extensible_xml=extensible if modern else None)
        cases[-1]['htmlProfile'] = {'review': 'final', 'comments': 'inline'}
        cases[-1]['htmlAssertions'] = [{'type': 'marker-attribute', 'version': 1,
            'marker': 'BirchDateAnchor', 'attribute': 'data-date', 'equals': date}]
    # The year reproduction is paired with an authored year token, which is already
    # readable without generated date captions. Both use the same margin font contract.
    for authored in [False, True]:
        anchor = 'BirchYearAnchor The crew verifies the calendar.'
        body = para(runs='<w:commentRangeStart w:id="4"/>' + run(anchor) +
                    '<w:commentRangeEnd w:id="4"/><w:r><w:commentReference w:id="4"/></w:r>')
        note = 'BirchYearNote YearProof2027' if authored else 'BirchYearNote Check the calendar.'
        comment = f'<w:comment w:id="4" w:author="Birch Reviewer" w:date="{date}">' + para(note) + '</w:comment>'
        add('comments-authored-year-control' if authored else 'comments-margin-year', 'paragraphs',
            'An authored year token is readable independently of generated captions' if authored else
            'Margin date must include its calendar year (Docxodus #1228)', [anchor], body,
            styles_xml=comment_styles, comments_xml=comment)
        cases[-1]['htmlProfile'] = {'review': 'final', 'comments': 'margin'}
        marker = 'YearProof2027' if authored else '2027'
        cases[-1]['htmlAssertions'] = [
            {'type': 'marker-attribute', 'version': 1, 'marker': marker, 'attribute': 'data-date', 'equals': date},
            {'type': 'marker-readable', 'version': 1, 'marker': marker, 'tokens': ['BirchYearNote', marker] if authored else ['Jan', '2,', marker]}]
    # Independent original comment return link and ordinary body bookmark control.
    for comments in [True, False]:
        text = ['Juniper navigation anchor.', 'Juniper bookmark destination.', 'JuniperBodyReturn']
        start = '<w:commentRangeStart w:id="4"/>' if comments else ''
        end = '<w:commentRangeEnd w:id="4"/><w:r><w:commentReference w:id="4"/></w:r>' if comments else ''
        body = para(runs=start + run(text[0]) + end)
        body += para(runs='<w:bookmarkStart w:id="31" w:name="JuniperDestination"/>' + run(text[1]) + '<w:bookmarkEnd w:id="31"/>')
        body += para(runs='<w:hyperlink w:anchor="JuniperDestination">' + run(text[2]) + '</w:hyperlink>')
        comment = '<w:comment w:id="4" w:author="">' + para('JuniperNote Return to the marked words.') + '</w:comment>'
        add('comments-paginated-return-link' if comments else 'comments-body-bookmark-return-control',
            'paragraphs', 'A paginated margin note returns to its unique rendered body reference (Docxodus #1229)' if comments else
            'An ordinary body bookmark link stays active without repeated comment copies', text, body,
            styles_xml=comment_styles, comments_xml=comment if comments else None)
        cases[-1]['htmlProfile'] = {'review': 'final', 'comments': 'margin'}
        cases[-1]['htmlAssertions'] = ([
            {'type': 'marker-attribute', 'version': 1, 'marker': '↩', 'attribute': 'href', 'equals': '#comment-ref-4'},
            {'type': 'marker-attribute', 'version': 1, 'marker': '[4]', 'attribute': 'id', 'equals': 'comment-ref-4'}] if comments else [
            {'type': 'marker-attribute', 'version': 1, 'marker': 'JuniperBodyReturn', 'attribute': 'href', 'equals': '#JuniperDestination'}])
    # Same original DOCX bytes; only delivered HTML stylesheet selectors differ.
    for child in [True, False]:
        text = ['PineCssNode Cascade proof.', 'PinePlainNode Unchanged body.']
        add('html-css-child-selector' if child else 'html-css-descendant-control', 'paragraphs',
            'A CSS child selector must survive XML serialization (Docxodus #1230)' if child else
            'A descendant selector supplies the same style without a raw greater-than character',
            text, para(runs='<w:commentRangeStart w:id="4"/>' + run(text[0]) +
                '<w:commentRangeEnd w:id="4"/><w:r><w:commentReference w:id="4"/></w:r>') + para(text[1]),
            styles_xml=comment_styles,
            comments_xml='<w:comment w:id="4" w:author="">' + para('Fir') + '</w:comment>')
        selector = 'div > p' if child else 'div p'
        cases[-1]['htmlProfile'] = {'review': 'final', 'comments': 'margin',
            'additionalCss': selector + ' {font-size:32px !important;line-height:1.5 !important;}'}
        cases[-1]['htmlAssertions'] = [{'type': 'marker-computed-style', 'version': 1,
            'marker': 'Fir', 'property': 'font-size', 'equals': '32px'}]
    # The reference is an independently authored composite. Candidates must build their own
    # composite from the source pair, so rendering a pre-fixed package cannot mask a merge defect.
    defaults = (f'<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}"/>'
                '<w:sz w:val="22"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>'
                '<w:spacing w:after="120" w:line="280" w:lineRule="exact"/></w:pPr></w:pPrDefault></w:docDefaults>')
    paragraph_style = ('<w:style w:type="paragraph" w:styleId="Shared"><w:name w:val="Body blue"/>'
                       '<w:rPr><w:color w:val="0000C0"/></w:rPr></w:style>')
    def character_style(style_id):
        return (f'<w:style w:type="character" w:styleId="{style_id}"><w:name w:val="Emphasis red"/>'
                '<w:rPr><w:b/><w:color w:val="C00000"/><w:sz w:val="32"/></w:rPr></w:style>')
    def style_part(styles):
        return f'<w:styles xmlns:w="{W}">{defaults}{styles}</w:styles>'
    first = para('AlderBuild The blue source.', '<w:pStyle w:val="Shared"/>')
    for collision in [True, False]:
        cid = 'builder-cross-type-style' if collision else 'builder-distinct-style-control'
        incoming_id = 'Shared' if collision else 'Separate'
        second = para(runs=run('BirchBuild The red source.', f'<w:rStyle w:val="{incoming_id}"/>'))
        sources = []
        for suffix, body, styles in [('first', first, paragraph_style), ('second', second, character_style(incoming_id))]:
            path = ROOT / 'fixtures' / 'build' / (cid + '-' + suffix + '.docx')
            package(path, body, styles_xml=style_part(styles))
            sources.append({'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        expected_second = para(runs=run('BirchBuild The red source.', '<w:rStyle w:val="Separate"/>'))
        add(cid, 'paragraphs',
            'Build two sources whose paragraph and character styles share an ID (Docxodus #1186)' if collision else
            'Build the same sources with distinct style IDs',
            ['AlderBuild The blue source.', 'BirchBuild The red source.'], first + expected_second,
            styles_xml=style_part(paragraph_style + character_style('Separate')),
            assertions=[{'type': 'same-page', 'version': 1, 'markers': ['AlderBuild', 'BirchBuild']}])
        cases[-1]['preparation'] = {'operation': 'build', 'inputs': sources}
    # Original repeated-story cards: the unbordered pair differs only in w:pBdr.
    # Share these generated bytes with native and WASM tests in the renderer repository.
    border = '<w:pBdr>' + ''.join(f'<w:{side} w:val="single" w:sz="6" w:space="4" w:color="246B7D"/>'
        for side in ('top', 'left', 'bottom', 'right')) + '</w:pBdr>'
    for kind in ('footnote', 'endnote'):
        for bordered in (True, False):
            texts = []
            def card(prefix, note=False):
                result = ''
                for index, suffix in enumerate(('One', 'Two', 'Plain')):
                    text = prefix + suffix
                    texts.append(text)
                    marker = f'<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:{kind}Ref/></w:r>' + run(' ') if note and index == 0 else ''
                    props = (border if bordered and index < 2 else '') + '<w:spacing w:after="0" w:line="280" w:lineRule="exact"/>'
                    result += para(props=props, runs=marker + run(text))
                return result
            body = card('CedarBody')
            header, footer, note = card('CedarHeader'), card('CedarFooter'), card('CedarNote', True)
            anchor = f'<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:{kind}Reference w:id="1"/></w:r>'
            body = body.replace(run('CedarBodyPlain'), run('CedarBodyPlain ') + anchor)
            marker = '1' if kind == 'footnote' else 'i'
            texts.extend([marker, marker])
            sect = section().replace('<w:sectPr>', '<w:sectPr><w:headerReference w:type="default" r:id="rStory"/><w:footerReference w:type="default" r:id="rStory1"/>')
            sect = sect.replace('w:top="1440"', 'w:top="2160"').replace('w:bottom="1440"', 'w:bottom="2160"')
            add('paragraphs-story-borders-' + kind + ('' if bordered else '-control'), 'notes',
                'Grouped paragraph borders in body, header, footer and ' + kind + ' (Docxodus #1203)' if bordered else
                'The same story paragraphs without borders', texts, body, sect=sect,
                stories=[('header', header), ('footer', footer)], notes=(kind, ''), notes_xml=note,
                assertions=[{'type': 'same-page', 'version': 1, 'markers': ['CedarBodyOne', 'CedarHeaderOne', 'CedarFooterOne', 'CedarNoteOne']}])
    for wrapped in (True, False):
        cid = 'compare-inline-customxml' if wrapped else 'compare-inline-hyperlink-control'
        def compared_body(word):
            return (para(runs=run('MapleBefore ') + custom_xml_link(run(word), wrapped) + run(' MapleAfter'))
                    + para(runs='<w:bookmarkStart w:id="91" w:name="BirchTarget"/>' + run('BirchTarget.') + '<w:bookmarkEnd w:id="91"/>'))
        sources = []
        for side, word in [('left', 'OakOpened'), ('right', 'OakClosed')]:
            path = ROOT / 'fixtures' / 'compare' / (cid + '-' + side + '.docx')
            package(path, compared_body(word))
            sources.append({'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        for review, word in [('final', 'OakClosed'), ('original', 'OakOpened')]:
            add(cid + '-' + review, 'paragraphs',
                'Compare changed inline custom XML inside a hyperlink (Docxodus #1188)' if wrapped else
                'Compare the same text inside a plain hyperlink',
                ['MapleBefore', word, 'MapleAfter', 'BirchTarget.'], compared_body(word))
            cases[-1]['profile']['review'] = review
            cases[-1]['preparation'] = {'operation': 'compare', 'inputs': sources}
    # Boundary markers are invisible in PDF: these cases verify both resolved views retain table content.
    # The companion redline cases independently check marker identity, placement and reviewer attribution.
    for operation, level in [('compare', 'tbl'), ('consolidate', 'tr'), ('consolidate', 'p')]:
        cid = 'boundary-bookmark-' + operation + '-' + ('paragraph-control' if level == 'p' else level)
        def boundary_body(marked, edited):
            start = '<w:bookmarkStart w:id="73" w:name="HazelBoundary"/>' if marked and level != 'p' else ''
            end = '<w:bookmarkEnd w:id="73"/>' if marked and level != 'p' else ''
            value = 'Hazel lower revised' if edited else 'Hazel lower'
            content = table([[cell('Hazel upper'), cell('Birch upper')], [cell(value), cell('Birch lower')]])
            if level == 'tbl':
                content = content.replace('</w:tr><w:tr>', '</w:tr>' + start + '<w:tr>', 1).replace('</w:tbl>', end + '</w:tbl>')
            elif level == 'tr':
                content = content.replace('</w:tc><w:tc>', '</w:tc>' + start + '<w:tc>', 1).replace('</w:tc></w:tr>', '</w:tc>' + end + '</w:tr>', 1)
            else:
                content = content.replace(run('Birch upper'), start + run('Birch upper' + (' checked' if marked else '')) + end, 1)
            return para('Hazel boundary ledger') + content + para('Ledger complete')
        sources = []
        variants = [(False, False), (True, False)] + ([(False, True)] if operation == 'consolidate' else [])
        for index, (marked, edited) in enumerate(variants):
            path = ROOT / 'fixtures' / 'compare' / (cid + '-' + str(index) + '.docx')
            package(path, boundary_body(marked, edited))
            sources.append({'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        for review in ('final', 'original'):
            edited = review == 'final' and operation == 'consolidate'
            add(cid + '-' + review, 'tables',
                operation.title() + (' independent plain-text edits (control)' if level == 'p' else
                    ' a bookmark between ' + {'tbl': 'rows', 'tr': 'cells'}[level]) + ' (Docxodus #1190)',
                ['Hazel boundary ledger', 'Hazel upper', 'Birch upper' + (' checked' if level == 'p' and review == 'final' else ''), 'Hazel lower' + (' revised' if edited else ''), 'Birch lower', 'Ledger complete'],
                boundary_body(review == 'final', edited))
            cases[-1]['profile']['review'] = review
            cases[-1]['preparation'] = {'operation': operation, 'inputs': sources}

    for case in comment_view_cases() + duplicate_comment_cases() + consolidated_field_cases() + comment_identity_cases() + bookmark_boundary_cases() + removed_comment_cases() + note_insertion_cases() + bookmark_reviewer_cases() + bookmark_conflict_cases():
        sources = []
        for i, document in enumerate(case['sources']):
            path = ROOT / 'fixtures' / case.get('directory', 'comment-views') / (case['id'] + f'-{i}.docx')
            package(path, **document)
            sources.append({'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        for review, document in zip(('final', 'original'), case['expected']):
            import xml.etree.ElementTree as ET
            content = document['body'] + ''.join(xml for _, xml in document.get('footnote_list', []))
            root = ET.fromstring(f'<w:body xmlns:w="{W}">' + content + '</w:body>')
            texts = [e.text or '' for e in root.iter('{' + W + '}t')]
            texts += [str(i) for i, _ in document.get('footnote_list', []) for _ in range(2)]
            if case.get('directory') == 'field-views' and not case['control']:
                texts = ['1' if text == '7' else text for text in texts]  # PAGE recalculates on this one-page document.
            add(case['id'] + '-' + review, case.get('category', 'paragraphs'),
                ('Control for ' if case['control'] else 'Reproduce ') + f"Docxodus #{case['issue']} " + case.get('description', 'comment views'),
                texts, **document)
            cases[-1]['profile']['review'] = review
            cases[-1]['preparation'] = {'operation': case['operation'], 'inputs': sources}
    lead = [f'MapleLead{i:02d} register retained.' for i in range(1, 16)]
    following = [f'BirchLine{i:02d} inventory retained.' for i in range(1, 21)]
    for kept in (False, True):
        body = para(props=line_properties, runs='<w:r><w:br/></w:r>'.join(run(t) for t in lead))
        body += para('CedarHeading', line_properties + '<w:keepNext/>')
        body += para(props=line_properties + ('<w:keepLines/>' if kept else ''),
                     runs='<w:r><w:br/></w:r>'.join(run(t) for t in following))
        body += para('WillowClose', line_properties)
        add('paragraph-keep-next-' + ('kept-control' if kept else 'fragment'), 'paragraphs',
            'Keep a heading with a ' + ('whole kept paragraph (control)' if kept else 'valid first fragment of a splittable paragraph') + ' (Docxodus #1182)',
            lead + ['CedarHeading'] + following + ['WillowClose'], body,
            assertions=[{'type': 'marker-region', 'version': 2, 'marker': 'CedarHeading', 'occurrence': 1,
                         'page': 2 if kept else 1, 'rect': [72, 60, 540, 720]},
                        {'type': 'same-page', 'version': 1, 'markers': ['CedarHeading', 'BirchLine01']},
                        {'type': 'marker-region', 'version': 2, 'marker': 'BirchLine20', 'occurrence': 1,
                         'page': 2, 'rect': [72, 60, 540, 720]}])
    # The row hides Birch and Cedar wholly. A PDF may omit them or retain complete words, but
    # letters cut out by the enclosing header band are not valid optional tokens.
    for control in (False, True):
        names = ['HdrAlder', 'HdrBirch', 'HdrCedar']
        header_table = exact_table([exact_row(300, [''.join(para(t, exact(300)) for t in names),
                                            para('HdrValue', exact(300))])])
        sect = section().replace('<w:sectPr>', '<w:sectPr><w:headerReference w:type="default" r:id="rStory"/>')
        if control: sect = sect.replace('w:top="1440"', 'w:top="2160"')
        add('tables-exact-row-header-' + ('wide-control' if control else 'band-clip'), 'tables',
            'Exact 15pt header row with two hidden paragraphs under a ' + ('72pt control' if control else '36pt clipping')
            + ' header band (Docxodus #1200)', ['HdrAlder', 'HdrValue', 'BodyWillow'],
            para('BodyWillow', exact(300)), sect=sect, story=('header', header_table + para('', exact(300))),
            assertions=[{'type': 'same-page', 'version': 1, 'markers': ['HdrAlder', 'HdrValue', 'BodyWillow']}])
        cases[-1]['clippedTokens'] = {'HdrBirch': 1, 'HdrCedar': 1}
    # core-v52: table placement measured in Word for the web (Docxodus #1219, #1244). Times New
    # Roman throughout, so a Word capture keeps the declared family and is eligible as a reference.
    tnr = 'Times New Roman'
    tnr_styles = (f'<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="{tnr}" w:hAnsi="{tnr}" w:cs="{tnr}"/>'
                  '<w:sz w:val="22"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:before="0" w:after="0" w:line="320" w:lineRule="exact"/>'
                  '</w:pPr></w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style></w:styles>')
    placement_sect = section().replace('w:footer="720"', 'w:footer="720" w:gutter="0"')
    def placement_table(texts, props='', borders=True, margins=True):
        edge = ('<w:tblBorders>' + ''.join(f'<w:{side} w:val="single" w:sz="8" w:color="000000"/>' for side in ('top', 'left', 'bottom', 'right', 'insideV')) + '</w:tblBorders>') if borders else ''
        mar = '<w:tblCellMar><w:top w:w="0" w:type="dxa"/><w:left w:w="108" w:type="dxa"/><w:bottom w:w="0" w:type="dxa"/><w:right w:w="108" w:type="dxa"/></w:tblCellMar>' if margins else ''
        cells = ''.join(f'<w:tc><w:tcPr><w:tcW w:w="2500" w:type="dxa"/></w:tcPr>{para(t)}</w:tc>' for t in texts)
        return (f'<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="dxa"/>{props}{edge}<w:tblLayout w:type="fixed"/>{mar}</w:tblPr>'
                '<w:tblGrid><w:gridCol w:w="2500"/><w:gridCol w:w="2500"/></w:tblGrid>'
                f'<w:tr><w:trPr><w:trHeight w:val="360" w:hRule="atLeast"/></w:trPr>{cells}</w:tr></w:tbl>')
    # Word's own "Normal Table" shape: the document's default table style states a zero indent and
    # 108-twip side margins, and applies to every table that names no style.
    tnr_default_table_styles = tnr_styles.replace('</w:styles>',
        '<w:style w:type="table" w:default="1" w:styleId="TableNormal"><w:name w:val="Normal Table"/><w:uiPriority w:val="99"/>'
        '<w:semiHidden/><w:unhideWhenUsed/><w:tblPr><w:tblInd w:w="0" w:type="dxa"/><w:tblCellMar><w:top w:w="0" w:type="dxa"/>'
        '<w:left w:w="108" w:type="dxa"/><w:bottom w:w="0" w:type="dxa"/><w:right w:w="108" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style></w:styles>')
    def placement(case_id, description, before, tables, compat='15', before_props='', styles=None):
        texts = [before] + [t for row in tables for t in row[0]] + ['PlacementAfter The register continues below.']
        body = para(before, before_props) + ''.join(placement_table(*row) for row in tables) + para(texts[-1])
        markers = [t.split()[0] for t in texts]
        settings = f'<w:settings xmlns:w="{W}">' + SETTINGS_BODY.replace('w:val="15"', f'w:val="{compat}"') + '</w:settings>'
        add(case_id, 'tables', description + ' (Docxodus #1219, #1244)', texts, body, sect=placement_sect,
            styles_xml=styles or tnr_styles, font=tnr, extra_parts={'word/settings.xml': settings},
            assertions=[{'type': 'marker-reference-position', 'version': 1, 'marker': m, 'tolerancePt': 0.5} for m in markers])
    before = 'PlacementBefore The register opens above the table.'
    # #1219: with no w:tblCellMar and no table style the left cell margin is zero; the control states 108.
    placement('tables-cell-margin-absent-times-new-roman', 'Bordered table with no cell margins declared anywhere',
              before, [(['MarginLeft Ledger cell.', 'MarginRight Entry cell.'], '', True, False)])
    placement('tables-cell-margin-explicit-times-new-roman', 'Control: the same table declaring 108-twip left and right cell margins',
              before, [(['MarginLeft Ledger cell.', 'MarginRight Entry cell.'], '', True, True)])
    # #1219: before compatibility mode 15 a stated w:tblInd places the first cell's text at the indent.
    for mode in ('14', '15'):
        for indent in ('stated', 'absent'):
            props = '<w:tblInd w:w="0" w:type="dxa"/>' if indent == 'stated' else ''
            placement(f'tables-indent-mode-{mode}-{indent}-times-new-roman',
                      f'Compatibility mode {mode}; table indent {"stated as zero" if indent == "stated" else "absent"}',
                      before, [(['IndentLeft Ledger cell.', 'IndentRight Entry cell.'], props, True, True)], compat=mode)
    for mode in ('14', '15'):
        placement(f'tables-indent-mode-{mode}-default-style-times-new-roman',
                  f'Compatibility mode {mode}; the table names no style and inherits the default table style',
                  before, [(['IndentLeft Ledger cell.', 'IndentRight Entry cell.'], '', True, False)], compat=mode,
                  styles=tnr_default_table_styles)
    # #1244: Word adds no space between a paragraph and a following table beyond the paragraph's own spacing.
    for after in ('0', '240'):
        for borders in (False, True):
            placement(f'tables-boundary-after-{after}-{"bordered" if borders else "borderless"}-times-new-roman',
                      f'Paragraph with {after}-twip after-spacing followed by a {"bordered" if borders else "borderless"} table',
                      before, [(['BoundaryLeft Ledger cell.', 'BoundaryRight Entry cell.'], '', borders, True)],
                      before_props=f'<w:spacing w:after="{after}"/>')
    placement('tables-boundary-adjacent-times-new-roman', 'Two tables with no paragraph between them',
              before, [(['FirstLeft Ledger cell.', 'FirstRight Entry cell.'], '', False, True),
                       (['SecondLeft Ledger cell.', 'SecondRight Entry cell.'], '', True, True)])
    # core-v52: six further table-placement probes for Docxodus #1219, captured in Word for the web from
    # content-identical inputs (same document, styles and settings parts; see the results doc).
    def probe_para(t):
        return f'<w:p><w:pPr><w:spacing w:after="0"/></w:pPr><w:r><w:t xml:space="preserve">{t}</w:t></w:r></w:p>'
    probe_borders = '<w:tblBorders>' + ''.join(f'<w:{side} w:val="single" w:sz="8" w:color="000000"/>' for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV')) + '</w:tblBorders>'
    probe_margins = '<w:tblCellMar><w:top w:w="0" w:type="dxa"/><w:left w:w="108" w:type="dxa"/><w:bottom w:w="0" w:type="dxa"/><w:right w:w="108" w:type="dxa"/></w:tblCellMar>'
    def probe_table(cells, props='', width='<w:tblW w:w="5000" w:type="dxa"/>', grid=None, before=None):
        grid = grid or [5000 // len(cells)] * len(cells)
        gb = f'<w:gridBefore w:val="1"/><w:wBefore w:w="{before}" w:type="dxa"/>' if before else ''
        cols = ([before] if before else []) + grid
        tcs = ''.join(f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/></w:tcPr>{c}</w:tc>' for c, w in zip(cells, grid))
        head = (props + width) if props.startswith('<w:tblStyle') else (width + props)
        return (f'<w:tbl><w:tblPr>{head}{probe_borders}<w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid>'
                + ''.join(f'<w:gridCol w:w="{x}"/>' for x in cols) + f'</w:tblGrid><w:tr><w:trPr>{gb}<w:trHeight w:val="360" w:hRule="atLeast"/></w:trPr>{tcs}</w:tr></w:tbl>')
    def probe_styles(default=True, extra=''):
        out = (f'<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="{tnr}" w:hAnsi="{tnr}" w:cs="{tnr}"/><w:sz w:val="22"/></w:rPr></w:rPrDefault>'
               '<w:pPrDefault><w:pPr><w:spacing w:before="0" w:after="0" w:line="320" w:lineRule="exact"/></w:pPr></w:pPrDefault></w:docDefaults>'
               '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>')
        if default:
            out += f'<w:style w:type="table" w:default="1" w:styleId="TableNormal"><w:name w:val="Normal Table"/><w:tblPr><w:tblInd w:w="0" w:type="dxa"/>{probe_margins}</w:tblPr></w:style>'
        return out + extra + '</w:styles>'
    probe_sect = '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>'
    probe_control = lambda label: probe_para(label + 'Before control paragraph.') + probe_table([probe_para(label + 'Cell control table.')])
    probe_grid = '<w:style w:type="table" w:styleId="Grid"><w:name w:val="Grid"/><w:tblPr>' + probe_borders + '</w:tblPr></w:style>'
    probes = [
        ('centred-default-style', 'Mode 14: a centred table beside a left-aligned control, both inheriting the default table style', '14',
         probe_control('Alpha') + probe_para('BravoBefore centred table.') + probe_table([probe_para('BravoCell centred table.')], props='<w:jc w:val="center"/>'), probe_styles()),
        ('nested-default-style', 'Mode 14: a table nested in a cell of a table inheriting the default table style', '14',
         probe_control('Alpha') + probe_para('BravoBefore outer table.') + probe_table([probe_para('BravoCell outer cell.') + probe_table([probe_para('CharlieCell nested table.')], width='<w:tblW w:w="3000" w:type="dxa"/>') + probe_para('')]), probe_styles()),
        ('named-style-no-margins-mode-14', 'Mode 14: a table naming a style that states neither an indent nor cell margins', '14',
         probe_para('AlphaBefore named style without cell margins.') + probe_table([probe_para('AlphaCell named style.')], props='<w:tblStyle w:val="Grid"/>'), probe_styles(False, probe_grid)),
        ('named-style-no-margins-mode-15', 'Mode 15: a table naming a style that states neither an indent nor cell margins', '15',
         probe_para('AlphaBefore named style without cell margins.') + probe_table([probe_para('AlphaCell named style.')], props='<w:tblStyle w:val="Grid"/>'), probe_styles(False, probe_grid)),
        ('grid-before-default-style', 'Mode 14: a first row that starts one grid column in (w:gridBefore)', '14',
         probe_control('Alpha') + probe_para('BravoBefore first row starts one column in.') + probe_table([probe_para('BravoCell after gridBefore.')], grid=[4000], before=1000), probe_styles()),
        ('pct-100-default-style', 'Mode 14: a table 100% of the text width', '14',
         probe_control('Alpha') + probe_para('BravoBefore full-width table.') + probe_table([probe_para('BravoCell full width.')], width='<w:tblW w:w="5000" w:type="pct"/>'), probe_styles()),
    ]
    for name, description, mode, body, styles_xml in probes:
        texts = [t for t in re.findall(r'<w:t xml:space="preserve">([^<]*)</w:t>', body + probe_para('ProbeAfter end of document.')) if t]
        markers = [t.split()[0] for t in texts]
        settings = f'<w:settings xmlns:w="{W}"><w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="{mode}"/></w:compat></w:settings>'
        add(f'tables-legacy-{name}-times-new-roman', 'tables', description + ' (Docxodus #1219)', texts,
            body + probe_para('ProbeAfter end of document.'), sect=probe_sect, styles_xml=styles_xml, font=tnr,
            extra_parts={'word/settings.xml': settings},
            assertions=[{'type': 'marker-reference-position', 'version': 1, 'marker': m, 'tolerancePt': 0.5} for m in markers])
    # Original adjacent-table property cases for Docxodus #1341. The separator controls
    # carry the same table declarations; only a real paragraph makes them nonadjacent.
    def harbor_table(text, second):
        width = 6000 if second else 4800
        border = ('<w:tblBorders>' + ''.join('<w:' + side + ' w:val="single" w:sz="8" w:color="246B7D"/>'
                  for side in ('top', 'left', 'bottom', 'right')) + '</w:tblBorders>') if second else ''
        return ('<w:tbl><w:tblPr><w:tblW w:w="' + str(width) + '" w:type="dxa"/>' + border
                + '<w:tblLayout w:type="fixed"/><w:tblCellMar><w:left w:w="' + ('720' if second else '0')
                + '" w:type="dxa"/><w:right w:w="180" w:type="dxa"/></w:tblCellMar></w:tblPr>'
                + '<w:tblGrid><w:gridCol w:w="' + str(width) + '"/></w:tblGrid><w:tr><w:tc><w:tcPr>'
                + '<w:tcW w:w="' + str(width) + '" w:type="dxa"/></w:tcPr>' + para(text) + '</w:tc></w:tr></w:tbl>')
    harbor_styles = (f'<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr>'
                     f'<w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}"/><w:sz w:val="22"/></w:rPr></w:rPrDefault>'
                     '<w:pPrDefault><w:pPr><w:spacing w:before="0" w:after="0" w:line="320" w:lineRule="exact"/>'
                     '</w:pPr></w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
                     '<w:name w:val="Normal"/></w:style></w:styles>')
    for review in ('final', 'original'):
        for control in (False, True):
            body = (para('EstuaryEntry') + harbor_table('CanalPier', False) + (para('') if control else '')
                    + harbor_table('InlandPier', True) + para('EstuaryExit'))
            add('tables-adjacent-properties-' + review + ('-control' if control else ''), 'tables',
                'Independent borders, widths and margins of ' + ('separated control' if control else 'adjacent')
                + ' tables under the ' + review + ' review profile (Docxodus #1341)',
                ['EstuaryEntry', 'CanalPier', 'InlandPier', 'EstuaryExit'], body, styles_xml=harbor_styles,
                assertions=[{'type': 'same-page', 'version': 1,
                             'markers': ['EstuaryEntry', 'CanalPier', 'InlandPier', 'EstuaryExit']}])
            cases[-1]['profile']['review'] = review
    # Original literal-text tabs and explicit-tab controls for Docxodus #1353.
    estuary_styles = (f'<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr>'
                     f'<w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}"/><w:sz w:val="22"/></w:rPr></w:rPrDefault>'
                     '<w:pPrDefault><w:pPr><w:spacing w:before="0" w:after="0" w:line="320" w:lineRule="exact"/>'
                     '</w:pPr></w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
                     '<w:name w:val="Normal"/></w:style></w:styles>')
    for kind in ('body', 'header', 'footer', 'multiple'):
        for literal in (True, False):
            props = '<w:rPr><w:b/><w:color w:val="225588"/></w:rPr>'
            if kind == 'multiple':
                content = ('<w:r>' + props + ('<w:t xml:space="preserve">North&#9;&#9; EstuaryMark</w:t>' if literal else
                           '<w:t>North</w:t><w:tab/><w:tab/><w:t xml:space="preserve"> EstuaryMark</w:t>') + '</w:r>')
            else:
                content = ('<w:r><w:t/></w:r><w:r>' + props +
                           ('<w:t xml:space="preserve">&#9;</w:t>' if literal else '<w:tab/>') +
                           '</w:r><w:r>' + props + '<w:t xml:space="preserve"> EstuaryMark</w:t></w:r>')
            stops = ('<w:tab w:val="left" w:pos="2400"/>' if kind == 'multiple' else '')
            tab_paragraph = ('<w:p><w:pPr><w:tabs>' + stops + '<w:tab w:val="right" w:pos="9360" w:leader="dot"/>'
                             '</w:tabs></w:pPr>' + content + '</w:p>')
            story = kind if kind in ('header', 'footer') else None
            sect = section()
            if story:
                sect = sect.replace('<w:sectPr>', '<w:sectPr><w:' + story + 'Reference w:type="default" r:id="rStory"/>')
            body = para('EstuaryBody') if story else tab_paragraph + para('EstuaryEnd')
            texts = ['EstuaryBody', 'EstuaryMark'] if story else (['North'] if kind == 'multiple' else []) + ['EstuaryMark', 'EstuaryEnd']
            add('tabs-literal-text-' + kind + ('' if literal else '-control'), 'paragraphs',
                ('Literal text tab' if literal else 'Explicit tab control') + ' in ' + kind + ' content (Docxodus #1353)',
                texts, body, sect=sect, story=(story, tab_paragraph) if story else None, styles_xml=estuary_styles,
                assertions=[{'type': 'marker-region', 'version': 2, 'marker': 'EstuaryMark', 'occurrence': 1,
                             'page': 1, 'rect': [400, 20, 552, 780]},
                            {'type': 'same-page', 'version': 1, 'markers': ['EstuaryMark', 'EstuaryBody' if story else 'EstuaryEnd']}])
            cases[-1]['pdfTextNormalization'] = 'isolated-dot-leaders-v1'
    for variant in ('literal', 'explicit', 'control'):
        tag = 't' if variant == 'control' else 'delText'
        def marked_text(value):
            return '<w:' + tag + ' xml:space="preserve">' + value + '</w:' + tag + '>'
        content = ('<w:r><w:rPr><w:b/><w:color w:val="225588"/></w:rPr>' +
                   (marked_text('North &#9; EstuaryMark') if variant == 'literal' else
                    marked_text('North ') + '<w:tab/>' + marked_text(' EstuaryMark')) + '</w:r>')
        if variant != 'control':
            content = '<w:del w:id="7" w:author="Estuary reviewer" w:date="2026-01-01T00:00:00Z">' + content + '</w:del>'
        body = ('<w:p><w:pPr><w:tabs><w:tab w:val="right" w:pos="9360" w:leader="dot"/></w:tabs></w:pPr>'
                + content + '</w:p>' + para('EstuaryEnd'))
        add('tabs-literal-text-deleted' + ('' if variant == 'literal' else '-' + variant), 'paragraphs',
            {'literal': 'Literal tab in visible deleted text', 'explicit': 'Explicit tab in visible deleted text',
             'control': 'Untracked explicit-tab control for visible deletion layout'}[variant] + ' (Docxodus #1353)',
            ['North', 'EstuaryMark', 'EstuaryEnd'], body, styles_xml=estuary_styles,
            assertions=[{'type': 'marker-region', 'version': 2, 'marker': 'EstuaryMark', 'occurrence': 1,
                         'page': 1, 'rect': [400, 20, 552, 780]},
                        {'type': 'same-page', 'version': 1, 'markers': ['EstuaryMark', 'EstuaryEnd']}])
        cases[-1]['profile']['review'] = 'markup'
        cases[-1]['pdfTextNormalization'] = 'isolated-dot-leaders-v1'
    # A comment anchored in a footer or a footnote must render like a body comment (Docxodus #1310).
    # The three cases share one document; only the story holding the commented words differs, and
    # the body control holds it in the body. PDFs hide comments, as everywhere in this suite; the
    # margin-profile HTML companion requires the note itself to be readable. The comment is a range
    # with no w:commentReference run: LibreOffice 25.8.7.3 refuses to open a package whose footer or
    # footnote holds one ("source file could not be loaded"), which would leave the reference
    # track without a PDF. The range alone still selects the note in every story.
    story_styles = comment_styles
    story_section = section().replace('<w:sectPr>', '<w:sectPr><w:footerReference w:type="default" r:id="rStory"/>')
    def story_commented(text, commented):
        return ('<w:commentRangeStart w:id="5"/>' + run(text) + '<w:commentRangeEnd w:id="5"/>') if commented else run(text)
    story_text = ['OakBodyLine The survey crew checks the oak ledger.', 'OakFooterLine Ledger copy.',
                  'OakNoteLine Counted twice.']
    for case_id, story, description, mixed in [
            ('comments-footer-story-margin', 'footer', 'A comment anchored in footer text (Docxodus #1310)', False),
            ('comments-footnote-story-margin', 'footnote', 'A comment anchored in footnote text (Docxodus #1310)', False),
            ('comments-body-story-control', 'body', 'The same document with the comment anchored in the body', False),
            ('comments-footer-story-mixed-reference', 'footer', 'A footer range beside a real body comment reference', True),
            ('comments-body-story-mixed-reference-control', 'body', 'Body references control for the mixed footer range', True)]:
        body = para(runs=story_commented(story_text[0], story == 'body') + '<w:r><w:footnoteReference w:id="1"/></w:r>'
                    + (comment_view_mark('Reference', 5) if mixed and story == 'body' else '')
                    + (comment_view_mark('Reference', 6) if mixed else ''))
        footer = para(runs=story_commented(story_text[1], story == 'footer'))
        note = para(runs='<w:r><w:footnoteRef/></w:r>' + run(' ') + story_commented(story_text[2], story == 'footnote'))
        comment = '<w:comment w:id="5" w:author="Oak Reviewer" w:date="2026-10-01T12:00:00Z">' + para('Check OakStoryNote') + '</w:comment>'
        if mixed: comment += comment_view_note(6, 'Review OakBodyPoint')
        add(case_id, 'paragraphs', description, story_text + ['1', '1'], body, sect=story_section,
            notes=('footnote', ''), notes_xml=note, styles_xml=story_styles, story=('footer', footer),
            comments_xml=comment)
        cases[-1]['htmlProfile'] = {'review': 'final', 'comments': 'margin'}
        cases[-1]['htmlAssertions'] = [{'type': 'marker-readable', 'version': 1, 'marker': 'OakStoryNote',
                                       'tokens': ['Check', 'OakStoryNote']}]
        if mixed: cases[-1]['htmlAssertions'].append({'type': 'marker-readable', 'version': 1, 'marker': 'OakBodyPoint',
                                                    'tokens': ['Review', 'OakBodyPoint']})
    # core-v66: reuse the original row-geometry helpers and unpublished #1202 cases.
    # A 300 x 160pt card with 10pt margins: a 140pt body band that a short table row overfills.
    rg_card = ('<w:sectPr><w:pgSz w:w="6000" w:h="3200"/><w:pgMar w:top="200" w:right="200" w:bottom="200" w:left="200" '
               'w:header="0" w:footer="0" w:gutter="0"/></w:sectPr>')
    # #1202: rows and bordered paragraphs taller than the 140pt body band of a 160pt card.
    def card_lines(prefix, count):
        return [f'{prefix}{i:02d}' for i in range(1, count + 1)]
    def card_paras(words):
        return ''.join(para(w, exact(300)) for w in words)
    for case_id, height, description in [('tables-row-exact-taller-than-page-times-new-roman', 8000, 'An exact 400pt row taller than the page'),
                                         ('tables-row-exact-taller-than-page-control-times-new-roman', 2000, 'Control: an exact 100pt row that fits the page')]:
        words = card_lines('Cedar', 8)
        # The 100pt control row hides its eighth line; the 400pt row shows all eight.
        hidden = {'Cedar08': 1} if height < 2400 else None
        texts = ['CedarBefore'] + [w for w in words if not hidden or w not in hidden] + ['CedarAfter']
        body = para('CedarBefore', exact(300)) + rg_table([rg_row([rg_cell(card_paras(words), 5400)], height)], [5400], True, no_margins) + para('CedarAfter', exact(300))
        rg_add(case_id, description + ' after a paragraph on a 300 x 160pt card (Docxodus #1202)', texts, body, sect=rg_card, clipped=hidden)
    words = card_lines('Maple', 8)
    texts = ['MapleBefore'] + words + ['Willow01', 'Willow02', 'MapleAfter']
    body = (para('MapleBefore', exact(300)) + rg_table([rg_row([rg_cell(card_paras(words), 5400)], 8000, header=True),
                                                        rg_row([rg_cell(card_paras(['Willow01']), 5400)]), rg_row([rg_cell(card_paras(['Willow02']), 5400)])],
                                                       [5400], True, no_margins) + para('MapleAfter', exact(300)))
    rg_add('tables-header-row-taller-than-page-times-new-roman', 'An exact 400pt header row above two body rows on a 300 x 160pt card (Docxodus #1202)', texts, body, sect=rg_card)
    words = card_lines('Inner', 8)
    texts = ['OuterBefore', 'OuterHead'] + words + ['OuterTail', 'OuterAfter']
    inner = rg_table([rg_row([rg_cell(card_paras(words), 5000)], 8000)], [5000], True, no_margins)
    body = (para('OuterBefore', exact(300)) + rg_table([rg_row([rg_cell(para('OuterHead', exact(300)) + inner + para('OuterTail', exact(300)), 5400)])],
                                                       [5400], True, no_margins) + para('OuterAfter', exact(300)))
    rg_add('tables-nested-row-taller-than-page-times-new-roman', 'A nested table whose exact 400pt row is taller than a 300 x 160pt card (Docxodus #1202)', texts, body, sect=rg_card)
    box = '<w:pBdr>' + ''.join(f'<w:{s} w:val="single" w:sz="8" w:space="0" w:color="000000"/>' for s in ('top', 'left', 'bottom', 'right')) + '</w:pBdr>'
    words = card_lines('Hazel', 28)
    body = (para('HazelBefore', exact(300)) + para(props=exact(300).replace('<w:spacing', box + '<w:spacing'), runs='<w:r><w:br/></w:r>'.join(run(w) for w in words)) + para('HazelAfter', exact(300)))
    rg_add('paragraphs-border-taller-than-page-times-new-roman', 'A bordered 28-line paragraph taller than a 300 x 160pt card (Docxodus #1202)',
           ['HazelBefore'] + words + ['HazelAfter'], body, sect=rg_card)
    words = card_lines('Larch', 28)
    body = para('LarchBefore', exact(300)) + ''.join(para(w, exact(300).replace('<w:spacing', box + '<w:spacing')) for w in words) + para('LarchAfter', exact(300))
    rg_add('paragraphs-border-group-taller-than-page-times-new-roman', 'Twenty-eight paragraphs sharing one border, taller than a 300 x 160pt card (Docxodus #1202)',
           ['LarchBefore'] + words + ['LarchAfter'], body, sect=rg_card)
    # New paper-edge probes use strict visible inventories: Cedar11/12 are not optional tokens.
    def rg_page_case(case_id, description, body, page_words, story=None):
        totals = Counter(w for words in page_words for w in words)
        assertions = []
        for page, words in enumerate(page_words, 1):
            for word in words:
                # Region markers must be unique; repeated footer words stay in the complete inventory.
                if totals[word] != 1: continue
                assertions.append({'type': 'marker-region', 'version': 2, 'marker': word,
                    'occurrence': 1, 'page': page, 'rect': [0, 0, 300, 161], 'adjudicated': 'word'})
        add(case_id, 'tables', description + ' (Docxodus #1202)', [w for words in page_words for w in words],
            body, sect=rg_card.replace('<w:sectPr>', '<w:sectPr><w:footerReference w:type="default" r:id="rStory"/>') if story else rg_card,
            styles_xml=rg_styles, font=rg_font, story=story, assertions=assertions)
    for suffix, footer, wrapped in [('lines', False, False), ('footer', True, False), ('soft-wrap', False, True)]:
        words = card_lines('Cedar', 12)
        width = 900 if wrapped else 5400
        content = para(' '.join(words), exact(300)) if wrapped else card_paras(words)
        body = (para('CedarBefore', exact(300)) + rg_table([rg_row([rg_cell(content, width)], 8000)],
                [width], True, no_margins) + para('CedarAfter', exact(300)))
        pages = [['CedarBefore'], words[:10], ['CedarAfter']]
        if footer: pages = [p + ['FooterProbe'] for p in pages]
        rg_page_case('tables-row-exact-paper-edge-' + suffix + '-times-new-roman',
            'An exact 400pt row with twelve ' + ('soft-wrapped words' if wrapped else 'paragraphs')
            + (' and a footer' if footer else ''), body, pages,
            ('footer', para('FooterProbe', exact(300))) if footer else None)
    for suffix, height, header in [('two-hundred', 4000, True), ('no-header', 8000, False)]:
        words = card_lines('Maple', 8)
        body = (para('MapleBefore', exact(300)) + rg_table([rg_row([rg_cell(card_paras(words), 5400)], height, header=header),
                rg_row([rg_cell(para('Willow01', exact(300)), 5400)]), rg_row([rg_cell(para('Willow02', exact(300)), 5400)])],
                [5400], True, no_margins) + para('MapleAfter', exact(300)))
        pages = [['MapleBefore'], words, ['Willow01', 'Willow02']]
        if header: pages.append(['MapleAfter'])
        else: pages[-1].append('MapleAfter')
        rg_page_case('tables-row-oversized-' + suffix + '-times-new-roman',
            'An oversized ' + ('200pt exact header' if header else '400pt first row without a header')
            + ' followed by two body rows', body, pages)
    # A missing serialized final paragraph still consumes a normal line in native Word.
    for suffix, header in [('exact-row', False), ('header-row', True)]:
        rows = [rg_row([rg_cell(para('AlderEnd', exact(300)), 5400)], 8000, header=header)]
        if header: rows.append(rg_row([rg_cell(para('BirchEnd', exact(300)), 5400)]))
        rg_page_case('tables-final-' + suffix + '-blank-page-times-new-roman',
            'A table-ending exact 400pt ' + ('header' if header else 'row') + ' with Word required final paragraph',
            rg_table(rows, [5400], True, no_margins),
            [['AlderEnd'], ['BirchEnd'], []] if header else [['AlderEnd'], []])
    rg_word = {'paragraphs-border-group-taller-than-page-times-new-roman': {'Larch09': [2, 10.0, 12.2, 47.01, 24.4], 'Larch10': [2, 10.0, 27.23, 47.01, 39.43], 'Larch11': [2, 10.0, 42.25, 47.01, 54.45], 'Larch12': [2, 10.0, 57.28, 47.01, 69.48], 'Larch13': [2, 10.0, 72.3, 47.01, 84.51], 'Larch14': [2, 10.0, 87.33, 47.01, 99.53], 'Larch15': [2, 10.0, 102.35, 47.01, 114.56], 'Larch16': [2, 10.0, 117.38, 47.01, 129.58], 'Larch17': [2, 10.0, 132.4, 47.01, 144.61], 'Larch18': [3, 10.0, 12.2, 47.01, 24.4], 'Larch19': [3, 10.0, 27.23, 47.01, 39.43], 'Larch20': [3, 10.0, 42.25, 47.01, 54.45], 'Larch21': [3, 10.0, 57.28, 47.01, 69.48], 'Larch22': [3, 10.0, 72.3, 47.01, 84.51], 'Larch23': [3, 10.0, 87.33, 47.01, 99.53], 'Larch24': [3, 10.0, 102.35, 47.01, 114.56], 'Larch25': [3, 10.0, 117.38, 47.01, 129.58], 'Larch26': [3, 10.0, 132.4, 47.01, 144.61], 'Larch27': [4, 10.0, 12.2, 47.01, 24.4], 'Larch28': [4, 10.0, 27.23, 47.01, 39.43], 'LarchAfter': [4, 10.0, 43.25, 58.87, 55.45]}, 'paragraphs-border-taller-than-page-times-new-roman': {'Hazel09': [2, 10.0, 12.2, 46.76, 24.4], 'Hazel10': [2, 10.0, 27.23, 46.76, 39.43], 'Hazel11': [2, 10.0, 42.25, 46.76, 54.45], 'Hazel12': [2, 10.0, 57.28, 46.76, 69.48], 'Hazel13': [2, 10.0, 72.3, 46.76, 84.51], 'Hazel14': [2, 10.0, 87.33, 46.76, 99.53], 'Hazel15': [2, 10.0, 102.35, 46.76, 114.56], 'Hazel16': [2, 10.0, 117.38, 46.76, 129.58], 'Hazel17': [2, 10.0, 132.4, 46.76, 144.61], 'Hazel18': [3, 10.0, 12.2, 46.76, 24.4], 'Hazel19': [3, 10.0, 27.23, 46.76, 39.43], 'Hazel20': [3, 10.0, 42.25, 46.76, 54.45], 'Hazel21': [3, 10.0, 57.28, 46.76, 69.48], 'Hazel22': [3, 10.0, 72.3, 46.76, 84.51], 'Hazel23': [3, 10.0, 87.33, 46.76, 99.53], 'Hazel24': [3, 10.0, 102.35, 46.76, 114.56], 'Hazel25': [3, 10.0, 117.38, 46.76, 129.58], 'Hazel26': [3, 10.0, 132.4, 46.76, 144.61], 'Hazel27': [4, 10.0, 12.2, 46.76, 24.4], 'Hazel28': [4, 10.0, 27.23, 46.76, 39.43], 'HazelAfter': [4, 10.0, 43.25, 58.88, 55.45]}, 'tables-nested-row-taller-than-page-times-new-roman': {'Inner01': [2, 12.0, 14.23, 46.24, 26.43], 'Inner02': [2, 12.0, 29.23, 46.24, 41.43], 'Inner03': [2, 12.0, 44.25, 46.24, 56.45], 'Inner04': [2, 12.0, 59.28, 46.24, 71.48], 'Inner05': [2, 12.0, 74.3, 46.24, 86.51], 'Inner06': [2, 12.0, 89.33, 46.24, 101.53], 'Inner07': [2, 12.0, 104.35, 46.24, 116.56], 'Inner08': [2, 12.0, 119.38, 46.24, 131.58], 'OuterAfter': [3, 10.0, 29.23, 58.37, 41.43], 'OuterTail': [3, 11.0, 13.2, 54.03, 25.4]}, 'tables-header-row-taller-than-page-times-new-roman': {'MapleAfter': [4, 10.0, 12.196725, 61.387525, 24.4014]}}
    for case in cases:
        boxes = rg_word.get(case['id'])
        if boxes:
            case['assertions'] = [a if a.get('marker') not in boxes else
                {'type': 'marker-region', 'version': 2, 'marker': a['marker'], 'occurrence': 1,
                 'page': boxes[a['marker']][0], 'rect': [boxes[a['marker']][1]-1, boxes[a['marker']][2]-1,
                 boxes[a['marker']][3]+1, boxes[a['marker']][4]+1], 'tolerancePt': 0.0001, 'adjudicated': 'word'}
                for a in case['assertions']]
            case['version'] = 2
    for cid, description, parts, pages, references in kept_note_flow_cases():
        # Literal text plus the semantic note number supplies the complete inventory.
        # The number touches its note's first word; body reference numbers are separate.
        # These assert page membership within the source paper, not exact baselines or
        # margin-edge rounding. Unaligned coordinates and rasters remain measured as usual.
        add(cid, 'notes', description, list(pages) + references, '',
            font='Times New Roman', literal_parts=parts,
            assertions=[{'type': 'marker-region', 'version': 2, 'marker': marker,
                         'occurrence': 1, 'page': page, 'rect': [0, 0, 400, 320],
                         'adjudicated': 'word'} for marker, page in pages.items()])
    for cid, description, parts, shape, count, variant, mode in kept_note_paragraph_inputs():
        if shape == 'short':
            first = (17 if count == 19 and variant != 'widow-off' else 18)
            if mode == 15:
                pages = {'SpruceCite01': 1, 'SpruceTail01': 1}
                note_pages = [2] * 19 + [3] * 2
            else:
                pages = {'SpruceCite01': 1, 'SpruceTail01': 2}
                note_pages = [1] * first + [2] * (count - first)
            pages.update({('1' if i == 1 else '') + f'SpruceNoteLine{i:02d}': page
                          for i, page in enumerate(note_pages, 1)})
            text = list(pages) + ['1']
            paper = [0, 0, 400, 320]
        else:
            cite = variant
            citation_page = 1 if cite == 1 else 2
            if mode == 15:
                body_pages = [1] * (cite - 1) + [citation_page] * (31 - cite)
                note_pages = [citation_page + 1] * 55 + [citation_page + 2] * 55 + [citation_page + 3] * 10
            else:
                body_pages = [1] * (cite - 1) + [citation_page] + [citation_page + 2] * (30 - cite)
                note_pages = [citation_page] * 53 + [citation_page + 1] * 55 + [citation_page + 2] * 12
            pages = {f'SpruceBody{i:02d}': page for i, page in enumerate(body_pages, 1)}
            pages.update({f'SpruceLongNote{i:03d}': page for i, page in enumerate(note_pages, 1)})
            text = list(pages) + ['1', '1']
            paper = [0, 0, 612, 792]
        add(cid, 'notes', description, text, '', font='Times New Roman', literal_parts=parts,
            assertions=[{'type': 'marker-region', 'version': 2, 'marker': marker,
                         'occurrence': 1, 'page': page, 'rect': paper, 'adjudicated': 'word'}
                        for marker, page in pages.items()])
    registry = {'schema': 1, 'suite': {'id': 'core-v69', 'version': 69, 'cases': [c['id'] for c in cases]}, 'cases': cases}
    (ROOT / 'fixtures' / 'manifest.json').write_text(json.dumps(registry, indent=2) + '\n')
    return registry


if __name__ == '__main__':
    print(f'Authored {len(generate()["cases"])} deterministic fixtures')
