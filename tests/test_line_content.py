import copy
import unittest

from bench.common import validate_registry
from bench.pdf import reference_failures

PAIRS = {'line-content-break-empty': 'line-content-break-control',
         'line-content-number-large': 'line-content-number-control',
         'line-content-lead-center': 'line-content-lead-center-control',
         'line-content-bullet-symbol': 'line-content-bullet-symbol-control'}


def ideal(case):
    """Each label's ink just inside its own slot, as a conforming render places it."""
    return dict(geometry=[dict(media=[0, 0, 612, 792], crop=[0, 0, 612, 792], rotation=0)],
        fonts=['LiberationSerif'], tokens=case['tokens'],
        words=[dict(text=a['marker'], page=1, rect=[a['rect'][0] + 18, a['rect'][1] + .2, 160, a['rect'][3] - .2])
            for a in case['assertions']])


class LineContentContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {c['id']: c for c in validate_registry()['cases'] if c['id'].startswith('line-content-')}

    def heights(self, case_id):
        return [round(a['rect'][3] - a['rect'][1], 3) for a in self.cases[case_id]['assertions']]

    def test_slots_follow_each_lines_own_fonts(self):
        self.assertEqual(len(self.cases), 8)
        natural = round(2355 / 2048 * 12, 3)
        # Empty 8pt break lines (not slots of their own) shorten the stack; text lines keep 12pt.
        self.assertEqual(self.heights('line-content-break-empty'), self.heights('line-content-break-control'))
        empty_tops = [a['rect'][1] for a in self.cases['line-content-break-empty']['assertions']]
        control_tops = [a['rect'][1] for a in self.cases['line-content-break-control']['assertions']]
        self.assertAlmostEqual(control_tops[-1] - empty_tops[-1], 5 * 2355 / 2048 * (12 - 8), 3)
        # An 18pt number lifts only its line's ascent; the following line keeps the text's height.
        self.assertEqual(self.heights('line-content-number-large')[:2], [round((1912 * 18 + 443 * 12) / 2048, 3), natural])
        self.assertEqual(self.heights('line-content-number-control')[:2], [natural, natural])
        # A centered 16pt lead label sizes only its own line.
        self.assertEqual(self.heights('line-content-lead-center')[:2], [round(2355 / 2048 * 16, 3), round(2355 / 2048 * 9, 3)])
        self.assertEqual(set(self.heights('line-content-lead-center')[1:]), set(self.heights('line-content-lead-center-control')))
        # A Symbol bullet keeps Symbol's 2059/2048 ascent over the text's descent.
        self.assertEqual(set(self.heights('line-content-bullet-symbol')), {round((2059 * 12 + 443 * 12) / 2048, 3)})
        self.assertEqual(set(self.heights('line-content-bullet-symbol-control')), {natural})
        for case in self.cases.values():
            self.assertTrue(all(a['tolerancePt'] == .76 and a['page'] == 1 for a in case['assertions']))

    def test_controls_and_largest_run_layouts_fail_their_targets(self):
        for target, control in PAIRS.items():
            with self.subTest(case=target):
                case = self.cases[target]
                self.assertFalse(reference_failures(case, ideal(case)))
                self.assertFalse(reference_failures(self.cases[control], ideal(self.cases[control])))
                # The control's uniform lines, or every line as tall as the tallest, misplace labels.
                moved = ideal(case)
                moved['words'] = [dict(word, text=label) for word, label in
                    zip(ideal(self.cases[control])['words'], [a['marker'] for a in case['assertions']])]
                self.assertIn('assertion-marker-region', reference_failures(case, moved))
                if len(set(self.heights(target))) == 1: continue
                tallest = max(self.heights(target))
                uniform = copy.deepcopy(ideal(case))
                for index, word in enumerate(uniform['words']):
                    word['rect'][1] = 72 + index * tallest + .2
                    word['rect'][3] = 72 + (index + 1) * tallest - .2
                self.assertIn('assertion-marker-region', reference_failures(case, uniform))
                dropped = ideal(case)
                dropped['words'].pop()
                self.assertIn('assertion-marker-region', reference_failures(case, dropped))


if __name__ == '__main__':
    unittest.main()
