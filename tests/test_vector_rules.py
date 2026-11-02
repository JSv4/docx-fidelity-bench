import copy
import math
import unittest
from bench import common, vector_rules


class VectorRules(unittest.TestCase):
    def widths(self, paint):
        return vector_rules.widths('<svg viewBox="0 0 100 100">'+paint+'</svg>', [32,80,128], [100,100])

    def test_strokes_and_rectangles_measure_the_same_physical_thickness(self):
        for width in [.25,.5,1,3]:
            self.assertEqual(self.widths(f'<path fill="none" stroke="rgb(32,80,128)" stroke-width="{width}" d="M0 0L80 0"/>'),[width])
            self.assertEqual(self.widths(f'<path fill="rgb(32,80,128)" d="M0 0L80 0L80 {width}L0 {width}Z M0 0"/>'),[width])

    def test_nested_transforms_use_the_perpendicular_scale(self):
        actual=self.widths('<g transform="matrix(2,0,0,1,10,20)" stroke="rgb(32,80,128)" stroke-width=".25" fill="none">'
                           '<g transform="matrix(0,1,-1,0,0,0)"><path d="M0 0L40 0"/></g><path d="M0 0L40 0"/></g>')
        self.assertEqual(actual,[.5,.25])
        actual=self.widths('<path fill="rgb(32,80,128)" transform="matrix(0,2,-2,0,20,30)" d="m0 0h40v.25h-40z"/>')
        self.assertEqual(actual,[.5])

    def test_unrelated_text_and_clip_definitions_do_not_add_rules(self):
        self.assertEqual(self.widths('<defs><path fill="rgb(32,80,128)" d="M0 0C1 1 2 2 3 3"/></defs>'
                                    '<g fill="rgb(0,0,0)"><use href="#glyph"/></g>'
                                    '<path stroke="rgb(32,80,128)" stroke-width=".5" d="M0 0L80 0"/>'),[.5])

    def test_unknown_colored_geometry_and_missing_paint_fail_closed(self):
        for paint in ['<path fill="rgb(32,80,128)" d="M0 0L80 0L40 10Z"/>',
                      '<path fill="rgb(32,80,128)" stroke="rgb(32,80,128)" stroke-width=".25" d="M0 0L80 0L80 .25L0 .25Z"/>',
                      '<path fill="rgb(32,80,128)" d="M0 0C1 1 2 2 3 3"/>',
                      '<use fill="rgb(32,80,128)" href="#glyph"/>',
                      '<path stroke="rgb(32,80,128)" transform="scale(2)" d="M0 0L80 0"/>',
                      '<path fill="rgb(0,0,0)" d="M0 0L80 0L80 1L0 1Z"/>']:
            with self.subTest(paint=paint), self.assertRaises(ValueError): self.widths(paint)

    def test_width_sets_require_every_declared_size_and_reject_extra_sizes(self):
        declaration={'widthsPt':[.25,1],'tolerancePt':.01}
        self.assertTrue(vector_rules.matches(declaration,{'widthsPt':[.25,.25,1]}))
        for observed in [[],[.25],[.25,1,.75],[.75],[math.inf]]:
            self.assertFalse(vector_rules.matches(declaration,{'widthsPt':observed}))
        self.assertFalse(vector_rules.matches(declaration,{'widthsPt':[.25,1],'error':'unsupported paint'}))

    def test_declarations_reject_ambiguous_or_nonfinite_widths(self):
        registry=common.validate_registry()
        original=next(c for c in registry['cases'] if c['id']=='tables-fractional-border-quarter')
        for key,value in [('widthsPt',[]),('widthsPt',[True]),('widthsPt',[float('nan')]),('widthsPt',[-1]),
                          ('page',True),('page',0),('rgb',[32,32,32]),('tolerancePt',.1),('tolerancePt',float('inf'))]:
            changed=copy.deepcopy(registry)
            case=copy.deepcopy(original);case['assertions']=[next(a for a in case['assertions'] if a['type']=='colored-rule-widths')]
            case['assertions'][0][key]=value
            changed['cases']=[case];changed['suite']['cases']=[case['id']]
            with self.subTest(key=key,value=value),self.assertRaises(ValueError): common.validate_registry(changed)


if __name__=='__main__': unittest.main()
