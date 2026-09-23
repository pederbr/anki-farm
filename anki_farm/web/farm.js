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
  let soundOn = true;
  let selectedSeed = null; // species picked in the bag for click-to-plant
  let press = null; // pointer down, maybe about to drag
  let drag = null; // active drag
  const el = {};

  // ---- sound --------------------------------------------------------------
  // Tiny chiptune synth on WebAudio: square/triangle blips, no audio files.

  const Sfx = (() => {
    let ctx = null;
    const audio = () => {
      if (!ctx) {
        const AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) return null;
        ctx = new AC();
      }
      if (ctx.state === "suspended") ctx.resume();
      return ctx;
    };
    const midi = (n) => 440 * Math.pow(2, (n - 69) / 12);

    // one note: midi number, start offset (s), length (s)
    function note(n, at, len, { type = "square", vol = 0.06, slideTo = null } = {}) {
      const a = audio();
      if (!a) return;
      const t = a.currentTime + at;
      const osc = a.createOscillator();
      const gain = a.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(midi(n), t);
      if (slideTo !== null) osc.frequency.exponentialRampToValueAtTime(midi(slideTo), t + len);
      gain.gain.setValueAtTime(vol, t);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + len);
      osc.connect(gain).connect(a.destination);
      osc.start(t);
      osc.stop(t + len + 0.02);
    }

    const sounds = {
      pick: () => note(84, 0, 0.04, { vol: 0.03 }),
      plant: () => {
        note(60, 0, 0.06, { type: "triangle", vol: 0.12 });
        note(67, 0.05, 0.08, { type: "triangle", vol: 0.1 });
      },
      move: () => note(64, 0, 0.05, { type: "triangle", vol: 0.08 }),
      swap: () => {
        note(67, 0, 0.05, { type: "triangle", vol: 0.08 });
        note(62, 0.05, 0.05, { type: "triangle", vol: 0.08 });
      },
      // higher tiers merge with a higher, longer arpeggio
      merge: (tier) => {
        const root = 60 + tier * 2;
        [0, 4, 7, 12].slice(0, Math.min(2 + tier, 4)).forEach((iv, i) => note(root + iv, i * 0.06, 0.1));
      },
      discover: () => [79, 84, 88, 91].forEach((n, i) => note(n, 0.25 + i * 0.07, 0.12, { vol: 0.04 })),
      golden: () => {
        [72, 76, 79, 84].forEach((n, i) => note(n, i * 0.09, 0.14));
        note(88, 0.4, 0.5, { vol: 0.05 });
        note(76, 0.4, 0.5, { type: "triangle", vol: 0.08 });
      },
      reward: () => {
        note(83, 0, 0.06, { vol: 0.04 });
        note(88, 0.06, 0.18, { vol: 0.04 });
      },
      packet: () =>
        [72, 72, 76, 79, 76, 79, 84].forEach((n, i) =>
          note(n, i * 0.08, i === 6 ? 0.35 : 0.08, { vol: 0.05 }),
        ),
      error: () => note(45, 0, 0.12, { vol: 0.05, slideTo: 38 }),
    };

    return {
      play(name, arg) {
        if (!soundOn || !sounds[name]) return;
        try {
          sounds[name](arg);
        } catch (e) {
          /* audio is a nicety; never break the game over it */
        }
      },
    };
  })();

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
          <button class="sound" title="Sound effects">♪ Sound</button>
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
    for (const name of ["stats", "board", "info", "bag", "count", "toast", "sound"]) {
      el[name] = root.querySelector(`.${name}`);
    }
    el.bagList = root.querySelector(".bag-list");
    el.auto = root.querySelector(".auto");
    el.plantAll = root.querySelector(".plant-all");

    el.auto.addEventListener("change", () => send({ op: "auto_plant", value: el.auto.checked }));
    el.plantAll.addEventListener("click", () => send({ op: "plant_all" }));
    el.sound.addEventListener("click", () => {
      soundOn = !soundOn;
      Sfx.play("pick");
      send({ op: "sound", value: soundOn });
    });
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
    soundOn = payload.sound !== false;
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
    el.sound.classList.toggle("off", !soundOn);
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
        if (p[1] === cat.maxTier) {
          Sfx.play("golden");
          toast(`Golden ${cat.species[p[0]].name}!`, true);
        } else {
          Sfx.play("merge", p[1]);
          if (ev.new) {
            Sfx.play("discover");
            toast(`New in the almanac: ${cat.species[p[0]].name} – ${cat.tierNames[p[1]]}!`);
          }
        }
      }
    } else if (ev.kind === "plant" || ev.kind === "move" || ev.kind === "swap") {
      if (tileEl) tileEl.classList.add("plant-in");
      Sfx.play(ev.kind);
    } else if (ev.kind === "reward") {
      const s = cat.species[ev.species];
      Sfx.play("reward");
      toast(`+1 ${s.name} seed`);
      if (tileEl) tileEl.classList.add("plant-in");
      flashBag(ev.tile ? [] : [ev.species]);
    } else if (ev.kind === "packet") {
      Sfx.play("packet");
      const names = ev.species.map((sp) => cat.species[sp].name).join(", ");
      toast(`Deck cleared! Seed packet: ${names}`, true);
      flashBag(ev.species);
    } else if (ev.kind === "plant_all" && ev.count) {
      Sfx.play("plant");
      el.board.querySelectorAll(".plant.t1").forEach((p) => p.classList.add("plant-in"));
    } else if (ev.kind === "to_bag") {
      Sfx.play("move");
    } else if (ev.kind === "error") {
      Sfx.play("error");
    }
  }

  function flashBag(species) {
    for (const sp of new Set(species)) {
      const item = el.bagList.querySelector(`[data-species="${sp}"]`);
      if (item) item.animate([{ background: "var(--gold)" }, { background: "transparent" }], 700);
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
  function toast(text, big = false) {
    el.toast.textContent = text;
    el.toast.classList.toggle("big", big);
    el.toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.toast.classList.remove("show"), big ? 3200 : 1800);
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
    Sfx.play("pick");
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
