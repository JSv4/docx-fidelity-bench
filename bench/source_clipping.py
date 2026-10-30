"""Conservative source proof for words outside authored fixed textbox clips.

Vertical exclusions require printable ASCII in the pinned Liberation Serif family
and more than two font ems of clear space below the clip. All four pinned faces'
global glyph tops are below 1.01 em; exact lines are at least one em high. This
deliberately leaves a larger guard than the glyph bound and rejects equality.
See docs/results/export-story-contexts/clip-boundary-probe.json for the font hashes
and independently read metrics. Rendered output never supplies this proof.
"""
from collections import Counter
from fractions import Fraction
import re
import xml.etree.ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
WP = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
WPS = '{http://schemas.microsoft.com/office/word/2010/wordprocessingShape}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
V = '{urn:schemas-microsoft-com:vml}'
MC = '{http://schemas.openxmlformats.org/markup-compatibility/2006}'
RUN_PROPERTIES = {W + name for name in ('rFonts', 'sz', 'color', 'b', 'i')}


def positive_integer(value):
    return int(value) if isinstance(value, str) and re.fullmatch(r'[0-9]+', value) and int(value) > 0 else None


def paragraph_line(paragraph):
    """Return a lower bound of one exact line; unsupported formatting has no proof."""
    if paragraph.tag != W + 'p' or any(child.tag not in {W + 'pPr', W + 'r'} for child in paragraph):
        return None
    properties = paragraph.find(W + 'pPr')
    if len(paragraph.findall(W + 'pPr')) != 1 or [child.tag for child in properties] != [W + 'spacing']:
        return None
    spacing = properties[0]
    if (set(spacing.attrib) != {W + name for name in ('before', 'after', 'line', 'lineRule')}
            or spacing.get(W + 'before') != '0' or spacing.get(W + 'after') != '0'
            or spacing.get(W + 'lineRule') != 'exact'):
        return None
    line = positive_integer(spacing.get(W + 'line'))
    runs = paragraph.findall(W + 'r')
    if line is None or not runs:
        return None
    largest_font = 0
    for run in runs:
        if any(child.tag not in {W + 'rPr', W + 't'} for child in run):
            return None
        formatting = run.find(W + 'rPr')
        if (len(run.findall(W + 'rPr')) != 1 or any(child.tag not in RUN_PROPERTIES for child in formatting)
                or len({child.tag for child in formatting}) != len(formatting)):
            return None
        size, font = formatting.find(W + 'sz'), formatting.find(W + 'rFonts')
        half_points = positive_integer(size.get(W + 'val')) if size is not None else None
        if (half_points is None or size.attrib != {W + 'val': str(half_points)}
                or half_points * 10 > line or font is None
                or font.attrib != {W + 'ascii': 'Liberation Serif', W + 'hAnsi': 'Liberation Serif'}):
            return None
        for toggle in (formatting.find(W + 'b'), formatting.find(W + 'i')):
            if toggle is not None and (len(toggle) or toggle.attrib not in ({}, {W + 'val': '0'}, {W + 'val': '1'})):
                return None
        text = run.findall(W + 't')
        if not text or any(not re.fullmatch(r'[\x20-\x7e]*', node.text or '') for node in text):
            return None
        largest_font = max(largest_font, half_points * 10)
    return line, largest_font


def clipped_story_words(content, height_twips=None):
    """A whole-box exclusion uses the same simple-story eligibility as a line clip."""
    paragraphs = list(content)
    lines = [paragraph_line(paragraph) for paragraph in paragraphs]
    if not paragraphs or any(line is None for line in lines):
        return Counter()
    result, offset = Counter(), 0
    for paragraph, (line, font) in zip(paragraphs, lines):
        if height_twips is None or offset - height_twips > font * 2:
            result.update(' '.join(node.text or '' for node in paragraph.iter(W + 't')).split())
        offset += line
    return result


def horizontal_paper_exclusion(anchor, parents, root, width_emu):
    """A far horizontal offset is outside any valid margin origin; no host-y estimate."""
    if root.tag != W + 'document' or anchor.get('simplePos') != '0':
        return False
    body = root.find(W + 'body')
    drawing = parents.get(anchor)
    run = parents.get(drawing)
    paragraph = parents.get(run)
    if (body is None or run is None or run.tag != W + 'r' or paragraph is None
            or paragraph.tag != W + 'p' or parents.get(paragraph) is not body):
        return False
    if paragraph.find(W + 'pPr/' + W + 'framePr') is not None:
        return False
    sections = list(root.iter(W + 'sectPr'))
    if len(sections) != 1 or parents.get(sections[0]) is not body:
        return False
    section = sections[0]
    if [node.tag for node in section] != [W + 'pgSz', W + 'pgMar']:
        return False
    size, margins = section
    if set(size.attrib) != {W + 'w', W + 'h'} or set(margins.attrib) != {W + key for key in ('top', 'right', 'bottom', 'left', 'header', 'footer')}:
        return False
    page_width, page_height = positive_integer(size.get(W + 'w')), positive_integer(size.get(W + 'h'))
    if page_width is None or page_height is None or any(not re.fullmatch(r'[0-9]+', value) for value in margins.attrib.values()):
        return False
    if (int(margins.get(W + 'left')) + int(margins.get(W + 'right')) >= page_width
            or int(margins.get(W + 'top')) + int(margins.get(W + 'bottom')) >= page_height):
        return False
    positions = []
    for axis, basis in [('H', 'margin'), ('V', 'paragraph')]:
        nodes = anchor.findall(WP + 'position' + axis)
        if (len(nodes) != 1 or nodes[0].attrib != {'relativeFrom': basis} or len(nodes[0]) != 1
                or nodes[0][0].tag != WP + 'posOffset' or nodes[0][0].attrib
                or not re.fullmatch(r'-?[0-9]+', nodes[0][0].text or '')):
            return False
        value = int(nodes[0][0].text)
        if not -2147483648 <= value <= 2147483647:
            return False
        positions.append(value)
    wrapping = [node for node in anchor if node.tag.startswith(WP + 'wrap')]
    if len(wrapping) != 1 or wrapping[0].tag != WP + 'wrapNone' or wrapping[0].attrib or len(wrapping[0]):
        return False
    # Margin origins lie within this explicitly bounded paper. This deliberately
    # rejects closer off-paper boxes whose proof would require additional layout.
    return positions[0] + width_emu + page_width * 635 < 0 or positions[0] > page_width * 635


def textbox_clipped_words(archive):
    """Inspect OOXML only; never accept clipping claimed by a rendered candidate."""
    roots = [ET.fromstring(archive.read(name)) for name in archive.namelist()
             if name.startswith('word/') and name.endswith('.xml')]
    # Continuations and incoming VML references can live outside the candidate box.
    # This narrow contract intentionally rejects those relationships document-wide.
    if any(node.tag in {WPS + 'linkedTxbx', MC + 'AlternateContent'}
           or any('mso-next-textbox' in value.lower() or 'mso-linked-textbox' in value.lower()
                  for value in node.attrib.values())
           for root in roots for node in root.iter()):
        return Counter()
    # Inherited hidden/raised text or positioned default paragraphs defeats this simple proof.
    for root in roots:
        if root.tag == W + 'styles':
            if any(node.tag in {W + 'framePr', W + 'textDirection'} for node in root.iter()):
                return Counter()
            if any(child.tag not in RUN_PROPERTIES for formatting in root.iter(W + 'rPr') for child in formatting):
                return Counter()
    result = Counter()
    for root in roots:
        parents = {child: parent for parent in root.iter() for child in parent}
        for container in list(root.iter(WP + 'inline')) + list(root.iter(WP + 'anchor')):
            shapes = list(container.iter(WPS + 'wsp'))
            if len(shapes) != 1 or any(node.tag.endswith(('sizeRelH', 'sizeRelV', 'linkedTxbx')) for node in container.iter()):
                continue
            if (parents.get(container) is None or parents[container].tag != W + 'drawing'
                    or container.findall(A + 'graphic/' + A + 'graphicData/' + WPS + 'wsp') != shapes):
                continue
            shape = shapes[0]
            body, story, extent = shape.find(WPS + 'bodyPr'), shape.find(WPS + 'txbx'), container.find(WP + 'extent')
            if body is None or story is None or story.attrib or extent is None:
                continue
            if (len(container.findall(WP + 'extent')) != 1 or len(shape.findall(WPS + 'bodyPr')) != 1
                    or len(shape.findall(WPS + 'txbx')) != 1 or len(story) != 1):
                continue
            if (body.attrib != {name: '0' for name in ('lIns', 'tIns', 'rIns', 'bIns')}
                    or len(body) != 1 or body[0].tag != A + 'noAutofit' or body[0].attrib or len(body[0])):
                continue
            width, height = positive_integer(extent.get('cx')), positive_integer(extent.get('cy'))
            properties = shape.find(WPS + 'spPr')
            if properties is None or any(node.tag not in {A + key for key in ('xfrm', 'prstGeom', 'noFill', 'ln')} for node in properties):
                continue
            line = properties.find(A + 'ln')
            if line is not None and (line.attrib or [node.tag for node in line] != [A + 'noFill']):
                continue
            transform = shape.find(WPS + 'spPr/' + A + 'xfrm')
            if (width is None or height is None or transform is None or transform.attrib
                    or [child.tag for child in transform] != [A + 'off', A + 'ext']):
                continue
            offset, size = transform.find(A + 'off'), transform.find(A + 'ext')
            if (offset is None or offset.attrib != {'x': '0', 'y': '0'} or size is None
                    or size.attrib != {'cx': str(width), 'cy': str(height)}):
                continue
            content = story.find(W + 'txbxContent')
            if content is not None:
                if container.tag == WP + 'inline':
                    result.update(clipped_story_words(content, Fraction(height, 635)))
                elif horizontal_paper_exclusion(container, parents, root, width):
                    result.update(clipped_story_words(content))
        for shape in root.iter(V + 'shape'):
            box = shape.find(V + 'textbox')
            if (box is None or box.attrib != {'inset': '0,0,0,0'}
                    or set(shape.attrib) - {'id', 'style', 'filled', 'stroked'}
                    or len(shape) != 1 or len(box) != 1
                    or parents.get(shape) is None or parents[shape].tag != W + 'pict'):
                continue
            declarations = shape.get('style', '').rstrip(';').split(';')
            if len(declarations) != 2 or any(':' not in declaration for declaration in declarations):
                continue
            dimensions = dict(part.strip().split(':', 1) for part in declarations)
            if set(dimensions) != {'width', 'height'}:
                continue
            values = [re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)pt', dimensions[key].strip()) for key in ('width', 'height')]
            if any(value is None or Fraction(value[1]) <= 0 for value in values):
                continue
            content = box.find(W + 'txbxContent')
            if content is not None:
                result.update(clipped_story_words(content, Fraction(values[1][1]) * 20))
    return result
