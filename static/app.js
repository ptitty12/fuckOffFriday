/* fuck off friday - front end. No framework, no build step. */
(() => {
  const $ = (id) => document.getElementById(id);
  const WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const WD_LONG = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  const fmt = (v, digits = 1) => (v == null ? "—" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(digits)}%`);
  const sign = (v) => (v == null ? "muted" : v > 0.05 ? "pos" : v < -0.05 ? "neg" : "");
  const dateLabel = (iso) => {
    const d = new Date(iso + "T12:00:00");
    return `${WD[(d.getDay() + 6) % 7]} ${d.toLocaleDateString("en-US", { month: "short", day: "numeric" })}`;
  };
  const longDate = (iso) => new Date(iso + "T12:00:00").toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" });

  let DATA = null;
  let range = 90;

  async function load() {
    try {
      const r = await fetch("/api/dashboard", { cache: "no-store" });
      DATA = await r.json();
    } catch (e) {
      $("hero-eyebrow").textContent = "could not load data";
      console.error(e);
      return;
    }
    renderHero(DATA.today);
    renderTiles(DATA.history.days, DATA.today);
    renderChart();
    renderProfile(DATA.profile);
    renderStatus(DATA.status, DATA.today);
    $("how-companies").textContent = listJoin(DATA.today.companies || window.FOF.companies);
  }

  function listJoin(arr) {
    if (!arr || !arr.length) return "";
    if (arr.length === 1) return arr[0];
    return arr.slice(0, -1).join(", ") + " and " + arr[arr.length - 1];
  }

  /* Hero ---------------------------------------------------------------- */
  function renderHero(t) {
    const eyebrow = $("hero-eyebrow"), value = $("hero-value"), sub = $("hero-sub");
    const mood = $("hero-mood"), meta = $("hero-meta"), chips = $("hero-companies"), notice = $("hero-notice");
    const r = t.reading, s = t.settled;
    let score = null, block = null, title = "", vs = "";

    if (t.headline === "reading" && r) {
      block = r; score = r.calibrated ? r.score : r.raw_score;
      title = `${r.label}${r.label === "Today" || r.label === "Yesterday" ? ", " + r.weekday : ""} · as of ${r.fetched_local}`;
      vs = `productivity vs. a normal ${r.weekday}`;
      const c = r.calibration;
      if (r.calibrated) {
        const how = c.method === "same_weekday" ? `${c.n} past ${r.weekday}s` : `${c.n} past days`;
        meta.textContent = `Calibrated for time of day using ${how} grabbed around ${r.fetched_local}` +
          (c.spread_pct ? ` · typical wobble ±${c.spread_pct}%` : "") +
          ` · raw reading ${fmt(r.raw_score)}`;
      } else {
        meta.textContent = `Raw reading · not yet calibrated for time of day, so it probably reads low`;
      }
    } else if (t.headline === "settled" && s) {
      block = s; score = s.score;
      title = `${s.label}${s.label === "Today" || s.label === "Yesterday" ? ", " + s.weekday : ""} · final`;
      vs = `productivity vs. a normal ${s.weekday}`;
      if (r) {
        const need = r.calibration.needed;
        notice.innerHTML = `<b>${r.label} so far (${r.fetched_local}): ${fmt(r.raw_score)}, uncalibrated.</b> ` +
          `Google only reports the hours it has seen, so early readings run low. ` +
          `The meter needs ${need} more grab${need === 1 ? "" : "s"} around this hour on a comparable day before it trusts today's number.`;
        notice.hidden = false;
        meta.textContent = `Showing the last settled day while today's reading calibrates`;
      } else {
        meta.textContent = `No live grab yet · run the updater to get today's reading`;
      }
    } else {
      eyebrow.textContent = "no data yet";
      value.textContent = "—"; value.className = "hero-value muted";
      sub.textContent = "run update_db.py to take the first grab";
      mood.hidden = true;
      return;
    }

    eyebrow.textContent = title;
    sub.textContent = vs;
    value.className = `hero-value ${sign(score)}`;
    countUp(value, score);
    const m = block.mood && block.mood.label !== "No reading yet" ? block.mood : moodFor(score);
    mood.querySelector(".mood-emoji").textContent = m.emoji;
    mood.querySelector(".mood-label").textContent = m.label;
    document.title = `${fmt(score, 0)} · fuck off friday`;

    chips.innerHTML = "";
    const comps = block.companies || {};
    Object.keys(comps).filter((name) => name !== "average").forEach((name) => {
      const v = comps[name].score != null ? comps[name].score : comps[name].raw;
      const el = document.createElement("span");
      el.className = "chip";
      el.innerHTML = `<i class="${sign(v)}"></i>${name} <b>${fmt(v)}</b>`;
      el.title = `${name}: search interest vs. its own ${block.weekday} median`;
      chips.appendChild(el);
    });

    if (score != null && score <= -20) confetti();
  }

  const MOODS = [[10, "🤖", "Suspiciously productive"], [3, "💪", "Locked in"], [-3, "😐", "Just another day at the office"], [-10, "☕", "Coasting"], [-20, "🏖️", "Half-day energy"], [-Infinity, "🍻", "Full fuck-off mode"]];
  function moodFor(v) {
    if (v == null) return { emoji: "🤷", label: "No reading yet" };
    for (const [th, emoji, label] of MOODS) if (v >= th) return { emoji, label };
    return { emoji: "🍻", label: "Full fuck-off mode" };
  }

  function countUp(el, target) {
    if (target == null) { el.textContent = "—"; return; }
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const dur = reduce ? 0 : 1100, t0 = performance.now();
    const step = (now) => {
      const p = dur ? Math.min(1, (now - t0) / dur) : 1;
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = fmt(target * eased);
      if (p < 1) requestAnimationFrame(step); else el.textContent = fmt(target);
    };
    requestAnimationFrame(step);
  }

  /* Tiles --------------------------------------------------------------- */
  function renderTiles(days, t) {
    const box = $("tiles");
    box.innerHTML = "";
    if (!days.length) return;
    const last = days[days.length - 1];
    const last7 = days.slice(-7), last30 = days.slice(-30);
    const avg = (arr) => arr.reduce((a, d) => a + d.score, 0) / arr.length;
    const worst = last30.reduce((a, d) => (d.score < a.score ? d : a), last30[0]);
    const best = last30.reduce((a, d) => (d.score > a.score ? d : a), last30[0]);
    const weekdays30 = last30.filter((d) => d.weekday < 5);
    const worstWd = weekdays30.length ? weekdays30.reduce((a, d) => (d.score < a.score ? d : a), weekdays30[0]) : worst;

    const tiles = [];
    if (t.headline !== "settled") tiles.push({ label: `${t.settled ? t.settled.label : dateLabel(last.date)} · final`, value: last.score, sub: WD_LONG[last.weekday] });
    tiles.push({ label: "Last 7 days", value: avg(last7), sub: "average settled score" });
    tiles.push({ label: "Biggest fuck-off, 30d", value: worstWd.score, sub: dateLabel(worstWd.date) + (worstWd !== worst ? " (weekdays only)" : "") });
    tiles.push({ label: "Most productive, 30d", value: best.score, sub: dateLabel(best.date) });
    tiles.forEach((x) => {
      const el = document.createElement("div");
      el.className = "tile";
      el.innerHTML = `<div class="label">${x.label}</div><div class="value ${sign(x.value)}">${fmt(x.value)}</div><div class="sub">${x.sub}</div>`;
      box.appendChild(el);
    });
  }

  /* Chart --------------------------------------------------------------- */
  function visibleDays() {
    let days = DATA.history.days;
    if (range > 0 && days.length) {
      const lastDate = new Date(days[days.length - 1].date + "T12:00:00");
      const cutoff = new Date(lastDate.getTime() - range * 86400000);
      days = days.filter((d) => new Date(d.date + "T12:00:00") > cutoff);
    }
    return days;
  }

  function renderChart() {
    const svg = $("chart");
    const days = visibleDays().map((d) => ({ ...d, kind: "settled" }));
    const r = DATA.today.reading;
    if (r && r.calibrated && r.score != null && (!days.length || r.date > days[days.length - 1].date)) {
      days.push({ date: r.date, weekday: WD_LONG.indexOf(r.weekday), score: r.score, companies: Object.fromEntries(Object.entries(r.companies).map(([k, v]) => [k, v.score])), kind: "today" });
    }
    const W = svg.clientWidth || 800, H = 260, padL = 40, padR = 8, padT = 12, padB = 26;
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.innerHTML = "";
    if (!days.length) {
      svg.innerHTML = `<text class="empty" x="${W / 2}" y="${H / 2}" text-anchor="middle">No settled days yet.</text>`;
      return;
    }
    const maxAbs = Math.max(10, ...days.map((d) => Math.abs(d.score)));
    const lim = niceCeil(maxAbs);
    const innerW = W - padL - padR, innerH = H - padT - padB;
    const y = (v) => padT + innerH / 2 - (v / lim) * (innerH / 2);
    const slot = innerW / days.length;
    const gap = slot >= 4 ? 2 : 0;
    const bw = Math.max(1, Math.min(24, slot - gap));
    const x = (i) => padL + i * slot + (slot - bw) / 2;

    let g = `<defs><pattern id="hatch" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)"><rect width="6" height="6" fill="var(--today)" opacity=".35"/><rect width="2.5" height="6" fill="var(--today)"/></pattern></defs>`;
    // gridlines + ticks
    const ticks = [lim, lim / 2, 0, -lim / 2, -lim];
    ticks.forEach((t) => {
      g += `<line class="${t === 0 ? "zero" : "grid"}" x1="${padL}" x2="${W - padR}" y1="${y(t)}" y2="${y(t)}"/>`;
      g += `<text class="tick" x="${padL - 6}" y="${y(t) + 4}" text-anchor="end">${t > 0 ? "+" : ""}${t}%</text>`;
    });
    // x labels: first of each month (or every ~7 days when short)
    const labelEvery = days.length <= 35 ? 7 : 0;
    days.forEach((d, i) => {
      const dt = new Date(d.date + "T12:00:00");
      const show = labelEvery ? i % labelEvery === 0 : dt.getDate() === 1 || (i === 0 && days.length < 60);
      if (show) {
        const txt = labelEvery || days.length < 60 ? dt.toLocaleDateString("en-US", { month: "short", day: "numeric" }) : dt.toLocaleDateString("en-US", { month: "short", year: days.length > 400 ? "2-digit" : undefined });
        g += `<text class="tick" x="${x(i) + bw / 2}" y="${H - 8}" text-anchor="middle">${txt}</text>`;
      }
    });
    // bars
    days.forEach((d, i) => {
      const top = Math.min(y(0), y(d.score)), h = Math.max(1, Math.abs(y(d.score) - y(0)));
      const cls = ["bar", d.kind === "today" ? "today pattern" : sign(d.score) || "pos", d.weekday >= 5 ? "weekend" : ""].join(" ");
      const rx = Math.min(4, bw / 2);
      g += `<rect class="${cls}" data-i="${i}" x="${x(i)}" y="${top}" width="${bw}" height="${h}" rx="${rx}"/>`;
    });
    // hit targets on top
    days.forEach((d, i) => {
      g += `<rect class="hit" data-i="${i}" x="${padL + i * slot}" y="${padT}" width="${slot}" height="${innerH}"/>`;
    });
    svg.innerHTML = g;

    const tip = $("tooltip");
    const bars = svg.querySelectorAll(".bar");
    let hovered = null;
    svg.querySelectorAll(".hit").forEach((hit) => {
      hit.addEventListener("mouseenter", () => {
        const i = +hit.dataset.i, d = days[i];
        if (hovered) hovered.classList.remove("hover");
        hovered = bars[i]; hovered.classList.add("hover");
        const comps = Object.entries(d.companies || {}).map(([k, v]) => `<div class="co">${k} ${fmt(v)}</div>`).join("");
        tip.innerHTML = `<div>${longDate(d.date)}${d.kind === "today" ? " · so far, calibrated" : ""}</div><b>${fmt(d.score)}</b> vs. a normal ${WD_LONG[d.weekday]}${comps}`;
        tip.hidden = false;
        const wrap = svg.parentElement.getBoundingClientRect(), sb = svg.getBoundingClientRect();
        const scale = sb.width / W;
        tip.style.left = `${(x(i) + bw / 2) * scale + (sb.left - wrap.left)}px`;
        tip.style.top = `${Math.min(y(0), y(d.score)) * scale + (sb.top - wrap.top)}px`;
      });
      hit.addEventListener("mouseleave", () => { tip.hidden = true; if (hovered) hovered.classList.remove("hover"); hovered = null; });
    });
  }

  function niceCeil(v) {
    const steps = [10, 20, 25, 40, 50, 60, 80, 100, 150, 200];
    for (const s of steps) if (v <= s) return s;
    return Math.ceil(v / 100) * 100;
  }

  $("range").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    range = +b.dataset.days;
    $("range").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
    renderChart();
  });
  let resizeT;
  window.addEventListener("resize", () => { clearTimeout(resizeT); resizeT = setTimeout(() => DATA && renderChart(), 120); });

  /* Weekday profile ----------------------------------------------------- */
  function renderProfile(p) {
    const box = $("profile-bars");
    box.innerHTML = "";
    const rows = p.weekdays.filter((w) => w.level_pct != null);
    if (!rows.length) { box.innerHTML = `<p class="hint">Not enough full weeks yet.</p>`; return; }
    $("profile-hint").textContent = `Typical level of each day vs. that week's Monday–Friday average, over ${p.n_weeks} week${p.n_weeks === 1 ? "" : "s"} of settled data.`;
    const maxNeg = Math.max(1, ...rows.map((w) => Math.max(0, -w.level_pct)));
    const maxPos = Math.max(1, ...rows.map((w) => Math.max(0, w.level_pct)));
    const zero = maxNeg / (maxNeg + maxPos) * 100;
    rows.forEach((w) => {
      const v = w.level_pct, neg = v < 0;
      const width = (Math.abs(v) / (maxNeg + maxPos)) * 100;
      const el = document.createElement("div");
      el.className = "prow";
      el.innerHTML = `<span class="name ${w.weekday === 4 ? "fri" : ""}">${w.name}</span>` +
        `<span class="track"><span class="zero" style="left:${zero}%"></span>` +
        `<span class="fill ${neg ? "neg" : ""} ${w.weekday >= 5 ? "weekend" : ""}" style="${neg ? `right:${100 - zero}%` : `left:${zero}%`};width:${width}%"></span></span>` +
        `<span class="val">${fmt(v)}</span>`;
      el.title = `${w.name}: ${fmt(v)} vs. the working-week average, median of ${w.n_weeks} weeks`;
      box.appendChild(el);
    });
  }

  /* Status -------------------------------------------------------------- */
  function renderStatus(s, t) {
    const box = $("status");
    const g = s.grabs, r = t.reading;
    let html = "";
    if (!g.n) {
      html += `<p>No live grabs archived yet. Imported history covers ${s.settled_days.first} to ${s.settled_days.last} (${s.settled_days.n} days). Run <code>python update_db.py</code> or start the <code>updater</code> container.</p>`;
    } else {
      html += `<p><b>${g.n}</b> grab${g.n === 1 ? "" : "s"} archived since ${g.first.slice(0, 10)}, last at ${r ? r.fetched_local_full : g.last}. ` +
        `${s.settled_days.n} settled days on record. Time zone ${s.tz}.</p>`;
    }
    const cov = s.calibration_coverage || [];
    if (cov.length) {
      const bands = [...new Set(cov.map((c) => c.hour_band))].sort();
      html += `<table><thead><tr><th>local hours</th>${WD.map((w) => `<th>${w}</th>`).join("")}<th>all</th></tr></thead><tbody>`;
      bands.forEach((b) => {
        const row = cov.filter((c) => c.hour_band === b);
        const byWd = WD.map((_, i) => (row.find((c) => c.weekday === i) || {}).n || 0);
        html += `<tr><td>${b}</td>${byWd.map((n) => `<td>${n || "·"}</td>`).join("")}<td>${byWd.reduce((a, b) => a + b, 0)}</td></tr>`;
      });
      html += `</tbody></table><p class="hint">Settled partial-day samples per hour band. Three in a column (or in a row's weekday/weekend group) is enough to calibrate that slot.</p>`;
    } else if (g.n) {
      html += `<p class="hint">No calibration samples yet: a sample appears the day after a grab, once that day has settled.</p>`;
    }
    box.innerHTML = html;
  }

  /* Confetti (only on proper fuck-off days) ----------------------------- */
  function confetti() {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const c = $("confetti"), ctx = c.getContext("2d");
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    c.width = innerWidth * dpr; c.height = innerHeight * dpr; ctx.scale(dpr, dpr);
    const colors = ["#d6453d", "#f4b400", "#3b6ff0", "#1f9d55", "#6e6cf2"];
    const parts = Array.from({ length: 140 }, () => ({
      x: innerWidth / 2 + (Math.random() - .5) * 200, y: innerHeight * .35,
      vx: (Math.random() - .5) * 14, vy: -Math.random() * 14 - 4,
      s: 5 + Math.random() * 6, r: Math.random() * Math.PI, vr: (Math.random() - .5) * .3,
      col: colors[Math.floor(Math.random() * colors.length)], life: 1,
    }));
    const t0 = performance.now();
    const tick = (now) => {
      ctx.clearRect(0, 0, innerWidth, innerHeight);
      const dt = Math.min(0.04, 0.016);
      let alive = false;
      parts.forEach((p) => {
        p.vy += 22 * dt; p.x += p.vx; p.y += p.vy; p.r += p.vr; p.vx *= .99;
        p.life -= 0.006;
        if (p.life <= 0 || p.y > innerHeight + 20) return;
        alive = true;
        ctx.save(); ctx.globalAlpha = Math.max(0, p.life); ctx.translate(p.x, p.y); ctx.rotate(p.r);
        ctx.fillStyle = p.col; ctx.fillRect(-p.s / 2, -p.s / 2, p.s, p.s * .6); ctx.restore();
      });
      if (alive && now - t0 < 4000) requestAnimationFrame(tick); else ctx.clearRect(0, 0, innerWidth, innerHeight);
    };
    requestAnimationFrame(tick);
  }

  load();
})();
