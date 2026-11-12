"""Independent font-unit glyph widths, vertical sizes and complete page inventories."""
import math


def checks(case, info):
    count, percent = map(int, case['id'].split('-')[-2:])
    advance = 1229 / 2048 * 12 * percent / 100
    pitch = 2320 / 2048 * 12
    per_line = math.floor((180 + advance) / (10 * advance))
    per_page = math.floor(648 / pitch)
    pages = math.ceil(math.ceil(count / per_line) / per_page)
    labels = [f'Sorrel{i:03d}' for i in range(1, count + 1)]
    result = [dict(kind='page-count', expected=pages, observed=len(info['geometry']), passed=len(info['geometry']) == pages),
              dict(kind='ordered-inventory', passed=[w['text'] for w in info['words']] == labels)]
    for label in labels:
        words = [w for w in info['words'] if w['text'] == label]
        width = words[0]['rect'][2] - words[0]['rect'][0] if len(words) == 1 else math.nan
        height = words[0]['rect'][3] - words[0]['rect'][1] if len(words) == 1 else math.nan
        # Native glyph widths differ by at most 0.05pt from font units across
        # these nine-character labels. A shared 0.1pt bound covers that rounding.
        result.append(dict(kind='glyph-width-height', marker=label, expectedWidthPt=9 * advance,
            observedWidthPt=width, expectedHeightPt=pitch, observedHeightPt=height, tolerancePt=.1,
            passed=math.isfinite(width + height) and abs(width - 9 * advance) <= .1 and abs(height - pitch) <= .1))
    return result
