import re
import unittest
from zipfile import ZipFile

from bench import html_artifacts, pdf
from bench.common import ROOT, read_json

BEGIN = '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
SEPARATE = '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
END = '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
LOCATION_FIELD = re.compile(re.escape(BEGIN) + r'<w:r><w:instrText xml:space="preserve"> HYPERLINK \\l "([^"]+)" '
                            r'</w:instrText></w:r>' + re.escape(SEPARATE))
SIMPLE_LOCATION = re.compile(r'<w:fldSimple w:instr=" HYPERLINK \\l &quot;([^&]+)&quot; ">')
SIMPLE_ADDRESS = re.compile(r'<w:fldSimple w:instr=" HYPERLINK &quot;([^&]+)&quot; ">')
TOC_CASES = ('field-link-toc-complex-entries', 'field-link-toc-simple-entries')
TOC_CONTROL = 'field-link-toc-element-entries-control'


def complex_to_element(xml):
    """Each complex `HYPERLINK \\l` field becomes a `w:hyperlink` holding its result, nested fields and all."""
    while (match := LOCATION_FIELD.search(xml)):
        depth, index = 1, match.end()
        while depth:
            begin, end = xml.find(BEGIN, index), xml.find(END, index)
            depth, index = (depth + 1, begin + len(BEGIN)) if -1 < begin < end else (depth - 1, end + len(END))
        xml = (xml[:match.start()] + f'<w:hyperlink w:anchor="{match.group(1)}" w:history="1">' +
               xml[match.end():index - len(END)] + '</w:hyperlink>' + xml[index:])
    return xml


def simple_to_element(xml, target):
    """Each simple HYPERLINK field becomes a `w:hyperlink`; `target` gives the element's attributes."""
    xml = SIMPLE_LOCATION.sub(lambda m: f'<w:hyperlink w:anchor="{m.group(1)}" w:history="1">', xml)
    return SIMPLE_ADDRESS.sub(lambda m: f'<w:hyperlink {target(m.group(1))}>', xml).replace('</w:fldSimple>', '</w:hyperlink>')


class FieldLinkInputs(unittest.TestCase):
    def setUp(self):
        self.cases = {c['id']: c for c in read_json(ROOT / 'fixtures/manifest.json')['cases']}

    def parts(self, case_id):
        with ZipFile(ROOT / self.cases[case_id]['input']) as package:
            return {name: package.read(name) for name in package.namelist()}

    def assert_pair(self, case_id, control_id, to_control):
        case, control = self.parts(case_id), self.parts(control_id)
        self.assertEqual(case.keys(), control.keys())
        for name in case:
            if name != 'word/document.xml':
                self.assertEqual(case[name], control[name], name)
        document = case['word/document.xml'].decode()
        self.assertNotIn('<w:hyperlink', document)
        self.assertEqual(to_control(document), control['word/document.xml'].decode())
        for key in ('tokens', 'assertions', 'htmlAssertions', 'fonts', 'profile'):
            self.assertEqual(self.cases[case_id].get(key), self.cases[control_id].get(key), key)

    def test_the_simple_field_links_differ_from_their_control_only_in_the_link_form(self):
        rels = self.parts('field-link-simple-hyperlink')['word/_rels/document.xml.rels'].decode()
        relation = {target: rid for rid, target in re.findall(r'Id="(r\w+)" Type="[^"]+/hyperlink" Target="([^"]+)"', rels)}
        document = self.parts('field-link-simple-hyperlink')['word/document.xml'].decode()
        targets = SIMPLE_ADDRESS.findall(document)
        # Both links are simple fields, one per paragraph, each naming the address its relationship holds.
        self.assertEqual(len(targets), 2)
        self.assertEqual(set(targets), set(relation))
        self.assertEqual(document.count('<w:p>'), 2)
        self.assertNotIn('fldChar', document)
        self.assert_pair('field-link-simple-hyperlink', 'field-link-simple-hyperlink-control',
                         lambda xml: simple_to_element(xml, lambda target: f'r:id="{relation[target]}"'))
        expected = {a['marker']: a['equals'] for a in self.cases['field-link-simple-hyperlink']['htmlAssertions']}
        self.assertEqual(sorted(expected.values()), sorted(targets))

    def test_each_contents_case_differs_from_the_control_only_in_the_link_form(self):
        self.assert_pair('field-link-toc-complex-entries', TOC_CONTROL, complex_to_element)
        self.assert_pair('field-link-toc-simple-entries', TOC_CONTROL,
                         lambda xml: simple_to_element(xml, lambda target: self.fail('no address link')))

    def test_the_contents_field_spans_the_entries_and_the_outside_link_follows_it(self):
        for case_id in TOC_CASES + (TOC_CONTROL,):
            document = self.parts(case_id)['word/document.xml'].decode()
            paragraphs = re.findall(r'<w:p>.*?</w:p>', document)
            entries = [p for p in paragraphs if '<w:pStyle w:val="TOC1"/>' in p]
            self.assertEqual(len(entries), 3)
            self.assertEqual(paragraphs[:3], entries)
            self.assertEqual(sum(' TOC \\o "1-3" \\h \\z \\u ' in p for p in paragraphs), 1)
            self.assertIn(' TOC \\o', entries[0])
            # The TOC field's own end closes the last entry paragraph, after the entry's link (a complex link ends
            # with its PAGEREF's end and its own); the outside link comes after it.
            link_end = {TOC_CASES[0]: END + END, TOC_CASES[1]: '</w:fldSimple>', TOC_CONTROL: '</w:hyperlink>'}[case_id]
            self.assertTrue(entries[-1].endswith(link_end + END + '</w:p>'))
            self.assertIn('WisteriaLantern', paragraphs[3])
            for i, entry in enumerate(entries, 1):
                location = f'_Toc9000{i}'
                self.assertIn(f' PAGEREF {location} \\h ', entry)
                self.assertIn('<w:rPr><w:webHidden/></w:rPr><w:t xml:space="preserve">1</w:t>', entry)
                self.assertIn('<w:r><w:rPr><w:rStyle w:val="Hyperlink"/></w:rPr><w:tab/></w:r>', entry)
                self.assertEqual(sum(f'w:name="{location}"' in p and '<w:pStyle w:val="Heading1"/>' in p
                                     for p in paragraphs), 1)
        self.assertEqual(len(LOCATION_FIELD.findall(self.parts(TOC_CASES[0])['word/document.xml'].decode())), 4)
        self.assertEqual(len(SIMPLE_LOCATION.findall(self.parts(TOC_CASES[1])['word/document.xml'].decode())), 4)

    def test_every_link_label_is_a_unique_word(self):
        for case_id in ('field-link-simple-hyperlink',) + TOC_CASES:
            case = self.cases[case_id]
            for assertion in case['htmlAssertions']:
                self.assertEqual(case['tokens'][assertion['marker']], 1)
        for case_id in TOC_CASES + (TOC_CONTROL,):
            self.assertEqual(self.cases[case_id]['pdfTextNormalization'], 'isolated-dot-leaders-v1')

    def test_the_hyperlink_blue_passes_on_the_outside_link_alone(self):
        # Regions as Poppler's 96-DPI raster measured them (docs/results/field-links/evidence.json): the reference
        # paints 0563C1 only on WisteriaLantern and its underline; blue entries spread it over the table of contents.
        declaration = self.cases['field-link-toc-complex-entries']['assertions'][0]
        self.assertEqual(declaration['rgb'], [5, 99, 193])
        info = lambda bounds, coverage: {'colorRegions': [{'page': 1, 'rgb': [5, 99, 193], 'boundsPt': bounds,
                                                           'coverage': coverage}]}
        reference = info([90.0, 132.75, 162.0, 142.5], 338.9)
        self.assertTrue(pdf.color_geometry_pass(declaration, reference, info([90.0, 132.75, 162.0, 142.5], 339.5)))
        self.assertFalse(pdf.color_geometry_pass(declaration, reference, info([71.25, 74.25, 523.5, 142.5], 3046.0)))
        # A fix that drew the outside link black too would leave no blue at all.
        self.assertFalse(pdf.color_geometry_pass(declaration, reference, info(None, 0)))

    def test_an_entry_passes_only_inside_a_link_to_its_heading(self):
        case = self.cases['field-link-toc-complex-entries']
        def html(gate):
            return ('<html><body><p>' + gate + '<span> </span><span>1</span></p>'
                    '<p><a href="#_Toc90002"><span>WisteriaTerrace </span></a></p>'
                    '<p><a href="#_Toc90003"><span>WisteriaCourt </span></a></p>'
                    '<p>See <a href="#_Toc90001"><span>WisteriaLantern</span></a></p></body></html>')
        passed = lambda gate: [r['passed'] for r in html_artifacts.check(html(gate), case['htmlAssertions'])]
        self.assertEqual(passed('<a href="#_Toc90001"><span>WisteriaGate </span></a>'), [True] * 4)
        self.assertEqual(passed('<span class="docx-Hyperlink">WisteriaGate </span>'), [False, True, True, True])
        self.assertEqual(passed('<a href="#_Toc90002"><span>WisteriaGate </span></a>'), [False, True, True, True])
        self.assertEqual(passed('<a href="#_Toc90001"><span>WisteriaGate</span></a><span>WisteriaGate</span>'),
                         [False, True, True, True])


if __name__ == '__main__':
    unittest.main()
