import copy
import unittest

from bench import common, pdf


class MarkerSeparation(unittest.TestCase):
    def checks(self, second, page=1, tolerance=0.5, duplicate=False, missing=False):
        declaration = {'type': 'non-overlapping-markers', 'version': 1,
                       'markers': ['Frame', 'After'], 'tolerancePt': tolerance}
        geometry = {'rotation': 0, 'media': [0, 0, 612, 792], 'crop': [0, 0, 612, 792]}
        info = {'geometry': [geometry, geometry], 'fonts': ['LiberationSerif'],
                'tokens': {'Frame': 1, 'After': 1}, 'words': [
                    {'text': 'Frame', 'page': 1, 'rect': [84, 84, 164, 96.2]},
                    {'text': 'After', 'page': page, 'rect': second}]}
        if duplicate:
            info['words'].append(copy.deepcopy(info['words'][-1]))
        if missing:
            info['words'].pop()
        case = {'fonts': ['Liberation Serif'], 'tokens': info['tokens'], 'assertions': [declaration]}
        return pdf.correctness(case, info, info)[-1]['passed']

    def test_beside_below_or_another_page_are_distinct_valid_layouts(self):
        for rect, page in [([270, 84, 320, 96.2], 1), ([72, 108, 122, 120.2], 1),
                           ([84, 84, 164, 96.2], 2), ([84, 96, 134, 108.2], 1)]:
            with self.subTest(rect=rect, page=page):
                self.assertTrue(self.checks(rect, page))

    def test_overprint_and_containment_fail_on_either_axis(self):
        for rect in ([72, 84, 122, 96.2], [90, 85, 120, 95], [70, 80, 180, 100],
                     [163.49, 84, 180, 96], [84, 95.69, 150, 108]):
            with self.subTest(rect=rect):
                self.assertFalse(self.checks(rect))

    def test_missing_or_duplicate_labels_cannot_establish_separation(self):
        self.assertFalse(self.checks([270, 84, 320, 96], missing=True))
        self.assertFalse(self.checks([270, 84, 320, 96], duplicate=True))

    def test_invalid_bounds_or_page_cannot_establish_separation(self):
        for rect in ([270, 84, float('nan'), 96], [270, 84, float('inf'), 96],
                     [270, 84, 270, 96], [270, 96, 320, 84], [270, 84, 320], None):
            with self.subTest(rect=rect):
                self.assertFalse(self.checks(rect))
        for page in (0, -1, 3, True):
            with self.subTest(page=page):
                self.assertFalse(self.checks([270, 84, 320, 96], page))

    def test_registry_requires_two_unique_inventory_labels_and_a_small_finite_tolerance(self):
        registry = common.validate_registry()
        case = registry['cases'][0]
        labels = [word for word, count in case['tokens'].items() if count == 1][:2]
        declaration = {'type': 'non-overlapping-markers', 'version': 1,
                       'markers': labels, 'tolerancePt': 0.5}
        case['assertions'] = [declaration]
        common.validate_registry(registry)
        for patch in [{'markers': [labels[0], labels[0]]}, {'markers': [labels[0]]},
                      {'markers': [labels[0], 'NotInSource']}, {'markers': 'not-a-list'},
                      {'tolerancePt': -1}, {'tolerancePt': 2}, {'tolerancePt': float('nan')},
                      {'tolerancePt': True}, {'unexpected': 1}]:
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                broken = copy.deepcopy(registry)
                broken['cases'][0]['assertions'][0].update(patch)
                common.validate_registry(broken)


if __name__ == '__main__':
    unittest.main()
