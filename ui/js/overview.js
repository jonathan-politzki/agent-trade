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

  // ---------- Premium histogram (overlapped densities) -----------------------

  function renderPremiumHistogram(sessions) {
    const host = document.getElementById("premium-histogram");
    host.innerHTML = "";

    const W = host.clientWidth, H = 320;
    const margin = { top: 16, right: 18, bottom: 42, left: 48 };
    const w = W - margin.left - margin.right;
    const h = H - margin.top - margin.bottom;

    const svg = d3.select(host).append("svg")
      .attr("viewBox", `0 0 ${W} ${H}`)
      .attr("preserveAspectRatio", "xMidYMid meet");
    const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

    const deals = sessions.filter(s => s.outcome === "deal" && s.premium_over_true != null);
    const x = d3.scaleLinear().domain([-0.18, 0.42]).range([0, w]);
    const personas = ["grandma", "casual", "engineer", "mechanic"];

    const bins = d3.bin().domain(x.domain()).thresholds(28);
    const series = personas.map(p => {
      const vals = deals.filter(s => s.buyer_persona_id === p).map(s => s.premium_over_true);
      return { persona: p, values: vals, bins: bins(vals) };
    });

    const maxY = d3.max(series, s => d3.max(s.bins, b => b.length)) || 1;
    const y = d3.scaleLinear().domain([0, maxY * 1.15]).range([h, 0]);

    // Grid
    g.append("g").attr("class", "grid")
      .call(d3.axisLeft(y).tickSize(-w).tickFormat(""))
      .call(g => g.select(".domain").remove())
      .selectAll("text").remove();

    // Zero-premium reference line.
    g.append("line").attr("class", "ref-line")
      .attr("x1", x(0)).attr("x2", x(0))
      .attr("y1", 0).attr("y2", h);
    g.append("text").attr("class", "ref-label")
      .attr("x", x(0) + 4).attr("y", 12)
      .text("true value");

    // Curves (smoothed histograms via stepped areas).
    const area = d3.area()
      .x(b => x((b.x0 + b.x1) / 2))
      .y0(h)
      .y1(b => y(b.length))
      .curve(d3.curveMonotoneX);

    series.forEach(s => {
      const color = COLORS[s.persona];
      g.append("path")
        .datum(s.bins)
        .attr("d", area)
        .attr("fill", color)
        .attr("fill-opacity", 0.18)
        .attr("stroke", color)
        .attr("stroke-width", 1.6);
    });

    // Axes
    const xAxis = d3.axisBottom(x).ticks(7).tickFormat(d => `${(d * 100).toFixed(0)}%`);
    g.append("g").attr("class", "axis").attr("transform", `translate(0,${h})`).call(xAxis);
    const yAxis = d3.axisLeft(y).ticks(5);
    g.append("g").attr("class", "axis").call(yAxis);

    g.append("text").attr("class", "axis-label")
      .attr("x", w).attr("y", h + 36).attr("text-anchor", "end")
      .text("premium over true value");

    g.append("text").attr("class", "axis-label")
      .attr("transform", "rotate(-90)")
      .attr("x", 0).attr("y", -36)
      .attr("text-anchor", "end")
      .text("deals (count)");

    // Legend
    const legend = document.getElementById("premium-histogram-legend");
    legend.innerHTML = personas.map(p => {
      const display = Data.displayLabel("buyer_persona", p);
      return `<span><span class="legend-swatch" style="background:${COLORS[p]}"></span>${display}</span>`;
    }).join("");
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
