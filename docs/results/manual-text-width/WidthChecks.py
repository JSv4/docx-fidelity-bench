"""Authored target widths and independently provisioned Liberation Mono font units."""
import math


def inspect_glyphs(path):
    import fitz
    with fitz.open(path) as document:
        return [dict(text=char['c'], page=page.number + 1, rect=list(char['bbox']),
                     font=span['font'], bold=bool(span['flags'] & 16))
                for page in document for block in page.get_text('rawdict')['blocks']
                for line in block.get('lines', []) for span in line['spans'] for char in span['chars']]


def checks(case, info):
    advance, pitch = 1229 / 2048 * 12, 2320 / 2048 * 12
    variant = case['id'].removeprefix('manual-text-width-')
    target = 7 * advance if variant == 'control' else 20 if variant == 'single-20' else 200 if variant == 'separate-100' else 100
    pages = 2 if variant == 'continued-100' else 1
    labels = [f'Fern{i:03d}' for i in range(120)] if variant == 'continued-100' else []
    ordered = labels[:100] + ['Juniper', 'Ledger'] + labels[100:]
    result = [dict(kind='page-count', expected=pages, observed=len(info['geometry']), passed=len(info['geometry']) == pages),
              dict(kind='ordered-inventory', passed=[w['text'] for w in info['words']] == ordered)]
    for token in case['tokens']:
        words = [w for w in info['words'] if w['text'] == token]
        width = words[0]['rect'][2] - words[0]['rect'][0] if len(words) == 1 else math.nan
        height = words[0]['rect'][3] - words[0]['rect'][1] if len(words) == 1 else math.nan
        expected = target if token == 'Juniper' else len(token) * advance
        # Multiple independently transformed regions have separately rounded print origins.
        # Keep each piece's width strict below; their aggregate uses the existing position bound.
        width_tolerance = .5 if variant == 'separate-100' and token == 'Juniper' else .1
        result.append(dict(kind='glyph-width-height', marker=token, expectedWidthPt=expected,
            observedWidthPt=width, expectedHeightPt=pitch, observedHeightPt=height, widthTolerancePt=width_tolerance, heightTolerancePt=.1,
            passed=math.isfinite(width + height) and abs(width - expected) <= width_tolerance and abs(height - pitch) <= .1))
    if variant in ('mixed-100', 'separate-100'):
        glyphs = [g for g in info['glyphs'] if not g['text'].isspace()]
        text = ''.join(g['text'] for g in glyphs)
        assert text.count('Juniper') == 1
        start = text.index('Juniper')
        letters = glyphs[start:start + 7]
        heights = [g['rect'][3] - g['rect'][1] for g in letters]
        result.append(dict(kind='fitted-piece-heights', expectedPt=pitch, observedPt=heights,
            tolerancePt=.1, passed=all(abs(height - pitch) <= .1 for height in heights)))
        expected_bold = [False] * 3 + [variant == 'mixed-100'] * 4
        result.append(dict(kind='fitted-font-styles', expected=expected_bold,
            observed=[g['bold'] for g in letters], passed=[g['bold'] for g in letters] == expected_bold))
        if variant == 'separate-100':
            observed = [letters[2]['rect'][2] - letters[0]['rect'][0],
                        letters[3]['rect'][0] - letters[0]['rect'][0],
                        letters[6]['rect'][2] - letters[3]['rect'][0]]
            result.append(dict(kind='separate-id-piece-widths', expectedPt=[100, 100, 100],
                observedPt=observed, tolerancesPt=[.1, .5, .1],
                passed=all(abs(value - 100) <= tolerance for value, tolerance in zip(observed, [.1, .5, .1]))))
    return result
