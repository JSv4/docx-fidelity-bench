"""Source-derived consecutive line pitches and page transitions for Oxlip text."""
import math


def checks(case, info):
    count = int(case['id'].split('-')[2])
    labels = [f'Oxlip{i:02d}' for i in range(1, count + 1)]
    pitch = 2355 / 2048 * 20
    per_page = math.floor(648 / pitch)
    words = {label: [w for w in info['words'] if w['text'] == label] for label in labels}
    expected_pages = math.ceil(count / per_page)
    result = [dict(kind='page-count', expected=expected_pages,
                   observed=len(info['geometry']), passed=len(info['geometry']) == expected_pages)]
    for index, (first, second) in enumerate(zip(labels, labels[1:])):
        a, b = words[first], words[second]
        pages = [index // per_page + 1, (index + 1) // per_page + 1]
        owned = len(a) == len(b) == 1 and [a[0]['page'], b[0]['page']] == pages
        observed = b[0]['rect'][1] - a[0]['rect'][1] if owned and pages[0] == pages[1] else None
        passed = owned and (pages[0] != pages[1] or
            math.isfinite(observed) and abs(observed - pitch) <= .75)
        result.append(dict(first=first, second=second, expectedPages=pages, expectedPt=pitch,
                           observedPt=observed, tolerancePt=.75, passed=passed))
    return result
