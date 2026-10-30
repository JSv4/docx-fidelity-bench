"""Original source-only contracts for entire paragraphs beyond fixed textbox clips."""
import copy
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from bench import common
from bench.source_clipping import A, V, W, WP, WPS, textbox_clipped_words


def source(dialect, mutate=None):
    paragraphs = ''.join(
        '<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="exact"/></w:pPr>'
        '<w:r><w:rPr><w:rFonts w:ascii="Liberation Serif" w:hAnsi="Liberation Serif"/>'
        '<w:sz w:val="20"/></w:rPr><w:t>' + word + '</w:t></w:r></w:p>'
        for word in ('TopQuartz', 'MiddleQuartz', 'EndQuartz', ' ', ' ', 'HiddenQuartz'))
    if dialect == 'drawingml':
        box = ('<w:drawing><wp:inline><wp:extent cx="1524000" cy="457200"/><a:graphic><a:graphicData>'
               '<wps:wsp><wps:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="1524000" cy="457200"/>'
               '</a:xfrm></wps:spPr><wps:txbx><w:txbxContent>' + paragraphs
               + '</w:txbxContent></wps:txbx><wps:bodyPr lIns="0" tIns="0" rIns="0" bIns="0">'
               '<a:noAutofit/></wps:bodyPr></wps:wsp></a:graphicData></a:graphic></wp:inline></w:drawing>')
    else:
        box = ('<w:pict><v:shape style="width:120pt;height:36pt" filled="f" stroked="f">'
               '<v:textbox inset="0,0,0,0"><w:txbxContent>' + paragraphs
               + '</w:txbxContent></v:textbox></v:shape></w:pict>')
    document = ET.fromstring('<w:document xmlns:w="' + W[1:-1] + '" xmlns:wp="' + WP[1:-1]
                            + '" xmlns:wps="' + WPS[1:-1] + '" xmlns:a="' + A[1:-1]
                            + '" xmlns:v="' + V[1:-1] + '"><w:body><w:p><w:r>' + box
                            + '</w:r></w:p></w:body></w:document>')
    styles = ET.fromstring('<w:styles xmlns:w="' + W[1:-1] + '"><w:docDefaults><w:rPrDefault>'
                          '<w:rPr><w:rFonts w:ascii="Liberation Serif" w:hAnsi="Liberation Serif"/>'
                          '<w:sz w:val="20"/></w:rPr></w:rPrDefault></w:docDefaults></w:styles>')
    if mutate:
        mutate(document, styles)
    output = io.BytesIO()
    with ZipFile(output, 'w') as archive:
        archive.writestr('word/document.xml', ET.tostring(document))
        archive.writestr('word/styles.xml', ET.tostring(styles))
    return output.getvalue()


def first(root, tag):
    return next(root.iter(tag))


def height(dialect, value):
    def change(document, styles):
        if dialect == 'drawingml':
            first(document, WP + 'extent').set('cy', str(value * 12700))
            first(document, A + 'ext').set('cy', str(value * 12700))
        else:
            first(document, V + 'shape').set('style', f'width:120pt;height:{value}pt')
    return change


def offpaper(document, styles):
    anchor = first(document, WP + 'inline')
    anchor.tag = WP + 'anchor'
    anchor.set('simplePos', '0')
    for axis, basis, value in [('H', 'margin', '-10160000'), ('V', 'paragraph', '0')]:
        position = ET.SubElement(anchor, WP + 'position' + axis, {'relativeFrom': basis})
        ET.SubElement(position, WP + 'posOffset').text = value
    ET.SubElement(anchor, WP + 'wrapNone')
    section = ET.SubElement(first(document, W + 'body'), W + 'sectPr')
    ET.SubElement(section, W + 'pgSz', {W + 'w': '9200', W + 'h': '9600'})
    ET.SubElement(section, W + 'pgMar', {W + key: value for key, value in
                  [('top', '800'), ('right', '1000'), ('bottom', '800'), ('left', '1000'), ('header', '200'), ('footer', '200')]})


class FixedTextboxClipContract(unittest.TestCase):
    def validate(self, dialect, mutate=None, optional=None):
        data = source(dialect, mutate)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'case.docx').write_bytes(data)
            (root / 'generator.py').write_text('# Original test source\n')
            case = {'id': 'fixed-box-source-contract', 'version': 1, 'category': 'paragraphs',
                    'description': 'Original exact-line clip contract', 'input': 'case.docx',
                    'sha256': hashlib.sha256(data).hexdigest(),
                    'generator': {'path': 'generator.py', 'sha256': common.digest(root / 'generator.py')},
                    'rights': {'license': 'MIT', 'author': 'John Scrudato IV', 'origin': 'Original test source'},
                    'profile': {'review': 'final', 'comments': 'hidden'}, 'fonts': ['Liberation Serif'],
                    'tokens': {'TopQuartz': 1, 'MiddleQuartz': 1, 'EndQuartz': 1}, 'assertions': [],
                    'clippedTokens': optional or {'HiddenQuartz': 1}}
            registry = {'schema': 1, 'suite': {'id': 'source-contract', 'version': 1, 'cases': [case['id']]}, 'cases': [case]}
            with patch.object(common, 'ROOT', root):
                return common.validate_registry(registry)

    def test_entire_final_paragraph_is_optional_in_both_fixed_dialects(self):
        for dialect in ('drawingml', 'vml'):
            with self.subTest(dialect=dialect):
                self.validate(dialect)
                with ZipFile(io.BytesIO(source(dialect))) as archive:
                    self.assertEqual(textbox_clipped_words(archive), {'HiddenQuartz': 1})

    def test_growing_the_box_or_exposing_part_of_the_line_rejects_the_exemption(self):
        for dialect in ('drawingml', 'vml'):
            for value in (40, 42, 59, 60, 66, 84):
                with self.subTest(dialect=dialect, height=value), self.assertRaises(ValueError):
                    self.validate(dialect, height(dialect, value))

    def test_moving_the_claimed_word_into_the_visible_region_is_rejected(self):
        def move(document, styles):
            paragraphs = list(first(document, W + 'txbxContent'))
            a, b = first(paragraphs[0], W + 't'), first(paragraphs[-1], W + 't')
            a.text, b.text = b.text, a.text
        for dialect in ('drawingml', 'vml'):
            with self.subTest(dialect=dialect), self.assertRaises(ValueError):
                self.validate(dialect, move)

    def test_unknown_line_and_font_geometry_is_rejected(self):
        mutations = {
            'automatic line': lambda d, s: first(d, W + 'spacing').set(W + 'lineRule', 'auto'),
            'paragraph margin': lambda d, s: first(d, W + 'spacing').set(W + 'before', '20'),
            'zero font': lambda d, s: first(d, W + 'sz').set(W + 'val', '0'),
            'raised text': lambda d, s: first(d, W + 'rPr').append(ET.Element(W + 'position', {W + 'val': '12'})),
            'hidden default': lambda d, s: first(s, W + 'rPr').append(ET.Element(W + 'vanish')),
            'duplicate size': lambda d, s: first(d, W + 'rPr').append(copy.deepcopy(first(d, W + 'sz'))),
            'unbounded font': lambda d, s: first(d, W + 'rFonts').set(W + 'ascii', 'Arial'),
            'theme substitution': lambda d, s: first(d, W + 'rFonts').set(W + 'asciiTheme', 'majorAscii'),
            'nonascii ink': lambda d, s: first(d, W + 't').__setattr__('text', 'TopQuartz\u0301'),
        }
        for dialect in ('drawingml', 'vml'):
            for label, mutation in mutations.items():
                with self.subTest(dialect=dialect, mutation=label), self.assertRaises(ValueError):
                    self.validate(dialect, mutation)

    def test_clip_boundary_and_two_em_equality_are_not_accepted(self):
        def no_gap(document, styles):
            content = first(document, W + 'txbxContent')
            for paragraph in list(content):
                if (first(paragraph, W + 't').text or '').isspace():
                    content.remove(paragraph)
        def larger_font(document, styles):
            first(list(first(document, W + 'txbxContent'))[-1], W + 'sz').set(W + 'val', '24')
        for dialect in ('drawingml', 'vml'):
            for mutation in (no_gap, larger_font, height(dialect, 40)):
                with self.subTest(dialect=dialect), self.assertRaises(ValueError):
                    self.validate(dialect, mutation)

    def test_all_four_pinned_font_faces_preserve_the_conservative_gap(self):
        for bold, italic in ((False, False), (True, False), (False, True), (True, True)):
            def face(document, styles):
                for formatting in document.iter(W + 'rPr'):
                    if bold:
                        ET.SubElement(formatting, W + 'b')
                    if italic:
                        ET.SubElement(formatting, W + 'i')
            for dialect in ('drawingml', 'vml'):
                with self.subTest(dialect=dialect, bold=bold, italic=italic):
                    self.validate(dialect, face)

    def test_far_horizontal_exclusion_covers_all_words_in_the_same_fixed_box(self):
        self.validate('drawingml', offpaper)
        with ZipFile(io.BytesIO(source('drawingml', offpaper))) as archive:
            self.assertEqual(textbox_clipped_words(archive),
                             {'TopQuartz': 1, 'MiddleQuartz': 1, 'EndQuartz': 1, 'HiddenQuartz': 1})

    def test_horizontal_exclusion_rejects_visible_ambiguous_and_nonfixed_geometry(self):
        changes = {
            'on paper': lambda d, s: first(d, WP + 'positionH')[0].__setattr__('text', '0'),
            'straddles left': lambda d, s: first(d, WP + 'positionH')[0].__setattr__('text', '-12700'),
            'touches conservative boundary': lambda d, s: first(d, WP + 'positionH')[0].__setattr__('text', '-7366000'),
            'unknown horizontal basis': lambda d, s: first(d, WP + 'positionH').set('relativeFrom', 'character'),
            'unknown vertical basis': lambda d, s: first(d, WP + 'positionV').set('relativeFrom', 'line'),
            'alignment instead of offset': lambda d, s: first(d, WP + 'positionH')[0].__setattr__('tag', WP + 'align'),
            'active simple position': lambda d, s: first(d, WP + 'anchor').set('simplePos', '1'),
            'wrapping': lambda d, s: first(d, WP + 'wrapNone').__setattr__('tag', WP + 'wrapSquare'),
            'relative width': lambda d, s: first(d, WP + 'anchor').append(ET.Element('{http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing}sizeRelH')),
            'overflow': lambda d, s: first(d, WPS + 'bodyPr').set('vertOverflow', 'overflow'),
            'autofit': lambda d, s: first(d, A + 'noAutofit').__setattr__('tag', A + 'spAutoFit'),
            'shadow ink': lambda d, s: first(d, WPS + 'spPr').append(ET.Element(A + 'effectLst')),
            'extra section': lambda d, s: first(d, W + 'body').append(copy.deepcopy(first(d, W + 'sectPr'))),
            'invalid margins': lambda d, s: first(d, W + 'pgMar').set(W + 'left', '9200'),
            'incoming link': lambda d, s: first(d, W + 'body').append(ET.Element(WPS + 'linkedTxbx', {'id': '0', 'seq': '1'})),
        }
        for label, change in changes.items():
            def mutate(document, styles):
                offpaper(document, styles)
                change(document, styles)
            with self.subTest(mutation=label), self.assertRaises(ValueError):
                self.validate('drawingml', mutate)

    def test_offpaper_optional_word_cannot_also_occur_in_the_visible_body(self):
        def duplicate(document, styles):
            offpaper(document, styles)
            paragraph = ET.SubElement(first(document, W + 'body'), W + 'p')
            ET.SubElement(ET.SubElement(paragraph, W + 'r'), W + 't').text = 'HiddenQuartz'
        with self.assertRaises(ValueError):
            self.validate('drawingml', duplicate)

    def test_links_autofit_relative_geometry_and_insets_are_rejected(self):
        mutations = {
            'drawingml': [
                lambda d, s: first(d, WPS + 'txbx').set('id', '8'),
                lambda d, s: first(d, WPS + 'bodyPr').remove(first(d, A + 'noAutofit')),
                lambda d, s: first(d, WPS + 'bodyPr').set('tIns', '12700'),
                lambda d, s: first(d, WP + 'inline').append(ET.Element('{http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing}sizeRelH')),
                lambda d, s: first(d, WP + 'extent').set('cx', '0'),
            ],
            'vml': [
                lambda d, s: first(d, V + 'shape').set('style', 'width:120pt;height:36pt;mso-next-textbox:NextBox'),
                lambda d, s: first(d, V + 'textbox').set('style', 'mso-fit-shape-to-text:true'),
                lambda d, s: first(d, V + 'textbox').set('inset', '0,1pt,0,0'),
                lambda d, s: first(d, V + 'shape').set('style', 'width:50%;height:36pt'),
                lambda d, s: first(d, V + 'shape').set('style', 'width:0pt;height:36pt'),
            ],
        }
        for dialect, changes in mutations.items():
            for index, mutation in enumerate(changes):
                with self.subTest(dialect=dialect, mutation=index), self.assertRaises(ValueError):
                    self.validate(dialect, mutation)

    def test_missing_or_duplicated_optional_source_words_are_rejected(self):
        for dialect in ('drawingml', 'vml'):
            for optional in ({'AbsentQuartz': 1}, {'HiddenQuartz': 2}):
                with self.subTest(dialect=dialect, optional=optional), self.assertRaises(ValueError):
                    self.validate(dialect, optional=optional)

    def test_external_continuation_or_incoming_vml_link_invalidates_the_proof(self):
        def continuation(document, styles):
            paragraph = ET.SubElement(first(document, W + 'body'), W + 'p')
            drawing = ET.SubElement(ET.SubElement(paragraph, W + 'r'), W + 'drawing')
            inline = ET.SubElement(drawing, WP + 'inline')
            graphic = ET.SubElement(ET.SubElement(inline, A + 'graphic'), A + 'graphicData')
            shape = ET.SubElement(graphic, WPS + 'wsp')
            ET.SubElement(shape, WPS + 'linkedTxbx', {'id': '0', 'seq': '1'})
        def incoming(document, styles):
            first(document, V + 'shape').set('id', 'ClipBox')
            paragraph = ET.SubElement(first(document, W + 'body'), W + 'p')
            picture = ET.SubElement(ET.SubElement(paragraph, W + 'r'), W + 'pict')
            ET.SubElement(picture, V + 'shape', {'style': 'width:120pt;height:36pt;mso-next-textbox:ClipBox'})
        for dialect in ('drawingml', 'vml'):
            with self.subTest(dialect=dialect), self.assertRaises(ValueError):
                self.validate(dialect, continuation)
        with self.assertRaises(ValueError):
            self.validate('vml', incoming)

    def test_conditional_alternatives_cannot_supply_clipping_proof(self):
        def conditional(document, styles):
            mc = '{http://schemas.openxmlformats.org/markup-compatibility/2006}'
            body = first(document, W + 'body')
            paragraph = body[0]
            body.remove(paragraph)
            alternatives = ET.SubElement(body, mc + 'AlternateContent')
            ET.SubElement(alternatives, mc + 'Choice', {'Requires': 'wps'}).append(paragraph)
            ET.SubElement(ET.SubElement(alternatives, mc + 'Fallback'), W + 'p')
        for dialect in ('drawingml', 'vml'):
            with self.subTest(dialect=dialect), self.assertRaises(ValueError):
                self.validate(dialect, conditional)

    def test_grouped_shape_ancestry_is_not_a_supported_fixed_box(self):
        def grouped(document, styles):
            tag = WPS + 'wsp' if any(True for _ in document.iter(WPS + 'wsp')) else V + 'shape'
            shape = first(document, tag)
            parent = next(parent for parent in document.iter() if shape in list(parent))
            parent.remove(shape)
            group_tag = '{http://schemas.microsoft.com/office/word/2010/wordprocessingGroup}wgp' if tag == WPS + 'wsp' else V + 'group'
            ET.SubElement(parent, group_tag).append(shape)
        for dialect in ('drawingml', 'vml'):
            with self.subTest(dialect=dialect), self.assertRaises(ValueError):
                self.validate(dialect, grouped)
