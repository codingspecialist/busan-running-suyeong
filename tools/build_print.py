"""Book figure: whole route on a bordered, pen-and-ink style sheet (SVG). PNG is rendered from it by Chrome."""
import json, math, sys

D = sys.argv[1]
route = json.load(open(f'{D}/data/route.json'))
base = json.load(open(f'{D}/data/basemap.json'))

W, H = 1600, 2200            # design units (px at 1x)
M = 56                       # outer margin to frame
FX0, FY0, FX1, FY1 = M, M, W - M, H - M
MAP = (M + 24, 250, W - M - 24, H - 262)   # map window inside frame

def merc(lat, lon):
    x = math.radians(lon)
    y = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    return x, y

pts = route['points']
xs, ys = zip(*[merc(a, b) for a, b in pts])
cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
# metres per mercator unit at this latitude
R = 6378137
lat0 = 35.177
m_per_u = R * math.cos(math.radians(lat0))
route_h_m = (max(ys) - min(ys)) * m_per_u
mw, mh = MAP[2] - MAP[0], MAP[3] - MAP[1]
scale_px_per_m = (mh * 0.80) / route_h_m
s = scale_px_per_m * m_per_u
ox = (MAP[0] + MAP[2]) / 2
oy = (MAP[1] + MAP[3]) / 2 + 10
def P(lat, lon):
    x, y = merc(lat, lon)
    return ox + (x - cx) * s, oy - (y - cy) * s

def path_d(coords, close=False):
    out = []
    for i, (lon, lat) in enumerate(coords):
        x, y = P(lat, lon)
        out.append(('M' if i == 0 else 'L') + f'{x:.1f} {y:.1f}')
    return ' '.join(out) + (' Z' if close else '')

def geom_d(g):
    t, c = g['type'], g['coordinates']
    if t == 'LineString':
        return path_d(c)
    if t == 'MultiLineString':
        return ' '.join(path_d(x) for x in c)
    if t == 'Polygon':
        return ' '.join(path_d(r, True) for r in c)
    if t == 'MultiPolygon':
        return ' '.join(path_d(r, True) for poly in c for r in poly)
    return ''

layers = {k: [] for k in ('water', 'park', 'building', 'road3', 'road2', 'road1', 'path', 'cycleNo', 'cycleOk')}
for f in base['features']:
    p = f['properties']; k = p['k']
    d = geom_d(f['geometry'])
    if not d:
        continue
    if k == 'road':
        layers['road' + str(p['c'])].append(d)
    elif k == 'cycle':
        layers['cycleNo' if p.get('foot') == 'no' else 'cycleOk'].append(d)
    elif k in layers:
        layers[k].append(d)

route_d = ' '.join(('M' if i == 0 else 'L') + '%.1f %.1f' % P(a, b) for i, (a, b) in enumerate(pts[:route['turnIndex'] + 1]))

# direction chevrons beside the line: outbound on the east side (north-going), return on the west side
cum = route['cum']; ti = route['turnIndex']; total = cum[-1]
def at(m):
    for i in range(1, len(cum)):
        if cum[i] >= m:
            t = (m - cum[i - 1]) / ((cum[i] - cum[i - 1]) or 1)
            a, b = pts[i - 1], pts[i]
            lat = a[0] + (b[0] - a[0]) * t; lon = a[1] + (b[1] - a[1]) * t
            x0, y0 = P(*a); x1, y1 = P(*b)
            ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
            return P(lat, lon), ang
    return P(*pts[-1]), 0
chev = []
def chevron(x, y, ang):
    return f'<path d="M-11 -9 L4 0 L-11 9" transform="translate({x:.1f} {y:.1f}) rotate({ang:.1f})" fill="none" stroke="#000" stroke-width="4" stroke-linejoin="miter" stroke-linecap="square"/>'
for m in (400, 760, 1280):
    (x, y), ang = at(m)
    r = math.radians(ang)
    nx, ny = -math.sin(r), math.cos(r)   # screen-space unit normal; for north-going travel it points east
    chev.append(chevron(x + nx * 28, y + ny * 28, ang))          # 갈 때: 동쪽(오른쪽)
    chev.append(chevron(x - nx * 28, y - ny * 28, ang + 180))    # 올 때: 서쪽(왼쪽)

kms = []
for m in (500, 1000, 1500):
    (x, y), ang = at(m)
    r = math.radians(ang)
    nx, ny = -math.sin(r), math.cos(r)
    tx, ty = x + nx * 22, y + ny * 22
    kms.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="#fff" stroke="#000" stroke-width="3"/>'
               f'<text x="{tx:.1f}" y="{ty + 8:.1f}" class="km" text-anchor="start">{m/1000:.1f}km</text>')

wp = {w['id']: w for w in route['waypoints']}
def pin(w, title, sub, dx, dy, anchor='start', solid=True, dot_fill=False):
    x, y = P(*pts[w['idx']])
    tx, ty = x + dx, y + dy
    tw = 26 * len(title) * 0.98 + 18 * len(sub) * 0.92 + 44
    bx = tx if anchor == 'start' else tx - tw
    fill, fg = ('#000', '#fff') if solid else ('#fff', '#000')
    return (f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{(bx if anchor=="start" else bx+tw):.1f}" y2="{ty:.1f}" stroke="#000" stroke-width="2"/>'
            f'<rect x="{bx:.1f}" y="{ty-30:.1f}" width="{tw:.1f}" height="54" fill="{fill}" stroke="#000" stroke-width="3"/>'
            f'<text x="{bx+16:.1f}" y="{ty+8:.1f}" style="fill:{fg}" class="pin"><tspan font-weight="700">{title}</tspan><tspan dx="12" class="pinsub">{sub}</tspan></text>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="11" fill="{"#000" if dot_fill else "#fff"}" stroke="#000" stroke-width="4.5"/>')

pins = [
    pin(wp['start'], '출발·도착', 'APEC 나루공원 야외무대 앞', -70, 90, 'end', True),
    pin(wp['jwa'], '중간', '좌수영교 부근', 80, -10, 'start', False),
    pin(wp['turn'], '반환', '과정교 부근', 90, 40, 'start', True, True),
]

def label(lat, lon, text, cls, rot=0):
    x, y = P(lat, lon)
    return f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" text-anchor="middle" transform="rotate({rot} {x:.1f} {y:.1f})">{text}</text>'
from shapely.geometry import shape, LineString
_water = shape(next(f for f in base['features'] if f['properties']['k'] == 'water')['geometry'])
def river_mid(lat):
    seg = _water.intersection(LineString([(129.10, lat), (129.14, lat)]))
    g = max(getattr(seg, 'geoms', [seg]), key=lambda q: q.length)
    return lat, g.centroid.x
labels = [
    label(*river_mid(35.1800), '수 영 강', 'river', -76),
    label(*river_mid(35.1712), '수 영 강', 'river', -60),
    label(35.17425, 129.11985, '좌수영교', 'bridge', 28),
    label(35.18470, 129.11560, '과정교', 'bridge', 0),
]

# scale bar 200 m
sb_px = 200 * scale_px_per_m
sbx, sby = MAP[0] + 30, MAP[3] - 40
scale = (f'<g class="scale"><rect x="{sbx:.1f}" y="{sby:.1f}" width="{sb_px/2:.1f}" height="10" fill="#000"/>'
         f'<rect x="{sbx+sb_px/2:.1f}" y="{sby:.1f}" width="{sb_px/2:.1f}" height="10" fill="#fff" stroke="#000" stroke-width="2"/>'
         f'<rect x="{sbx:.1f}" y="{sby:.1f}" width="{sb_px:.1f}" height="10" fill="none" stroke="#000" stroke-width="2"/>'
         f'<text x="{sbx:.1f}" y="{sby-12:.1f}" class="small">0</text>'
         f'<text x="{sbx+sb_px/2:.1f}" y="{sby-12:.1f}" class="small" text-anchor="middle">100</text>'
         f'<text x="{sbx+sb_px:.1f}" y="{sby-12:.1f}" class="small" text-anchor="middle">200 m</text></g>')
# north arrow
nax, nay = MAP[2] - 70, MAP[1] + 80
north = (f'<g transform="translate({nax} {nay})"><circle r="40" fill="#fff" stroke="#000" stroke-width="2.5"/>'
         f'<path d="M0 -30 L12 14 L0 6 L-12 14 Z" fill="#000"/><text y="-48" class="nlab" text-anchor="middle">북</text></g>')

oneway = route['oneWayMeters'] / 1000
comp = route['computedMeters'] / 1000

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
<title>수영강 왕복 코스 전체 경로 — APEC 나루공원 ↔ 과정교 부근</title>
<defs>
 <pattern id="hatch" width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(-35)"><line x1="0" y1="0" x2="0" y2="9" stroke="#8a8a8a" stroke-width="1.1"/></pattern>
 <clipPath id="mapclip"><rect x="{MAP[0]}" y="{MAP[1]}" width="{mw}" height="{mh}"/></clipPath>
 <style>
  text {{ font-family: 'Gowun Batang', 'Noto Serif KR', serif; fill: #000; }}
  .sans, .pin, .km, .small, .bridge, .nlab, .legend, .fine {{ font-family: 'IBM Plex Sans KR', 'Noto Sans KR', sans-serif; }}
  .h1 {{ font-size: 64px; font-weight: 700; letter-spacing: -1px; }}
  .h2 {{ font-size: 30px; fill: #333; }}
  .pin {{ font-size: 26px; }}
  .pinsub {{ font-size: 21px; font-weight: 400; }}
  .km {{ font-size: 21px; font-weight: 600; }}
  .river {{ font-size: 34px; fill: #6b6b6b; letter-spacing: 8px; }}
  .bridge {{ font-size: 22px; font-weight: 600; paint-order: stroke; stroke: #fff; stroke-width: 7px; }}
  .place {{ font-size: 24px; fill: #555; paint-order: stroke; stroke: #fff; stroke-width: 6px; }}
  .small {{ font-size: 20px; }}
  .nlab {{ font-size: 22px; font-weight: 600; }}
  .legend {{ font-size: 22px; }}
  .fine {{ font-size: 17px; fill: #333; }}
  .big {{ font-family: 'IBM Plex Sans KR', sans-serif; font-size: 44px; font-weight: 600; }}
 </style>
</defs>
<rect width="{W}" height="{H}" fill="#fff"/>
<rect x="{FX0}" y="{FY0}" width="{FX1-FX0}" height="{FY1-FY0}" fill="none" stroke="#000" stroke-width="5"/>
<rect x="{FX0+10}" y="{FY0+10}" width="{FX1-FX0-20}" height="{FY1-FY0-20}" fill="none" stroke="#000" stroke-width="1.5"/>

<text x="{MAP[0]}" y="{FY0+92}" class="h1">수영강 왕복 코스</text>
<text x="{MAP[0]}" y="{FY0+142}" class="h2">APEC 나루공원에서 과정교 부근까지, 같은 길로 돌아오기</text>
<g transform="translate({MAP[2]} {FY0+70})" text-anchor="end">
 <text class="fine" x="0" y="0">공식 안내 거리</text><text class="big" x="0" y="46">4km</text>
</g>
<g transform="translate({MAP[2]-200} {FY0+70})" text-anchor="end">
 <text class="fine" x="0" y="0">좌표로 잰 왕복</text><text class="big" x="0" y="46">{comp:.2f}km</text>
</g>

<g clip-path="url(#mapclip)">
 <rect x="{MAP[0]}" y="{MAP[1]}" width="{mw}" height="{mh}" fill="#fff"/>
 <path d="{' '.join(layers['water'])}" fill="url(#hatch)" stroke="#6f6f6f" stroke-width="1.6" fill-rule="evenodd"/>
 <path d="{' '.join(layers['park'])}" fill="none" stroke="#b5b5b5" stroke-width="1.4" stroke-dasharray="3 5"/>
 <path d="{' '.join(layers['building'])}" fill="#fff" stroke="#c9c9c9" stroke-width="1.2"/>
 <path d="{' '.join(layers['road3'])}" fill="none" stroke="#d2d2d2" stroke-width="3.2" stroke-linecap="round"/>
 <path d="{' '.join(layers['path'])}" fill="none" stroke="#bdbdbd" stroke-width="1.3"/>
 <path d="{' '.join(layers['cycleOk'])}" fill="none" stroke="#bdbdbd" stroke-width="1.6"/>
 <path d="{' '.join(layers['road2'])}" fill="none" stroke="#a9a9a9" stroke-width="7"/>
 <path d="{' '.join(layers['road2'])}" fill="none" stroke="#fff" stroke-width="4.2"/>
 <path d="{' '.join(layers['road1'])}" fill="none" stroke="#9c9c9c" stroke-width="11"/>
 <path d="{' '.join(layers['road1'])}" fill="none" stroke="#fff" stroke-width="7.4"/>
 <path d="{' '.join(layers['cycleNo'])}" fill="none" stroke="#555" stroke-width="2.6" stroke-dasharray="1 6" stroke-linecap="round"/>
 {''.join(labels)}
 <path d="{route_d}" fill="none" stroke="#fff" stroke-width="20" stroke-linejoin="round" stroke-linecap="round"/>
 <path d="{route_d}" fill="none" stroke="#000" stroke-width="9" stroke-linejoin="round" stroke-linecap="round"/>
 {''.join(chev)}
 {''.join(kms)}
 {''.join(pins)}
 {north}
 {scale}
</g>
<rect x="{MAP[0]}" y="{MAP[1]}" width="{mw}" height="{mh}" fill="none" stroke="#000" stroke-width="2.5"/>

<g transform="translate({MAP[0]} {MAP[3]+52})" class="legend">
 <line x1="0" y1="-8" x2="56" y2="-8" stroke="#000" stroke-width="9"/><text x="72" y="0">달릴 길 (갈 때와 올 때 같은 길)</text>
 <path d="M500 -16 L512 -8 L500 0" fill="none" stroke="#000" stroke-width="3.2"/><text x="526" y="0">달리는 방향</text>
 <line x1="740" y1="-8" x2="796" y2="-8" stroke="#555" stroke-width="2.6" stroke-dasharray="1 6" stroke-linecap="round"/><text x="812" y="0">보행 금지로 등록된 자전거길</text>
 <rect x="1180" y="-22" width="44" height="26" fill="url(#hatch)" stroke="#6f6f6f" stroke-width="1.4"/><text x="1236" y="0">수영강</text>
</g>
<g transform="translate({MAP[0]} {MAP[3]+112})" class="fine">
 <text x="0" y="0">편도 {oneway:.2f}km. 좌수영교 북쪽부터 반환점까지는 보행 허용으로 등록된 자전거길이에요. 강을 건너는 다리는 쓰지 않아요.</text>
 <text x="0" y="32">OpenStreetMap에서 보행 가능한 길만 이은 샘플이에요. 현장 답사나 실측 GPS로 확인하지 않았으니 현장 안내를 따라 주세요.</text>
 <text x="0" y="64">코스 참고: 달려라부산 러닝크루 APEC 나루공원 A코스(안내 4km). 지도 데이터 © OpenStreetMap contributors, ODbL 1.0 (기준 {route['osmBase'][:10]}).</text>
</g>
</svg>
'''
open(f'{D}/print/route-print.svg', 'w').write(svg)
html = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><link rel="stylesheet" href="../fonts/fonts.css">
<style>html,body{{margin:0;background:#fff}}#sheet{{width:{W}px;height:{H}px}}</style></head><body><div id="sheet">{svg}</div></body></html>'''
open(f'{D}/print/print-render.html', 'w').write(html)
print('scale m/px', round(1/scale_px_per_m, 3), 'map px', mw, mh)
