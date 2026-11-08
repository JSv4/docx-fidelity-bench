"""Check unscaled Liberation Mono words independently of line-selection rectangles."""
import math
import subprocess


def source_order(path):
    # Bbox-layout treats sufficiently large justified gaps as separate columns.
    # Read content-stream order from the same PDF; geometry still uses bbox words.
    return subprocess.check_output(['pdftotext', '-raw', '-enc', 'UTF-8', str(path), '-'], text=True).split()


def checks(case, info):
    # Independently provisioned Liberation Mono: hmtx 1229, line metric 2320,
    # unitsPerEm 2048, authored size 12pt. No renderer measurement is an oracle.
    advance, height = 1229 / 2048 * 12, 2320 / 2048 * 12
    ordered = [a['marker'] for a in case['assertions']]
    expected_pages = max(a['page'] for a in case['assertions'])
    result = [dict(kind='page-count', expected=expected_pages, observed=len(info['geometry']),
                   passed=len(info['geometry']) == expected_pages),
              dict(kind='ordered-inventory', passed=info['rawTokens'] == ordered)]
    for token in ordered:
        words = [w for w in info['words'] if w['text'] == token]
        observed_width = words[0]['rect'][2] - words[0]['rect'][0] if len(words) == 1 else math.nan
        observed_height = words[0]['rect'][3] - words[0]['rect'][1] if len(words) == 1 else math.nan
        expected_width = len(token) * advance
        result.append(dict(kind='unscaled-glyph-width-height', marker=token,
            expectedWidthPt=expected_width, observedWidthPt=observed_width,
            expectedHeightPt=height, observedHeightPt=observed_height, tolerancePt=.1,
            passed=math.isfinite(observed_width + observed_height)
                and abs(observed_width - expected_width) <= .1 and abs(observed_height - height) <= .1))
    return result
