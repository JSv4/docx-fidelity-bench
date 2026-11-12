"""Scoped source-derived line-pitch checks for the original Mallow cases."""
import math


def checks(case, info):
    labels = [f'Mallow{i:02d}' for i in range(1, 17)]
    step = 2355 / 2048 * 12 * int(case['id'].split('-')[2])
    by_label = {label: [w for w in info['words'] if w['text'] == label] for label in labels}
    result = []
    for first, second in zip(labels, labels[1:]):
        a, b = by_label[first], by_label[second]
        observed = b[0]['rect'][1] - a[0]['rect'][1] if len(a) == len(b) == 1 else None
        # Each PDF origin rounds independently to 0.75pt: their difference can
        # depart from the natural pitch by up to one quantum.
        passed = (observed is not None and math.isfinite(observed)
                  and a[0]['page'] == b[0]['page'] == 1 and abs(observed - step) <= 0.75)
        result.append(dict(first=first, second=second, expectedPt=step,
                           observedPt=observed, tolerancePt=0.75, passed=passed))
    return result
