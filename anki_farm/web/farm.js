/* Anki Farm UI.
 *
 * Renders whatever state Python sends via AnkiFarm.render() and reports the
 * player's intents back with pycmd("farm:{...}"). No game rules live here.
 */
(() => {
  "use strict";

  const SHEET_COLS_PER_CROP = 6;
  const MAX_STAGE = 5; // the crop sheet has 5 growth stages

  let cat = null; // catalog: species, tier names, ...
  let state = null;
  let autoPlant = false;
  let selectedSeed = null; // species picked in the bag for click-to-plant
  let press = null; // pointer down, maybe about to drag
  let drag = null; // active drag
  const el = {};

  // ---- sprites ------------------------------------------------------------

  function spritePos(sheet, col) {
    const row = Math.floor(sheet / 2);
    const c = (sheet % 2) * SHEET_COLS_PER_CROP + col;
    return `calc(var(--sprite) * -${c}) calc(var(--sprite) * -${row})`;
  }

  function stageCol(tier) {
    // columns per crop: portrait, grown, ..., seeds
    const stage = Math.min(tier, MAX_STAGE);
    return SHEET_COLS_PER_CROP - stage;
  }

  function spriteEl(species, tier) {
    const div = document.createElement("div");
    div.className = "sprite";
    div.style.backgroundPosition = spritePos(cat.species[species].sheet, stageCol(tier));
    return div;
  }

  function plantEl(species, tier) {
    const p = document.createElement("div");
    p.className = `plant t${tier} r-${cat.species[species].rarity}`;
    p.appendChild(spriteEl(species, tier));
    if (tier >= 6) {
      for (let i = 0; i < 3; i++) {
        const s = document.createElement("span");
        s.className = "spark";
        p.appendChild(s);
      }
    }
    const badge = document.createElement("span");
    badge.className = "tier";
    badge.textContent = tier;
    p.appendChild(badge);
    return p;
  }

  function describe(species, tier) {
    const s = cat.species[species];
    return `${s.name} · ${cat.tierNames[tier]} (${tier}/${cat.maxTier}) · ${cat.rarities[s.rarity]}`;
  }

  // ---- skeleton -----------------------------------------------------------

  function build() {
    const root = document.getElementById("farm-root");
    root.innerHTML = `
      <div class="farm">
        <header class="bar">
          <h1>Anki Farm</h1>
          <div class="stats"></div>
          <label class="toggle" title="Plant new seeds straight onto empty tiles">
            <input type="checkbox" class="auto"> Auto-plant
          </label>
        </header>
        <div class="main">
          <section class="board-wrap">
            <div class="board"></div>
            <div class="info"></div>
          </section>
          <aside class="bag">
            <h2>Seed Bag <span class="count"></span></h2>
            <div class="bag-list"></div>
            <div class="bag-actions">
              <button class="btn plant-all">Plant all</button>
              <p class="hint">Drag a seed onto the soil, or click a seed and then a tile.</p>
            </div>
          </aside>
        </div>
        <div class="toast"></div>
      </div>`;
    for (const name of ["stats", "board", "info", "bag", "count", "toast"]) {
      el[name] = root.querySelector(`.${name}`);
    }
    el.bagList = root.querySelector(".bag-list");
    el.auto = root.querySelector(".auto");
    el.plantAll = root.querySelector(".plant-all");

    el.auto.addEventListener("change", () => send({ op: "auto_plant", value: el.auto.checked }));
    el.plantAll.addEventListener("click", () => send({ op: "plant_all" }));
    document.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    window.addEventListener("pointercancel", cancelDrag);
    el.board.addEventListener("pointerover", onHover);
    el.board.addEventListener("pointerleave", () => setInfo());
  }

  // ---- rendering ----------------------------------------------------------

  function render(payload) {
    state = payload.state;
    autoPlant = payload.autoPlant;
    if (selectedSeed && !state.bag[selectedSeed]) selectedSeed = null;
    cancelDrag();
    drawStats();
    drawBoard();
    drawBag();
    setInfo();
    if (payload.event) playEvent(payload.event);
  }

  function drawStats() {
    const s = state.stats;
    const found = Object.values(state.almanac).reduce((a, b) => a + b, 0);
    const total = Object.keys(cat.species).length * cat.maxTier;
    el.stats.innerHTML =
      `<span>Seeds <b>${s.seeds_earned || 0}</b></span>` +
      `<span>Merges <b>${s.merges || 0}</b></span>` +
      `<span>Golden <b>${s.golden_crops || 0}</b></span>` +
      `<span>Almanac <b>${found}/${total}</b></span>`;
    el.auto.checked = autoPlant;
  }

  function drawBoard() {
    el.board.style.gridTemplateColumns = `repeat(${state.w}, var(--tile))`;
    el.board.innerHTML = "";
    for (let y = 0; y < state.h; y++) {
      for (let x = 0; x < state.w; x++) {
        const key = `${x},${y}`;
        const tile = document.createElement("div");
        tile.className = "tile" + ((x + y) % 2 ? " alt" : "");
        tile.dataset.key = key;
        const p = state.tiles[key];
        if (p) tile.appendChild(plantEl(p[0], p[1]));
        el.board.appendChild(tile);
      }
    }
  }

  function drawBag() {
    const entries = Object.entries(state.bag).sort((a, b) => {
      const ra = rarityRank(a[0]);
      const rb = rarityRank(b[0]);
      return rb - ra || cat.species[a[0]].name.localeCompare(cat.species[b[0]].name);
    });
    const total = entries.reduce((n, [, c]) => n + c, 0);
    el.count.textContent = total;
    el.bagList.innerHTML = "";
    if (!entries.length) {
      el.bagList.innerHTML = `<div class="bag-empty">Empty. Review some cards to earn seeds!</div>`;
    }
    for (const [species, n] of entries) {
      const s = cat.species[species];
      const item = document.createElement("div");
      item.className = `bag-item r-${s.rarity}` + (species === selectedSeed ? " selected" : "");
      item.dataset.species = species;
      item.title = `${s.name} seed (${cat.rarities[s.rarity]})`;
      item.appendChild(spriteEl(species, 1));
      item.insertAdjacentHTML("beforeend", `<span class="name">${s.name}</span><span class="n">×${n}</span>`);
      el.bagList.appendChild(item);
    }
    const hasEmpty = Object.keys(state.tiles).length < state.w * state.h;
    el.plantAll.disabled = !total || !hasEmpty;
  }

  function rarityRank(species) {
    return Object.keys(cat.rarities).indexOf(cat.species[species].rarity);
  }

  function setInfo(text) {
    el.info.textContent =
      text ||
      (selectedSeed
        ? `Click an empty tile to plant ${cat.species[selectedSeed].name}`
        : "Drag two identical plants together to merge them");
  }

  function onHover(e) {
    if (drag) return;
    const tile = e.target.closest(".tile");
    const p = tile && state.tiles[tile.dataset.key];
    setInfo(p ? describe(p[0], p[1]) : undefined);
  }

  // ---- events from Python -------------------------------------------------

  function playEvent(ev) {
    const tileEl = ev.tile && el.board.querySelector(`[data-key="${ev.tile}"] .plant`);
    if (ev.kind === "merge" && tileEl) {
      tileEl.classList.add("pop");
      burst(tileEl.parentElement, ev.new ? 14 : 8);
      const p = state.tiles[ev.tile];
      if (p) {
        setInfo(describe(p[0], p[1]));
        if (ev.new) toast(`New in the almanac: ${cat.species[p[0]].name} – ${cat.tierNames[p[1]]}!`);
        else if (p[1] === cat.maxTier) toast(`Golden ${cat.species[p[0]].name}!`);
      }
    } else if ((ev.kind === "plant" || ev.kind === "move") && tileEl) {
      tileEl.classList.add("plant-in");
    } else if (ev.kind === "reward") {
      const s = cat.species[ev.species];
      toast(`+1 ${s.name} seed`);
      if (tileEl) tileEl.classList.add("plant-in");
      const item = el.bagList.querySelector(`[data-species="${ev.species}"]`);
      if (!ev.tile && item) item.animate([{ background: "var(--gold)" }, { background: "transparent" }], 600);
    } else if (ev.kind === "plant_all" && ev.count) {
      el.board.querySelectorAll(".plant.t1").forEach((p) => p.classList.add("plant-in"));
    }
  }

  function burst(tile, n) {
    const colors = ["#e2b53c", "#fff6e0", "#6aa84f", "#f2d27a"];
    for (let i = 0; i < n; i++) {
      const d = document.createElement("span");
      d.className = "particle";
      const angle = (Math.PI * 2 * i) / n + Math.random() * 0.4;
      const dist = 26 + Math.random() * 18;
      d.style.setProperty("--dx", `${Math.round(Math.cos(angle) * dist)}px`);
      d.style.setProperty("--dy", `${Math.round(Math.sin(angle) * dist)}px`);
      d.style.setProperty("--c", colors[i % colors.length]);
      tile.appendChild(d);
      setTimeout(() => d.remove(), 600);
    }
  }

  let toastTimer = null;
  function toast(text) {
    el.toast.textContent = text;
    el.toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.toast.classList.remove("show"), 1800);
  }

  // ---- input: click and drag ----------------------------------------------

  function onPointerDown(e) {
    if (e.button !== 0 || !state) return;
    const plant = e.target.closest(".plant");
    const item = e.target.closest(".bag-item");
    const tile = e.target.closest(".tile");
    if (plant && tile) {
      const [species, tier] = state.tiles[tile.dataset.key];
      press = { from: "tile", key: tile.dataset.key, species, tier, source: plant, x: e.clientX, y: e.clientY };
    } else if (item) {
      press = { from: "bag", species: item.dataset.species, tier: 1, source: item, x: e.clientX, y: e.clientY };
    } else if (tile) {
      press = { from: "empty", key: tile.dataset.key, x: e.clientX, y: e.clientY };
    } else {
      press = null;
      return;
    }
    e.preventDefault();
  }

  function onPointerMove(e) {
    if (press && !drag && press.from !== "empty") {
      if (Math.hypot(e.clientX - press.x, e.clientY - press.y) > 5) startDrag(press);
    }
    if (!drag) return;
    drag.ghost.style.left = `${e.clientX}px`;
    drag.ghost.style.top = `${e.clientY}px`;
    const target = document.elementFromPoint(e.clientX, e.clientY);
    const tile = target && target.closest(".tile");
    if (tile !== drag.hover) {
      if (drag.hover) drag.hover.classList.remove("hover");
      if (tile) tile.classList.add("hover");
      drag.hover = tile;
    }
    const overBag = drag.from === "tile" && drag.tier === 1 && target && target.closest(".bag");
    el.bag.classList.toggle("drop-target", !!overBag);
  }

  function startDrag(p) {
    drag = { ...p, hover: null };
    press = null;
    selectedSeed = null;
    p.source.classList.add("dragging");
    const ghost = document.createElement("div");
    ghost.className = `ghost t${p.tier}`;
    ghost.appendChild(spriteEl(p.species, p.tier));
    ghost.style.left = `${p.x}px`;
    ghost.style.top = `${p.y}px`;
    document.body.appendChild(ghost);
    drag.ghost = ghost;
    // highlight where this can go
    for (const tile of el.board.children) {
      const t = state.tiles[tile.dataset.key];
      if (tile.dataset.key === p.key) continue;
      if (t && t[0] === p.species && t[1] === p.tier && p.tier < cat.maxTier) tile.classList.add("can-merge");
      else if (!t) tile.classList.add("can-drop");
    }
    setInfo(describe(p.species, p.tier));
  }

  function onPointerUp(e) {
    if (drag) {
      const target = document.elementFromPoint(e.clientX, e.clientY);
      const tile = target && target.closest(".tile");
      const overBag = target && target.closest(".bag");
      const d = drag;
      cancelDrag();
      if (tile && d.from === "tile" && tile.dataset.key !== d.key) {
        send({ op: "move", src: d.key, dst: tile.dataset.key });
      } else if (tile && d.from === "bag") {
        send({ op: "plant", species: d.species, tile: tile.dataset.key });
      } else if (overBag && d.from === "tile" && d.tier === 1) {
        send({ op: "to_bag", tile: d.key });
      }
      return;
    }
    if (!press) return;
    const p = press;
    press = null;
    // plain click
    if (p.from === "bag") {
      selectedSeed = selectedSeed === p.species ? null : p.species;
      drawBag();
      setInfo();
    } else if (selectedSeed && (p.from === "empty" || (p.species === selectedSeed && p.tier === 1))) {
      send({ op: "plant", species: selectedSeed, tile: p.key });
    }
  }

  function cancelDrag() {
    press = null;
    if (!drag) return;
    drag.ghost.remove();
    drag.source.classList.remove("dragging");
    el.bag.classList.remove("drop-target");
    for (const tile of el.board.children) tile.classList.remove("hover", "can-merge", "can-drop");
    drag = null;
  }

  function send(msg) {
    pycmd("farm:" + JSON.stringify(msg));
  }

  // ---- public API ---------------------------------------------------------

  window.AnkiFarm = {
    init(catalog) {
      cat = catalog;
      build();
    },
    render,
  };
})();
