// "Who's in the lot" — renders buyer cards, seller cards, car cards in
// the screenshot's clean style. Loads from window.AT_DATA (E1 data) so
// personas/cars come from the existing data layer.
(function() {
  'use strict';

  // Buyer indicator dots.
  const BUYER_DOT = {
    grandma:  '#c64e3a',   // red
    casual:   '#d97e3a',   // orange
    engineer: '#7ba84e',   // green
    mechanic: '#3a9b8a',   // teal
  };

  // Seller indicator squares.
  const SELLER_SQUARE = {
    honest:    '#3a9b8a',  // teal
    pragmatic: '#8a8a3a',  // olive
    pushy:     '#d97e3a',  // orange
    slimy:     '#c64e3a',  // red
  };

  // Car severity dot by tier.
  function severityDot(gap) {
    if (gap < 1000)  return '#3a9b8a';
    if (gap < 4000)  return '#cb8e3a';
    if (gap < 7000)  return '#d97e3a';
    return '#c64e3a';
  }

  function escapeHtml(s) {
    return String(s || '').replace(/[&<>"']/g,
      c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  function bar(label, value) {
    const v = Math.max(0, Math.min(1, value || 0));
    return `<div class="lot-bar">
      <span class="lot-bar-label">${escapeHtml(label)}</span>
      <span class="lot-bar-track"><span class="lot-bar-fill" style="width:${v*100}%"></span></span>
      <span class="lot-bar-val">${v.toFixed(2)}</span>
    </div>`;
  }

  function buyerCard(p) {
    const dot = BUYER_DOT[p.persona_id] || '#999';
    return `<div class="lot-card">
      <div class="lot-card-eyebrow">BUYER</div>
      <div class="lot-card-name">
        <span class="lot-name-text">${escapeHtml(p.display_name || p.persona_id)}</span>
        <span class="lot-dot" style="background:${dot}"></span>
      </div>
      <div class="lot-card-bars">
        ${bar('knowledge', p.knowledge_level)}
        ${bar('skepticism', p.skepticism)}
        ${bar('inspects', p.inspection_propensity)}
      </div>
    </div>`;
  }

  function sellerCard(p) {
    const sq = SELLER_SQUARE[p.persona_id] || '#999';
    // "honesty" = 1 - deceptiveness so the bar reads positively
    const honesty = 1.0 - (p.deceptiveness || 0);
    return `<div class="lot-card">
      <div class="lot-card-eyebrow">SELLER</div>
      <div class="lot-card-name">
        <span class="lot-name-text">${escapeHtml(p.display_name || p.persona_id)}</span>
        <span class="lot-square" style="background:${sq}"></span>
      </div>
      <div class="lot-card-bars">
        ${bar('honesty', honesty)}
        ${bar('pressure', p.pressure)}
        ${bar('patience', p.patience)}
      </div>
    </div>`;
  }

  function carCard(c) {
    const gap = (c.asking_price || 0) - (c.true_value || 0);
    const dot = severityDot(gap);
    // Normalized bars 0..1:
    const sev = Math.min(1, gap / 13200);                  // tahoe = 1.0
    const miles = Math.min(1, (c.odometer_miles || 0) / 200000);
    const facts = Math.min(1, (c.private_facts || []).length / 5);
    const name = `${c.year} ${c.make} ${c.model}`;
    return `<div class="lot-card">
      <div class="lot-card-eyebrow">CAR</div>
      <div class="lot-card-name">
        <span class="lot-name-text">${escapeHtml(name)}</span>
        <span class="lot-dot" style="background:${dot}"></span>
      </div>
      <div class="lot-card-bars">
        ${bar('severity', sev)}
        ${bar('mileage', miles)}
        ${bar('hidden facts', facts)}
      </div>
    </div>`;
  }

  function render() {
    const data = window.AT_DATA;
    if (!data) return;
    const personasObj = data.personas || {};
    const buyersObj  = personasObj.buyers  || {};
    const sellersObj = personasObj.sellers || {};
    const carsObj    = data.cars || {};

    const buyers  = Array.isArray(buyersObj)  ? buyersObj  : Object.values(buyersObj);
    const sellers = Array.isArray(sellersObj) ? sellersObj : Object.values(sellersObj);
    const carsAll = Array.isArray(carsObj)    ? carsObj    : Object.values(carsObj);

    // Buyer order: grandma → casual → engineer → mechanic
    const buyerOrder = ['grandma', 'casual', 'engineer', 'mechanic'];
    const sellerOrder = ['honest', 'pragmatic', 'pushy', 'slimy'];
    const buyersOrdered  = buyerOrder.map(id => buyers.find(p => p.persona_id === id)).filter(Boolean);
    const sellersOrdered = sellerOrder.map(id => sellers.find(p => p.persona_id === id)).filter(Boolean);

    // Cars used in e3 sweep: prius_2018 (clean), altima_2017 (moderate), tahoe_2016 (catastrophic)
    const carOrder = ['prius_2018', 'altima_2017', 'tahoe_2016'];
    const cars = carOrder.map(id => carsAll.find(c => c.car_id === id)).filter(Boolean);

    const bEl = document.getElementById('lot-buyers');
    const sEl = document.getElementById('lot-sellers');
    const cEl = document.getElementById('lot-cars');
    if (bEl) bEl.innerHTML = buyersOrdered.map(buyerCard).join('');
    if (sEl) sEl.innerHTML = sellersOrdered.map(sellerCard).join('');
    if (cEl) cEl.innerHTML = cars.map(carCard).join('');
  }

  window.AT_LOT_RENDER = render;
})();
