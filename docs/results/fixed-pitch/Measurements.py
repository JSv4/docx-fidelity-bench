"""Check complete lines, glyph dimensions and total pages without product imports."""
from bench.pdf import reference_failures, companion_checks


def failures(case, info):
    result = reference_failures(case, info) + [c['name'] for c in companion_checks(case['pdfCompanion'], info) if not c['passed']]
    if len(info['geometry']) != 1:
        result.append('total-pages')
    for assertion in case['assertions']:
        label = assertion['marker']
        words = [w for w in info['words'] if w['text'] == label]
        if len(words) != 1:
            result.append('glyph-inventory:' + label)
            continue
        x0, y0, x1, y1 = words[0]['rect']
        if not (abs(x1 - x0 - len(label) * 1229 / 2048 * 12) <= .1
                and abs(y1 - y0 - 2320 / 2048 * 12) <= .1):
            result.append('glyph-dimensions:' + label)
    return result
