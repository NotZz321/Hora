(function () {
  const MN = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.'];
  const MC = ['#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f', '#edc948',
              '#b07aa1', '#ff9da7', '#9c755f', '#bab0ac', '#1170aa', '#c85200'];
  const $ = s => document.querySelector(s);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const mix = (a, b) => t => 'rgb(' + a.map((v, i) => Math.round(v + (b[i] - v) * t)).join(',') + ')';
  const ramp = mix([74, 40, 34], [255, 150, 120]);
  const mapRamp = mix([26, 44, 92], [110, 182, 255]);

  const payload = JSON.parse($('#hora-data').textContent);
  const D0 = payload.rows, TH = payload.th;
  let D = [], careers = [], s1 = new Set(), s2 = new Set();

  function bars(el, it, H, rot) {
    const W = Math.max(520, it.length * 46), mt = 24, mb = rot ? 125 : 60, pl = 34;
    const max = Math.max(1, ...it.map(x => x.v)), bw = (W - pl) / Math.max(it.length, 1);
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img">`;
    for (let k = 0; k <= 4; k++) {
      const y = mt + (H - mt - mb) * (1 - k / 4);
      s += `<line class="gl" x1="${pl}" x2="${W}" y1="${y}" y2="${y}"/><text class="ax" x="${pl - 6}" y="${y + 4}" text-anchor="end">${Math.round(max * k / 4)}</text>`;
    }
    let g0 = 0;
    it.forEach((x, i) => {
      const h = (H - mt - mb) * x.v / max, cx = pl + bw * i + bw / 2, y = H - mb - h, ty = H - mb + 14;
      s += `<rect x="${cx - bw * .36}" y="${y}" width="${bw * .72}" height="${h}" rx="2" fill="${x.c}"><title>${esc(x.t)}: ${x.v}</title></rect>`;
      s += `<text class="ax" x="${cx}" y="${y - 5}" text-anchor="middle">${x.v}</text>`;
      s += rot
        ? `<text class="ax" transform="translate(${cx + 4} ${ty}) rotate(-40)" text-anchor="end">${esc(x.l)}</text>`
        : `<text class="ax" x="${cx}" y="${ty}" text-anchor="middle">${esc(x.l)}</text>`;
      if (x.g && (i === it.length - 1 || it[i + 1].g !== x.g)) {
        const mid = pl + bw * (g0 + i + 1) / 2;
        s += `<text class="ax group" x="${mid}" y="${H - 10}" text-anchor="middle">${esc(x.g)}</text>`;
        g0 = i + 1;
      }
    });
    el.innerHTML = s + '</svg>';
  }

  function chart1() {
    const c = {};
    D.forEach(r => { if (r.c) c[r.c] = (c[r.c] || 0) + 1; });
    const it = Object.entries(c).sort((a, b) => b[1] - a[1]), max = it[0] ? it[0][1] : 1;
    bars($('#c1'), it.map(([l, v]) => ({ l, v, t: l, c: ramp(.15 + .85 * v / max) })), 360, true);
    $('#lg1').style.background = `linear-gradient(90deg,${ramp(.15)},${ramp(1)})`;
    $('#mx1').textContent = max;
  }

  function chart2() {
    const it = [];
    careers.filter(c => s1.has(c)).forEach(c => {
      const m = Array(12).fill(0);
      D.forEach(r => { if (r.c === c && r.m >= 1 && r.m <= 12) m[r.m - 1]++; });
      m.forEach((v, i) => it.push({ l: MN[i], v, t: c + ' · ' + MN[i], c: MC[i], g: c }));
    });
    bars($('#c2'), it, 320, false);
  }

  function mapView() {
    const cnt = {};
    D.forEach(r => { if (s2.has(r.c) && GEO[r.p]) cnt[r.p] = (cnt[r.p] || 0) + 1; });
    const mx = Math.max(1, ...Object.values(cnt));
    const X = lo => ((lo - 97.3) * 39).toFixed(1), Y = la => ((20.7 - la) * 40).toFixed(1);
    let s = '<svg viewBox="0 0 335 610" role="img" aria-label="แผนที่จำนวนคนต่อจังหวัด">';
    Object.entries(GEO).forEach(([k, v]) => {
      const n = cnt[k] || 0;
      const d = v.r.map(r => 'M' + r.map(p => X(p[0]) + ' ' + Y(p[1])).join('L') + 'Z').join('');
      s += `<path d="${d}" fill="${n ? mapRamp(.15 + .85 * n / mx) : 'var(--nd)'}"><title>${esc(TH[k] || v.n)}: ${n}</title></path>`;
    });
    $('#map').innerHTML = s + '</svg>';
    $('#lg2').style.background = `linear-gradient(90deg,${mapRamp(.15)},${mapRamp(1)})`;
    $('#mx2').textContent = mx;
  }

  function filt(el, set, fn) {
    const top = el.scrollTop;
    el.innerHTML = `<label class="all"><input type="checkbox" ${set.size === careers.length ? 'checked' : ''}> ทั้งหมด</label>` +
      careers.map(c => `<label><input type="checkbox" value="${esc(c)}" ${set.has(c) ? 'checked' : ''}> ${esc(c)}</label>`).join('');
    el.scrollTop = top;
    el.onchange = e => {
      const i = e.target;
      if (i.closest('.all')) { set.clear(); if (i.checked) careers.forEach(c => set.add(c)); }
      else if (i.checked) set.add(i.value);
      else set.delete(i.value);
      filt(el, set, fn);
      fn();
    };
  }

  function render() {
    D = D0;
    const c = {};
    D.forEach(r => { if (r.c) c[r.c] = (c[r.c] || 0) + 1; });
    careers = Object.keys(c).sort((a, b) => c[b] - c[a]);
    s1 = new Set(careers.includes('ผู้นำ/บริหาร/ราชการ') ? ['ผู้นำ/บริหาร/ราชการ'] : careers.slice(0, 1));
    s2 = new Set(careers);
    $('#dash-stat').textContent = `รวม ${D.length.toLocaleString('th-TH')} ดวง · ${careers.length} กลุ่มอาชีพ`;
    const empty = !D.length;
    $('#dash-empty').hidden = !empty;
    $('#dash').hidden = empty;
    if (empty) return;
    filt($('#f1'), s1, chart2);
    filt($('#f2'), s2, mapView);
    chart1(); chart2(); mapView();
  }

  render();
})();
