// Replay view: transcript player + the "iceberg" (public listing above the
// waterline, private facts below; facts surface when the playhead crosses
// the turn at which they were revealed via inspection, voluntary disclosure,
// or a lie caught).

const Replay = (() => {

  let cachedData = null;
  let state = {
    session: null,
    car: null,
    annotations: {},
    turns: [],
    cursor: 0,           // turn idx currently being shown
    playing: false,
    timer: null,
    speedMs: 900,
    // For the price track:
    priceHistory: [],    // { turn, side, price }
  };

  async function render(data) {
    cachedData = data;
    populateSessionSelect(data.replayable);
    bindControls();
    if (data.replayable.length) {
      await loadSession(data.replayable[0].session_id);
    }
  }

  function populateSessionSelect(replayable) {
    const sel = document.getElementById("replay-session-select");
    sel.innerHTML = "";
    replayable.forEach(s => {
      const seller = Data.displayLabel("seller_persona", s.seller_persona_id);
      const buyer  = Data.displayLabel("buyer_persona", s.buyer_persona_id);
      const car = cachedData.cars[s.car_id];
      const carLbl = `${car.year} ${car.make} ${car.model}`;
      const tac = s.hacking_tactic ? ` · ${Data.displayLabel("tactic", s.hacking_tactic)}` : "";
      const opt = document.createElement("option");
      opt.value = s.session_id;
      opt.textContent = `${carLbl} — ${seller} × ${buyer}${tac}`;
      sel.appendChild(opt);
    });
  }

  function bindControls() {
    document.getElementById("replay-session-select").addEventListener("change", e => {
      loadSession(e.target.value);
    });
    document.getElementById("replay-play").addEventListener("click", togglePlay);
    document.getElementById("replay-prev").addEventListener("click", () => stepBy(-1));
    document.getElementById("replay-next").addEventListener("click", () => stepBy(+1));
    document.getElementById("replay-reset").addEventListener("click", reset);
    document.getElementById("replay-speed").addEventListener("change", e => {
      state.speedMs = +e.target.value;
      if (state.playing) restartTimer();
    });
  }

  async function loadSession(sid) {
    stopTimer();
    const sess = cachedData.replayable.find(s => s.session_id === sid);
    const ann  = cachedData.annotations[sid] || {};
    const car  = cachedData.cars[sess.car_id];
    const turns = await Data.loadTranscript(sess);

    state.session = sess;
    state.car = car;
    state.annotations = ann;
    state.turns = turns;
    state.cursor = -1;
    state.playing = false;
    state.priceHistory = computePriceHistory(turns, sess);

    renderMeta();
    renderIceberg();
    renderTranscript();
    renderPriceTrack();
    stepTo(0);

    // Default: pause until user hits play, but pre-show turn 0.
    document.getElementById("replay-play").textContent = "▶ Play";
  }

  function renderMeta() {
    const s = state.session;
    const car = state.car;
    const seller = Data.displayLabel("seller_persona", s.seller_persona_id);
    const buyer = Data.displayLabel("buyer_persona", s.buyer_persona_id);
    const outcome = ({
      "deal": "deal closed",
      "walk_away_buyer": "buyer walked",
      "walk_away_seller": "seller walked",
      "timeout": "timed out",
    })[s.outcome] || s.outcome;

    const premium = s.premium_over_true != null
      ? ` · premium ${(s.premium_over_true * 100).toFixed(1)}%`
      : "";
    document.getElementById("replay-meta").textContent =
      `${seller} × ${buyer} · ${outcome}${premium} · ${s.n_turns} turns · ${s.n_inspections} inspections`;
  }

  // ---------- Iceberg --------------------------------------------------------

  function renderIceberg() {
    const host = document.getElementById("replay-iceberg");
    host.innerHTML = "";

    const car = state.car;
    const sess = state.session;

    // Public listing (above waterline).
    const listing = document.createElement("div");
    listing.className = "iceberg-listing";
    listing.innerHTML = `
      <div class="listing-make">${car.year} ${car.make} ${car.model}</div>
      <div class="listing-trim">${car.trim} · listed</div>
      <div class="listing-stats">
        <div>
          <div class="listing-stat-label">Odometer</div>
          <div class="listing-stat-value">${car.odometer_miles.toLocaleString()} mi</div>
        </div>
        <div>
          <div class="listing-stat-label">Condition</div>
          <div class="listing-stat-value">${car.exterior_condition}</div>
        </div>
        <div>
          <div class="listing-stat-label">Asking</div>
          <div class="listing-stat-value">$${car.asking_price.toLocaleString()}</div>
        </div>
      </div>
      <p class="listing-pitch">"${car.dealer_pitch}"</p>
    `;
    host.appendChild(listing);

    // Waterline.
    const wl = document.createElement("div");
    wl.className = "waterline-wrap";
    wl.innerHTML = `
      <div class="waterline"></div>
      <div class="waterline-label-left">public · what the buyer sees</div>
      <div class="waterline-label-right">private · seller-only</div>
    `;
    host.appendChild(wl);

    // Private facts (below).
    const factsContainer = document.createElement("div");
    factsContainer.className = "private-facts";
    factsContainer.id = "private-facts-list";
    car.private_facts.forEach((f, i) => {
      const node = document.createElement("div");
      node.className = "fact";
      node.dataset.factIdx = i;
      const sevDots = Array.from({ length: 5 }).map((_, k) =>
        `<span class="sev-dot ${k < f.severity ? "" : "off"}"></span>`).join("");
      node.innerHTML = `
        <span class="fact-area">${f.focus_area}</span>
        <span class="fact-text">${f.summary}
          <span class="fact-severity" title="severity">${sevDots}</span>
        </span>
        <span class="fact-impact">−$${Math.abs(f.price_impact_usd).toLocaleString()}</span>
      `;
      factsContainer.appendChild(node);
    });

    // If there are no private facts, show a friendly note.
    if (!car.private_facts.length) {
      const empty = document.createElement("div");
      empty.style.color = "var(--ink-3)";
      empty.style.fontSize = "0.85rem";
      empty.style.fontStyle = "italic";
      empty.style.padding = "0.6rem 0";
      empty.textContent = "No significant private facts — this car is genuinely clean.";
      factsContainer.appendChild(empty);
    }
    host.appendChild(factsContainer);
  }

  // ---------- Transcript -----------------------------------------------------

  function renderTranscript() {
    const host = document.getElementById("replay-transcript");
    host.innerHTML = "";

    state.turns.forEach((t, i) => {
      const ann = state.annotations[String(i)];

      const div = document.createElement("div");
      div.className = "turn";
      div.dataset.idx = i;
      if (ann?.type === "lie") div.classList.add("lie");
      if (ann?.type === "lie_caught") div.classList.add("lie-caught");
      if (ann?.type === "inspection_reveal") div.classList.add("inspection");
      if (ann?.type === "tactic") {
        div.classList.add("tactic");
        div.dataset.tactic = ann.tactic.replace(/_/g, " ");
      }

      const sideTag = t.speaker === "seller"
        ? '<span class="seller-tag">seller</span>'
        : t.speaker === "buyer"
          ? '<span class="buyer-tag">buyer</span>'
          : '<span>system</span>';

      const tool = t.tool ? `<span class="turn-tool">${t.tool}</span>` : "";
      const price = (t.args?.price != null) ? ` <span class="turn-tool">$${(+t.args.price).toLocaleString()}</span>` : "";

      div.innerHTML = `
        <div class="turn-meta">
          <div>turn ${t.idx}</div>
          <div class="speaker">${sideTag}</div>
        </div>
        <div class="turn-body">${tool}${price}<span class="turn-text">${escapeHtml(t.text || "")}</span></div>
      `;
      div.addEventListener("click", () => stepTo(i));
      host.appendChild(div);

      // For lies, append a small "truth" annotation row right after.
      if (ann?.type === "lie") {
        const truth = document.createElement("div");
        truth.className = "turn lie-truth";
        truth.dataset.idx = i; // matched to same turn so it animates together
        truth.innerHTML = `
          <div class="turn-meta"></div>
          <div class="turn-body">truth: ${escapeHtml(ann.truth)}</div>
        `;
        host.appendChild(truth);
      }
    });
  }

  // ---------- Cursor / playback ----------------------------------------------

  function stepTo(idx) {
    state.cursor = Math.max(0, Math.min(state.turns.length - 1, idx));
    paintCursor();
  }

  function stepBy(n) {
    stepTo(state.cursor + n);
  }

  function paintCursor() {
    const transcript = document.getElementById("replay-transcript");
    const turnsEls = transcript.querySelectorAll(".turn");
    turnsEls.forEach(el => {
      const i = +el.dataset.idx;
      el.classList.toggle("active", i === state.cursor);
      el.classList.toggle("visible", i <= state.cursor);
      el.classList.toggle("future", i > state.cursor);
    });
    // Scroll active into view.
    const active = transcript.querySelector(`.turn.active`);
    if (active) active.scrollIntoView({ behavior: "smooth", block: "center" });

    // Update facts: reveal those whose annotation turn <= cursor.
    updateFactReveal();

    // Update turn indicator.
    document.getElementById("replay-turn-indicator").textContent =
      `turn ${state.cursor} / ${state.turns.length - 1}`;

    // Update price track marker.
    updatePriceTrack();

    // If we hit the end while playing, stop.
    if (state.cursor >= state.turns.length - 1) {
      stopTimer();
      document.getElementById("replay-play").textContent = "↻ Replay";
    }
  }

  function updateFactReveal() {
    const facts = document.querySelectorAll("#private-facts-list .fact");
    const revealed = computeRevealedFacts(state.cursor);
    facts.forEach(f => {
      const i = +f.dataset.factIdx;
      f.classList.remove("revealed", "revealed-inspection", "revealed-lie", "revealed-volunteer");
      const r = revealed[i];
      if (r) {
        f.classList.add("revealed", `revealed-${r}`);
      }
    });
  }

  // For each private fact, decide if revealed by cursor turn, and how.
  // Mechanism priority: lie-caught > inspection > voluntary.
  function computeRevealedFacts(upToTurn) {
    const out = {};
    const ann = state.annotations || {};
    for (const [turnStr, a] of Object.entries(ann)) {
      const t = +turnStr;
      if (t > upToTurn) continue;
      const idxs = Array.isArray(a.fact_idx) ? a.fact_idx : [a.fact_idx];
      if (idxs[0] == null) continue;
      idxs.forEach(idx => {
        if (a.type === "lie_caught") out[idx] = "lie";
        else if (a.type === "inspection_reveal" && !out[idx]) out[idx] = "inspection";
        else if (a.type === "voluntary_disclosure" && !out[idx]) out[idx] = "volunteer";
      });
    }
    return out;
  }

  // ---------- Playback timer -------------------------------------------------

  function togglePlay() {
    if (state.cursor >= state.turns.length - 1) {
      // Replay from start
      stepTo(0);
    }
    state.playing = !state.playing;
    document.getElementById("replay-play").textContent = state.playing ? "❚❚ Pause" : "▶ Play";
    if (state.playing) restartTimer();
    else stopTimer();
  }

  function restartTimer() {
    stopTimer();
    state.timer = setInterval(() => {
      if (state.cursor >= state.turns.length - 1) {
        stopTimer();
        state.playing = false;
        document.getElementById("replay-play").textContent = "↻ Replay";
        return;
      }
      stepTo(state.cursor + 1);
    }, state.speedMs);
  }

  function stopTimer() {
    if (state.timer) { clearInterval(state.timer); state.timer = null; }
  }

  function reset() {
    stopTimer();
    state.playing = false;
    document.getElementById("replay-play").textContent = "▶ Play";
    stepTo(0);
  }

  // ---------- Price track ----------------------------------------------------

  function computePriceHistory(turns, sess) {
    // Track every quoted number through the conversation. The latest seller-side
    // and buyer-side number is what the price marker shows.
    const events = [];
    for (const t of turns) {
      if (t.args?.price != null) {
        events.push({ turn: t.idx, side: t.speaker, price: +t.args.price });
      }
    }
    return events;
  }

  function renderPriceTrack() {
    const host = document.getElementById("replay-price-track");
    host.innerHTML = "";

    const inner = document.createElement("div");
    inner.className = "price-track-inner";
    host.appendChild(inner);

    const W = host.clientWidth || 560;
    const H = 76;
    const margin = { top: 28, right: 16, bottom: 28, left: 16 };
    const w = W - margin.left - margin.right;
    const h = H - margin.top - margin.bottom;

    const svg = d3.select(inner).append("svg")
      .attr("viewBox", `0 0 ${W} ${H}`)
      .attr("preserveAspectRatio", "xMidYMid meet");
    const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

    const car = state.car;
    const prices = [
      car.true_value, car.public_fair_value, car.asking_price,
      ...state.priceHistory.map(e => e.price),
    ];
    const minP = Math.min(...prices) * 0.95;
    const maxP = Math.max(...prices) * 1.05;
    const x = d3.scaleLinear().domain([minP, maxP]).range([0, w]);

    g.append("line")
      .attr("x1", 0).attr("x2", w).attr("y1", h / 2).attr("y2", h / 2)
      .attr("stroke", "var(--rule-strong)").attr("stroke-width", 2);

    // Reference markers.
    const refs = [
      { v: car.true_value, label: "true value", color: "var(--teal-deep)" },
      { v: car.public_fair_value, label: "public fair", color: "var(--gold)" },
      { v: car.asking_price, label: "asking", color: "var(--clay)" },
    ];
    refs.forEach(r => {
      g.append("line")
        .attr("x1", x(r.v)).attr("x2", x(r.v))
        .attr("y1", h / 2 - 10).attr("y2", h / 2 + 10)
        .attr("stroke", r.color).attr("stroke-width", 1.5);
      g.append("text")
        .attr("x", x(r.v)).attr("y", h / 2 - 14)
        .attr("text-anchor", "middle")
        .attr("font-family", "var(--sans)").attr("font-size", 10)
        .attr("fill", r.color)
        .text(r.label);
      g.append("text")
        .attr("x", x(r.v)).attr("y", h / 2 + 22)
        .attr("text-anchor", "middle")
        .attr("font-family", "var(--mono)").attr("font-size", 10)
        .attr("fill", "var(--ink-2)")
        .text(`$${Math.round(r.v).toLocaleString()}`);
    });

    // Live markers for current seller and buyer quoted prices.
    const sellerMarker = g.append("circle")
      .attr("class", "marker-seller")
      .attr("r", 6).attr("cy", h / 2)
      .attr("fill", "var(--clay)").attr("stroke", "var(--bg-elev)").attr("stroke-width", 2)
      .style("opacity", 0);
    const buyerMarker = g.append("circle")
      .attr("class", "marker-buyer")
      .attr("r", 6).attr("cy", h / 2)
      .attr("fill", "var(--teal-deep)").attr("stroke", "var(--bg-elev)").attr("stroke-width", 2)
      .style("opacity", 0);

    state.priceTrackXScale = x;
    state.priceTrackEls = { sellerMarker, buyerMarker };
  }

  function updatePriceTrack() {
    if (!state.priceTrackEls) return;
    const { sellerMarker, buyerMarker } = state.priceTrackEls;
    const x = state.priceTrackXScale;

    let lastSeller = null, lastBuyer = null;
    for (const e of state.priceHistory) {
      if (e.turn > state.cursor) break;
      if (e.side === "seller") lastSeller = e.price;
      else if (e.side === "buyer") lastBuyer = e.price;
    }
    // Default: seller at asking until they counter.
    if (lastSeller == null) lastSeller = state.car.asking_price;

    sellerMarker.transition().duration(400)
      .style("opacity", 1).attr("cx", x(lastSeller));
    if (lastBuyer != null) {
      buyerMarker.transition().duration(400)
        .style("opacity", 1).attr("cx", x(lastBuyer));
    } else {
      buyerMarker.style("opacity", 0);
    }
  }

  function escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  }

  return { render };
})();
