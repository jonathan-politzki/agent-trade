// "Who's on the lot" view — renders sellers, buyers, cars (grouped by severity).
//
// Data: window.AT_DATA is the global object built by data.js (loaded JSONs).
// Note: AT_DATA.cars may be an object keyed by car_id (carsById) or an array;
// we normalise to an array via Object.values() so both shapes work.

(function() {
  'use strict';

  const SELLER_ARCHETYPE_COLOR = {
    honest:     '#3a7',
    honest_:    '#3a7',
    pragmatic:  '#666',
    pushy:      '#d80',
    slimy:      '#c33',
    aggressive: '#c33',
    moderate:   '#d80',
  };

  function bar(value, label) {
    const pct = Math.max(0, Math.min(1, value)) * 100;
    return `<div class="lot-bar"><span class="lot-bar-label">${label}</span>`
         + `<span class="lot-bar-track"><span class="lot-bar-fill" style="width:${pct}%"></span></span>`
         + `<span class="lot-bar-val">${value.toFixed(2)}</span></div>`;
  }

  function sellerCard(p) {
    const arch = p.archetype || p.persona_id;
    const color = SELLER_ARCHETYPE_COLOR[arch] || SELLER_ARCHETYPE_COLOR[p.persona_id] || '#888';
    const tactics = (p.default_tactics || []).slice(0, 4).join(', ') || '—';
    const sys = (p.system_prompt || '').slice(0, 220) + ((p.system_prompt || '').length > 220 ? '…' : '');
    return `<div class="lot-card lot-card-seller" style="border-left-color:${color}">
      <div class="lot-card-head">
        <div class="lot-card-name">${p.display_name || p.persona_id}</div>
        <div class="lot-card-tag" style="background:${color}22;color:${color}">${arch}</div>
      </div>
      ${bar(p.knowledge_level ?? 0, 'knowledge')}
      ${bar(p.deceptiveness ?? 0, 'deceptiveness')}
      ${bar(p.pressure ?? 0, 'pressure')}
      <div class="lot-card-row"><span class="lot-card-label">tactics</span><span class="lot-card-val">${tactics}</span></div>
      <details class="lot-card-prompt"><summary>system prompt</summary><pre>${sys}</pre></details>
    </div>`;
  }

  function buyerCard(p) {
    const sys = (p.system_prompt || '').slice(0, 220) + ((p.system_prompt || '').length > 220 ? '…' : '');
    return `<div class="lot-card lot-card-buyer">
      <div class="lot-card-head">
        <div class="lot-card-name">${p.display_name || p.persona_id}</div>
        <div class="lot-card-tag">budget $${(p.default_budget || 0).toLocaleString()}</div>
      </div>
      ${bar(p.knowledge_level ?? 0, 'knowledge')}
      ${bar(p.skepticism ?? 0, 'skepticism')}
      ${bar(p.inspection_propensity ?? 0, 'inspection prop.')}
      ${bar(p.patience ?? 0, 'patience')}
      <details class="lot-card-prompt"><summary>system prompt</summary><pre>${sys}</pre></details>
    </div>`;
  }

  function severityTier(gap) {
    if (gap < 1000)  return {name: 'Clean',         color: '#3a7'};
    if (gap < 2000)  return {name: 'Minor',         color: '#7b3'};
    if (gap < 4000)  return {name: 'Moderate',      color: '#cb3'};
    if (gap < 7000)  return {name: 'Severe',        color: '#d80'};
    return                  {name: 'Catastrophic', color: '#c33'};
  }

  function carCard(c) {
    const gap = (c.asking_price || 0) - (c.true_value || 0);
    const tier = severityTier(gap);
    const facts = (c.private_facts || []).length;
    return `<div class="lot-card lot-card-car" style="border-left-color:${tier.color}">
      <div class="lot-card-head">
        <div class="lot-card-name">${c.year} ${c.make} ${c.model}</div>
        <div class="lot-card-tag" style="background:${tier.color}22;color:${tier.color}">${tier.name}</div>
      </div>
      <div class="lot-car-prices">
        <span><span class="lot-card-label">asking</span> $${(c.asking_price || 0).toLocaleString()}</span>
        <span><span class="lot-card-label">true</span> $${(c.true_value || 0).toLocaleString()}</span>
        <span><span class="lot-card-label">gap</span> <strong>$${gap >= 0 ? '+' : ''}${gap.toLocaleString()}</strong></span>
      </div>
      <div class="lot-card-row"><span class="lot-card-label">miles</span><span class="lot-card-val">${(c.odometer_miles || 0).toLocaleString()}</span></div>
      <div class="lot-card-row"><span class="lot-card-label">private facts</span><span class="lot-card-val">${facts} hidden</span></div>
    </div>`;
  }

  function carTierBlock(tierName, tierColor, cars) {
    if (!cars.length) return '';
    return `<div class="lot-tier">
      <h3 class="lot-tier-head" style="color:${tierColor}">${tierName} <span class="lot-tier-count">(${cars.length})</span></h3>
      <div class="lot-grid">${cars.map(carCard).join('')}</div>
    </div>`;
  }

  function render() {
    const data = window.AT_DATA;
    if (!data) return;
    const sellers = Object.values((data.personas && data.personas.sellers) || {});
    const buyers  = Object.values((data.personas && data.personas.buyers)  || {});
    // data.cars may be an object (carsById dict from data.js) or an array.
    const carsRaw = data.cars || {};
    const cars = Array.isArray(carsRaw) ? carsRaw : Object.values(carsRaw);

    const sellersEl = document.getElementById('lot-sellers');
    if (sellersEl) sellersEl.innerHTML = sellers.map(sellerCard).join('');
    const buyersEl = document.getElementById('lot-buyers');
    if (buyersEl) buyersEl.innerHTML = buyers.map(buyerCard).join('');

    const carsEl = document.getElementById('lot-cars');
    if (carsEl) {
      const tiers = [
        {name: 'Clean',        color: '#3a7', cars: []},
        {name: 'Minor',        color: '#7b3', cars: []},
        {name: 'Moderate',     color: '#cb3', cars: []},
        {name: 'Severe',       color: '#d80', cars: []},
        {name: 'Catastrophic', color: '#c33', cars: []},
      ];
      cars.forEach(c => {
        const gap = (c.asking_price || 0) - (c.true_value || 0);
        const t = severityTier(gap);
        const tier = tiers.find(x => x.name === t.name);
        if (tier) tier.cars.push(c);
      });
      // Sort cars within each tier by gap descending.
      tiers.forEach(t => t.cars.sort((a, b) =>
        ((b.asking_price - b.true_value) - (a.asking_price - a.true_value))));
      carsEl.innerHTML = tiers.map(t => carTierBlock(t.name, t.color, t.cars)).join('');
    }
  }

  window.AT_LOT_RENDER = render;
})();
