// Data loader. Centralizes fetches; exposes a single async init that returns
// the shapes the views consume. Drop the analysis agent's real output into
// ui/data/ and nothing else changes.

const Data = (() => {
  let state = null;

  async function init() {
    if (state) return state;
    const [sessions, annotations, cars, personas, tactics] = await Promise.all([
      fetch("data/sessions.json").then(r => r.json()),
      fetch("data/session_annotations.json").then(r => r.json()),
      fetch("data/cars.json").then(r => r.json()),
      fetch("data/personas.json").then(r => r.json()),
      fetch("data/tactics.json").then(r => r.json()),
    ]);

    const carsById = Object.fromEntries(cars.map(c => [c.car_id, c]));
    const tacticsById = tactics;

    // Sessions with annotations (only handcrafted ones have any).
    const replayable = sessions.filter(s => annotations[s.session_id]);

    state = {
      sessions,
      annotations,
      cars: carsById,
      personas,
      tactics: tacticsById,
      replayable,
    };
    return state;
  }

  async function loadTranscript(session) {
    const text = await fetch(`data/${session.transcript_path}`).then(r => r.text());
    return text
      .split("\n")
      .filter(Boolean)
      .map(line => JSON.parse(line));
  }

  // --- Aggregation helpers (used by overview + heatmap) -------------------

  function deals(sessions) { return sessions.filter(s => s.outcome === "deal"); }

  function mean(arr) { return arr.length ? arr.reduce((a,b) => a + b, 0) / arr.length : null; }

  // Bin sessions by (rowKey, colKey) and compute the metric over closed deals.
  function aggregateGrid(sessions, rowKey, colKey, metric) {
    const buckets = new Map(); // "row|col" -> array of values
    const counts  = new Map(); // "row|col" -> n total
    for (const s of sessions) {
      const r = keyFor(s, rowKey);
      const c = keyFor(s, colKey);
      const k = `${r}||${c}`;
      if (!buckets.has(k)) buckets.set(k, []);
      if (!counts.has(k))  counts.set(k, 0);
      counts.set(k, counts.get(k) + 1);

      const v = metricValue(s, metric);
      if (v != null) buckets.get(k).push(v);
    }
    const rows = uniqueKeys(sessions, rowKey);
    const cols = uniqueKeys(sessions, colKey);

    const cells = [];
    for (const r of rows) {
      for (const c of cols) {
        const k = `${r}||${c}`;
        const vals = buckets.get(k) || [];
        cells.push({
          row: r, col: c,
          value: vals.length ? mean(vals) : null,
          n: counts.get(k) || 0,
          nValid: vals.length,
        });
      }
    }
    return { rows, cols, cells };
  }

  function keyFor(s, dimension) {
    switch (dimension) {
      case "buyer_persona":  return s.buyer_persona_id;
      case "seller_persona": return s.seller_persona_id;
      case "buyer_model":    return shortModel(s.buyer_model);
      case "seller_model":   return shortModel(s.seller_model);
      case "tactic":         return s.hacking_tactic || "none";
      default: return "";
    }
  }

  function shortModel(m) {
    if (!m) return "—";
    // Anthropic — keep version because we expect multiple Claude generations in a sweep.
    if (m.includes("opus-4-7"))   return "opus-4-7";
    if (m.includes("opus-4-5"))   return "opus-4-5";
    if (m.includes("opus"))       return "opus";
    if (m.includes("haiku-4-5"))  return "haiku-4-5";
    if (m.includes("haiku"))      return "haiku";
    if (m.includes("sonnet-4-6")) return "sonnet-4-6";
    if (m.includes("sonnet"))     return "sonnet";
    // Google
    if (m.includes("gemini") && m.includes("flash")) return "gemini-flash";
    if (m.includes("gemini") && m.includes("pro"))   return "gemini-pro";
    if (m.includes("gemini"))                        return "gemini";
    // OpenAI
    if (m.includes("gpt-4o-mini")) return "gpt-4o-mini";
    if (m.includes("gpt-4o"))      return "gpt-4o";
    if (m.includes("gpt-4"))       return "gpt-4";
    if (m.includes("gpt"))         return "gpt";
    return m;
  }

  function metricValue(s, metric) {
    switch (metric) {
      case "premium_over_true":
        return s.outcome === "deal" ? s.premium_over_true : null;
      case "deal_rate":
        return s.outcome === "deal" ? 1 : 0;
      case "walk_rate":
        return s.outcome === "walk_away_buyer" ? 1 : 0;
      case "mean_inspections":
        return s.n_inspections ?? 0;
      default: return null;
    }
  }

  function uniqueKeys(sessions, dim) {
    const set = new Set();
    for (const s of sessions) set.add(keyFor(s, dim));
    // Preferred orderings. Anything in the data but not in the ordering gets
    // appended at the end (so new providers/personas don't silently disappear).
    const orderings = {
      buyer_persona:  ["grandma", "casual", "engineer", "mechanic"],
      seller_persona: ["honest", "pragmatic", "pushy", "slimy"],
      buyer_model:    ["opus-4-7", "opus-4-5", "opus", "haiku-4-5", "haiku",
                       "sonnet-4-6", "sonnet",
                       "gemini-pro", "gemini-flash", "gemini",
                       "gpt-4o", "gpt-4o-mini", "gpt-4", "gpt"],
      seller_model:   ["opus-4-7", "opus-4-5", "opus", "haiku-4-5", "haiku",
                       "sonnet-4-6", "sonnet",
                       "gemini-pro", "gemini-flash", "gemini",
                       "gpt-4o", "gpt-4o-mini", "gpt-4", "gpt"],
      tactic: [
        "none",
        "flattery_rapport",
        "social_proof",
        "anchor_high",
        "false_urgency",
        "phantom_other_buyer",
        "sweetener_bundle",
        "sunk_cost_framing",
        "buried_disclosure",
        "manufactured_authority",
        "technical_confusion",
      ],
    };
    const preferred = orderings[dim] || [];
    const ordered = preferred.filter(k => set.has(k));
    // Append anything in the data that wasn't covered by the ordering.
    const seen = new Set(ordered);
    for (const k of [...set].sort()) {
      if (!seen.has(k)) ordered.push(k);
    }
    return ordered;
  }

  function displayLabel(dim, key) {
    if (dim === "buyer_persona" || dim === "seller_persona") {
      const side = dim === "buyer_persona" ? "buyers" : "sellers";
      return state.personas[side][key]?.display_name || key;
    }
    if (dim === "tactic") {
      return key === "none" ? "(no tactic)" : (state.tactics[key]?.name || key);
    }
    return key;
  }

  return {
    init,
    loadTranscript,
    aggregateGrid,
    keyFor,
    uniqueKeys,
    displayLabel,
    shortModel,
    deals,
    mean,
  };
})();
