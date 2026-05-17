// Susceptibility heatmap view + tactic bars.

const HeatmapView = (() => {

  let cachedData = null;

  function render(data) {
    cachedData = data;
    bindControls();
    update();
  }

  function bindControls() {
    ["heatmap-rows", "heatmap-cols", "heatmap-metric"].forEach(id => {
      const el = document.getElementById(id);
      el.removeEventListener("change", update);
      el.addEventListener("change", update);
    });
  }

  function update() {
    const rowDim = document.getElementById("heatmap-rows").value;
    const colDim = document.getElementById("heatmap-cols").value;
    const metric = document.getElementById("heatmap-metric").value;
    renderHeatmap(cachedData.sessions, rowDim, colDim, metric);
    renderTacticBars(cachedData.sessions, rowDim, metric);
    updateLede(rowDim, colDim, metric);
  }

  function updateLede(rowDim, colDim, metric) {
    const lede = document.getElementById("heatmap-lede");
    const metricLabel = {
      premium_over_true: "mean premium over true value",
      deal_rate: "deal-close rate",
      walk_rate: "buyer walk-away rate",
      mean_inspections: "mean inspections per session",
    }[metric];
    const rowLabel = dimNoun(rowDim);
    const colLabel = dimNoun(colDim);
    lede.innerHTML = `Each cell is the <strong>${metricLabel}</strong> across all sessions
      in that (${rowLabel}, ${colLabel}) bin. Warmer cells mean the seller extracted
      more rent; cooler cells mean the buyer held the line. Empty cells had no sessions
      meeting the metric's criteria (e.g. premium is only defined on closed deals).`;
  }

  function dimNoun(d) {
    return ({
      buyer_persona: "buyer persona",
      seller_persona: "seller persona",
      buyer_model: "buyer model",
      seller_model: "seller model",
      tactic: "forced tactic",
    })[d];
  }

  function renderHeatmap(sessions, rowDim, colDim, metric) {
    const host = document.getElementById("heatmap-chart");
    host.innerHTML = "";

    const grid = Data.aggregateGrid(sessions, rowDim, colDim, metric);
    // Reserve more room on the right when columns are tactics (long labels rotate
    // and project past the rightmost cell).
    const longCols = colDim === "tactic";
    const rightMargin = longCols ? 90 : 12;
    const cellW = Math.max(54, Math.min(110, (host.clientWidth - 200 - rightMargin) / Math.max(1, grid.cols.length)));
    const cellH = 42;

    const W = host.clientWidth;
    const margin = { top: longCols ? 130 : 100, right: rightMargin, bottom: 16, left: 200 };
    const w = cellW * grid.cols.length;
    const h = cellH * grid.rows.length;
    const H = h + margin.top + margin.bottom;

    const svg = d3.select(host).append("svg")
      .attr("viewBox", `0 0 ${W} ${H}`)
      .attr("preserveAspectRatio", "xMidYMid meet");
    const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

    // Color scale: diverging for premium, sequential clay for others.
    let color;
    if (metric === "premium_over_true") {
      const max = d3.max(grid.cells, c => c.value == null ? 0 : Math.abs(c.value)) || 0.2;
      color = d3.scaleLinear()
        .domain([-max, -max/2, 0, max/2, max])
        .range(["#2F6E6E", "#7BA9A9", "#E7E1D2", "#E0A98F", "#A0432F"]).clamp(true);
    } else if (metric === "deal_rate") {
      color = d3.scaleLinear().domain([0, 0.5, 1]).range(["#FAF9F5", "#E0A98F", "#A0432F"]).clamp(true);
    } else if (metric === "walk_rate") {
      color = d3.scaleLinear().domain([0, 0.3, 0.7]).range(["#FAF9F5", "#E0A98F", "#A0432F"]).clamp(true);
    } else {
      const max = d3.max(grid.cells, c => c.value == null ? 0 : c.value) || 2;
      color = d3.scaleLinear().domain([0, max]).range(["#FAF9F5", "#2F6E6E"]).clamp(true);
    }

    const tt = Overview.ensureTooltip();

    g.selectAll("rect.cell")
      .data(grid.cells)
      .join("rect")
      .attr("class", d => d.value == null ? "heatmap-cell heatmap-cell-empty" : "heatmap-cell")
      .attr("x", d => grid.cols.indexOf(d.col) * cellW)
      .attr("y", d => grid.rows.indexOf(d.row) * cellH)
      .attr("width", cellW).attr("height", cellH)
      .attr("fill", d => d.value == null ? "var(--bg)" : color(d.value))
      .on("mousemove", (e, d) => {
        const rowLbl = Data.displayLabel(rowDim, d.row);
        const colLbl = Data.displayLabel(colDim, d.col);
        const formatted = formatMetric(d.value, metric);
        tt.html(`<strong>${rowLbl} × ${colLbl}</strong>
                 <div class="tt-row"><span>${dimNoun(rowDim)}</span><span>${rowLbl}</span></div>
                 <div class="tt-row"><span>${dimNoun(colDim)}</span><span>${colLbl}</span></div>
                 <div class="tt-row"><span>value</span><span>${formatted}</span></div>
                 <div class="tt-row"><span>n (valid / total)</span><span>${d.nValid} / ${d.n}</span></div>`)
          .style("opacity", 1)
          .style("left", `${e.pageX + 12}px`).style("top", `${e.pageY + 12}px`);
      })
      .on("mouseout", () => tt.style("opacity", 0));

    g.selectAll("text.cell-label")
      .data(grid.cells.filter(d => d.value != null))
      .join("text")
      .attr("class", "heatmap-cell-label")
      .attr("x", d => grid.cols.indexOf(d.col) * cellW + cellW / 2)
      .attr("y", d => grid.rows.indexOf(d.row) * cellH + cellH / 2 + 4)
      .attr("text-anchor", "middle")
      .attr("fill", d => labelColor(d.value, metric, color))
      .text(d => formatMetric(d.value, metric));

    // Row labels
    g.selectAll("text.row")
      .data(grid.rows)
      .join("text")
      .attr("class", "heatmap-axis-label heatmap-axis-label-strong")
      .attr("x", -12).attr("y", (d, i) => i * cellH + cellH / 2 + 4)
      .attr("text-anchor", "end")
      .text(d => Data.displayLabel(rowDim, d));

    // Column labels (rotated for tactic dim because they're long)
    g.selectAll("text.col")
      .data(grid.cols)
      .join("text")
      .attr("class", "heatmap-axis-label heatmap-axis-label-strong")
      .attr("transform", (d, i) => {
        const x = i * cellW + cellW / 2;
        const y = -10;
        return longCols ? `translate(${x},${y}) rotate(-32)` : `translate(${x},${y})`;
      })
      .attr("text-anchor", longCols ? "start" : "middle")
      .text(d => Data.displayLabel(colDim, d));

    // Legend
    drawLegend(metric, color);
  }

  function formatMetric(v, metric) {
    if (v == null) return "—";
    if (metric === "premium_over_true") {
      const pct = Math.round(v * 100);
      return pct === 0 ? "0%" : `${pct}%`;
    }
    if (metric === "deal_rate" || metric === "walk_rate") return `${(v * 100).toFixed(0)}%`;
    if (metric === "mean_inspections") return v.toFixed(2);
    return v.toFixed(2);
  }

  function labelColor(v, metric, color) {
    // Pick a label color that contrasts with the fill.
    if (v == null) return "var(--ink)";
    const c = d3.color(color(v));
    if (!c) return "var(--ink)";
    const lum = (c.r * 0.299 + c.g * 0.587 + c.b * 0.114);
    return lum < 130 ? "#FAF9F5" : "var(--ink)";
  }

  function drawLegend(metric, color) {
    const host = document.getElementById("heatmap-legend");
    host.innerHTML = "";

    const W = 280, H = 32;
    const svg = d3.select(host).append("svg").attr("width", W).attr("height", H);
    const grad = svg.append("defs").append("linearGradient")
      .attr("id", "legend-grad").attr("x1", "0%").attr("x2", "100%");

    let stops;
    if (metric === "premium_over_true") {
      stops = [
        { o: "0%",   c: "#2F6E6E", l: "−" },
        { o: "50%",  c: "#E7E1D2", l: "0" },
        { o: "100%", c: "#A0432F", l: "+" },
      ];
    } else if (metric === "mean_inspections") {
      stops = [{ o: "0%", c: "#FAF9F5", l: "0" }, { o: "100%", c: "#2F6E6E", l: "high" }];
    } else {
      stops = [{ o: "0%", c: "#FAF9F5", l: "0%" }, { o: "100%", c: "#A0432F", l: "high" }];
    }
    stops.forEach(s => grad.append("stop").attr("offset", s.o).attr("stop-color", s.c));

    svg.append("rect").attr("x", 6).attr("y", 4).attr("width", W - 60).attr("height", 14)
      .attr("fill", "url(#legend-grad)").attr("stroke", "var(--rule-strong)");

    svg.append("text").attr("x", 6).attr("y", 30)
      .attr("font-family", "var(--sans)").attr("font-size", 10).attr("fill", "var(--ink-3)")
      .text(stops[0].l);
    svg.append("text").attr("x", W - 60).attr("y", 30).attr("text-anchor", "end")
      .attr("font-family", "var(--sans)").attr("font-size", 10).attr("fill", "var(--ink-3)")
      .text(stops[stops.length - 1].l);

    const note = document.createElement("span");
    note.style.marginLeft = "1rem";
    note.style.color = "var(--ink-3)";
    note.style.fontSize = "0.78rem";
    note.textContent = ({
      premium_over_true: "cool = buyer surplus · warm = seller rent",
      deal_rate: "% of sessions in cell ending in a deal",
      walk_rate: "% of sessions where buyer walked",
      mean_inspections: "mean inspections per session in cell",
    })[metric];
    host.appendChild(note);
  }

  // ---------- Tactic profile bars --------------------------------------------

  function renderTacticBars(sessions, rowDim, metric) {
    const host = document.getElementById("tactic-bars");
    host.innerHTML = "";

    // For each row, compute: mean(metric | tactic = T) - mean(metric | tactic = none).
    const rows = Data.uniqueKeys(sessions, rowDim);
    const tactics = Data.uniqueKeys(sessions, "tactic"); // includes "none"
    const tacticsNoNone = tactics.filter(t => t !== "none");

    // Map: row -> tactic -> mean
    const cellMean = {};
    rows.forEach(r => { cellMean[r] = {}; });
    for (const t of tactics) {
      for (const r of rows) {
        const subset = sessions.filter(s =>
          Data.keyFor(s, rowDim) === r && (s.hacking_tactic || "none") === t);
        const vals = subset.map(s => {
          if (metric === "premium_over_true") return s.outcome === "deal" ? s.premium_over_true : null;
          if (metric === "deal_rate") return s.outcome === "deal" ? 1 : 0;
          if (metric === "walk_rate") return s.outcome === "walk_away_buyer" ? 1 : 0;
          if (metric === "mean_inspections") return s.n_inspections ?? 0;
          return null;
        }).filter(v => v != null);
        cellMean[r][t] = vals.length ? d3.mean(vals) : null;
      }
    }

    // Build long-format records for plotting: {row, tactic, lift}.
    const records = [];
    for (const r of rows) {
      const base = cellMean[r]["none"];
      for (const t of tacticsNoNone) {
        const v = cellMean[r][t];
        if (v == null || base == null) continue;
        records.push({ row: r, tactic: t, lift: v - base });
      }
    }

    // If the sweep didn't toggle any tactics, show a friendly empty-state
    // rather than an axis-only chart.
    if (records.length === 0) {
      host.innerHTML = "";
      const empty = document.createElement("div");
      empty.style.cssText = "padding: 2.5rem 1.25rem; color: var(--ink-3); font-family: var(--serif); font-style: italic; text-align: center;";
      empty.innerHTML = "No forced-tactic sessions in this dataset.<br><span style=\"font-size:0.85rem;\">Run a sweep that toggles <code>hacking_tactic</code> to populate this chart.</span>";
      host.appendChild(empty);
      return;
    }

    // Layout: grouped bars by tactic, one cluster per tactic, one bar per row.
    const W = host.clientWidth, H = 320;
    const margin = { top: 18, right: 24, bottom: 80, left: 56 };
    const w = W - margin.left - margin.right;
    const h = H - margin.top - margin.bottom;

    const svg = d3.select(host).append("svg")
      .attr("viewBox", `0 0 ${W} ${H}`)
      .attr("preserveAspectRatio", "xMidYMid meet");
    const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

    const x0 = d3.scaleBand().domain(tacticsNoNone).range([0, w]).paddingInner(0.18);
    const x1 = d3.scaleBand().domain(rows).range([0, x0.bandwidth()]).padding(0.08);

    const maxLift = d3.max(records, d => Math.abs(d.lift)) || 0.05;
    const y = d3.scaleLinear().domain([-maxLift, maxLift]).range([h, 0]).nice();

    g.append("g").attr("class", "grid")
      .call(d3.axisLeft(y).tickSize(-w).tickFormat(""))
      .call(gg => gg.select(".domain").remove())
      .selectAll("text").remove();

    // Zero line.
    g.append("line").attr("class", "ref-line")
      .attr("x1", 0).attr("x2", w)
      .attr("y1", y(0)).attr("y2", y(0));

    const rowColors = {
      // Buyer personas (knowledge-axis)
      grandma:  "#A0432F",
      casual:   "#CC785C",
      engineer: "#7A8B5A",
      mechanic: "#2F6E6E",
      // Seller personas (deception-axis)
      honest:    "#2F6E6E",
      pragmatic: "#7A8B5A",
      pushy:     "#CC785C",
      slimy:     "#A0432F",
      // Anthropic — clay family
      "opus-4-7":  "#A0432F",
      "opus-4-5":  "#CC785C",
      "opus":      "#A0432F",
      "haiku-4-5": "#E0A98F",
      "haiku":     "#E0A98F",
      "sonnet-4-6":"#CC785C",
      "sonnet":    "#CC785C",
      // Google — slate-blue family. Lighter shade distinguishes flash-lite from flash.
      "gemini-pro":        "#3B5B7A",
      "gemini-flash":      "#6B8AA8",
      "gemini-flash-lite": "#A5BACC",
      "gemini":            "#6B8AA8",
      // OpenAI — teal-green family
      "gpt-4o":      "#2F6E6E",
      "gpt-4o-mini": "#7A8B5A",
      "gpt-4":       "#2F6E6E",
      "gpt":         "#7A8B5A",
    };

    const tt = Overview.ensureTooltip();

    g.selectAll("g.cluster")
      .data(tacticsNoNone)
      .join("g")
      .attr("class", "cluster")
      .attr("transform", t => `translate(${x0(t)},0)`)
      .selectAll("rect")
      .data(t => records.filter(r => r.tactic === t))
      .join("rect")
      .attr("x", d => x1(d.row))
      .attr("y", d => d.lift > 0 ? y(d.lift) : y(0))
      .attr("width", x1.bandwidth())
      .attr("height", d => Math.abs(y(d.lift) - y(0)))
      .attr("fill", d => rowColors[d.row] || "var(--clay)")
      .attr("fill-opacity", 0.92)
      .on("mousemove", (e, d) => {
        const tac = Data.displayLabel("tactic", d.tactic);
        const rowLbl = Data.displayLabel(rowDim, d.row);
        const fmt = metric === "mean_inspections" ? `${d.lift.toFixed(2)}` : `${(d.lift * 100).toFixed(1)} pp`;
        tt.html(`<strong>${tac} on ${rowLbl}</strong>
                 <div class="tt-row"><span>lift vs no-tactic baseline</span><span>${fmt}</span></div>`)
          .style("opacity", 1)
          .style("left", `${e.pageX + 12}px`).style("top", `${e.pageY + 12}px`);
      })
      .on("mouseout", () => tt.style("opacity", 0));

    // X axis: rotated tactic labels.
    const xAxis = d3.axisBottom(x0).tickFormat(d => Data.displayLabel("tactic", d));
    g.append("g").attr("class", "axis").attr("transform", `translate(0,${h})`)
      .call(xAxis)
      .selectAll("text")
      .attr("transform", "rotate(-30)")
      .attr("text-anchor", "end")
      .attr("dx", "-0.5em").attr("dy", "0.3em");

    const yAxis = d3.axisLeft(y).ticks(6).tickFormat(d =>
      metric === "mean_inspections" ? d.toFixed(1) : `${(d * 100).toFixed(0)}%`);
    g.append("g").attr("class", "axis").call(yAxis);

    g.append("text").attr("class", "axis-label")
      .attr("transform", "rotate(-90)")
      .attr("x", 0).attr("y", -42).attr("text-anchor", "end")
      .text(`Δ from no-tactic baseline (${metric.replace(/_/g, " ")})`);

    // Inline mini-legend for row colors.
    const legend = g.append("g").attr("transform", `translate(0,${-4})`);
    let xOff = 0;
    rows.forEach(r => {
      const grp = legend.append("g").attr("transform", `translate(${xOff},0)`);
      grp.append("rect").attr("width", 10).attr("height", 10)
        .attr("y", -10).attr("fill", rowColors[r] || "var(--clay)");
      const lbl = Data.displayLabel(rowDim, r);
      grp.append("text")
        .attr("x", 14).attr("y", -1)
        .attr("font-family", "var(--sans)").attr("font-size", 11).attr("fill", "var(--ink-2)")
        .text(lbl);
      xOff += 14 + lbl.length * 7 + 14;
    });
  }

  return { render };
})();
