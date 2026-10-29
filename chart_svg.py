from math import sqrt, atan2, cos, sin, radians, degrees

R, A = 100.0, 30.0
C = sqrt(R * R - A * A)
THAI_DIGITS = str.maketrans('0123456789', '๐๑๒๓๔๕๖๗๘๙')


def _arc(t1, t2, n=12):
    return [(R * cos(radians(t1 + (t2 - t1) * i / n)), R * sin(radians(t1 + (t2 - t1) * i / n)))
            for i in range(n + 1)]


def _base_cells():
    t_top_r, t_top_l = degrees(atan2(C, A)), degrees(atan2(C, -A))
    t_left_u = degrees(atan2(A, -C))
    top = [(-A, A), (A, A)] + _arc(t_top_r, t_top_l)
    upper = [(-A, A)] + _arc(t_top_l, 135)
    lower = [(-A, A)] + _arc(135, t_left_u)
    return [top, upper, lower]


def _rot(pt, q):
    x, y = pt
    for _ in range(q):
        x, y = -y, x
    return x, y


def _centroid(poly):
    a = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        cr = x1 * y2 - x2 * y1
        a += cr; cx += (x1 + x2) * cr; cy += (y1 + y2) * cr
    return cx / (3 * a), cy / (3 * a)


def _mean(pts):
    xs, ys = zip(*pts)
    return sum(xs) / len(xs), sum(ys) / len(ys)


CELLS = []
for q in range(4):
    for shape in _base_cells():
        CELLS.append([_rot(p, q) for p in shape])


def _svg_pt(p):
    return f"{p[0]:.1f},{-p[1]:.1f}"


def render(result, size=360):
    lagna_sign = result['lagna']['sign_no']
    karma_sign = (lagna_sign + 9) % 12
    by_sign = {i: [] for i in range(12)}
    by_sign[lagna_sign].append(('ลั', 'lagna'))
    for p in result['planets']:
        by_sign[p['sign_no']].append((str(p['no']).translate(THAI_DIGITS), 'planet'))

    from career import SIGNS, HOUSES
    out = [f'<svg viewBox="-108 -108 216 216" width="{size}" height="{size}" '
           f'class="rasi" role="img" aria-label="ดวงชาตาราศีจักร">']
    out.append(f'<circle cx="0" cy="0" r="{R + 5}" class="rim"/>')
    for s, poly in enumerate(CELLS):
        cls = 'cell karma' if s == karma_sign else 'cell'
        out.append(f'<polygon points="{" ".join(_svg_pt(p) for p in poly)}" class="{cls}"/>')
    out.append(f'<rect x="{-A}" y="{-A}" width="{2*A}" height="{2*A}" class="center"/>')

    for s, poly in enumerate(CELLS):
        arc_pts = [p for p in poly if abs(sqrt(p[0]**2 + p[1]**2) - R) < 0.5]
        mx, my = _mean(arc_pts)
        k = (R - 5.5) / sqrt(mx * mx + my * my)
        out.append(f'<text x="{mx*k:.1f}" y="{-my*k:.1f}" class="signname">{SIGNS[s]}</text>')
        cx, cy = _centroid(poly)
        ix, iy = _mean([p for p in poly if p not in arc_pts])
        d = 7 if s % 3 == 0 else 18
        L = sqrt((cx - ix) ** 2 + (cy - iy) ** 2)
        hx, hy = ix + (cx - ix) * d / L, iy + (cy - iy) * d / L
        out.append(f'<text x="{hx:.1f}" y="{-hy:.1f}" class="housename">'
                   f'{HOUSES[(s - lagna_sign) % 12]}</text>')
        items = by_sign[s]
        if not items:
            continue
        cols = 3 if s % 3 == 0 else 2
        rows = (len(items) + cols - 1) // cols
        for i, (label, kind) in enumerate(items):
            r, c = divmod(i, cols)
            n_in_row = min(cols, len(items) - r * cols)
            x = cx + (c - (n_in_row - 1) / 2) * (14 if cols == 3 else 12)
            y = cy - (r - (rows - 1) / 2) * 15
            out.append(f'<text x="{x:.1f}" y="{-y:.1f}" class="{kind}">{label}</text>')

    out.append('<text x="0" y="0" class="centertext">ราศีจักร</text>')
    out.append('</svg>')
    return '\n'.join(out)
