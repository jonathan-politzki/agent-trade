// E3 — Delegation tab. Loads ui/data/e3_sessions.json independently of the
// main AT_DATA, so this view doesn't touch E1 data.
(function() {
  'use strict';

  let _rows = null;

  async function loadE3() {
    if (_rows !== null) return _rows;
    try {
      const r = await fetch('data/e3_sessions.json');
      _rows = await r.json();
      console.log(`E3: loaded ${_rows.length} session rows`);
    } catch (e) {
      console.warn('E3: failed to load data/e3_sessions.json', e);
      _rows = [];
    }
    return _rows;
  }

  function mean(xs) {
    if (!xs.length) return null;
    return xs.reduce((a,b) => a+b, 0) / xs.length;
  }

  function aggregateByCell(rows, cell) {
    const bucket = rows.filter(r => r.cell === cell);
    const deals = bucket.filter(r => r.outcome === 'deal');
    const walks = bucket.filter(r => (r.outcome || '').includes('walk_away'));
    const timeouts = bucket.filter(r => r.outcome === 'timeout');
    const prems = deals.map(r => r.premium_over_true).filter(p => p !== null && p !== undefined);
    const turns = bucket.map(r => r.n_turns || 0);
    return {
      n: bucket.length, deals: deals.length, walks: walks.length, timeouts: timeouts.length,
      deal_rate: bucket.length ? deals.length / bucket.length : 0,
      mean_premium: mean(prems),
      mean_turns: mean(turns),
    };
  }

  function fmtPct(x, signed) {
    if (x === null || x === undefined) return '—';
    const v = x * 100;
    return (signed && v >= 0 ? '+' : '') + v.toFixed(1) + '%';
  }

  function renderAggregate(rows) {
    const el = document.getElementById('e3-aggregate');
    if (!el) return;
    const hh = aggregateByCell(rows, 'H-H');
    const aa = aggregateByCell(rows, 'A-A');
    const delta_pct = (aa.deal_rate - hh.deal_rate) * 100;
    const delta_prem = ((aa.mean_premium || 0) - (hh.mean_premium || 0)) * 100;
    el.innerHTML = `
      <table class="e3-table">
        <thead>
          <tr>
            <th></th>
            <th>H-H (persona voice)</th>
            <th>A-A (agent briefing)</th>
            <th>delta</th>
          </tr>
        </thead>
        <tbody>
          <tr><td>n</td><td>${hh.n}</td><td>${aa.n}</td><td></td></tr>
          <tr><td>deals</td><td>${hh.deals}</td><td>${aa.deals}</td><td>${aa.deals - hh.deals >= 0 ? '+' : ''}${aa.deals - hh.deals}</td></tr>
          <tr><td>deal rate</td><td>${fmtPct(hh.deal_rate, false)}</td><td>${fmtPct(aa.deal_rate, false)}</td><td class="e3-delta-positive">${delta_pct >= 0 ? '+' : ''}${delta_pct.toFixed(1)} pp</td></tr>
          <tr><td>walk-aways</td><td>${hh.walks}</td><td>${aa.walks}</td><td>${aa.walks - hh.walks >= 0 ? '+' : ''}${aa.walks - hh.walks}</td></tr>
          <tr><td>timeouts</td><td>${hh.timeouts}</td><td>${aa.timeouts}</td><td>${aa.timeouts - hh.timeouts >= 0 ? '+' : ''}${aa.timeouts - hh.timeouts}</td></tr>
          <tr><td>mean premium on deals</td><td>${fmtPct(hh.mean_premium, true)}</td><td>${fmtPct(aa.mean_premium, true)}</td><td class="e3-delta-positive">${delta_prem >= 0 ? '+' : ''}${delta_prem.toFixed(1)} pp</td></tr>
          <tr><td>mean turns</td><td>${hh.mean_turns ? hh.mean_turns.toFixed(1) : '—'}</td><td>${aa.mean_turns ? aa.mean_turns.toFixed(1) : '—'}</td><td></td></tr>
        </tbody>
      </table>
      <p class="e3-callout">Same model on both sides (Gemini-flash-lite via Vertex). Same tools, same 22-turn cap. Only the system prompt changes.</p>
    `;
  }

  function renderOutcomeChart(rows) {
    const el = document.getElementById('e3-outcome-chart');
    if (!el || !window.d3) return;
    el.innerHTML = '';
    const cells = ['H-H', 'A-A'];
    const outcomes = ['deal', 'walk_away_buyer', 'walk_away_seller', 'timeout'];
    const data = [];
    cells.forEach(c => {
      const bucket = rows.filter(r => r.cell === c);
      const tot = bucket.length || 1;
      outcomes.forEach(o => {
        const n = bucket.filter(r => r.outcome === o).length;
        data.push({cell: c, outcome: o, n, frac: n/tot});
      });
    });
    const W = 600, H = 300, M = {top: 20, right: 140, bottom: 50, left: 70};
    const svg = d3.select(el).append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('width', '100%');
    const x = d3.scaleBand().domain(cells).range([M.left, W-M.right]).padding(0.25);
    const y = d3.scaleLinear().domain([0,1]).range([H-M.bottom, M.top]);
    const colors = {deal: '#3a7', walk_away_buyer: '#d80', walk_away_seller: '#cb3', timeout: '#888'};
    const stacked = {};
    cells.forEach(c => {
      let acc = 0;
      stacked[c] = outcomes.map(o => {
        const row = data.find(d => d.cell===c && d.outcome===o);
        const start = acc;
        acc += row.frac;
        return {...row, y0: start, y1: acc};
      });
    });
    cells.forEach(c => {
      stacked[c].forEach(seg => {
        svg.append('rect')
          .attr('x', x(c)).attr('width', x.bandwidth())
          .attr('y', y(seg.y1)).attr('height', y(seg.y0) - y(seg.y1))
          .attr('fill', colors[seg.outcome])
          .append('title').text(`${seg.outcome}: ${seg.n} (${(seg.frac*100).toFixed(1)}%)`);
        if (seg.frac > 0.05) {
          svg.append('text')
            .attr('x', x(c) + x.bandwidth()/2)
            .attr('y', y((seg.y0 + seg.y1)/2) + 4)
            .attr('text-anchor', 'middle').attr('font-size', '11px').attr('fill', '#fff')
            .text(seg.n);
        }
      });
    });
    svg.append('g').attr('transform', `translate(0,${H-M.bottom})`).call(d3.axisBottom(x));
    svg.append('g').attr('transform', `translate(${M.left},0)`).call(d3.axisLeft(y).ticks(5).tickFormat(d => `${(d*100).toFixed(0)}%`));
    svg.append('text').attr('x', M.left/3).attr('y', M.top + 10).attr('font-size', '11px').text('% of sessions');

    // Legend
    const legend = svg.append('g').attr('transform', `translate(${W-M.right+10},${M.top})`);
    outcomes.forEach((o, i) => {
      const g = legend.append('g').attr('transform', `translate(0,${i*22})`);
      g.append('rect').attr('width', 14).attr('height', 14).attr('fill', colors[o]);
      g.append('text').attr('x', 20).attr('y', 12).attr('font-size', '12px').text(o);
    });
  }

  function renderPerCar(rows) {
    const el = document.getElementById('e3-per-car');
    if (!el || !window.d3) return;
    el.innerHTML = '';
    const cars = ['prius_2018', 'altima_2017', 'tahoe_2016'];
    const carLabel = {prius_2018: 'Prius 2018 (clean)', altima_2017: 'Altima 2017 (moderate)', tahoe_2016: 'Tahoe 2016 (catastrophic)'};
    const cells = ['H-H', 'A-A'];
    const data = [];
    cars.forEach(c => cells.forEach(cell => {
      const bucket = rows.filter(r => r.car_id===c && r.cell===cell);
      const deals = bucket.filter(r => r.outcome==='deal');
      const prems = deals.map(r => r.premium_over_true).filter(p => p!==null && p!==undefined);
      data.push({car: c, cell, n: bucket.length, n_deals: deals.length,
                  mean_premium: prems.length ? prems.reduce((a,b)=>a+b,0)/prems.length : null});
    }));
    const W = 700, H = 320, M = {top: 20, right: 120, bottom: 60, left: 70};
    const svg = d3.select(el).append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('width', '100%');
    const x0 = d3.scaleBand().domain(cars.map(c => carLabel[c])).range([M.left, W-M.right]).padding(0.2);
    const x1 = d3.scaleBand().domain(cells).range([0, x0.bandwidth()]).padding(0.1);
    const maxP = Math.max(0.1, d3.max(data, d => d.mean_premium || 0));
    const y = d3.scaleLinear().domain([0, maxP * 1.1]).range([H-M.bottom, M.top]);
    const colors = {'H-H': '#557', 'A-A': '#c33'};
    data.forEach(d => {
      const px = x0(carLabel[d.car]) + x1(d.cell);
      const w = x1.bandwidth();
      if (d.mean_premium !== null) {
        svg.append('rect').attr('x', px).attr('width', w)
          .attr('y', y(d.mean_premium)).attr('height', y(0) - y(d.mean_premium))
          .attr('fill', colors[d.cell])
          .append('title').text(`${d.car} ${d.cell}: ${d.n_deals} deals, mean premium ${(d.mean_premium*100).toFixed(1)}%`);
        svg.append('text').attr('x', px + w/2).attr('y', y(d.mean_premium) - 4)
          .attr('text-anchor', 'middle').attr('font-size', '11px').attr('fill', '#333')
          .text(`${(d.mean_premium*100).toFixed(0)}%`);
      }
      svg.append('text').attr('x', px + w/2).attr('y', H-M.bottom + 15)
        .attr('text-anchor', 'middle').attr('font-size', '10px').attr('fill', '#666')
        .text(`${d.n_deals}/${d.n}`);
    });
    svg.append('g').attr('transform', `translate(0,${H-M.bottom})`).call(d3.axisBottom(x0))
      .selectAll('text').attr('font-size', '11px').style('text-anchor', 'middle');
    svg.append('g').attr('transform', `translate(${M.left},0)`).call(d3.axisLeft(y).ticks(6).tickFormat(d => `${(d*100).toFixed(0)}%`));
    svg.append('text').attr('x', M.left/3).attr('y', M.top + 10).attr('font-size', '11px').text('mean premium');

    const legend = svg.append('g').attr('transform', `translate(${W-M.right+10},${M.top})`);
    cells.forEach((c, i) => {
      const g = legend.append('g').attr('transform', `translate(0,${i*22})`);
      g.append('rect').attr('width', 14).attr('height', 14).attr('fill', colors[c]);
      g.append('text').attr('x', 20).attr('y', 12).attr('font-size', '12px').text(c);
    });
  }

  function renderFeatured(rows) {
    const el = document.getElementById('e3-featured');
    if (!el) return;
    const featured = [
      's_tahoe_2016_honest_mechanic_geminif_geminif_000_AhAb_kh',
      's_tahoe_2016_slimy_mechanic_geminif_geminif_000_AhAb_kh',
      's_tahoe_2016_honest_casual_geminif_geminif_000_kh',
      's_altima_2017_pragmatic_grandma_geminif_geminif_000_AhAb_kh',
      's_prius_2018_slimy_mechanic_geminif_geminif_000_kh',
    ];
    el.innerHTML = featured.map(sid => {
      const r = rows.find(x => x.session_id === sid);
      if (!r) return `<li><code>${sid}</code> <em>(not found in dataset)</em></li>`;
      const prem = r.premium_over_true !== null ? (r.premium_over_true*100).toFixed(1) + '%' : '—';
      const cell = r.cell || '?';
      const label = `${r.car_id} · ${r.seller_persona_id} → ${r.buyer_persona_id} · cell ${cell} · outcome ${r.outcome} · premium ${prem}`;
      return `<li><code>${sid}</code><br><span class="e3-featured-label">${label}</span></li>`;
    }).join('');
  }

  async function render() {
    const rows = await loadE3();
    renderAggregate(rows);
    renderOutcomeChart(rows);
    renderPerCar(rows);
    renderFeatured(rows);
  }

  window.AT_E3_RENDER = render;
})();
