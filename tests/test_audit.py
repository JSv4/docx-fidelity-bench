import io
import unittest
from zipfile import ZipFile

from bench import audit
from bench.common import PLACEHOLDER_FONT_BYTES

REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'


def archive(members):
    buffer = io.BytesIO()
    with ZipFile(buffer, 'w') as package:
        for name, payload in members.items():
            package.writestr(name, payload)
    return ZipFile(io.BytesIO(buffer.getvalue()))


def rels(*items):
    return f'<Relationships xmlns="{PKG}">' + ''.join(
        f'<Relationship Id="{i}" Type="{REL + kind}" Target="{target}"{" TargetMode=" + chr(34) + "External" + chr(34) if external else ""}/>'
        for i, kind, target, external in items) + '</Relationships>'


def document(*items):
    return {'word/document.xml': '<w:document/>', 'word/_rels/document.xml.rels': rels(*items)}


def font_package(payload, target='fonts/ExampleSans-regular.ttf', name='word/fonts/ExampleSans-regular.ttf'):
    members = document(('rFonts', 'fontTable', 'fontTable.xml', False))
    members.update({'word/fontTable.xml': '<w:fonts/>',
                    'word/_rels/fontTable.xml.rels': rels(('rIdEmb1', 'font', target, False)),
                    name: payload})
    return archive(members)


class PackageAudit(unittest.TestCase):
    def test_plain_package_passes(self):
        audit.check_package(archive(document(('rStyles', 'styles', 'styles.xml', False))))

    def test_reserved_hyperlinks_from_the_main_document_pass(self):
        for target in ('mailto:first@example.com;second@example.com', 'mailto:solo@example.com',
                       'mailto:first@example.com, second@example.com', 'mailto:first@example.com second@example.com',
                       'https://example.com/terms', 'https://example.com'):
            audit.check_package(archive(document(('rLink', 'hyperlink', target, True))))

    def test_other_external_relationships_are_refused(self):
        for item in [('rLink', 'hyperlink', 'mailto:someone@example.org', True),
                     ('rLink', 'hyperlink', 'mailto:first@example.com;someone@example.net', True),
                     ('rLink', 'hyperlink', 'mailto:', True),
                     ('rLink', 'hyperlink', 'mailto:first@example.com;;second@example.com', True),
                     ('rLink', 'hyperlink', 'mailto:first@example.com;', True),
                     ('rLink', 'hyperlink', 'mailto:Solo@example.com', True),
                     ('rLink', 'hyperlink', 'mailto:solo@example.com?subject=Notice', True),
                     ('rLink', 'hyperlink', 'mailto:solo%40example.com', True),
                     ('rLink', 'hyperlink', 'https://example.com/terms?ref=1', True),
                     ('rLink', 'hyperlink', 'https://example.com:8443/terms', True),
                     ('rLink', 'hyperlink', 'https://example.com/%7Eterms', True),
                     ('rLink', 'hyperlink', 'https://EXAMPLE.com/terms', True),
                     ('rLink', 'hyperlink', 'https://example.com.evil.test/terms', True),
                     ('rLink', 'hyperlink', 'http://example.com/terms', True),
                     ('rImage', 'image', 'https://example.com/picture.png', True),
                     ('rFrame', 'oleObject', 'https://example.com/object', True)]:
            with self.subTest(item=item), self.assertRaisesRegex(ValueError, 'External document resource'):
                audit.check_package(archive(document(item)))

    def test_external_hyperlink_from_another_part_is_refused(self):
        members = document()
        members['word/_rels/header1.xml.rels'] = rels(('rLink', 'hyperlink', 'https://example.com/terms', True))
        with self.assertRaisesRegex(ValueError, 'External document resource'):
            audit.check_package(archive(members))

    def test_font_table_with_the_placeholder_passes(self):
        audit.check_package(font_package(PLACEHOLDER_FONT_BYTES))

    def test_font_entry_holding_other_bytes_is_refused(self):
        for payload in (b'\x00\x01\x00\x00' + bytes(60), PLACEHOLDER_FONT_BYTES + b'x'):
            with self.subTest(payload=payload[:8]), self.assertRaisesRegex(ValueError, 'Unexpected embedded asset'):
                audit.check_package(font_package(payload))

    def test_font_named_entry_no_font_relationship_reaches_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'Unexpected embedded asset'):
            audit.check_package(font_package(PLACEHOLDER_FONT_BYTES, target='fonts/Other.ttf'))
        members = document()
        members['word/fonts/Loose.ttf'] = PLACEHOLDER_FONT_BYTES
        with self.assertRaisesRegex(ValueError, 'Unexpected embedded asset'):
            audit.check_package(archive(members))

    def test_font_relationship_to_a_differently_named_part_needs_the_placeholder(self):
        truetype = b'\x00\x01\x00\x00' + bytes(60)
        with self.assertRaisesRegex(ValueError, 'Unexpected embedded asset'):
            audit.check_package(font_package(truetype, target='media/image1.bin', name='word/media/image1.bin'))
        audit.check_package(font_package(PLACEHOLDER_FONT_BYTES, target='media/image1.bin', name='word/media/image1.bin'))

    def test_font_relationship_to_a_missing_part_is_refused(self):
        members = document(('rFonts', 'fontTable', 'fontTable.xml', False))
        members.update({'word/fontTable.xml': '<w:fonts/>',
                        'word/_rels/fontTable.xml.rels': rels(('rIdEmb1', 'font', 'fonts/Absent.ttf', False))})
        with self.assertRaisesRegex(ValueError, 'Unexpected embedded asset'):
            audit.check_package(archive(members))

    def test_font_relationship_outside_the_font_table_is_refused(self):
        for payload in (PLACEHOLDER_FONT_BYTES, b'\x00\x01\x00\x00' + bytes(60)):
            members = document(('rFont', 'font', 'media/face.bin', False))
            members['word/media/face.bin'] = payload
            with self.subTest(payload=payload[:8]), self.assertRaisesRegex(ValueError, 'Unexpected embedded asset'):
                audit.check_package(archive(members))

    def test_font_content_types_need_the_placeholder(self):
        truetype = b'\x00\x01\x00\x00' + bytes(60)
        for types in ('<Default Extension="bin" ContentType="application/x-font-ttf"/>',
                      '<Override PartName="/word/media/face.bin" ContentType="application/vnd.openxmlformats-officedocument.obfuscatedFont"/>',
                      '<Default Extension="BIN" ContentType="font/ttf"/>'):
            members = document()
            members['word/media/face.bin'] = truetype
            members['[Content_Types].xml'] = f'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">{types}</Types>'
            with self.subTest(types=types), self.assertRaisesRegex(ValueError, 'Unexpected embedded asset'):
                audit.check_package(archive(members))
            members['word/media/face.bin'] = PLACEHOLDER_FONT_BYTES
            audit.check_package(archive(members))

    def test_font_table_type_is_not_a_font_program_type(self):
        package = font_package(PLACEHOLDER_FONT_BYTES)
        members = {name: package.read(name) for name in package.namelist()}
        members['[Content_Types].xml'] = ('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                                          '<Default Extension="ttf" ContentType="application/x-font-ttf"/>'
                                          '<Override PartName="/word/fontTable.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml"/></Types>')
        audit.check_package(archive(members))

    def test_metadata_is_matched_whatever_its_case_or_parameters(self):
        text = b'Plain text standing in for a part that metadata calls a font.'
        # A renamed font table whose relationships file has an upper-case extension.
        members = document(('rFonts', 'fontTable', 'ft.xml', False))
        members.update({'word/ft.xml': '<w:fonts/>', 'word/_rels/ft.xml.RELS': rels(('rIdEmb1', 'font', 'media/face.bin', False)),
                        'word/media/face.bin': text})
        with self.assertRaisesRegex(ValueError, 'Unexpected embedded asset'):
            audit.check_package(archive(members))
        # An external image in a relationships file with an upper-case extension.
        members = document()
        members['word/_rels/document.xml.RELS'] = rels(('rImage', 'image', 'https://example.org/x.png', True))
        with self.assertRaisesRegex(ValueError, 'External document resource'):
            audit.check_package(archive(members))
        # Font relationship types differing only in case or trailing space.
        for kind in ('Font', 'font '):
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'Unexpected embedded asset'):
                audit.check_package(archive({**document(('rFonts', 'fontTable', 'fontTable.xml', False)), 'word/fontTable.xml': '<w:fonts/>',
                                             'word/_rels/fontTable.xml.rels': rels(('rIdEmb1', kind, 'media/face.bin', False)),
                                             'word/media/face.bin': text}))
        # Content types in a lower-case part, with parameters, or for embedded OpenType.
        for name, item in (('[content_types].xml', '<Default Extension="bin" ContentType="application/x-font-ttf"/>'),
                           ('[Content_Types].xml', '<Override PartName="/WORD/media/face.bin" ContentType="application/vnd.openxmlformats-officedocument.obfuscatedFont; x=1"/>'),
                           ('[Content_Types].xml', '<Default Extension="bin" ContentType="application/vnd.ms-fontobject"/>')):
            members = document()
            members['word/media/face.bin'] = text
            members[name] = f'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">{item}</Types>'
            with self.subTest(item=item), self.assertRaisesRegex(ValueError, 'Unexpected embedded asset'):
                audit.check_package(archive(members))
            members['word/media/face.bin'] = PLACEHOLDER_FONT_BYTES
            audit.check_package(archive(members))

    def test_case_variant_duplicate_of_the_placeholder_is_refused(self):
        package = font_package(PLACEHOLDER_FONT_BYTES)
        members = {name: package.read(name) for name in package.namelist()}
        members['word/fonts/examplesans-regular.TTF'] = b'Plain text beside the placeholder.'
        with self.assertRaisesRegex(ValueError, 'Unexpected embedded asset'):
            audit.check_package(archive(members))

    def test_orphan_font_programs_are_refused_whatever_their_name(self):
        def sfnt(tag):
            return tag + b'\x00\x0b\x00\x80\x00\x03\x00\x30' + b'cmap\x00\x00\x00\x00\x00\x00\x00\xbc\x00\x00\x01\x00' * 11
        programs = {tag: sfnt(tag) for tag in (b'\x00\x01\x00\x00', b'OTTO', b'true', b'typ1', b'ttcf', b'wOFF', b'wOF2')}
        program = programs[b'\x00\x01\x00\x00']
        programs['obfuscated'] = bytes(b ^ 0x5A for b in program[:32]) + program[32:]
        programs['png-prefixed'] = b'\x89PNG\r\n\x1a\n' + program
        for name in ('word/media/image1.bin', 'word/media/image1.png', 'word/fonts/face.odttf', 'docProps/thumbnail.jpeg', 'word/media/face.xml'):
            for label, payload in programs.items():
                members = document()
                members[name] = payload
                with self.subTest(name=name, program=label), self.assertRaisesRegex(ValueError, 'Unexpected embedded asset'):
                    audit.check_package(archive(members))

    def test_text_png_and_placeholder_entries_pass(self):
        members = document()
        members['[trash]/0000.dat'] = b'<obsolete>Discarded text fragment'
        members['word/media/dot.png'] = b'\x89PNG\r\n\x1a\n' + b'\x00\x00\x00\x00IEND\xaeB`\x82'
        audit.check_package(archive(members))

    def test_custom_xml_is_still_refused(self):
        members = document()
        members['customXml/item1.xml'] = '<root/>'
        with self.assertRaisesRegex(ValueError, 'Unexpected embedded asset'):
            audit.check_package(archive(members))


if __name__ == '__main__':
    unittest.main()
