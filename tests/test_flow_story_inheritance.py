import copy
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from bench.common import ROOT, read_json
from bench.fixtures import W, R
from bench import pdf


class FlowStoryInputs(unittest.TestCase):
    def test_swapping_stories_between_pages_fails_despite_unchanged_token_counts(self):
        records = {c['id']: c for c in read_json(ROOT / 'fixtures/manifest.json')['cases']}
        bundle = read_json(ROOT / 'docs/results/flow-story-inheritance/reference-bundle.json')
        for name, capture in bundle['cases'].items():
            reference = capture['inspection']
            self.assertEqual([], pdf.reference_failures(records[name], reference, 'libreoffice'))
            for kind in ('Header', 'Footer'):
                swapped = copy.deepcopy(reference)
                for word in swapped['words']:
                    if word['text'].endswith(kind) and word['page'] in (1, 2):
                        word['page'] = 3 - word['page']
                self.assertTrue(pdf.reference_failures(records[name], swapped, 'libreoffice'))

    def test_control_only_makes_the_final_default_explicit(self):
        records = {c['id']: c for c in read_json(ROOT / 'fixtures/manifest.json')['cases']}
        documents = []
        for suffix in ('inherited', 'explicit-control'):
            case = records['stories-final-default-' + suffix]
            with ZipFile(ROOT / case['input']) as package:
                documents.append(ET.fromstring(package.read('word/document.xml')))
            self.assertEqual(2, case['tokens']['GentianBodyHeader'])
            self.assertEqual(2, case['tokens']['GentianBodyFooter'])
            self.assertFalse(any('Unused' in token for token in case['tokens']))
        for document in documents:
            sections = document.findall(f'.//{{{W}}}sectPr')
            self.assertEqual(3, len(sections))
            self.assertEqual('rgentianBodyheader', sections[1].find(f'{{{W}}}headerReference').get(f'{{{R}}}id'))
        final = documents[1].find(f'{{{W}}}body/{{{W}}}sectPr')
        for ref in list(final):
            if ref.tag in (f'{{{W}}}headerReference', f'{{{W}}}footerReference') and ref.get(f'{{{W}}}type') == 'default':
                final.remove(ref)
        self.assertEqual(ET.tostring(documents[0]), ET.tostring(documents[1]))


if __name__ == '__main__':
    unittest.main()
