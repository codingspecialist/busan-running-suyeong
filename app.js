'use strict';
/* 수영강 왕복 코스 — 경로 재생
   데이터: data/route.json(경로), data/basemap.json(배경) — 둘 다 OpenStreetMap 파생, ODbL */
(async () => {
  const $ = (id) => document.getElementById(id);
  const msg = $('map-msg');
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  let base, data;
  try {
    [base, data] = await Promise.all(['data/basemap.json', 'data/route.json'].map(async (p) => {
      const r = await fetch(p);
      if (!r.ok) throw new Error(p + ' ' + r.status);
      return r.json();
    }));
  } catch (e) {
    msg.textContent = '지도 데이터를 불러오지 못했어요. 새로고침해 주세요.';
    console.error(e);
    return;
  }

  const pts = data.points;               // [lat, lon]
  const cum = data.cum;                  // 출발점부터 누적 거리(m)
  const total = cum[cum.length - 1];
  const turnM = cum[data.turnIndex];
  const wp = Object.fromEntries(data.waypoints.map((w) => [w.id, w]));
  const km = (m) => (m / 1000).toFixed(2);

  // ---------- 지도 ----------
  const map = L.map('map', {
    zoomControl: false,
    minZoom: 13, maxZoom: 19, zoomSnap: 0.25,
    maxBounds: [[35.158, 129.100], [35.198, 129.142]], maxBoundsViscosity: 0.9,
    renderer: L.canvas({ padding: 0.5 }),
    tap: false,
  });
  map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
  map.attributionControl.addAttribution('© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, ODbL');

  // 강을 펜 빗금으로 칠하기 위한 캔버스 패턴.
  // Leaflet 캔버스는 레이어 좌표로 translate한 뒤 그리므로 패턴이 지도에 고정된다.
  const hatch = (() => {
    const c = document.createElement('canvas');
    const n = 8; c.width = n; c.height = n;
    const g = c.getContext('2d');
    g.strokeStyle = '#9a9a9a'; g.lineWidth = 0.9;
    g.beginPath();
    for (let k = -n; k <= n; k += n) { g.moveTo(k, n); g.lineTo(k + n, 0); }
    g.stroke();
    return g.createPattern(c, 'repeat');
  })();

  const style = {
    water: { stroke: true, color: '#7a7a7a', weight: 1, fillColor: hatch, fillOpacity: 1 },
    park: { stroke: true, color: '#b8b8b8', weight: 0.8, dashArray: '2 3', fill: false },
    building: { stroke: true, color: '#cfcfcf', weight: 0.7, fillColor: '#ffffff', fillOpacity: 1 },
    road1: { color: '#b0b0b0', weight: 7, opacity: 1, lineCap: 'butt' },
    road2: { color: '#c4c4c4', weight: 4.5, opacity: 1, lineCap: 'butt' },
    road3: { color: '#d6d6d6', weight: 2.5, opacity: 1 },
    path: { color: '#bdbdbd', weight: 1, opacity: 1 },
    cycleNo: { color: '#6e6e6e', weight: 1.8, dashArray: '1 4', lineCap: 'round', opacity: 1 },
    cycleOk: { color: '#bdbdbd', weight: 1.2, opacity: 1 },
  };
  const addKind = (filter, st) => L.geoJSON(base, { filter, style: () => st, interactive: false }).addTo(map);

  // 위쪽은 반환 표시 이름표, 오른쪽은 지도 도구 자리를 비워 둔다
  const FIT = { paddingTopLeft: [24, 58], paddingBottomRight: [80, 36] };
  map.fitBounds(L.latLngBounds(pts), FIT);
  addKind((f) => f.properties.k === 'park', style.park);
  addKind((f) => f.properties.k === 'water', style.water);
  addKind((f) => f.properties.k === 'building', style.building);
  addKind((f) => f.properties.k === 'road' && f.properties.c === 3, style.road3);
  addKind((f) => f.properties.k === 'path', style.path);
  addKind((f) => f.properties.k === 'cycle' && f.properties.foot !== 'no', style.cycleOk);
  addKind((f) => f.properties.k === 'road' && f.properties.c === 2, style.road2);
  addKind((f) => f.properties.k === 'road' && f.properties.c === 1, style.road1);
  addKind((f) => f.properties.k === 'cycle' && f.properties.foot === 'no', style.cycleNo);
  // 도로 가운데를 비워 두 줄 펜선처럼 보이게
  L.geoJSON(base, { filter: (f) => f.properties.k === 'road' && f.properties.c === 1, style: () => ({ color: '#fff', weight: 4.6, opacity: 1, lineCap: 'butt' }), interactive: false }).addTo(map);
  L.geoJSON(base, { filter: (f) => f.properties.k === 'road' && f.properties.c === 2, style: () => ({ color: '#fff', weight: 2.6, opacity: 1, lineCap: 'butt' }), interactive: false }).addTo(map);

  // 지명(배경). 위치는 OSM 다리·강 좌표 근처에 손으로 둔 것
  const place = (lat, lon, text, cls) => L.marker([lat, lon], {
    interactive: false, keyboard: false,
    icon: L.divIcon({ className: '', html: `<span class="place ${cls}">${text}</span>`, iconSize: [0, 0] }),
  }).addTo(map);
  place(35.1793, 129.1170, '수영강', 'river');
  place(35.17435, 129.11990, '좌수영교', 'bridge');
  place(35.18465, 129.11560, '과정교', 'bridge');
  const parkLabel = place(35.1688, 129.1270, 'APEC 나루공원', '');
  const toggleParkLabel = () => parkLabel.setOpacity(map.getZoom() >= 15.5 ? 1 : 0);
  map.on('zoomend', toggleParkLabel); toggleParkLabel();

  // 경로
  // 경로는 별도 창(pane)의 작은 SVG에 그린다. 재생 중 배경 캔버스를 다시 그리지 않게 하려는 것
  map.createPane('route').style.zIndex = 450;
  const routeR = L.svg({ pane: 'route', padding: 0.3 });
  const ll = pts.map(([a, b]) => [a, b]);
  const outLL = ll.slice(0, data.turnIndex + 1);
  L.polyline(outLL, { renderer: routeR, pane: 'route', color: '#fff', weight: 11, opacity: 1, interactive: false }).addTo(map);
  L.polyline(outLL, { renderer: routeR, pane: 'route', color: '#000', weight: 4.5, opacity: 1, lineJoin: 'round', interactive: false }).addTo(map);
  const doneOut = L.polyline([], { renderer: routeR, pane: 'route', color: '#000', weight: 8, opacity: 1, lineJoin: 'round', lineCap: 'round', interactive: false }).addTo(map);
  // 돌아오는 길은 굵은 선 위에 흰 점선을 겹쳐 표시
  const doneBack = L.polyline([], { renderer: routeR, pane: 'route', color: '#fff', weight: 2.5, opacity: 1, dashArray: '5 5', lineCap: 'butt', interactive: false }).addTo(map);

  // 출발·중간·반환 표시
  const pin = (w, text, sub, opts = {}) => {
    const [lat, lon] = pts[w.idx];
    const html = `<div class="pin${opts.left ? ' left' : ''}"><span class="pin-dot${opts.fill ? ' fill' : ''}"></span>` +
      `<span class="pin-box${opts.solid ? ' solid' : ''}">${text}${sub ? `<em>${sub}</em>` : ''}</span></div>`;
    return L.marker([lat, lon], { interactive: false, keyboard: false, zIndexOffset: 500,
      icon: L.divIcon({ className: '', html, iconSize: [0, 0] }) }).addTo(map);
  };
  pin(wp.start, '출발·도착', 'APEC 나루공원', { solid: true });
  pin(wp.jwa, '중간', '좌수영교 부근', { left: false });
  pin(wp.turn, '반환', '과정교 부근', { fill: true, solid: true });

  // 움직이는 화살표
  const runner = L.marker(ll[0], {
    interactive: false, keyboard: false, zIndexOffset: 1000,
    icon: L.divIcon({
      className: 'runner', iconSize: [0, 0],
      html: '<svg viewBox="-17 -17 34 34" aria-hidden="true"><g class="rot">' +
        '<circle r="13" fill="#fff" stroke="#000" stroke-width="2"/>' +
        '<path d="M0 -8 L6.5 6 L0 2.6 L-6.5 6 Z" fill="#000"/></g></svg>',
    }),
  }).addTo(map);

  msg.hidden = true;

  // ---------- 위치 계산 ----------
  const KX = Math.cos(35.177 * Math.PI / 180);
  const locate = (m) => {
    m = Math.max(0, Math.min(total, m));
    let lo = 0, hi = cum.length - 1;
    while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (cum[mid] <= m) lo = mid; else hi = mid; }
    const seg = cum[hi] - cum[lo] || 1;
    const t = Math.min(1, (m - cum[lo]) / seg);
    const a = pts[lo], b = pts[hi];
    const lat = a[0] + (b[0] - a[0]) * t, lon = a[1] + (b[1] - a[1]) * t;
    const bearing = Math.atan2((b[1] - a[1]) * KX, b[0] - a[0]) * 180 / Math.PI;
    return { lat, lon, i: lo, bearing };
  };

  const statusFor = (m) => {
    if (m <= 0.5) return '출발할 준비가 됐어요';
    if (m >= total - 0.5) return '출발점으로 돌아왔어요';
    if (Math.abs(m - turnM) < 25) return '반환점이에요. 같은 길로 돌아가요';
    if (m < wp.jwa.m - 30) return '나루공원 강변길을 따라 북쪽으로';
    if (m < wp.jwa.m + 30) return '좌수영교 아래를 지나가요';
    if (m < turnM) return '과정교를 향해 강변 자전거길 옆으로';
    if (m < wp.jwa2.m - 30) return '돌아오는 길, 좌수영교 쪽으로';
    if (m < wp.jwa2.m + 30) return '다시 좌수영교 아래를 지나요';
    return '나루공원 출발점으로 돌아가는 중';
  };

  // ---------- 재생 상태 ----------
  const DURATION_1X = 60; // 1× 전체 재생 시간(초)
  let pos = 0, playing = false, speed = 1, follow = true, last = 0, holdUntil = 0, passedTurn = false;
  let rafId = 0;

  const scrub = $('scrub'), kmNow = $('km-now'), now = $('now');
  const playBtn = $('play'), playLabel = $('play-label');
  const followBtn = $('follow');
  const segBtns = [];
  const rot = runner.getElement().querySelector('.rot');

  let lastStatus = '';
  const render = (opts = {}) => {
    const p = locate(pos);
    runner.setLatLng([p.lat, p.lon]);
    rot.setAttribute('transform', `rotate(${p.bearing.toFixed(1)})`);
    // 지나온 길: 반환 전엔 출발~현재, 반환 후엔 반환점~현재(같은 선 위를 거꾸로)
    if (pos <= turnM) {
      doneOut.setLatLngs(ll.slice(0, p.i + 1).concat([[p.lat, p.lon]]));
      doneBack.setLatLngs([]);
    } else {
      doneOut.setLatLngs(outLL);
      doneBack.setLatLngs(ll.slice(data.turnIndex, p.i + 1).concat([[p.lat, p.lon]]));
    }
    scrub.value = Math.round(pos / total * 1000);
    scrub.style.setProperty('--p', (pos / total * 100).toFixed(2) + '%');
    kmNow.textContent = km(pos);
    const st = statusFor(pos);
    if (st !== lastStatus) { now.textContent = st; lastStatus = st; }
    const segI = pos >= total ? 3 : data.segments.findIndex((s) => pos >= wp[s.from].m - 0.01 && pos < wp[s.to].m);
    segBtns.forEach((b, i) => b.setAttribute('aria-current', String(i === segI)));
    if (follow && (playing || opts.pan)) {
      if (!map.getBounds().pad(-0.25).contains([p.lat, p.lon]) || opts.pan) {
        map.panTo([p.lat, p.lon], { animate: !reduceMotion && !playing, duration: 0.4 });
      }
    }
  };

  const setPlaying = (on) => {
    playing = on;
    playBtn.classList.toggle('on', on);
    playBtn.setAttribute('aria-label', on ? '일시정지' : (pos >= total ? '다시 재생' : '재생'));
    playLabel.textContent = on ? '일시정지' : (pos >= total ? '다시 재생' : (pos > 0 ? '이어서 재생' : '재생'));
    if (on) { last = performance.now(); rafId = requestAnimationFrame(tick); }
    else cancelAnimationFrame(rafId);
  };

  const tick = (t) => {
    if (!playing) return;
    const dt = Math.min(0.1, (t - last) / 1000);
    last = t;
    if (t < holdUntil) { rafId = requestAnimationFrame(tick); return; }
    const before = pos;
    pos += dt * speed * total / DURATION_1X;
    // 반환점에서 잠깐 멈춰 방향을 바꾸는 모습을 보여준다
    if (before < turnM && pos >= turnM && !passedTurn) { pos = turnM; holdUntil = t + 900 / speed; passedTurn = true; }
    if (pos >= total) { pos = total; render(); setPlaying(false); return; }
    render();
    rafId = requestAnimationFrame(tick);
  };

  const jump = (m, panToIt = true) => {
    pos = Math.max(0, Math.min(total, m));
    passedTurn = pos >= turnM;
    holdUntil = 0;
    render({ pan: panToIt });
    if (!playing) setPlaying(false);
  };

  // ---------- 버튼 ----------
  playBtn.addEventListener('click', () => {
    if (playing) { setPlaying(false); return; }
    if (pos >= total) jump(0);
    if (follow) {
      const p = locate(pos);
      if (map.getZoom() < 16) map.setView([p.lat, p.lon], 16.5, { animate: !reduceMotion });
    }
    setPlaying(true);
  });
  $('reset').addEventListener('click', () => { setPlaying(false); jump(0); });

  document.querySelectorAll('.speed button').forEach((b) => b.addEventListener('click', () => {
    speed = Number(b.dataset.speed);
    document.querySelectorAll('.speed button').forEach((x) => x.setAttribute('aria-checked', String(x === b)));
  }));

  scrub.addEventListener('input', () => { setPlaying(false); jump(scrub.value / 1000 * total); });

  // 구간 이동
  const segList = $('segs');
  data.segments.forEach((s) => {
    const li = document.createElement('li');
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = s.title;
    b.addEventListener('click', () => { const wasPlaying = playing; setPlaying(false); jump(wp[s.from].m); if (wasPlaying) setPlaying(true); });
    li.appendChild(b); segList.appendChild(li); segBtns.push(b);
  });

  // 재생 막대 눈금
  const ticks = $('ticks');
  [['출발', 0, 'first'], ['좌수영교', wp.jwa.m, ''], ['반환', turnM, 'turn'], ['좌수영교', wp.jwa2.m, ''], ['도착', total, 'last']]
    .forEach(([t, m, c]) => {
      const s = document.createElement('span');
      s.textContent = t; if (c) s.className = c;
      s.style.left = (m / total * 100).toFixed(2) + '%';
      ticks.appendChild(s);
    });

  // 지도 도구
  $('zoom-in').addEventListener('click', () => map.zoomIn(0.5));
  $('zoom-out').addEventListener('click', () => map.zoomOut(0.5));
  $('fit').addEventListener('click', () => {
    setFollow(false);
    map.fitBounds(L.latLngBounds(pts), { ...FIT, animate: !reduceMotion });
  });
  const setFollow = (on) => { follow = on; followBtn.setAttribute('aria-pressed', String(on)); };
  followBtn.addEventListener('click', () => { setFollow(!follow); if (follow) render({ pan: true }); });
  map.on('dragstart', () => setFollow(false)); // 손으로 지도를 옮기면 따라가기를 끈다

  // 키보드: 스페이스 재생/정지, 좌우 화살표 100m 이동
  document.addEventListener('keydown', (e) => {
    const tag = (e.target.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'button' || tag === 'a') return;
    if (e.code === 'Space') { e.preventDefault(); playBtn.click(); }
    if (e.code === 'ArrowRight') jump(pos + 100);
    if (e.code === 'ArrowLeft') jump(pos - 100);
  });

  // ---------- 본문 채우기 ----------
  const stops = $('stops');
  const stopDefs = [
    [wp.start, 'APEC 나루공원', '야외무대 앞 강변길에서 출발해요.', ''],
    [wp.jwa, '좌수영교 부근', '다리 위로 올라가지 말고, 다리 아래 강변길로 지나가요.', ''],
    [wp.turn, '과정교 부근 반환', '다리 바로 앞에서 돌아서 왔던 길로 가요.', 'turn'],
    [wp.finish, 'APEC 나루공원 도착', '출발했던 곳으로 돌아오면 끝이에요.', ''],
  ];
  stopDefs.forEach(([w, t, d, c]) => {
    const li = document.createElement('li');
    if (c) li.className = c;
    li.innerHTML = `<span class="dot" aria-hidden="true"></span><button type="button"><span class="t">${t}<small>${km(w.m)}km</small></span><span class="d">${d}</span></button>`;
    li.querySelector('button').addEventListener('click', () => {
      setPlaying(false); setFollow(true); jump(w.m);
      if (map.getZoom() < 16) { const p = locate(w.m); map.setView([p.lat, p.lon], 16.5); }
      $('figure').scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
    });
    stops.appendChild(li);
  });

  const totalKm = km(total);
  $('km-total').textContent = totalKm;
  $('dist-computed').innerHTML = `${totalKm}<small>km</small>`;
  $('dist-computed-2').textContent = totalKm + 'km';
  const bk = data.outboundByKind || {};
  if (bk.footway) $('kind-foot').textContent = km(bk.footway) + 'km';
  if (bk.cycleway_foot_yes) $('kind-cycle').textContent = km(bk.cycleway_foot_yes) + 'km';
  $('osm-base').textContent = (data.osmBase || '').slice(0, 10);

  // 주소 표시·복사
  const here = location.protocol.startsWith('http') && !/localhost|127\.0\.0\.1/.test(location.hostname)
    ? location.origin + location.pathname : null;
  if (here) $('page-url').textContent = here.replace(/^https?:\/\//, '').replace(/\/$/, '');
  $('copy').addEventListener('click', async () => {
    const url = 'https://' + $('page-url').textContent + '/';
    try { await navigator.clipboard.writeText(url); $('copy').textContent = '복사했어요'; }
    catch { $('copy').textContent = '복사하지 못했어요'; }
    setTimeout(() => { $('copy').textContent = '주소 복사'; }, 1800);
  });

  render();
  window.__route = { get pos() { return pos; }, get playing() { return playing; }, total, turnM, jump, setSpeed: (s) => { speed = s; } };
})();
