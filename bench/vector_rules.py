"""Physical widths of declared colored straight rules in Poppler's vector SVG output.

This deliberately accepts stroked polylines and filled rectangles only. Unexpected colored
paint fails the declaration; it is never silently omitted or inferred from raster thickness.
"""
import math
import re
import xml.etree.ElementTree as ET

NUMBER = r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?'
IDENTITY = (1, 0, 0, 1, 0, 0)


def multiply(a, b):
    return (a[0]*b[0]+a[2]*b[1], a[1]*b[0]+a[3]*b[1],
            a[0]*b[2]+a[2]*b[3], a[1]*b[2]+a[3]*b[3],
            a[0]*b[4]+a[2]*b[5]+a[4], a[1]*b[4]+a[3]*b[5]+a[5])


def transform(value):
    if not value.strip(): return IDENTITY
    match = re.fullmatch(r'\s*matrix\(([^)]+)\)\s*', value)
    if not match: raise ValueError('Unsupported vector-rule transform')
    values = tuple(float(n) for n in re.split(r'[\s,]+', match[1].strip()))
    if len(values) != 6 or not all(math.isfinite(n) for n in values):
        raise ValueError('Invalid vector-rule transform')
    return values


def color(value):
    match = re.fullmatch(r'rgb\(([^)]+)\)', value.strip())
    if not match: return None
    parts = re.split(r'[\s,]+', match[1].strip())
    if len(parts) != 3: return None
    return [round(float(p[:-1])*255/100) if p.endswith('%') else round(float(p)) for p in parts]


def paths(value):
    tokens = re.findall(r'[MLHVZmlhvz]|'+NUMBER, value)
    if re.sub(r'[MLHVZmlhvz]|'+NUMBER+r'|[\s,]', '', value):
        raise ValueError('Colored vector rule is not a straight path')
    result, current, point, command, i = [], [], (0, 0), None, 0
    while i < len(tokens):
        if tokens[i].isalpha():
            command = tokens[i]; i += 1
            if command.upper() == 'Z':
                if current: result.append((current, True)); point = current[0]; current = []
                command = None; continue
        if command is None: raise ValueError('Invalid colored path commands')
        count = 2 if command.upper() in ('M', 'L') else 1
        if i+count > len(tokens) or any(t.isalpha() for t in tokens[i:i+count]):
            raise ValueError('Invalid colored path coordinates')
        values = [float(n) for n in tokens[i:i+count]]; i += count
        x, y = point
        if command.upper() in ('M', 'L'):
            x, y = values
            if command.islower(): x += point[0]; y += point[1]
        elif command.upper() == 'H': x = values[0]+(x if command.islower() else 0)
        else: y = values[0]+(y if command.islower() else 0)
        if command.upper() == 'M':
            if current: result.append((current, False))
            current = []; command = 'l' if command.islower() else 'L'
        point = (x, y); current.append(point)
    if current: result.append((current, False))
    return result


def widths(svg, rgb, page_size):
    root = ET.fromstring(svg)
    box = [float(n) for n in root.get('viewBox', '').split()]
    if len(box) != 4 or box[2] <= 0 or box[3] <= 0: raise ValueError('Missing SVG page geometry')
    sx, sy = page_size[0]/box[2], page_size[1]/box[3]
    result = []
    def visit(node, parent_matrix, inherited):
        if node.tag.rsplit('}', 1)[-1] in ('defs', 'clipPath'): return
        matrix = multiply(parent_matrix, transform(node.get('transform', '')))
        style = dict(inherited)
        style.update(node.attrib)
        style.update(dict(pair.strip().split(':', 1) for pair in node.get('style', '').split(';') if ':' in pair))
        fill, stroke = color(style.get('fill', '')), color(style.get('stroke', ''))
        tag = node.tag.rsplit('}', 1)[-1]
        if tag not in ('svg', 'g') and (fill == rgb or stroke == rgb):
            if tag != 'path': raise ValueError('Unexpected colored vector-rule shape: '+tag)
            if fill == rgb and style.get('stroke', 'none') != 'none' and float(style.get('stroke-opacity', '1')) > 0:
                raise ValueError('Filled vector rule has an additional outline')
            def project(p): return (matrix[0]*p[0]+matrix[2]*p[1]+matrix[4], matrix[1]*p[0]+matrix[3]*p[1]+matrix[5])
            for points, closed in paths(node.get('d', '')):
                if len(points) < 2: continue  # Poppler emits a trailing, unpainted move.
                if len(points) > 1 and points[0] == points[-1]: points = points[:-1]; closed = True
                projected = [project(p) for p in points]
                if fill == rgb:
                    if not closed or len(points) != 4: raise ValueError('Colored fill is not one rectangle')
                    vectors = [(projected[(i+1)%4][0]-p[0],projected[(i+1)%4][1]-p[1]) for i,p in enumerate(projected)]
                    lengths = [math.hypot(*v) for v in vectors]
                    if min(lengths) <= 0 or any(abs(vectors[i][0]*vectors[(i+1)%4][0]+vectors[i][1]*vectors[(i+1)%4][1]) > lengths[i]*lengths[(i+1)%4]*.0001 for i in range(4)):
                        raise ValueError('Colored fill is not an orthogonal rectangle')
                    result.append(min(lengths))
                if stroke == rgb:
                    width = float(style.get('stroke-width', '1'))
                    pairs = list(zip(points, points[1:]+([points[0]] if closed else [])))
                    determinant = abs(matrix[0]*matrix[3]-matrix[1]*matrix[2])
                    for a,b in pairs:
                        p,q = project(a),project(b)
                        length = math.dist(p,q)
                        if length: result.append(width*determinant*math.dist(a,b)/length)
        for child in node: visit(child, matrix, style)
    visit(root,(sx,0,0,sy,-box[0]*sx,-box[1]*sy),{})
    if not result or any(not math.isfinite(w) or w <= 0 for w in result):
        raise ValueError('No positive colored vector-rule widths')
    return result


def matches(declaration, observation):
    actual = observation.get('widthsPt', [])
    expected, tolerance = declaration['widthsPt'], declaration['tolerancePt']
    return (not observation.get('error') and bool(actual)
            and all(any(abs(a-e) <= tolerance for e in expected) for a in actual)
            and all(any(abs(a-e) <= tolerance for a in actual) for e in expected))
