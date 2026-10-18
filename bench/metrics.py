"""Metric v1, implemented here without image or metric library defaults."""
from __future__ import annotations

import math
from pathlib import Path
from .fixtures import png

CONTRACT = {'version': 3, 'clippedText': 'declared exact-row tokens may be absent or whole up to their authored count', 'dpi': 96, 'inkThreshold': 24, 'inkRadius': 1, 'ssimWindow': 8, 'ssimC1': 6.5025, 'ssimC2': 58.5225, 'alignment': 'none', 'pageScore': '100 * min(ssim, inkF1)', 'caseScore': 'worst page; zero on mandatory failure', 'visibleText': 'excludes UAX #9 bidi formatting controls', 'canvas': 'rasters within 1 pixel per axis share a white union canvas at the CropBox top-left origin; larger differences fail'}


def read_ppm(path):
    data = Path(path).read_bytes()
    tokens, i = [], 0
    while len(tokens) < 4:
        while i < len(data) and data[i] in b' \t\r\n':
            i += 1
        if i < len(data) and data[i] == 35:
            i = data.index(b'\n', i) + 1
            continue
        j = i
        while i < len(data) and data[i] not in b' \t\r\n':
            i += 1
        tokens.append(data[j:i])
    if tokens[0] != b'P6' or tokens[3] != b'255':
        raise ValueError('Expected binary RGB PPM with maximum 255')
    width, height = map(int, tokens[1:3])
    if width < 1 or height < 1 or width * height > 50_000_000:
        raise ValueError('Raster dimensions outside the measurement limit')
    if data[i:i+2] == b'\r\n':
        i += 2
    else:
        i += 1
    pixels = data[i:]
    if len(pixels) != width * height * 3:
        raise ValueError('Raster byte length does not match dimensions')
    return width, height, pixels


# One 96-DPI pixel is 0.75pt. Two pages whose physical boxes agree within the 0.25pt geometry
# tolerance can still round to canvases one pixel apart, because Poppler sizes each raster from
# its own fractional extent. That difference is blank edge, not layout, so both rasters are placed
# unchanged at their shared top-left origin on a white union canvas. Nothing is resized, shifted or
# aligned, and a larger difference remains a mandatory raster-dimensions failure.
CANVAS_TOLERANCE_PX = 1


def canvas_compatible(reference_size, candidate_size):
    return all(abs(a - b) <= CANVAS_TOLERANCE_PX for a, b in zip(reference_size, candidate_size))


def union_canvas(pixels, width, height, union_width, union_height):
    if (width, height) == (union_width, union_height):
        return pixels
    row_padding = b'\xff' * ((union_width - width) * 3)
    rows = [pixels[y * width * 3:(y + 1) * width * 3] + row_padding for y in range(height)]
    rows += [b'\xff' * (union_width * 3)] * (union_height - height)
    return b''.join(rows)


def ink_mask(pixels):
    return bytearray(int(min(pixels[i:i+3]) < 231) for i in range(0, len(pixels), 3))


def dilate(mask, width, height):
    result = bytearray(len(mask))
    for i, ink in enumerate(mask):
        if ink:
            x, y = i % width, i // width
            for yy in range(max(0, y - 1), min(height, y + 2)):
                left, right = yy * width + max(0, x - 1), yy * width + min(width, x + 2)
                result[left:right] = b'\1' * (right - left)
    return result


def ink_metrics(reference, candidate, width, height):
    r, c = ink_mask(reference), ink_mask(candidate)
    nr, nc = sum(r), sum(c)
    if nr == nc == 0:
        return {'precision': 1.0, 'recall': 1.0, 'inkF1': 1.0, 'referenceInk': 0, 'candidateInk': 0}
    if not nr or not nc:
        return {'precision': 0.0, 'recall': 0.0, 'inkF1': 0.0, 'referenceInk': nr, 'candidateInk': nc}
    dr, dc = dilate(r, width, height), dilate(c, width, height)
    precision = sum(a & b for a, b in zip(c, dr)) / nc
    recall = sum(a & b for a, b in zip(r, dc)) / nr
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {'precision': precision, 'recall': recall, 'inkF1': f1, 'referenceInk': nr, 'candidateInk': nc}


def ssim(reference, candidate, width, height):
    if reference == candidate:
        return 1.0
    luminance = lambda p: [0.2126 * p[i] + 0.7152 * p[i+1] + 0.0722 * p[i+2] for i in range(0, len(p), 3)]
    r, c = luminance(reference), luminance(candidate)
    weighted = 0.0
    for y in range(0, height, 8):
        for x in range(0, width, 8):
            sr = sc = srr = scc = src = 0.0
            n = 0
            for yy in range(y, min(y + 8, height)):
                for xx in range(x, min(x + 8, width)):
                    a, b = r[yy * width + xx], c[yy * width + xx]
                    sr += a
                    sc += b
                    srr += a * a
                    scc += b * b
                    src += a * b
                    n += 1
            mr, mc = sr / n, sc / n
            vr, vc = max(0.0, srr / n - mr * mr), max(0.0, scc / n - mc * mc)
            covariance = src / n - mr * mc
            value = ((2 * mr * mc + 6.5025) * (2 * covariance + 58.5225)) / ((mr * mr + mc * mc + 6.5025) * (vr + vc + 58.5225))
            weighted += value * n
    return weighted / (width * height)


def page_metrics(reference, candidate, width, height):
    raw = ssim(reference, candidate, width, height)
    result = ink_metrics(reference, candidate, width, height)
    result.update({'ssimRaw': raw, 'ssim': max(0.0, min(1.0, raw)), 'pixelMismatch': sum(reference[i:i+3] != candidate[i:i+3] for i in range(0, len(reference), 3)) / (width * height)})
    result['score'] = 100 * min(result['ssim'], result['inkF1'])
    result['close'] = result['ssim'] >= 0.98 and result['inkF1'] >= 0.95
    return result


def write_images(folder, number, reference, candidate, width, height):
    folder = Path(folder)
    def pixel(data, x, y):
        i = (y * width + x) * 3
        return data[i:i+3]
    for name, data in [('reference', reference), ('candidate', candidate)]:
        (folder / f'{number}-{name}.png').write_bytes(png(width, height, lambda x, y: pixel(data, x, y)))
    rm, cm = ink_mask(reference), ink_mask(candidate)
    def overlay(x, y):
        i = y * width + x
        if rm[i] and cm[i]:
            return (70, 70, 70)
        if rm[i]:
            return (20, 90, 230)
        if cm[i]:
            return (220, 40, 35)
        return (255, 255, 255)
    (folder / f'{number}-overlay.png').write_bytes(png(width, height, overlay))


def case_score(pages, checks):
    return min((p['score'] for p in pages), default=0.0) if all(c['passed'] for c in checks) else 0.0


def aggregate(cases, required):
    ids = {c['id'] for c in cases}
    measured = [c for c in cases if c['status'] == 'measured']
    complete = ids == set(required) and len(measured) == len(required) and len(ids) == len(cases)
    categories = {}
    for case in measured:
        categories.setdefault(case['category'], []).append(case['score'])
    means = {k: sum(v) / len(v) for k, v in sorted(categories.items())}
    return {'complete': complete, 'measured': len(measured), 'required': len(required), 'score': sum(means.values()) / len(means) if complete and means else None, 'categoryMeans': means, 'mandatoryPassRate': sum(all(ch['passed'] for ch in c['checks']) for c in measured) / len(required) if required else 0, 'closeMatchRate': sum(c.get('close', False) for c in measured) / len(required) if required else 0}
