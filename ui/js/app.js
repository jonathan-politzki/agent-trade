// Bootstraps the app, wires hash-based navigation across views.

(async function () {
  // Load everything once.
  let data;
  try {
    data = await Data.init();
  } catch (e) {
    document.querySelector(".content").innerHTML = `
      <div style="padding:2rem;background:var(--bg-elev);border:1px solid var(--rule);border-radius:4px;">
        <h2 style="font-family:var(--serif);">Data not loadable</h2>
        <p>The UI fetches JSON from <code>data/</code>. Browsers block <code>file://</code> fetches —
           run a local server first.</p>
        <pre>cd ui &amp;&amp; python -m http.server 8000</pre>
        <p>Then visit <a href="http://localhost:8000">http://localhost:8000</a>.</p>
        <p style="color:var(--ink-3);">Error: ${e.message}</p>
      </div>`;
    return;
  }

  // Expose data globally for view modules (e.g. lot.js).
  window.AT_DATA = data;

  // Update data-source tag.
  document.getElementById("data-source-tag").textContent =
    `${data.sessions.length} sessions · ${data.replayable.length} replayable transcripts`;

  // Replay state lives across view switches; build the DOM scaffolding now
  // (transcript + iceberg). Width-dependent SVG draws happen on activation.
  await Replay.render(data);

  // Track which views have rendered, so we only build SVGs once they're visible
  // and have a real clientWidth. Re-render on view-switch to recompute layouts.
  const rendered = { overview: false, susceptibility: false };

  function renderViewIfNeeded(v) {
    // Need to wait one frame after un-hiding so layout settles.
    requestAnimationFrame(() => {
      if (v === "primer") {
        if (typeof Primer !== "undefined" && Primer.render) Primer.render(data);
      } else if (v === "overview") {
        Overview.render(data);
        rendered.overview = true;
      } else if (v === "lot") {
        window.AT_LOT_RENDER && window.AT_LOT_RENDER();
      } else if (v === "e3") {
        window.AT_E3_RENDER && window.AT_E3_RENDER();
      } else if (v === "susceptibility") {
        HeatmapView.render(data);
        rendered.susceptibility = true;
      } else if (v === "reputation") {
        if (typeof Reputation !== "undefined" && Reputation.render) Reputation.render(data);
      }
      // Replay view is rendered once at boot; it uses HTML for the iceberg
      // and a viewBox-scaled SVG for the price track, so it survives being
      // initially hidden.
    });
  }

  // Hash routing.
  const views = ["primer", "overview", "lot", "replay", "susceptibility", "reputation", "e3", "methods"];

  function setView(v) {
    if (!views.includes(v)) v = "primer";
    document.querySelectorAll(".view").forEach(el => el.classList.remove("active"));
    document.getElementById(`view-${v}`).classList.add("active");
    document.querySelectorAll(".nav-link").forEach(a => {
      a.classList.toggle("active", a.dataset.view === v);
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
    renderViewIfNeeded(v);
  }

  document.querySelectorAll(".nav-link").forEach(a => {
    a.addEventListener("click", e => {
      const v = e.currentTarget.dataset.view;
      window.location.hash = v;
    });
  });
  window.addEventListener("hashchange", () => setView(window.location.hash.slice(1)));
  setView(window.location.hash.slice(1) || "primer");

  // Re-render charts on resize (debounced) for whichever view is active.
  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      const active = document.querySelector(".view.active");
      if (!active) return;
      const v = active.id.replace("view-", "");
      if (v === "overview") Overview.render(data);
      else if (v === "susceptibility") HeatmapView.render(data);
    }, 220);
  });
})();
