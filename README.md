# 수영강 왕복 코스 · 부산 초보 러너 지도

APEC 나루공원 → 좌수영교 부근 → 과정교 부근 → 같은 길로 복귀.
책에 넣을 QR코드로 여는 실제 지도 기반 경로 재생 페이지입니다.

- 공개 주소(예정): https://codingspecialist.github.io/busan-running-suyeong/
- 코스 참고: [달려라부산 러닝크루 러닝코스 소개](https://runbusancrew.com/course.html) — APEC 나루공원 A코스, 공식 안내 **4km**
- 좌표 계산 거리: **3.57km** (왕복, 편도 1.79km)

공식 안내 거리와 좌표 계산 거리는 따로 표시합니다. 공식 안내에 반환 지점과 공원 안 동선이 정확히 나와 있지 않아 차이의 원인은 확인하지 못했습니다.

## 들어 있는 것

| 파일 | 내용 |
| --- | --- |
| `index.html`, `style.css`, `app.js` | 경로 재생 페이지 (재생·일시정지·처음으로·속도 1/2/4×·구간 이동·막대 이동·확대/축소·전체 경로·따라가기) |
| `data/route.json` | 경로 좌표, 누적 거리, 출발·중간·반환 지점, 사용한 OSM 길 태그 |
| `data/basemap.json` | 배경 지도 (강, 공원, 건물, 도로, 보행로, 자전거길) |
| `data/suyeong-apec-gwajeong.gpx` | GPX 1.1 경로 (트랙 + 출발·중간·반환 웨이포인트) |
| `qr/qr.png`, `qr/qr.svg` | 공개 주소 QR코드 (오류 정정 Q, PNG 1800px·600dpi) |
| `print/route-print.png` | 책용 전체 경로 그림 3200×4400px (400dpi로 약 20×28cm) |
| `print/route-print.svg` | 같은 그림의 벡터 원본 (글꼴: 고운바탕, IBM Plex Sans KR) |
| `tools/` | 데이터·인쇄 그림을 다시 만드는 스크립트와 경로 원자료 |

외부 지도 타일이나 API 키 없이 동작합니다. Leaflet과 글꼴은 저장소 안에 들어 있습니다.

## 경로를 만든 방법

1. Overpass API로 OpenStreetMap의 현재 데이터를 받았습니다(기준 시각 `2026-10-17T16:26:21Z`).
2. 보행 가능한 길만 그래프로 만들고 최단 경로를 구했습니다.
   - 제외: `foot=no/private`, 보행 허용 태그 없는 `access=no/private`, 보행 허용 태그 없는 `highway=cycleway`, 자동차 전용급 도로, 버스 전용 도로
   - 비용: 보행로 1, 보행 허용 자전거길 1.6, 일반 도로 2.5–3.5, 계단 4
3. 출발: 야외무대(OSM node 4197447182)에서 22m 떨어진 가장 가까운 보행로 지점.
   반환: 과정교 상판 선에서 약 15m 남쪽, 같은 OSM 길(way 667277397) 위의 지점.
4. 사용한 길(편도 순서): way 1510246890(보행로) → 667277398(보행로) → 825680591(자전거길, `foot=yes`) → 471302214(보행로) → 825680591 → 825680590(작은 다리, `foot=yes`) → 667277397(자전거길, `foot=yes`)
5. 피한 길: 나루공원 안 자전거길 way 667383251(`foot=no`), 좌수영교 보도 way 1186022479(강을 건넘), 강 위 보행교 way 1477730651.

### 좌표로 확인한 것

- 경로가 수영강 물 영역(OSM way 37269413)에 들어가는 길이 0m, 물 영역과 가장 가까운 거리 3.4m, 강 가로지름 없음
- 좌수영교 아래를 지나는 지점 1곳(출발 후 약 0.70km), 과정교는 건너지 않고 다리 앞에서 반환
- `foot=no` 길 사용 없음

### 확인하지 못한 것

- **현장 답사, 실측 GPS 기록으로 검증하지 않았습니다.** 공사·침수·통행 제한 같은 현재 상황은 반영되지 않습니다.
- 편도 1.00km는 OSM에 `highway=cycleway` + `foot=yes`(보행 허용)로 등록된 길입니다. 실제 표지와 노면 표시가 자전거·보행자 겸용인지는 현장에서 확인해야 합니다.
- 공식 4km와 좌표 3.57km의 차이 원인.

## 배경 지도

배경(`data/basemap.json`)은 OSM 파생 데이터입니다. 기존 저장소 `codingspecialist/busan-running-map`의 `basemap.geojson`을 읽어 다시 가공했고, 도로·보행로 869개 길의 좌표 체크섬과 수영강 물 영역 좌표가 위 기준 시각의 OSM과 모두 같은 것을 확인했습니다. 자전거길의 `foot` 태그와 다리 이름은 OSM에서 새로 붙였습니다. 기존 저장소의 파일은 수정하지 않았습니다.

## 다시 만들기

```bash
pip install shapely segno
python tools/build_data.py tools/route_src.json <basemap.geojson 경로> .
python tools/build_print.py .
python -m http.server 8765   # print/print-render.html 을 브라우저에서 열어 #sheet 를 2배율로 캡처
```

## 출처와 라이선스

- 지도·경로 데이터: © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/). `data/`의 JSON·GPX와 인쇄용 그림의 지도 부분도 ODbL을 따릅니다.
- [Leaflet](https://leafletjs.com) 1.9.4 — BSD-2-Clause (`vendor/LEAFLET-LICENSE.txt`)
- 글꼴: 고운바탕, IBM Plex Sans KR — SIL Open Font License 1.1 (`fonts/*-LICENSE.txt`, [@fontsource](https://fontsource.org) 배포본에서 이 페이지에 쓰인 글자의 분할 파일만 남김)
- 코스 정보: 달려라부산 러닝크루 공식 사이트 안내. 이 페이지는 공식 안내물이 아닌 책용 샘플입니다.

## 로컬에서 보기

```bash
python -m http.server 8765
# http://localhost:8765/
```
