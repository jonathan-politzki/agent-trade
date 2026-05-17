// Overview view: topline stat cards, premium histogram (split by buyer
// persona), persona-pair matrix, and inspection-vs-premium scatter.

const Overview = (() => {

  const COLORS = {
    grandma:  "#A0432F",
    casual:   "#CC785C",
    engineer: "#7A8B5A",
    mechanic: "#2F6E6E",
  };

  function render(data) {
    renderStatCards(data.sessions);
    renderPremiumHistogram(data.sessions);
    renderPairMatrix(data.sessions);
    renderInspectionScatter(data.sessions);
  }

  // ---------- Stat cards -----------------------------------------------------

  function renderStatCards(sessions) {
    const deals = sessions.filter(s => s.outcome === "deal");
    const inspected = sessions.filter(s => s.n_inspections > 0);
    const meanPrem = Data.mean(deals.map(s => s.premium_over_true).filter(v => v != null));
    const setStat = (key, v) => {
      const el = document.querySelector(`[data-stat="${key}"]`);
      if (el) el.textContent = v;
    };
    setStat("n_sessions", sessions.length.toLocaleString());
    setStat("deal_rate", `${(deals.length / sessions.length * 100).toFixed(1)}%`);
    setStat("mean_premium", meanPrem == null ? "—" : `${(meanPrem * 100).toFixed(1)}%`);
    setStat("inspection_rate", `${(inspected.length / sessions.length * 100).toFixed(1)}%`);
  }

  // ---------- Premium distribution (ridgeline) -------------------------------
  //
  // Why a ridgeline and not stacked density curves: when one persona has many
  // more closed deals than another, count-based curves let the larger-N
  // persona visually dominate even when distributional *shape* is what the
  // reader needs. A ridgeline puts each persona on its own row, normalizes to
  // unit area, and annotates n + median so sample-size info is preserved
  // without distorting the shape comparison.

  function renderPremiumHistogram(sessions) {
    const host = document.getElementById("premium-histogram");
    host.innerHTML = "";

    const deals = sessions.filter(s => s.outcome === "deal" && s.premium_over_true != null);
    const personaOrder = ["grandma", "casual", "engineer", "mechanic"];
    const rows = personaOrder.map(p => {
      const vals = deals.filter(s => s.buyer_persona_id === p).map(s => s.premium_over_true);
      return { persona: p, vals, n: vals.length,
               median: vals.length ? d3.quantile(vals.slice().sort(d3.ascending), 0.5) : null,
               mean:   vals.length ? d3.mean(vals) : null };
    }).filter(r => r.n > 0);  // hide rows with no data so the chart isn't half empty

    const W = host.clientWidth || 760;
    const rowH = 86;                                 // visual height per persona row
    const overlap = 22;                              // small overlap so ridges read as a single chart
    const innerH = rows.length * (rowH - overlap) + overlap + 18;
    const margin = { top: 16, right: 24, bottom: 42, left: 178 };
    const H = innerH + margin.top + margin.bottom;
    const w = W - margin.left - margin.right;

    const svg = d3.select(host).append("svg")
      .attr("viewBox", `0 0 ${W} ${H}`)
      .attr("preserveAspectRatio", "xMidYMid meet");
    const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

    // X domain: clip to the empirical range but always include zero and a few
    // pp of negative space, so "true value" stays visible even if every deal
    // is positive.
    const allVals = deals.map(s => s.premium_over_true);
    const xMin = Math.min(-0.05, d3.quantile(allVals.slice().sort(d3.ascending), 0.01) ?? -0.05);
    const xMax = Math.max( 0.10, d3.quantile(allVals.slice().sort(d3.ascending), 0.99) ?? 0.10);
    const x = d3.scaleLinear().domain([xMin - 0.02, xMax + 0.04]).range([0, w]);

    // Compute KDE per row, scaled so the peak fills the row height. Gaussian
    // kernel with bandwidth that scales with the row's IQR — large-N rows get
    // tighter curves automatically.
    const sampleXs = d3.range(xMin - 0.02, xMax + 0.04, (xMax - xMin) / 160);
    const rowDensities = rows.map(r => {
      const bw = bandwidth(r.vals);
      const density = sampleXs.map(xv => ({
        x: xv,
        y: d3.mean(r.vals, v => gauss((xv - v) / bw)) / bw || 0,
      }));
      const peak = d3.max(density, d => d.y) || 1;
      return { ...r, density, peak };
    });

    // Per-row baselines.
    rowDensities.forEach((r, i) => {
      const yBaseline = i * (rowH - overlap) + (rowH - 18);
      const yMin = yBaseline - rowH + 18;
      const ridgeY = d3.scaleLinear().domain([0, r.peak]).range([yBaseline, yMin]);
      const color = COLORS[r.persona];

      // baseline tick (faint)
      g.append("line")
        .attr("x1", 0).attr("x2", w)
        .attr("y1", yBaseline).attr("y2", yBaseline)
        .attr("stroke", "var(--rule)").attr("stroke-width", 0.8);

      // ridge fill
      const area = d3.area()
        .x(d => x(d.x))
        .y0(yBaseline)
        .y1(d => ridgeY(d.y))
        .curve(d3.curveBasis);
      g.append("path").datum(r.density)
        .attr("d", area)
        .attr("fill", color).attr("fill-opacity", 0.22);

      // ridge outline
      const line = d3.line()
        .x(d => x(d.x)).y(d => ridgeY(d.y)).curve(d3.curveBasis);
      g.append("path").datum(r.density)
        .attr("d", line).attr("fill", "none")
        .attr("stroke", color).attr("stroke-width", 1.6);

      // median tick within the ridge
      if (r.median != null) {
        g.append("line")
          .attr("x1", x(r.median)).attr("x2", x(r.median))
          .attr("y1", yBaseline).attr("y2", yMin + 6)
          .attr("stroke", color).attr("stroke-width", 1.5)
          .attr("stroke-dasharray", "2 3");
      }

      // row label (left)
      const label = Data.displayLabel("buyer_persona", r.persona);
      g.append("text")
        .attr("x", -16).attr("y", yBaseline - 4)
        .attr("text-anchor", "end")
        .attr("font-family", "var(--serif)").attr("font-size", 13)
        .attr("fill", "var(--ink)").attr("font-weight", 500)
        .text(label);

      // sample-size + median annotation under the label
      const medianStr = r.median == null ? "—"
        : `${r.median >= 0 ? "+" : "−"}${Math.abs(r.median * 100).toFixed(1)}%`;
      g.append("text")
        .attr("x", -16).attr("y", yBaseline + 10)
        .attr("text-anchor", "end")
        .attr("font-family", "var(--mono)").attr("font-size", 10)
        .attr("fill", "var(--ink-3)")
        .text(`n=${r.n} · median ${medianStr}`);
    });

    // Zero-premium reference line spanning all ridges.
    g.append("line").attr("class", "ref-line")
      .attr("x1", x(0)).attr("x2", x(0))
      .attr("y1", 0).attr("y2", innerH - 20);
    g.append("text").attr("class", "ref-label")
      .attr("x", x(0) + 4).attr("y", 10)
      .text("true value (fair)");

    // X axis at bottom.
    const xAxis = d3.axisBottom(x).ticks(7).tickFormat(d => `${(d * 100).toFixed(0)}%`);
    g.append("g").attr("class", "axis")
      .attr("transform", `translate(0,${innerH - 14})`)
      .call(xAxis);
    g.append("text").attr("class", "axis-label")
      .attr("x", w).attr("y", innerH + 14).attr("text-anchor", "end")
      .text("premium over true value (deals only)");

    // Legend simplified — colors match row labels but rows are self-labeled,
    // so the legend is just a small note about what the median ticks mean.
    const legend = document.getElementById("premium-histogram-legend");
    legend.innerHTML = `
      <span style="color:var(--ink-3);font-size:0.78rem;">
        Each row: density of premiums for that buyer persona's closed deals,
        normalized to unit area. Dashed tick = median.
      </span>`;
  }

  // Gaussian kernel + bandwidth helper (Silverman's rule of thumb).
  function gauss(u) { return Math.exp(-0.5 * u * u) / Math.sqrt(2 * Math.PI); }
  function bandwidth(vals) {
    if (vals.length < 2) return 0.04;
    const sd = d3.deviation(vals) || 0.04;
    const iqr = (d3.quantile(vals.slice().sort(d3.ascending), 0.75) -
                 d3.quantile(vals.slice().sort(d3.ascending), 0.25));
    const a = Math.min(sd, (iqr || sd) / 1.34);
    return Math.max(0.012, 0.9 * a * Math.pow(vals.length, -1/5));
  }

  // ---------- Pair matrix (seller × buyer) -----------------------------------

  function renderPairMatrix(sessions) {
    const host = document.getElementById("pair-matrix");
    host.innerHTML = "";

    const grid = Data.aggregateGrid(sessions, "seller_persona", "buyer_persona", "premium_over_true");
    const W = host.clientWidth, cellH = 64, cellW = (W - 220 - 24) / grid.cols.length;
    const margin = { top: 56, right: 12, bottom: 12, left: 220 };
    const w = grid.cols.length * cellW;
    const h = grid.rows.length * cellH;
    const H = h + margin.top + margin.bottom;

    const svg = d3.select(host).append("svg")
      .attr("viewBox", `0 0 ${W} ${H}`)
      .attr("preserveAspectRatio", "xMidYMid meet");
    const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

    const color = premiumColorScale(0.30);

    const tt = ensureTooltip();

    g.selectAll("rect.cell")
      .data(grid.cells)
      .join("rect")
      .attr("class", d => d.value == null ? "heatmap-cell heatmap-cell-empty" : "heatmap-cell")
      .attr("x", d => grid.cols.indexOf(d.col) * cellW)
      .attr("y", d => grid.rows.indexOf(d.row) * cellH)
      .attr("width", cellW)
      .attr("height", cellH)
      .attr("fill", d => d.value == null ? "var(--bg)" : color(d.value))
      .on("mousemove", (e, d) => {
        const rowLbl = Data.displayLabel("seller_persona", d.row);
        const colLbl = Data.displayLabel("buyer_persona", d.col);
        const pct = d.value == null ? "—" : `${(d.value * 100).toFixed(1)}%`;
        tt.html(`<strong>${rowLbl} seller × ${colLbl} buyer</strong>
                 <div class="tt-row"><span>mean premium</span><span>${pct}</span></div>
                 <div class="tt-row"><span>n (deals / total)</span><span>${d.nValid} / ${d.n}</span></div>`)
          .style("opacity", 1)
          .style("left", `${e.pageX + 12}px`)
          .style("top",  `${e.pageY + 12}px`);
      })
      .on("mouseout", () => tt.style("opacity", 0));

    g.selectAll("text.cell-label")
      .data(grid.cells.filter(d => d.value != null))
      .join("text")
      .attr("class", "heatmap-cell-label")
      .attr("x", d => grid.cols.indexOf(d.col) * cellW + cellW / 2)
      .attr("y", d => grid.rows.indexOf(d.row) * cellH + cellH / 2 + 4)
      .attr("text-anchor", "middle")
      .attr("fill", d => Math.abs(d.value) > 0.13 ? "#FAF9F5" : "var(--ink)")
      .text(d => {
        const pct = Math.round(d.value * 100);
        return pct === 0 ? "0%" : `${pct}%`;
      });

    // Row labels
    g.selectAll("text.row")
      .data(grid.rows)
      .join("text")
      .attr("class", "heatmap-axis-label heatmap-axis-label-strong")
      .attr("x", -12).attr("y", (d, i) => i * cellH + cellH / 2 + 4)
      .attr("text-anchor", "end")
      .text(d => Data.displayLabel("seller_persona", d));

    // Column labels
    g.selectAll("text.col")
      .data(grid.cols)
      .join("text")
      .attr("class", "heatmap-axis-label heatmap-axis-label-strong")
      .attr("x", (d, i) => i * cellW + cellW / 2)
      .attr("y", -16).attr("text-anchor", "middle")
      .text(d => Data.displayLabel("buyer_persona", d));

    // Section labels
    g.append("text").attr("class", "axis-label")
      .attr("x", -12).attr("y", -32).attr("text-anchor", "end")
      .text("seller →");
    g.append("text").attr("class", "axis-label")
      .attr("x", w / 2).attr("y", -38).attr("text-anchor", "middle")
      .text("buyer ↓");
  }

  // ---------- Inspection scatter ---------------------------------------------

  function renderInspectionScatter(sessions) {
    const host = document.getElementById("inspection-scatter");
    host.innerHTML = "";
    const deals = sessions.filter(s => s.outcome === "deal" && s.premium_over_true != null);

    const W = host.clientWidth, H = 300;
    const margin = { top: 16, right: 18, bottom: 42, left: 48 };
    const w = W - margin.left - margin.right;
    const h = H - margin.top - margin.bottom;

    const svg = d3.select(host).append("svg")
      .attr("viewBox", `0 0 ${W} ${H}`)
      .attr("preserveAspectRatio", "xMidYMid meet");
    const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

    // x = number of questions asked (jittered slightly), y = premium
    const x = d3.scaleLinear().domain([-0.5, d3.max(deals, d => d.n_questions) + 1]).range([0, w]);
    const y = d3.scaleLinear().domain([-0.18, 0.45]).range([h, 0]);

    g.append("g").attr("class", "grid")
      .call(d3.axisLeft(y).tickSize(-w).tickFormat(""))
      .call(gg => gg.select(".domain").remove())
      .selectAll("text").remove();

    // Zero line.
    g.append("line").attr("class", "ref-line")
      .attr("x1", 0).attr("x2", w)
      .attr("y1", y(0)).attr("y2", y(0));
    g.append("text").attr("class", "ref-label")
      .attr("x", w - 4).attr("y", y(0) - 4).attr("text-anchor", "end")
      .text("true value");

    const tt = ensureTooltip();

    g.selectAll("circle")
      .data(deals)
      .join("circle")
      .attr("cx", d => x(d.n_questions + (Math.random() - 0.5) * 0.6))
      .attr("cy", d => y(d.premium_over_true))
      .attr("r", d => 3 + d.n_inspections * 1.4)
      .attr("fill", d => COLORS[d.buyer_persona_id])
      .attr("fill-opacity", 0.45)
      .attr("stroke", d => COLORS[d.buyer_persona_id])
      .attr("stroke-opacity", 0.8)
      .attr("stroke-width", 0.8)
      .on("mousemove", (e, d) => {
        const buyer = Data.displayLabel("buyer_persona", d.buyer_persona_id);
        const seller = Data.displayLabel("seller_persona", d.seller_persona_id);
        const tac = d.hacking_tactic ? Data.displayLabel("tactic", d.hacking_tactic) : "(no forced tactic)";
        tt.html(`<strong>${buyer} buyer · ${seller} seller</strong>
                 <div class="tt-row"><span>tactic</span><span>${tac}</span></div>
                 <div class="tt-row"><span>questions</span><span>${d.n_questions}</span></div>
                 <div class="tt-row"><span>inspections</span><span>${d.n_inspections}</span></div>
                 <div class="tt-row"><span>premium</span><span>${(d.premium_over_true * 100).toFixed(1)}%</span></div>`)
          .style("opacity", 1)
          .style("left", `${e.pageX + 12}px`).style("top", `${e.pageY + 12}px`);
      })
      .on("mouseout", () => tt.style("opacity", 0));

    const xAxis = d3.axisBottom(x).ticks(8).tickFormat(d3.format("d"));
    g.append("g").attr("class", "axis").attr("transform", `translate(0,${h})`).call(xAxis);
    const yAxis = d3.axisLeft(y).ticks(6).tickFormat(d => `${(d * 100).toFixed(0)}%`);
    g.append("g").attr("class", "axis").call(yAxis);

    g.append("text").attr("class", "axis-label")
      .attr("x", w).attr("y", h + 36).attr("text-anchor", "end")
      .text("questions asked by buyer (circle size = inspections)");
    g.append("text").attr("class", "axis-label")
      .attr("transform", "rotate(-90)")
      .attr("x", 0).attr("y", -36).attr("text-anchor", "end")
      .text("premium over true value");
  }

  // ---------- Shared utilities -----------------------------------------------

  function premiumColorScale(max) {
    return d3.scaleLinear()
      .domain([-max, -max/2, 0, max/2, max])
      .range(["#2F6E6E", "#7BA9A9", "#E7E1D2", "#E0A98F", "#A0432F"])
      .clamp(true);
  }

  function ensureTooltip() {
    let t = d3.select("body").select(".tooltip");
    if (t.empty()) t = d3.select("body").append("div").attr("class", "tooltip");
    return t;
  }

  return { render, premiumColorScale, ensureTooltip };
})();
