"""Build route.json, basemap.json and GPX for the Suyeong River sample.

Inputs
- build/route_src.json : route nodes + tags read from current OSM (Overpass, base timestamp inside)
- reference basemap.geojson : OSM-derived background (geometry checked equal to current OSM by checksum)
"""
import json, math, sys
from shapely.geometry import LineString, Polygon, Point

SRC = sys.argv[1]
REF_BASEMAP = sys.argv[2]
OUT = sys.argv[3]

src = json.load(open(SRC))

def hav(a, b):
    R = 6371008.8
    t = math.pi / 180
    dl = (b[0] - a[0]) * t
    dn = (b[1] - a[1]) * t
    h = math.sin(dl / 2) ** 2 + math.cos(a[0] * t) * math.cos(b[0] * t) * math.sin(dn / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))

out_pts = [tuple(map(float, s.split(','))) for s in src['coords'].split()]
way_at = [None] + [int(x) for x in src['wayAt'].split(',')]  # way of segment ending at i
assert len(way_at) == len(out_pts)

# Turnaround: on the same OSM segment, ~15 m south of the 과정교 deck line.
a, b = out_pts[-1], tuple(src['next_after_last'])
TURN_LAT = 35.18430
f = (TURN_LAT - a[0]) / (b[0] - a[0])
turn = (round(TURN_LAT, 7), round(a[1] + (b[1] - a[1]) * f, 7))
out_pts.append(turn)
way_at.append(667277397)

n_out = len(out_pts)
pts = out_pts + out_pts[-2::-1]
ways = way_at + way_at[::-1][:-1]
# ways for return half: segment ending at index j (j>=n_out) is the reverse of out segment
ways = way_at[:]
for j in range(n_out, len(pts)):
    k = 2 * (n_out - 1) - j  # mirrored index
    ways.append(way_at[k + 1])

cum = [0.0]
for i in range(1, len(pts)):
    cum.append(cum[-1] + hav(pts[i - 1], pts[i]))
turn_idx = n_out - 1

# --- background -------------------------------------------------------------
ref = json.load(open(REF_BASEMAP))
cf = src['cycle_foot']
foot_of = {}
for k, ids in cf.items():
    for i in ids:
        foot_of[str(i)] = k
bridges = src['named_bridges']

BBOX = (129.1085, 35.1625, 129.1365, 35.1925)  # lon/lat clip window (whole features kept if they touch)
def touches(coords):
    flat = []
    def walk(c):
        if isinstance(c[0], (int, float)):
            flat.append(c)
        else:
            for x in c:
                walk(x)
    walk(coords)
    return any(BBOX[0] <= x <= BBOX[2] and BBOX[1] <= y <= BBOX[3] for x, y in flat)

def r6(c):
    if isinstance(c[0], (int, float)):
        return [round(c[0], 6), round(c[1], 6)]
    return [r6(x) for x in c]

feats = []
water_poly = None
for ft in ref['features']:
    p = ft['properties']
    g = ft['geometry']
    if not touches(g['coordinates']):
        continue
    kind = p['kind']
    hw = p.get('highway', '')
    props = {'k': kind}
    if kind == 'road':
        props['c'] = {'trunk': 1, 'secondary': 1, 'tertiary': 2, 'secondary_link': 2, 'trunk_link': 2}.get(hw, 3)
        if hw in ('raceway',):
            continue
    if kind == 'path':
        if hw == 'cycleway':
            props['k'] = 'cycle'
            props['foot'] = foot_of.get(p['id'], 'untagged')
        elif hw == 'steps':
            props['k'] = 'path'
    if p['id'] in bridges:
        props['bridge'] = bridges[p['id']]
    if kind == 'water':
        water_poly = Polygon(g['coordinates'][0])
        props['n'] = p.get('name', '')
    if kind == 'park' and p.get('name'):
        props['n'] = p['name']
    from shapely.geometry import shape, mapping
    from shapely import clip_by_rect
    geo = shape(g)
    if kind == 'water':
        water_poly = geo  # keep unclipped copy for checks
    tol = 0.000006 if kind in ('building', 'path', 'cycle') else 0.000004
    geo = clip_by_rect(geo, *BBOX).simplify(tol, preserve_topology=True)
    if geo.is_empty:
        continue
    gj = mapping(geo)
    feats.append({'type': 'Feature', 'properties': props,
                  'geometry': {'type': gj['type'], 'coordinates': r6(json.loads(json.dumps(gj['coordinates'])))}})

# --- checks -------------------------------------------------------------------
route_line = LineString([(lon, lat) for lat, lon in out_pts])
checks = {}
# metres per degree near 35.18N
KX = math.cos(math.radians(35.177)) * 111320
KY = 110574
def to_m(geom):
    from shapely import affinity
    return affinity.scale(geom, xfact=KX, yfact=KY, origin=(129.12, 35.177))
wm = to_m(water_poly)
rm = to_m(route_line)
inside = rm.intersection(wm)
checks['route_length_inside_water_polygon_m'] = round(inside.length, 1)
checks['route_min_distance_to_water_m'] = round(rm.distance(wm), 1) if inside.length == 0 else 0
# does the route cross the river? (route endpoints both east of water; crossing = intersection splits)
checks['route_crosses_water_polygon'] = bool(rm.crosses(wm))

# bridge crossings (route passes beneath bridge decks; record where)
bridge_lines = {}
for ft in ref['features']:
    pid = ft['properties']['id']
    if pid in bridges and ft['geometry']['type'] == 'LineString':
        bridge_lines.setdefault(bridges[pid], []).append(LineString(ft['geometry']['coordinates']))
under = {}
for name, lines in bridge_lines.items():
    for ln in lines:
        x = route_line.intersection(ln)
        if not x.is_empty:
            pt = x if x.geom_type == 'Point' else list(x.geoms)[0]
            d = route_line.project(pt)
            # convert projected degrees distance to metres via cumulative lookup
            best = min(range(n_out), key=lambda i: hav(out_pts[i], (pt.y, pt.x)))
            under.setdefault(name, []).append({'lat': round(pt.y, 7), 'lon': round(pt.x, 7), 'near_idx': best})
checks['route_under_bridges'] = under
# no use of avoided ways
checks['uses_foot_no_way'] = any(w in (667383251,) for w in ways if w)

# --- waypoints ------------------------------------------------------------
def nearest_idx(lat, lon, lo=0, hi=None):
    hi = hi if hi is not None else n_out
    return min(range(lo, hi), key=lambda i: hav(pts[i], (lat, lon)))

jw = under.get('좌수영교', [{}])[0]
jw_idx = nearest_idx(jw['lat'], jw['lon'])
waypoints = [
    {'id': 'start', 'label': '출발', 'name': 'APEC 나루공원', 'note': '야외무대 앞 강변길', 'idx': 0},
    {'id': 'jwa', 'label': '중간', 'name': '좌수영교 부근', 'note': '다리 밑을 지나 계속 북쪽으로', 'idx': jw_idx},
    {'id': 'turn', 'label': '반환', 'name': '과정교 부근', 'note': '다리 앞에서 돌아서기', 'idx': turn_idx},
    {'id': 'jwa2', 'label': '중간', 'name': '좌수영교 부근', 'note': '왔던 길 그대로', 'idx': 2 * turn_idx - jw_idx},
    {'id': 'finish', 'label': '도착', 'name': 'APEC 나루공원', 'note': '출발했던 곳', 'idx': len(pts) - 1},
]
for w in waypoints:
    w['m'] = round(cum[w['idx']], 1)

# segments (for jump buttons)
segments = [
    {'from': 'start', 'to': 'jwa', 'title': '나루공원 → 좌수영교'},
    {'from': 'jwa', 'to': 'turn', 'title': '좌수영교 → 과정교'},
    {'from': 'turn', 'to': 'jwa2', 'title': '과정교 → 좌수영교'},
    {'from': 'jwa2', 'to': 'finish', 'title': '좌수영교 → 나루공원'},
]

# surface summary per kind for honest labelling (outbound)
kind_m = {}
for i in range(1, n_out):
    w = way_at[i]
    tags = src['ways'][str(w)]
    k = 'footway' if tags['highway'] == 'footway' else ('cycleway_foot_yes' if tags.get('foot') == 'yes' else tags['highway'])
    kind_m[k] = kind_m.get(k, 0) + hav(out_pts[i - 1], out_pts[i])

route = {
    'title': '수영강 · APEC 나루공원 ↔ 과정교 부근 왕복',
    'officialDistanceKm': 4.0,
    'officialSource': 'https://runbusancrew.com/course.html',
    'computedMeters': round(cum[-1], 1),
    'oneWayMeters': round(cum[turn_idx], 1),
    'turnIndex': turn_idx,
    'points': [[round(a, 7), round(b, 7)] for a, b in pts],
    'cum': [round(c, 1) for c in cum],
    'way': ways,
    'waypoints': waypoints,
    'segments': segments,
    'stage': {'lat': src['stage_node']['lat'], 'lon': src['stage_node']['lon'],
              'gapMeters': round(hav((src['stage_node']['lat'], src['stage_node']['lon']), pts[0]), 1)},
    'osmBase': src['osm_base'],
    'checkedOn': '2026-10-18',
    'outboundByKind': {k: round(v, 1) for k, v in kind_m.items()},
    'osmWays': src['ways'],
}
json.dump(route, open(f'{OUT}/data/route.json', 'w'), ensure_ascii=False, separators=(',', ':'))
json.dump({'type': 'FeatureCollection', 'features': feats}, open(f'{OUT}/data/basemap.json', 'w'),
          ensure_ascii=False, separators=(',', ':'))

# --- GPX -------------------------------------------------------------------------
def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;')
g = ['<?xml version="1.0" encoding="UTF-8"?>',
     '<gpx version="1.1" creator="busan-running-suyeong" xmlns="http://www.topografix.com/GPX/1/1">',
     '<metadata><name>수영강 APEC 나루공원 - 과정교 부근 왕복 (샘플)</name>',
     f'<desc>좌표 계산 거리 {cum[-1]/1000:.2f}km / 공식 안내 4km. OpenStreetMap 보행 허용 길 좌표를 이어 만든 샘플. '
     '현장 답사·실측 GPS로 검증하지 않음. 현재 통행 여부는 현장 안내를 따를 것.</desc>',
     '<copyright author="OpenStreetMap contributors"><license>https://opendatacommons.org/licenses/odbl/1-0/</license></copyright>',
     '<link href="https://www.openstreetmap.org/copyright"><text>Map data © OpenStreetMap contributors (ODbL)</text></link>',
     f'<time>{src["osm_base"]}</time></metadata>']
for w in waypoints:
    if w['id'] in ('jwa2', 'finish'):
        continue
    la, lo = pts[w['idx']]
    g.append(f'<wpt lat="{la:.7f}" lon="{lo:.7f}"><name>{esc(w["label"] + " · " + w["name"])}</name><desc>{esc(w["note"])}</desc></wpt>')
g.append('<trk><name>수영강 왕복 4km (샘플)</name><type>running</type><trkseg>')
for la, lo in pts:
    g.append(f'<trkpt lat="{la:.7f}" lon="{lo:.7f}"></trkpt>')
g.append('</trkseg></trk></gpx>')
open(f'{OUT}/data/suyeong-apec-gwajeong.gpx', 'w').write('\n'.join(g) + '\n')

print(json.dumps({'computed_m': route['computedMeters'], 'one_way_m': route['oneWayMeters'], 'turn': turn,
                  'n_points': len(pts), 'stage_gap_m': route['stage']['gapMeters'], 'byKind': route['outboundByKind'],
                  'waypoints': [(w['id'], w['m']) for w in waypoints], 'checks': checks, 'basemap_feats': len(feats)},
                 ensure_ascii=False, indent=1))
