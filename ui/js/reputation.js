// Reputation view (e4 sweep). Treatment (rep visible) vs control (rep hidden)
// across 8 sequential trades per arc, 5 arcs per condition. The headline is
// the per-trade decay curve.

const Reputation = (() => {

  const COLOR_TREATMENT = "#2F6E6E";  // rep visible — buyer surplus
  const COLOR_CONTROL   = "#A0432F";  // rep hidden — seller extracts

  let cachedRep = null;
  let currentPersona = null;  // null => "all personas combined"

  function render(data) {
    const rep = data.reputation;
    if (!rep || !rep.trades?.length) {
      renderEmpty();
      return;
    }
    cachedRep = rep;
    bindControls(rep);
    renderAll();
  }

  function bindControls(rep) {
    const sel = document.getElementById("reputation-persona-select");
    if (!sel) return;
    const personas = rep.personas || [...new Set(rep.trades.map(t => t.buyer_persona_id))];
    sel.innerHTML = "";
    const allOpt = document.createElement("option");
    allOpt.value = ""; allOpt.textContent = "All personas (combined)";
    sel.appendChild(allOpt);
    personas.sort().forEach(p => {
      const opt = document.createElement("option");
      opt.value = p; opt.textContent = personaLabel(p);
      sel.appendChild(opt);
    });
    // Default to whichever persona has the most trades, since the user is
    // usually about to talk about one specific persona's story.
    const counts = {};
    for (const t of rep.trades) {
      counts[t.buyer_persona_id] = (counts[t.buyer_persona_id] || 0) + 1;
    }
    const defaultPersona = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] || "";
    sel.value = currentPersona ?? defaultPersona ?? "";
    currentPersona = sel.value || null;

    sel.removeEventListener("change", onPersonaChange);
    sel.addEventListener("change", onPersonaChange);
  }

  function onPersonaChange(e) {
    currentPersona = e.target.value || null;
    renderAll();
  }

  function filteredTrades() {
    if (!cachedRep) return [];
    if (!currentPersona) return cachedRep.trades;
    return cachedRep.trades.filter(t => t.buyer_persona_id === currentPersona);
  }

  function personaLabel(p) {
    return ({ grandma: "Grandma (low knowledge)", casual: "Casual Shopper", engineer: "Methodical Engineer", mechanic: "Mechanic (expert)" })[p] || p;
  }

  function renderAll() {
    const trades = filteredTrades();
    const summaryEl = document.getElementById("reputation-filter-summary");
    if (summaryEl) {
      const label = currentPersona ? personaLabel(currentPersona) : "all buyer personas";
      summaryEl.textContent = `${trades.length} trades · ${label}`;
    }
    renderStats(trades);
    renderDecayChart(trades);
    renderCloseChart(trades);
    renderReviewFeed(trades);
  }

  function renderEmpty() {
    const host = document.getElementById("reputation-stats");
    if (host) host.innerHTML = `
      <div style="padding:1.5rem;font-style:italic;color:var(--ink-3);font-family:var(--serif);">
        No reputation sweep loaded. Run
        <code>python3 ui/import_reputation.py sweeps/&lt;arc_sweep&gt;</code> then refresh.
      </div>`;
  }

  // ---- per-cell aggregation ----

  function aggregate(trades) {
    const by = {}; // (rep, t) -> { n, deals, sumPrem, totalExtracted, sumRating, ratingN }
    for (const t of trades) {
      const k = `${t.reputation_visible}|${t.trade_index}`;
      if (!by[k]) by[k] = { rep: t.reputation_visible, ti: t.trade_index,
                            n: 0, deals: 0, sumPrem: 0, premN: 0,
                            totalExtracted: 0, sumRating: 0, ratingN: 0 };
      const c = by[k];
      c.n += 1;
      if (t.outcome === "deal") {
        c.deals += 1;
        if (t.premium_over_true != null) {
          c.sumPrem += t.premium_over_true;
          c.premN += 1;
          c.totalExtracted += (t.final_price ?? 0) - (t.true_value ?? 0);
        }
      }
      if (t.review?.rating != null) {
        c.sumRating += t.review.rating;
        c.ratingN += 1;
      }
    }
    return Object.values(by);
  }

  function topline(trades) {
    const t = trades.filter(x => x.reputation_visible);
    const c = trades.filter(x => !x.reputation_visible);
    return {
      treatment: summarize(t),
      control: summarize(c),
    };
  }
  function summarize(rows) {
    const deals = rows.filter(r => r.outcome === "deal");
    const closed = deals.length;
    const meanPrem = closed ? deals.reduce((s,r) => s + (r.premium_over_true || 0), 0) / closed : null;
    const ratings = rows.filter(r => r.review?.rating != null).map(r => r.review.rating);
    const meanRating = ratings.length ? ratings.reduce((a,b) => a+b, 0) / ratings.length : null;
    const totalExtracted = deals.reduce((s,r) => s + ((r.final_price ?? 0) - (r.true_value ?? 0)), 0);
    return { n: rows.length, closed, meanPrem, meanRating, totalExtracted };
  }

  // ---- stats cards ----

  function renderStats(trades) {
    const t = topline(trades);
    const ratio = t.control.totalExtracted > 0
      ? t.treatment.totalExtracted / t.control.totalExtracted
      : null;
    const host = document.getElementById("reputation-stats");
    host.innerHTML = "";

    const rows = [
      ["Close rate",
       `${(t.treatment.closed/t.treatment.n*100).toFixed(0)}%`,
       `${(t.control.closed/t.control.n*100).toFixed(0)}%`,
       `${((t.treatment.closed/t.treatment.n - t.control.closed/t.control.n)*100).toFixed(0)} pp`,
       (t.treatment.closed/t.treatment.n - t.control.closed/t.control.n) < 0],
      ["Mean premium (closed deals)",
       fmtPct(t.treatment.meanPrem),
       fmtPct(t.control.meanPrem),
       fmtPctDelta((t.treatment.meanPrem ?? 0) - (t.control.meanPrem ?? 0)),
       (t.treatment.meanPrem ?? 0) < (t.control.meanPrem ?? 0)],
      ["Mean buyer rating",
       t.treatment.meanRating != null ? `${t.treatment.meanRating.toFixed(2)} / 5` : "—",
       t.control.meanRating != null ? `${t.control.meanRating.toFixed(2)} / 5` : "—",
       t.treatment.meanRating != null && t.control.meanRating != null
         ? `+${(t.treatment.meanRating - t.control.meanRating).toFixed(2)}` : "—",
       (t.treatment.meanRating ?? 0) > (t.control.meanRating ?? 0)],
      ["Total extracted value (seller surplus)",
       fmtUsd(t.treatment.totalExtracted),
       fmtUsd(t.control.totalExtracted),
       ratio != null ? `${((1 - ratio) * 100).toFixed(0)}% drop` : "—",
       (t.treatment.totalExtracted ?? 0) < (t.control.totalExtracted ?? 0)],
    ];

    const table = document.createElement("div");
    table.className = "rep-stats-grid";
    table.innerHTML = `
      <div class="rep-stats-head"></div>
      <div class="rep-stats-head rep-stats-head-treatment">Treatment<br><span>reputation visible</span></div>
      <div class="rep-stats-head rep-stats-head-control">Control<br><span>reputation hidden</span></div>
      <div class="rep-stats-head">Δ</div>
      ${rows.map(([label, a, b, delta, good]) => `
        <div class="rep-stats-label">${label}</div>
        <div class="rep-stats-cell rep-stats-cell-treatment">${a}</div>
        <div class="rep-stats-cell rep-stats-cell-control">${b}</div>
        <div class="rep-stats-cell rep-stats-cell-delta ${good ? "rep-good" : "rep-bad"}">${delta}</div>
      `).join("")}
    `;
    host.appendChild(table);
  }

  // ---- decay curve ----

  function renderDecayChart(trades) {
    const host = document.getElementById("reputation-decay");
    host.innerHTML = "";

    const cells = aggregate(trades);

    const W = host.clientWidth || 800, H = 340;
    const margin = { top: 22, right: 36, bottom: 50, left: 56 };
    const w = W - margin.left - margin.right, h = H - margin.top - margin.bottom;

    const svg = d3.select(host).append("svg")
      .attr("viewBox", `0 0 ${W} ${H}`).attr("preserveAspectRatio", "xMidYMid meet");
    const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

    const x = d3.scaleLinear().domain([0, 7]).range([0, w]);
    const yMax = d3.max(cells, d => d.premN ? d.sumPrem / d.premN : 0);
    const yMin = Math.min(0, d3.min(cells, d => d.premN ? d.sumPrem / d.premN : 0));
    const y = d3.scaleLinear().domain([yMin - 0.02, Math.max(0.6, yMax + 0.05)]).range([h, 0]);

    g.append("g").attr("class", "grid")
      .call(d3.axisLeft(y).tickSize(-w).tickFormat(""))
      .call(gg => gg.select(".domain").remove())
      .selectAll("text").remove();

    g.append("line").attr("class", "ref-line")
      .attr("x1", 0).attr("x2", w)
      .attr("y1", y(0)).attr("y2", y(0));
    g.append("text").attr("class", "ref-label")
      .attr("x", w - 4).attr("y", y(0) - 4).attr("text-anchor", "end")
      .text("zero premium (fair price)");

    const xAxis = d3.axisBottom(x).ticks(8).tickFormat(d => `trade ${d}`);
    g.append("g").attr("class", "axis").attr("transform", `translate(0,${h})`).call(xAxis);
    const yAxis = d3.axisLeft(y).ticks(7).tickFormat(d => `${(d * 100).toFixed(0)}%`);
    g.append("g").attr("class", "axis").call(yAxis);

    g.append("text").attr("class", "axis-label")
      .attr("transform", "rotate(-90)").attr("x", 0).attr("y", -42).attr("text-anchor", "end")
      .text("mean premium over true value");

    const series = [
      { rep: true,  color: COLOR_TREATMENT, label: "reputation visible (treatment)" },
      { rep: false, color: COLOR_CONTROL,   label: "reputation hidden (control)" },
    ];

    series.forEach(s => {
      const points = d3.range(0, 8).map(ti => {
        const c = cells.find(c => c.rep === s.rep && c.ti === ti);
        return c && c.premN ? { ti, val: c.sumPrem / c.premN, n: c.premN } : null;
      }).filter(Boolean);

      const line = d3.line()
        .x(d => x(d.ti)).y(d => y(d.val))
        .curve(d3.curveMonotoneX);
      g.append("path").datum(points)
        .attr("d", line).attr("fill", "none")
        .attr("stroke", s.color).attr("stroke-width", 2);
      g.selectAll(null).data(points).join("circle")
        .attr("cx", d => x(d.ti)).attr("cy", d => y(d.val))
        .attr("r", 4.5).attr("fill", s.color).attr("stroke", "var(--bg-elev)").attr("stroke-width", 1.5);
    });

    // Annotation: where treatment "crystallizes".
    g.append("line").attr("class", "ref-line")
      .attr("x1", x(3)).attr("x2", x(3))
      .attr("y1", 0).attr("y2", h)
      .attr("stroke", "var(--gold)").attr("stroke-dasharray", "3 4");
    g.append("text").attr("class", "ref-label")
      .attr("x", x(3) + 5).attr("y", 14).attr("fill", "var(--gold)")
      .text("seller's reputation crystallizes here");

    const legend = document.getElementById("reputation-decay-legend");
    legend.innerHTML = series.map(s =>
      `<span><span class="legend-swatch" style="background:${s.color}"></span>${s.label}</span>`
    ).join("");
  }

  // ---- close rate chart ----

  function renderCloseChart(trades) {
    const host = document.getElementById("reputation-close");
    host.innerHTML = "";

    const cells = aggregate(trades);
    const W = host.clientWidth || 800, H = 220;
    const margin = { top: 18, right: 36, bottom: 42, left: 56 };
    const w = W - margin.left - margin.right, h = H - margin.top - margin.bottom;

    const svg = d3.select(host).append("svg")
      .attr("viewBox", `0 0 ${W} ${H}`).attr("preserveAspectRatio", "xMidYMid meet");
    const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

    const x = d3.scaleLinear().domain([0, 7]).range([0, w]);
    const y = d3.scaleLinear().domain([0, 1]).range([h, 0]);

    g.append("g").attr("class", "grid")
      .call(d3.axisLeft(y).tickSize(-w).tickFormat(""))
      .call(gg => gg.select(".domain").remove())
      .selectAll("text").remove();

    const xAxis = d3.axisBottom(x).ticks(8).tickFormat(d => `trade ${d}`);
    g.append("g").attr("class", "axis").attr("transform", `translate(0,${h})`).call(xAxis);
    const yAxis = d3.axisLeft(y).ticks(5).tickFormat(d => `${(d * 100).toFixed(0)}%`);
    g.append("g").attr("class", "axis").call(yAxis);

    g.append("text").attr("class", "axis-label")
      .attr("transform", "rotate(-90)").attr("x", 0).attr("y", -42).attr("text-anchor", "end")
      .text("close rate");

    const series = [
      { rep: true,  color: COLOR_TREATMENT },
      { rep: false, color: COLOR_CONTROL },
    ];
    series.forEach(s => {
      const points = d3.range(0, 8).map(ti => {
        const c = cells.find(c => c.rep === s.rep && c.ti === ti);
        return c ? { ti, val: c.deals / c.n } : null;
      }).filter(Boolean);
      const line = d3.line().x(d => x(d.ti)).y(d => y(d.val)).curve(d3.curveMonotoneX);
      g.append("path").datum(points).attr("d", line).attr("fill", "none")
        .attr("stroke", s.color).attr("stroke-width", 2);
      g.selectAll(null).data(points).join("circle")
        .attr("cx", d => x(d.ti)).attr("cy", d => y(d.val))
        .attr("r", 4).attr("fill", s.color).attr("stroke", "var(--bg-elev)").attr("stroke-width", 1.5);
    });
  }

  // ---- reviews feed ----

  function renderReviewFeed(trades) {
    const host = document.getElementById("reputation-reviews");
    host.innerHTML = "";

    // Take all reviews with text, sort by treatment (treatment first for context),
    // then by trade_index so reader sees the seller's reputation building.
    const reviews = trades
      .filter(t => t.review?.review_text)
      .sort((a, b) => {
        if (a.reputation_visible !== b.reputation_visible)
          return a.reputation_visible ? -1 : 1;
        if (a.arc_id !== b.arc_id) return a.arc_id < b.arc_id ? -1 : 1;
        return a.trade_index - b.trade_index;
      });

    // Limit to ~20 to keep the page manageable.
    const slice = reviews.slice(0, 24);
    slice.forEach(t => {
      const r = t.review;
      const stars = "★".repeat(r.rating) + "☆".repeat(5 - r.rating);
      const cond = t.reputation_visible
        ? `<span class="rev-cond rev-cond-treatment">rep visible</span>`
        : `<span class="rev-cond rev-cond-control">rep hidden</span>`;
      const card = document.createElement("div");
      card.className = "review-card";
      card.innerHTML = `
        <div class="review-head">
          <span class="review-stars" data-rating="${r.rating}">${stars}</span>
          <span class="review-meta">trade ${t.trade_index} · ${t.arc_id.replace(/_/g," ")}</span>
          ${cond}
        </div>
        <div class="review-text">"${escape(r.review_text)}"</div>
        <div class="review-foot">
          paid <strong>$${fmt(t.final_price)}</strong> for a car worth
          <strong>$${fmt(t.true_value)}</strong>
          (<span style="color:${(t.premium_over_true||0)>0?'var(--clay-deep)':'var(--teal-deep)'}">${fmtPct(t.premium_over_true)}</span>)
        </div>
      `;
      host.appendChild(card);
    });
  }

  // ---- helpers ----

  function fmtPct(v) {
    if (v == null) return "—";
    const sign = v >= 0 ? "+" : "−";
    return `${sign}${Math.abs(v*100).toFixed(1)}%`;
  }
  function fmtPctDelta(v) {
    const sign = v >= 0 ? "+" : "−";
    return `${sign}${Math.abs(v*100).toFixed(1)} pp`;
  }
  function fmtUsd(v) {
    if (v == null) return "—";
    return `$${Math.round(v).toLocaleString()}`;
  }
  function fmt(v) {
    if (v == null) return "—";
    return Math.round(v).toLocaleString();
  }
  function escape(s) {
    return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
                    .replace(/"/g,"&quot;").replace(/'/g,"&#039;");
  }

  return { render };
})();
