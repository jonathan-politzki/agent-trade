// Primer view — animated marketplace + persona cards.
//
// Buyers (circles) and sellers (squares) wander a 2D plane. When a buyer and
// seller come within radius they pause, run a brief "trade" animation, and a
// deal outcome is sampled from the empirical premium distribution observed in
// the real sweep. Running counters update in the side panel.
//
// The animation is intentionally slow and academic — no flashy easing, no
// particle effects. The point is to convey "this is a market with stakes,"
// not to entertain.

const Primer = (() => {

  let svgState = null;     // running simulation state (one per page lifetime)
  let cachedData = null;

  // Persona colors (same palette as the rest of the UI).
  const BUYER_COLOR = {
    grandma:  "#A0432F",
    casual:   "#CC785C",
    engineer: "#7A8B5A",
    mechanic: "#2F6E6E",
  };
  const SELLER_COLOR = {
    honest:    "#2F6E6E",
    pragmatic: "#7A8B5A",
    pushy:     "#CC785C",
    slimy:     "#A0432F",
  };

  function render(data) {
    cachedData = data;
    renderPersonaCards(data);
    initMarket(data);
  }

  // ---------- Persona cards ----------

  function renderPersonaCards(data) {
    const host = document.getElementById("primer-persona-grid");
    if (!host) return;
    host.innerHTML = "";

    const stats = (p, side) => {
      const rows = side === "buyer"
        ? [
            ["knowledge",   p.knowledge_level],
            ["skepticism",  p.skepticism],
            ["inspects",    p.inspection_propensity],
          ]
        : [
            ["honesty",     1 - (p.deceptiveness ?? 0)],
            ["pressure",    p.pressure ?? 0],
            ["patience",    p.patience ?? 0.5],
          ];
      return rows.map(([label, v]) => `
        <div class="persona-stat-row">
          <span class="persona-stat-label">${label}</span>
          <div class="persona-stat-bar"><div class="persona-stat-bar-fill" style="width:${Math.round((v ?? 0) * 100)}%"></div></div>
          <span class="persona-stat-value">${(v ?? 0).toFixed(2)}</span>
        </div>
      `).join("");
    };

    const buyers = ["grandma", "casual", "engineer", "mechanic"];
    const sellers = ["honest", "pragmatic", "pushy", "slimy"];

    const buyerCards = buyers
      .filter(id => data.personas.buyers[id])
      .map(id => {
        const p = data.personas.buyers[id];
        return `
          <div class="persona-card">
            <div class="persona-card-side">Buyer</div>
            <div class="persona-card-name">${p.display_name}
              <span class="persona-card-tag" style="background:${BUYER_COLOR[id]}"></span>
            </div>
            <div class="persona-card-stats">${stats(p, "buyer")}</div>
          </div>
        `;
      }).join("");

    const sellerCards = sellers
      .filter(id => data.personas.sellers[id])
      .map(id => {
        const p = data.personas.sellers[id];
        return `
          <div class="persona-card">
            <div class="persona-card-side">Seller</div>
            <div class="persona-card-name">${p.display_name}
              <span class="persona-card-tag persona-card-tag-square" style="background:${SELLER_COLOR[id]}"></span>
            </div>
            <div class="persona-card-stats">${stats(p, "seller")}</div>
          </div>
        `;
      }).join("");

    host.innerHTML = buyerCards + sellerCards;
  }

  // ---------- Animated market ----------

  function initMarket(data) {
    // Build empirical premium distribution per (buyer, seller) persona pair.
    // For pairs with no data, fall back to the dataset-wide mean. We sample
    // from this when a "deal" closes.
    const premiumDist = buildPremiumDist(data);

    const host = document.getElementById("market-canvas");
    if (!host) return;
    host.innerHTML = "";

    // Stop any previous animation (in case render is called twice).
    if (svgState?.timer) svgState.timer.stop();

    const W = host.clientWidth || 700;
    const H = 420;
    const svg = d3.select(host).append("svg")
      .attr("viewBox", `0 0 ${W} ${H}`)
      .attr("preserveAspectRatio", "xMidYMid meet");

    // Subtle grid backdrop — gives sense of place without being noisy.
    const bg = svg.append("g");
    for (let x = 60; x < W; x += 60) {
      bg.append("line").attr("x1", x).attr("x2", x).attr("y1", 0).attr("y2", H)
        .attr("stroke", "var(--rule)").attr("stroke-dasharray", "2 4").attr("stroke-width", 0.5);
    }
    for (let y = 60; y < H; y += 60) {
      bg.append("line").attr("x1", 0).attr("x2", W).attr("y1", y).attr("y2", y)
        .attr("stroke", "var(--rule)").attr("stroke-dasharray", "2 4").attr("stroke-width", 0.5);
    }

    // Floating layers (back→front).
    const tradesLayer = svg.append("g").attr("class", "trades-layer");
    const agentsLayer = svg.append("g").attr("class", "agents-layer");
    const bubbleLayer = svg.append("g").attr("class", "bubbles-layer");

    // Spawn agents. Distribution chosen to roughly match the experiment matrix.
    const buyerPersonas = ["grandma", "casual", "engineer", "mechanic"];
    const sellerPersonas = ["honest", "pragmatic", "pushy", "slimy"];

    const agents = [];
    // 10 buyers: more casual/engineer because those are the experimental cells.
    const buyerSpawn = ["grandma", "casual", "casual", "casual", "engineer",
                        "engineer", "engineer", "mechanic", "casual", "engineer"];
    for (const persona of buyerSpawn) {
      agents.push(makeAgent("buyer", persona, W, H));
    }
    // 6 sellers, slimy-skewed to match e3 (slimy is the studied seller).
    const sellerSpawn = ["honest", "pragmatic", "pushy", "slimy", "slimy", "slimy"];
    for (const persona of sellerSpawn) {
      agents.push(makeAgent("seller", persona, W, H));
    }

    // Render initial agent marks.
    const node = agentsLayer.selectAll("g.agent")
      .data(agents, d => d.id)
      .join("g")
      .attr("class", "agent")
      .attr("transform", d => `translate(${d.x},${d.y})`);
    node.each(function(d) {
      const g = d3.select(this);
      if (d.side === "buyer") {
        g.append("circle").attr("r", 8).attr("fill", BUYER_COLOR[d.persona])
          .attr("fill-opacity", 0.92)
          .attr("stroke", "var(--bg-elev-2)").attr("stroke-width", 1.5);
      } else {
        g.append("rect").attr("x", -8).attr("y", -8).attr("width", 16).attr("height", 16)
          .attr("rx", 2)
          .attr("fill", SELLER_COLOR[d.persona]).attr("fill-opacity", 0.92)
          .attr("stroke", "var(--bg-elev-2)").attr("stroke-width", 1.5);
      }
    });

    // Stats counters.
    const stats = { deals: 0, walks: 0, premiumSum: 0, premiumN: 0 };
    const updateStatsDom = () => {
      const dealsEl = document.getElementById("market-stat-deals");
      const premEl  = document.getElementById("market-stat-premium");
      const walksEl = document.getElementById("market-stat-walks");
      if (dealsEl) dealsEl.textContent = stats.deals.toString();
      if (walksEl) walksEl.textContent = stats.walks.toString();
      if (premEl)  {
        const mean = stats.premiumN ? stats.premiumSum / stats.premiumN : null;
        premEl.textContent = mean == null ? "—" : `${(mean * 100).toFixed(1)}%`;
      }
    };
    updateStatsDom();

    const PAIR_RADIUS = 32;          // px — when buyer and seller are this close, they pair up
    const TRADE_DURATION = 2600;     // ms — how long a "trade" sequence lasts
    const SPEED = 0.25;              // px per ms — walking pace

    // Trade lifecycle: detect pair → freeze both → bubble in → bubble out → walk away.
    const tradingPairs = new Map(); // id-pair-key → { buyer, seller, t0, finalPremium, outcome }

    function tryPair(a, b, now) {
      // Pair a buyer with a seller (not buyer-buyer or seller-seller).
      if (a.side === b.side) return false;
      const buyer = a.side === "buyer" ? a : b;
      const seller = a.side === "seller" ? a : b;
      if (buyer.locked || seller.locked) return false;
      const dx = buyer.x - seller.x, dy = buyer.y - seller.y;
      if (dx * dx + dy * dy > PAIR_RADIUS * PAIR_RADIUS) return false;

      // Sample an outcome from the empirical distribution.
      const samples = premiumDist[`${buyer.persona}|${seller.persona}`]
        || premiumDist["__overall__"]
        || [{ outcome: "deal", premium: 0.1 }];
      const sampled = samples[Math.floor(Math.random() * samples.length)];

      buyer.locked = true;
      seller.locked = true;
      const key = `${buyer.id}|${seller.id}|${now}`;
      tradingPairs.set(key, { buyer, seller, t0: now, sample: sampled, key });

      // Speech-bubble dot above each agent — different glyph by outcome.
      drawBubble(buyer, "buyer", sampled.outcome);
      drawBubble(seller, "seller", sampled.outcome);

      // Connecting "deal line".
      tradesLayer.append("line")
        .attr("class", "deal-line")
        .attr("data-key", key)
        .attr("x1", buyer.x).attr("y1", buyer.y)
        .attr("x2", seller.x).attr("y2", seller.y)
        .attr("stroke", outcomeColor(sampled.outcome))
        .attr("stroke-opacity", 0)
        .attr("stroke-width", 1.6)
        .transition().duration(420)
        .attr("stroke-opacity", 0.45);

      return true;
    }

    function drawBubble(agent, side, outcome) {
      const y = agent.y - 18;
      const glyph = bubbleGlyph(outcome);
      const color = outcomeColor(outcome);
      const grp = bubbleLayer.append("g")
        .attr("class", "bubble")
        .attr("data-agent", agent.id)
        .attr("transform", `translate(${agent.x},${y})`)
        .style("opacity", 0);
      grp.append("rect")
        .attr("x", -10).attr("y", -10)
        .attr("width", 20).attr("height", 16).attr("rx", 3)
        .attr("fill", "var(--bg-elev-2)").attr("stroke", color).attr("stroke-width", 1);
      grp.append("text")
        .attr("text-anchor", "middle").attr("y", 2)
        .attr("font-family", "var(--mono)").attr("font-size", 9)
        .attr("fill", color).attr("font-weight", 600)
        .text(glyph);
      grp.transition().duration(220).style("opacity", 1);
      agent._bubble = grp;
    }

    function completeTrade(pair, now) {
      const { buyer, seller, sample, key } = pair;
      // Drop a "deal record" at the center of the pair so the user sees a trail
      // of completed transactions accumulating.
      const cx = (buyer.x + seller.x) / 2;
      const cy = (buyer.y + seller.y) / 2;
      const color = outcomeColor(sample.outcome);
      const label = formatTrade(sample);
      const rec = tradesLayer.append("g")
        .attr("class", "trade-record")
        .attr("transform", `translate(${cx},${cy})`);
      rec.append("circle").attr("r", 3).attr("fill", color).attr("opacity", 0.85);
      rec.append("text")
        .attr("x", 6).attr("y", 3)
        .attr("font-family", "var(--mono)").attr("font-size", 9)
        .attr("fill", color).attr("opacity", 0.95)
        .text(label);
      rec.transition().delay(2500).duration(2400)
        .style("opacity", 0).on("end", () => rec.remove());

      // Update stats.
      if (sample.outcome === "deal") {
        stats.deals += 1;
        stats.premiumSum += sample.premium;
        stats.premiumN += 1;
      } else if (sample.outcome === "walk") {
        stats.walks += 1;
      }
      updateStatsDom();

      // Clean up bubbles + deal line.
      buyer._bubble?.transition().duration(220).style("opacity", 0).on("end", function() { d3.select(this).remove(); });
      seller._bubble?.transition().duration(220).style("opacity", 0).on("end", function() { d3.select(this).remove(); });
      buyer._bubble = null; seller._bubble = null;

      tradesLayer.selectAll(`line.deal-line[data-key="${key}"]`)
        .transition().duration(420).attr("stroke-opacity", 0).remove();

      // Send them on new headings.
      buyer.locked = false; seller.locked = false;
      reorient(buyer); reorient(seller);
      tradingPairs.delete(key);
    }

    function reorient(a) {
      const ang = Math.random() * Math.PI * 2;
      a.vx = Math.cos(ang) * SPEED;
      a.vy = Math.sin(ang) * SPEED;
    }

    let lastT = null;
    const timer = d3.timer((elapsed) => {
      const now = elapsed;
      const dt = lastT == null ? 16 : (now - lastT);
      lastT = now;

      // Move free agents.
      for (const a of agents) {
        if (a.locked) continue;
        a.x += a.vx * dt;
        a.y += a.vy * dt;
        // Soft wall bounce — keep them off the very edge so labels don't clip.
        if (a.x < 16) { a.x = 16; a.vx = Math.abs(a.vx); }
        if (a.x > W - 16) { a.x = W - 16; a.vx = -Math.abs(a.vx); }
        if (a.y < 16) { a.y = 16; a.vy = Math.abs(a.vy); }
        if (a.y > H - 16) { a.y = H - 16; a.vy = -Math.abs(a.vy); }
        // Mild random perturbation — wandering, not lockstep.
        if (Math.random() < 0.005) reorient(a);
      }

      // Detect pairs.
      for (let i = 0; i < agents.length; i++) {
        for (let j = i + 1; j < agents.length; j++) {
          tryPair(agents[i], agents[j], now);
        }
      }

      // Update trade lifecycles.
      for (const pair of tradingPairs.values()) {
        if (now - pair.t0 > TRADE_DURATION) {
          completeTrade(pair, now);
        }
      }

      // Re-render positions.
      agentsLayer.selectAll("g.agent")
        .attr("transform", d => `translate(${d.x},${d.y})`);
      // Bubbles follow their agents.
      bubbleLayer.selectAll("g.bubble").each(function() {
        const id = this.getAttribute("data-agent");
        const a = agents.find(x => x.id === id);
        if (a) this.setAttribute("transform", `translate(${a.x},${a.y - 18})`);
      });
      // Deal lines follow.
      tradesLayer.selectAll("line.deal-line").each(function() {
        const key = this.getAttribute("data-key");
        const pair = tradingPairs.get(key);
        if (!pair) return;
        this.setAttribute("x1", pair.buyer.x); this.setAttribute("y1", pair.buyer.y);
        this.setAttribute("x2", pair.seller.x); this.setAttribute("y2", pair.seller.y);
      });
    });

    svgState = { timer };
  }

  function makeAgent(side, persona, W, H) {
    const ang = Math.random() * Math.PI * 2;
    const speed = 0.25;
    return {
      id: `${side}_${persona}_${Math.random().toString(36).slice(2, 8)}`,
      side, persona,
      x: 30 + Math.random() * (W - 60),
      y: 30 + Math.random() * (H - 60),
      vx: Math.cos(ang) * speed,
      vy: Math.sin(ang) * speed,
      locked: false,
    };
  }

  function outcomeColor(outcome) {
    return outcome === "deal" ? "#A0432F"
         : outcome === "walk" ? "#2F6E6E"
         : "#8A8480";
  }
  function bubbleGlyph(outcome) {
    return outcome === "deal" ? "$" : outcome === "walk" ? "✕" : "…";
  }
  function formatTrade(sample) {
    if (sample.outcome === "deal") {
      const sign = sample.premium >= 0 ? "+" : "−";
      return `${sign}${Math.abs(sample.premium * 100).toFixed(0)}%`;
    }
    if (sample.outcome === "walk") return "walk";
    return "timeout";
  }

  function buildPremiumDist(data) {
    const out = { __overall__: [] };
    for (const s of data.sessions) {
      const key = `${s.buyer_persona_id}|${s.seller_persona_id}`;
      if (!out[key]) out[key] = [];
      let entry;
      if (s.outcome === "deal" && s.premium_over_true != null) {
        entry = { outcome: "deal", premium: s.premium_over_true };
      } else if (s.outcome === "walk_away_buyer" || s.outcome === "walk_away_seller") {
        entry = { outcome: "walk" };
      } else {
        entry = { outcome: "timeout" };
      }
      out[key].push(entry);
      out.__overall__.push(entry);
    }
    return out;
  }

  function stop() {
    if (svgState?.timer) svgState.timer.stop();
    svgState = null;
  }

  return { render, stop };
})();
