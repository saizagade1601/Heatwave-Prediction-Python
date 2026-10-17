/* =====================================================================
   app.js  -  front end of HeatGuard AI
   Talks to the Python (Flask) back end through /api/... and renders the
   six pages, the theme engine, pop-up alerts and the live AWS monitor.
   ===================================================================== */
const $ = id => document.getElementById(id);
const STATUS = [["#3ecf8e", "✔", "Normal"], ["#f2c94c", "▲", "Watch"], ["#ff8c2a", "⚠", "Warning"], ["#ff4d4f", "✖", "Severe"]];
const THEMES = {
  solar: { label: "SOLAR", sym: "☀", accent: "#ff8a1f", accent2: "#ffc361", text: "#1a0d04", particles: ["#ffb347", "#ff8a1f", "#ffd27a", "#ff7a00"] },
  blaze: { label: "BLAZE", sym: "♨", accent: "#ff4d1a", accent2: "#ffb000", text: "#1a0502", particles: ["#ff3d00", "#ff7a00", "#ffb000", "#ffd54f", "#ff5722"] },
  frost: { label: "FROST", sym: "❄", accent: "#5ccfff", accent2: "#c3efff", text: "#03111c", particles: ["#ffffff", "#d6f3ff", "#9fdcff", "#e8f9ff"] },
  gale: { label: "GALE", sym: "≋", accent: "#3fe0b0", accent2: "#b5f7e3", text: "#03140f", particles: ["#c8fff0", "#7debd0", "#ffffff", "#9ff5dc"] },
  monsoon: { label: "MONSOON", sym: "☂", accent: "#6f8cff", accent2: "#a8e0ff", text: "#060917", particles: ["#9fc4ff", "#c9dcff", "#6f8cff", "#dfe9ff"] },
};
const S = { meta: null, country: "India", page: "overview", theme: "solar", auto: true, alerted: new Set(),
            forecast: null, horizon: 14, model: "AI Ensemble", stake: "Citizens", sql: null, history: [],
            anMode: "country", monSince: 0, monRunning: false, redraw: {} };

// ------------------------------------------------------------- API helper
async function api(path, body) {
  const opt = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch(path, opt);
  const data = await r.json().catch(() => ({ error: `Server error ${r.status}` }));
  if (!r.ok || data.error) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}
const status = (t, err) => { $("status-msg").textContent = t; $("status-msg").style.color = err ? "#ff6b6b" : ""; };
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// ------------------------------------------------------------ weather icons
function icon(kind, size = 40) {
  const sun = (cx, cy, r, core = "#ffb020", ray = "#ffcf5a") => {
    let s = "";
    for (let i = 0; i < 8; i++) { const a = i * Math.PI / 4; s += `<line x1="${cx + Math.cos(a) * r * 1.38}" y1="${cy + Math.sin(a) * r * 1.38}" x2="${cx + Math.cos(a) * r * 2}" y2="${cy + Math.sin(a) * r * 2}" stroke="${ray}" stroke-width="${r * .22}" stroke-linecap="round"/>`; }
    return s + `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${core}"/>`;
  };
  const cloud = (cx, cy, s, c) => `<g fill="${c}"><circle cx="${cx - .38 * s}" cy="${cy + .18 * s}" r="${.25 * s}"/><circle cx="${cx - .08 * s}" cy="${cy - .06 * s}" r="${.36 * s}"/><circle cx="${cx + .3 * s}" cy="${cy + .12 * s}" r="${.28 * s}"/><rect x="${cx - .38 * s}" y="${cy + .1 * s}" width="${.7 * s}" height="${.33 * s}" rx="${.1 * s}"/></g>`;
  let b = "";
  switch (kind) {
    case "sun": b = sun(50, 50, 20); break;
    case "heat": b = sun(50, 44, 18, "#ff5a1f", "#ffb000") + [-1, 0, 1].map(k => `<path d="M${50 + k * 16} 80 q4 4 0 8 q-4 4 0 8" stroke="#ff7a29" stroke-width="3" fill="none"/>`).join(""); break;
    case "partly": b = sun(38, 38, 13) + cloud(58, 58, 52, "#dfe7f1"); break;
    case "cloud": b = cloud(50, 50, 70, "#cfd9e6"); break;
    case "rain": b = cloud(50, 40, 66, "#bfcbe0") + [-1, 0, 1].map(k => `<line x1="${50 + k * 18}" y1="70" x2="${44 + k * 18}" y2="86" stroke="#5aa9ff" stroke-width="5" stroke-linecap="round"/>`).join(""); break;
    case "storm": b = cloud(50, 38, 66, "#8e9bb3") + `<path d="M50 56 L40 76 L50 75 L44 94 L62 68 L51 69 L57 56Z" fill="#ffd23f"/>`; break;
    case "snow": b = cloud(50, 40, 66, "#dbe7f5") + [-1, 0, 1].map(k => `<circle cx="${50 + k * 18}" cy="${78 + (k % 2) * 8}" r="4" fill="#fff"/>`).join(""); break;
    case "fog": b = [0, 1, 2].map(k => `<line x1="18" x2="82" y1="${34 + k * 16}" y2="${34 + k * 16}" stroke="#b9c3cf" stroke-width="6" stroke-linecap="round"/>`).join(""); break;
    case "wind": b = [0, 1, 2].map(k => `<path d="M16 ${34 + k * 16} H${60 - k * 8} q12 0 10 -10 q-3 -8 -10 -4" stroke="#9fe8d6" stroke-width="5" fill="none" stroke-linecap="round"/>`).join(""); break;
    case "drop": b = `<path d="M50 14 C64 38 74 50 74 64 a24 24 0 0 1 -48 0 C26 50 36 38 50 14Z" fill="#4aa8ff"/>`; break;
    case "thermo": b = `<rect x="44" y="12" width="12" height="54" rx="6" fill="#ffe1c2"/><rect x="47" y="34" width="6" height="34" fill="#ff4d1a"/><circle cx="50" cy="74" r="13" fill="#ff4d1a"/>`; break;
    case "leaf": b = `<path d="M20 78 C20 30 60 18 82 20 C84 50 66 82 20 78Z" fill="#3ecf8e"/><path d="M24 76 L70 30" stroke="#13573a" stroke-width="4"/>`; break;
    default: b = sun(50, 50, 20);
  }
  return `<svg viewBox="0 0 100 100" width="${size}" height="${size}">${b}</svg>`;
}

// ------------------------------------------------------------- logo rays
document.querySelectorAll(".logo .rays").forEach(g => {
  for (let i = 0; i < 8; i++) { const a = i * Math.PI / 4;
    g.insertAdjacentHTML("beforeend", `<line x1="${50 + Math.cos(a) * 27}" y1="${50 + Math.sin(a) * 27}" x2="${50 + Math.cos(a) * 36}" y2="${50 + Math.sin(a) * 36}"/>`); }
});

// =============================================================== THEMES
function setTheme(name, reason, manual = false) {
  if (!THEMES[name]) return;
  if (!manual && !S.auto) { $("mode-reason").textContent = `Manual theme • ${reason}`; return; }
  const changed = name !== S.theme;
  S.theme = name;
  document.body.dataset.theme = name;
  $("mode-name").textContent = `${THEMES[name].sym}  ${THEMES[name].label} MODE`;
  $("mode-reason").textContent = reason || "";
  document.querySelectorAll(".swatches button").forEach(b => b.classList.toggle("on", b.dataset.theme === name));
  if (changed) { Particles.reset(); setTimeout(redrawCharts, 720); }   // after the CSS colour fade
}
function redrawCharts() { const fn = S.redraw[S.page]; if (fn) fn(); }

// ============================================== animated particle banner
const Particles = (() => {
  const cv = $("particles"), ctx = cv.getContext("2d");
  let parts = [], W = 0, H = 0, rot = 0, flash = 0;
  const resize = () => { W = cv.width = cv.clientWidth * devicePixelRatio; H = cv.height = cv.clientHeight * devicePixelRatio; reset(); };
  const rnd = (a, b) => a + Math.random() * (b - a);
  function spawn(init) {
    const m = S.theme, col = THEMES[m].particles[Math.floor(Math.random() * THEMES[m].particles.length)], d = devicePixelRatio;
    if (m === "blaze") return { x: rnd(0, W), y: init ? rnd(0, H) : H + 5, vx: rnd(-.3, .3) * d, vy: rnd(-1.7, -.5) * d, r: rnd(1.2, 3.4) * d, c: col, life: rnd(.6, 1), ph: rnd(0, 6) };
    if (m === "frost") return { x: rnd(0, W), y: init ? rnd(0, H) : -6, vx: rnd(-.2, .2) * d, vy: rnd(.35, 1.1) * d, r: rnd(1, 2.6) * d, c: col, life: 1, ph: rnd(0, 6), flake: Math.random() < .25 };
    if (m === "gale") return { x: init ? rnd(0, W) : -140 * d, y: rnd(6, H - 6), vx: rnd(4, 9) * d, vy: 0, len: rnd(40, 130) * d, c: col, life: 1, ph: rnd(0, 6), w: Math.random() < .3 ? 2 : 1 };
    if (m === "monsoon") return { x: rnd(0, W + 40), y: init ? rnd(0, H) : -14, vx: -1.6 * d, vy: rnd(7, 11) * d, len: rnd(8, 16) * d, c: col, life: 1 };
    return { x: rnd(0, W), y: init ? rnd(0, H) : H + 4, vx: rnd(.1, .5) * d, vy: rnd(-.45, -.15) * d, r: rnd(1, 2.6) * d, c: col, life: 1, ph: rnd(0, 6) };
  }
  function reset() {
    const n = { solar: 40, blaze: 90, frost: 90, gale: 30, monsoon: 120 }[S.theme] || 40;
    parts = Array.from({ length: n }, () => spawn(true));
  }
  function emblem() {
    const d = devicePixelRatio, cx = W - 80 * d, cy = H / 2, m = S.theme, a2 = THEMES[m].accent2;
    ctx.save(); ctx.translate(cx, cy);
    const glow = ctx.createRadialGradient(0, 0, 4, 0, 0, 120 * d);
    glow.addColorStop(0, THEMES[m].accent + "55"); glow.addColorStop(1, "transparent");
    ctx.fillStyle = glow; ctx.beginPath(); ctx.arc(0, 0, 120 * d, 0, 7); ctx.fill();
    ctx.strokeStyle = a2; ctx.lineCap = "round"; ctx.lineWidth = 3 * d;
    if (m === "solar" || m === "blaze") {
      for (let i = 0; i < 12; i++) { const a = rot + i * Math.PI / 6; ctx.beginPath(); ctx.moveTo(Math.cos(a) * 30 * d, Math.sin(a) * 30 * d); ctx.lineTo(Math.cos(a) * 44 * d, Math.sin(a) * 44 * d); ctx.stroke(); }
      ctx.fillStyle = m === "solar" ? "#ffb020" : "#ff4d1a"; ctx.beginPath(); ctx.arc(0, 0, 24 * d, 0, 7); ctx.fill();
    } else if (m === "frost") {
      for (let i = 0; i < 6; i++) { const a = rot + i * Math.PI / 3; ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(Math.cos(a) * 40 * d, Math.sin(a) * 40 * d); ctx.stroke();
        [-.6, .6].forEach(s => { const mx = Math.cos(a) * 24 * d, my = Math.sin(a) * 24 * d; ctx.beginPath(); ctx.moveTo(mx, my); ctx.lineTo(mx + Math.cos(a + s) * 11 * d, my + Math.sin(a + s) * 11 * d); ctx.stroke(); }); }
    } else if (m === "gale") {
      for (let k = 0; k < 3; k++) { const y = (k - 1) * 18 * d, off = Math.sin(rot * 3 + k) * 6 * d; ctx.beginPath(); ctx.moveTo(-48 * d + off, y); ctx.lineTo(10 * d + off, y);
        ctx.quadraticCurveTo(28 * d + off, y - 2 * d, 16 * d + off, y - 18 * d); ctx.stroke(); }
    } else {
      ctx.fillStyle = "#b8c6ea"; [[-14, 0, 12], [2, -8, 15], [17, 0, 11]].forEach(([x, y, r]) => { ctx.beginPath(); ctx.arc(x * d, y * d, r * d, 0, 7); ctx.fill(); });
      ctx.fillRect(-26 * d, -2 * d, 52 * d, 13 * d);
      ctx.strokeStyle = "#7fb6ff"; [-1, 0, 1].forEach(k => { const off = ((rot * 60 + k * 9) % 18) * d; ctx.beginPath(); ctx.moveTo(k * 14 * d, 16 * d + off); ctx.lineTo(k * 14 * d - 4 * d, 26 * d + off); ctx.stroke(); });
    }
    ctx.restore();
  }
  function tick(t) {
    ctx.clearRect(0, 0, W, H);
    emblem(); rot += .012;
    const m = S.theme;
    parts = parts.map(p => {
      const sway = ["blaze", "frost", "solar"].includes(m) ? Math.sin(t / 500 + p.ph) * .6 : 0;
      p.x += p.vx + sway; p.y += p.vy;
      if (m === "blaze") p.life -= .004;
      ctx.globalAlpha = Math.max(0, Math.min(1, p.life));
      if (m === "gale") { ctx.strokeStyle = p.c; ctx.lineWidth = p.w * devicePixelRatio; ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.quadraticCurveTo(p.x + p.len / 2, p.y - 3, p.x + p.len, p.y); ctx.stroke(); }
      else if (m === "monsoon") { ctx.strokeStyle = p.c; ctx.lineWidth = devicePixelRatio; ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p.x - p.len * .25, p.y + p.len); ctx.stroke(); }
      else if (p.flake) { ctx.fillStyle = p.c; ctx.font = `${10 * devicePixelRatio}px sans-serif`; ctx.fillText("❄", p.x, p.y); }
      else { ctx.fillStyle = p.c; ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, 7); ctx.fill(); }
      const out = p.y < -12 || p.y > H + 20 || p.x > W + 150 || p.x < -160 * devicePixelRatio || p.life <= 0;
      return out ? spawn(false) : p;
    });
    ctx.globalAlpha = 1;
    if (m === "monsoon") {
      if (flash > 0) { ctx.fillStyle = `rgba(255,255,255,${flash / 10})`; ctx.fillRect(0, 0, W, H); flash--; }
      else if (Math.random() < .004) flash = 4;
    }
    requestAnimationFrame(tick);
  }
  addEventListener("resize", resize);
  return { start() { resize(); requestAnimationFrame(tick); }, reset };
})();

// ================================================================ POP-UPS
function toast(title, msg, level = 1, ms = 6500) {
  const [color, sym] = STATUS[level];
  const el = document.createElement("div");
  el.className = "toast"; el.style.borderColor = color;
  el.innerHTML = `<span class="ic" style="color:${color}">${sym}</span><div><b>${esc(title)}</b><p>${esc(msg)}</p></div>`;
  el.onclick = () => close();
  $("toasts").appendChild(el);
  beep(level);
  const close = () => { el.classList.add("out"); setTimeout(() => el.remove(), 300); };
  setTimeout(close, ms);
  while ($("toasts").children.length > 4) $("toasts").firstChild.remove();
}
function modal(title, msg, actions = []) {
  const m = $("modal");
  m.innerHTML = `<div class="modal-box"><div class="modal-top"><div class="tri"></div><div><div class="lvl">SEVERE • EARLY WARNING</div>
    <h2>${esc(title)}</h2></div></div><p class="muted">${esc(msg)}</p><ul>${actions.map(a => `<li>${esc(a)}</li>`).join("")}</ul>
    <button class="btn" id="ack">ACKNOWLEDGE</button><div style="clear:both"></div></div>`;
  m.classList.remove("hidden");
  beep(3); setTimeout(() => beep(3), 350);
  $("ack").onclick = () => m.classList.add("hidden");
  $("ack").focus();
}
let audio;
function beep(level) {
  if (level < 2) return;
  try {
    audio = audio || new (window.AudioContext || window.webkitAudioContext)();
    const o = audio.createOscillator(), g = audio.createGain();
    o.frequency.value = level >= 3 ? 880 : 660; g.gain.value = .05;
    o.connect(g); g.connect(audio.destination); o.start(); o.stop(audio.currentTime + .18);
  } catch (e) { /* sound is optional */ }
}
function showAlerts(list) {
  (list || []).forEach(a => {
    const key = `${a.country}|${a.analyzer}|${a.label}|${a.source}|${Math.round(a.temperature || 0)}`;
    if (S.alerted.has(key)) return;
    S.alerted.add(key);
    if (a.level >= 3 && a.actions) modal(`${titleCase(a.label)} - ${a.country}`, a.message, a.actions);
    else toast(`${a.label} • ${a.country}`, a.message, a.level);
  });
}
const titleCase = s => s.toLowerCase().replace(/\b\w/g, c => c.toUpperCase());

// ================================================================ ROUTING
function go(page) {
  S.page = page;
  document.querySelectorAll(".page").forEach(p => p.classList.toggle("active", p.id === "page-" + page));
  document.querySelectorAll("#nav a").forEach(a => a.classList.toggle("active", a.dataset.page === page));
  location.hash = page;
  ({ overview: loadOverview, forecast: loadForecast, sql: loadSql, analytics: loadAnalytics, alerts: loadAlerts, project: loadProject })[page]();
}
function setCountry(c) {
  S.country = c; $("country").value = c;
  status(`Region changed to ${c}`);
  go(S.page);
}

// ======================================================= COMMAND CENTER
const EPA = { 1: ["Good", 0], 2: ["Moderate", 1], 3: ["Unhealthy (sensitive)", 2], 4: ["Unhealthy", 3], 5: ["Very unhealthy", 3], 6: ["Hazardous", 3] };
function kpi(label, ic, value, unit, note, level, meter, color) {
  const dot = level == null ? "" : `<span class="dot" style="background:${STATUS[level][0]}"></span>`;
  return `<div class="kpi"><div class="lab">${icon(ic, 22)}${label.toUpperCase()}</div><div class="val">${value}<small>${unit}</small></div>
    <div class="meter"><i style="width:${Math.max(0, Math.min(100, meter))}%;background:${color}"></i></div><div class="note">${dot}${esc(note)}</div></div>`;
}
async function loadOverview() {
  const c = S.country;
  $("ov-title").textContent = c;
  let d;
  try { d = await api(`/api/overview?country=${encodeURIComponent(c)}`); } catch (e) { status(e.message, true); return; }
  const r = d.reading, res = d.results;
  $("ov-sub").textContent = `Last reading ${r.time} • ${r.condition} • ${r.season} season • lon ${r.longitude.toFixed(2)}`;
  const top = Math.max(...res.map(x => x.level)), worst = res.reduce((a, b) => b.level > a.level ? b : a);
  $("ov-badge").textContent = `${STATUS[top][1]}  ${top ? worst.label : "ALL CLEAR"}`; $("ov-badge").style.background = STATUS[top][0];
  const t = r.temperature, hi = r.heat_index ?? t, gust = (r.gust_mph || 0) * 1.609;
  const [epaName, epaLvl] = EPA[r.aqi_index] || ["Unknown", 0];
  const kindRain = /thunder|storm/i.test(r.condition) ? "storm" : /snow|sleet/i.test(r.condition) ? "snow" : /rain|drizzle|shower/i.test(r.condition) ? "rain" : /mist|fog|haze/i.test(r.condition) ? "fog" : /cloud|overcast/i.test(r.condition) ? "cloud" : "sun";
  $("kpis").innerHTML = [
    kpi("Temperature", "thermo", t.toFixed(1), "°C", `${r.temp_change >= 0 ? "+" : ""}${r.temp_change.toFixed(1)}° vs previous${r.normal != null ? ` • normal ${r.normal.toFixed(1)}°` : ""}`, t >= 25 ? res[0].level : res[2].level, (t + 10) / 60 * 100, Charts.tempColor(t)),
    kpi("Feels like", "heat", hi.toFixed(0), "°C", titleCase(res[1].label), res[1].level, (hi + 10) / 70 * 100, Charts.tempColor(hi)),
    kpi("Humidity", "drop", r.humidity.toFixed(0), "%", r.humidity >= 70 ? "Muggy" : r.humidity <= 30 ? "Dry" : "Comfortable", null, r.humidity, "#4aa8ff"),
    kpi("Wind", "wind", r.wind_kph.toFixed(0), "km/h", `${r.wind_direction} • gusts ${gust.toFixed(0)} km/h`, res[3].level, r.wind_kph / 80 * 100, "#3fe0b0"),
    kpi("Rain", kindRain, r.precip_mm.toFixed(1), "mm", r.condition, res[4].level, r.precip_mm / 20 * 100, "#5aa9ff"),
    kpi("Air quality", "leaf", (r.ozone || 0).toFixed(0), "O₃ µg/m³", `US-EPA ${r.aqi_index} • ${epaName}`, epaLvl, (r.ozone || 0) / 250 * 100, "#3ecf8e"),
  ].join("");
  $("risk").innerHTML = res.map(x => `<div class="risk-row">${icon({ heat: "heat", snow: "snow", drop: "drop", wind: "wind", rain: "rain" }[x.icon] || "sun", 26)}
    <div class="txt"><b>${x.analyzer}</b><div class="msg" title="${esc(x.message)}">${esc(x.message)}</div></div>
    <span class="pill" style="background:${STATUS[x.level][0]}">${STATUS[x.level][1]} ${x.label}</span></div>`).join("");
  $("ov-normal").textContent = r.normal != null ? `Seasonal normal ${r.normal.toFixed(1)}°C • departure ${(t - r.normal >= 0 ? "+" : "")}${(t - r.normal).toFixed(1)}°C` : "";
  const draw = () => {
    Charts.gauge("dial", t, hi, `${c.toUpperCase()} • ${r.time.slice(4, 10)}`);
    const tr = d.trend, heat = S.meta.thresholds.heat_c;
    Charts.timeSeries("ov-trend", {
      thresholds: [{ y: heat, label: `Heatwave threshold ${heat}°C`, color: Charts.STATUS[3] }],
      series: [
        { name: "Daily reading", dates: tr.dates, values: tr.temp, color: Charts.css("muted"), style: "thin", hot: heat },
        { name: "7-day average", dates: tr.dates, values: tr.avg7, color: Charts.css("line"), glow: true, area: true },
        { name: "Seasonal normal", dates: tr.dates, values: tr.normal, color: Charts.css("accent2"), style: "dash", width: 1.4 },
      ] });
  };
  S.redraw.overview = draw; draw();
  setTheme(d.theme.name, d.theme.reason);
  showAlerts(d.alerts);
  loadOutlook(c);
}
async function loadOutlook(c) {
  $("ol-head").textContent = "AI ensemble is training on this region...";
  $("ol-text").textContent = "Seasonal-trend model + random forest are learning from the history.";
  $("days").innerHTML = "";
  let f;
  try { f = await api(`/api/forecast?country=${encodeURIComponent(c)}&horizon=7&model=AI%20Ensemble&backtest=0`); } catch (e) { $("ol-head").textContent = "Forecast unavailable"; return; }
  if (c !== S.country) return;
  $("days").innerHTML = f.dates.map((d, i) => {
    const dt = Charts.parse(d);
    return `<div class="day ${f.risk_level[i] >= 2 ? "alert" : ""}"><b>${d3.timeFormat("%a")(dt)}</b><div class="d">${d3.timeFormat("%d %b")(dt)}</div>
      ${icon(f.kind[i], 40)}<div class="t" style="color:${Charts.tempColor(f.temp[i])}">${f.temp[i].toFixed(0)}°</div>
      <div class="r">${f.low[i].toFixed(0)}° / ${f.high[i].toFixed(0)}°</div><div class="rain">☂ ${(f.rain[i] * 100).toFixed(0)}%</div>
      <div class="rb"><i style="width:${f.rain[i] * 100}%"></i></div></div>`;
  }).join("");
  const worst = Math.max(...f.risk_level), wet = f.rain.filter(p => p >= .5).length;
  let head = ["Calm week ahead", "Warm spell ahead - stay alert", "Early warning issued", "Severe early warning"][worst];
  if (!worst && wet >= 4) head = `Wet week ahead - rain likely on ${wet} of 7 days`;
  $("ol-head").innerHTML = `<span style="color:${STATUS[worst][0]}">${STATUS[worst][1]}</span> ${head}`;
  $("ol-text").textContent = f.summary;
  (f.alerts || []).forEach(a => toast(`Forecast early warning • ${a.country}`, a.message, a.level, 9000));
}

// ========================================================= FORECAST LAB
function seg(el, options, value, onPick) {
  $(el).innerHTML = options.map(([v, t]) => `<button data-v="${esc(v)}" class="${v == value ? "on" : ""}">${t}</button>`).join("");
  $(el).querySelectorAll("button").forEach(b => b.onclick = () => {
    $(el).querySelectorAll("button").forEach(x => x.classList.toggle("on", x === b)); onPick(b.dataset.v);
  });
}
const SHORT = { "AI Ensemble": "AI Ensemble", "Random Forest (ML)": "Random Forest", "Seasonal-Trend AR": "Seasonal AR" };
async function loadForecast() {
  const c = S.country;
  $("fc-title").textContent = `AI Forecast Lab • ${c}`;
  $("fc-head").textContent = `Training ${S.model} on ${c}'s history...`;
  $("fc-summary").textContent = "Fitting seasonal-trend regression, random forest, humidity, wind and rain models + a 30-day backtest.";
  $("fc-spin").classList.remove("hidden");
  let f;
  try { f = await api(`/api/forecast?country=${encodeURIComponent(c)}&horizon=${S.horizon}&model=${encodeURIComponent(S.model)}`); }
  catch (e) { $("fc-head").textContent = "Forecast failed"; $("fc-summary").textContent = e.message; $("fc-spin").classList.add("hidden"); return; }
  $("fc-spin").classList.add("hidden");
  if (c !== S.country) return;
  S.forecast = f;
  const adv = f.advisory, [col, sym] = STATUS[adv.level];
  $("fc-adv").style.borderLeftColor = col; $("fc-adv-icon").textContent = sym; $("fc-adv-icon").style.color = col;
  $("fc-head").textContent = adv.headline; $("fc-summary").textContent = f.summary;
  showStake();
  const best = Object.entries(f.metrics).sort((a, b) => a[1].MAE - b[1].MAE)[0]?.[0];
  $("fc-metrics").innerHTML = `<tr><th>MODEL</th><th>MAE</th><th>RMSE</th><th>±3°C ACC</th></tr>` + Object.entries(f.metrics).map(([k, m]) =>
    `<tr class="${k === best ? "best" : ""}"><td>${k === best ? "★ " : ""}${SHORT[k] || k}</td><td>${m.MAE.toFixed(2)}°</td><td>${m.RMSE.toFixed(2)}°</td><td>${m.within3.toFixed(0)}%</td></tr>`).join("");
  $("fc-table").innerHTML = `<tr><th>DATE</th><th>SKY</th><th>TEMP</th><th>RANGE</th><th>RAIN</th><th>HUMIDITY</th><th>RISK</th><th>MESSAGE</th></tr>` +
    f.dates.map((d, i) => `<tr data-i="${i}"><td>${d3.timeFormat("%a %d %b")(Charts.parse(d))}</td><td>${icon(f.kind[i], 22)}</td><td>${f.temp[i].toFixed(1)}°C</td>
      <td>${f.low[i].toFixed(0)}–${f.high[i].toFixed(0)}°</td><td>${(f.rain[i] * 100).toFixed(0)}%</td><td>${f.humidity[i].toFixed(0)}%</td>
      <td class="l${f.risk_level[i]}">${STATUS[f.risk_level[i]][1]} ${f.risk_label[i]}</td><td>${esc(f.messages[i].split("->").pop().trim())}</td></tr>`).join("");
  $("fc-table").querySelectorAll("tr[data-i]").forEach(tr => tr.onclick = () => { const i = +tr.dataset.i; toast(d3.timeFormat("%A %d %B")(Charts.parse(f.dates[i])), f.messages[i], f.risk_level[i], 9000); });
  const draw = () => {
    const heat = S.meta.thresholds.heat_c, line = Charts.css("line");
    const pk = f.temp.indexOf(Math.max(...f.temp));
    const lastH = f.history.dates.length - 1;
    Charts.timeSeries("fc-main", {
      shade: { from: f.dates[0] }, vline: { date: f.history.dates[lastH], label: "last observation → forecast" },
      thresholds: [{ y: heat, label: `Heatwave ${heat}°C`, color: Charts.STATUS[3] }],
      band: { dates: [f.history.dates[lastH], ...f.dates], low: [f.history.temp[lastH], ...f.low], high: [f.history.temp[lastH], ...f.high], color: Charts.css("band") },
      peak: { date: f.dates[pk], value: f.high[pk], text: `peak ${f.temp[pk].toFixed(1)}°C` },
      series: [
        { name: "Observed", dates: f.history.dates, values: f.history.temp, color: Charts.css("muted"), style: "thin" },
        { name: `AI forecast (${SHORT[f.model]})`, dates: [f.history.dates[lastH], ...f.dates], values: [f.history.temp[lastH], ...f.temp], color: line, glow: true, markers: Charts.tempColor },
        { name: "Seasonal normal", dates: f.dates, values: f.normal, color: Charts.css("accent2"), style: "dash", width: 1.4 },
      ],
      legend: [{ name: "Observed", color: Charts.css("muted"), width: 1.4 }, { name: "80% band", color: Charts.css("band"), type: "band" },
               { name: `AI forecast (${SHORT[f.model]})`, color: line }, { name: "Seasonal normal", color: Charts.css("accent2"), dash: "5 4" }] });
    Charts.vbars("fc-rain", { dates: f.dates, values: f.rain.map(p => p * 100), ref: { v: 50, label: "likely" }, yLabel: "rain %",
      colorFn: v => d3.interpolateRgb("#1d3557", "#8cc8ff")(v / 100) });
    Charts.timeSeries("fc-hum", { yMin: 0, yMax: 100, yLabel: "%", series: [
      { name: "Humidity", dates: f.dates, values: f.humidity, color: "#5ab0ff", glow: true, area: true, fmt: v => v.toFixed(0) + "%" }] });
    if (f.test) {
      const ser = [{ name: "Actual", dates: f.test.dates, values: f.test.actual, color: Charts.css("text"), width: 2 }];
      Object.entries(f.metrics).forEach(([k, m], i) => ser.push({ name: { "AI Ensemble": "Ensemble", "Random Forest (ML)": "Forest", "Seasonal-Trend AR": "Seasonal" }[k] || k, dates: f.test.dates, values: m.pred, color: Charts.CATEGORICAL[i], width: 1.6 }));
      Charts.timeSeries("fc-bt", { series: ser });
    }
  };
  S.redraw.forecast = draw; draw();
  setTheme(f.theme.name, f.theme.reason);
  if (adv.level >= 2) toast(`Early warning • ${f.country}`, adv.headline, adv.level, 8000);
  (f.alerts || []).forEach(a => status(`${a.label} forecast saved to the alerts table`));
  status(`Forecast ready • ${c} • ${f.model} • ${f.horizon} days`);
}
function showStake() { if (S.forecast) $("fc-advice").textContent = S.forecast.advisory.advice[S.stake] || ""; }
function exportCsv(name, header, rows) {
  const q = v => /[",\n]/.test(String(v ?? "")) ? `"${String(v).replace(/"/g, '""')}"` : (v ?? "");
  const text = [header, ...rows].map(r => r.map(q).join(",")).join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "text/csv" })); a.download = name; a.click();
}

// ================================================================ SQL LAB
const KW = new Set(`select from where and or not in between like is null order by asc desc group having limit offset distinct count avg min max sum as insert into values update set delete create table drop alter add column view index join left inner on case when then else end round strftime date datetime cast real integer text primary key autoincrement if exists union all substr`.split(/\s+/));
function highlight() {
  const t = $("sql").value;
  const html = esc(t).replace(/(--[^\n]*)|('(?:[^']|'')*'?)|\b(\d+(?:\.\d+)?)\b|\b([A-Za-z_]+)\b/g, (m, com, str, num, word) =>
    com ? `<span class="hl-com">${com}</span>` : str ? `<span class="hl-str">${str}</span>` : num ? `<span class="hl-num">${num}</span>` :
    KW.has(word.toLowerCase()) ? `<span class="hl-kw">${word}</span>` : word);
  $("sql-hl").innerHTML = html + "\n";
  $("sql-hl").scrollTop = $("sql").scrollTop;
}
function loadSql() {
  if (!$("lib-presets").innerHTML) {
    $("lib-presets").innerHTML = S.meta.presets.map(g => `<div class="lib-group">${esc(g.group)}</div>` +
      g.items.map(it => `<div class="lib-item" data-sql="${esc(it.sql)}">${esc(it.name)}</div>`).join("")).join("");
    $("lib-presets").querySelectorAll(".lib-item").forEach(el => {
      el.onclick = () => { $("lib-presets").querySelectorAll(".lib-item").forEach(x => x.classList.toggle("on", x === el)); $("sql").value = el.dataset.sql; highlight(); };
      el.ondblclick = () => runSql();
    });
    seg("lib-tabs", [["presets", "Presets"], ["schema", "Schema"], ["history", "History"]], "presets", v =>
      ["presets", "schema", "history"].forEach(k => $("lib-" + k).classList.toggle("hidden", k !== v)));
    $("sql").value = S.meta.presets[1].items[0].sql; highlight();
    loadSchema();
    runSql(false);
  } else if (S.sql) { S.redraw.sql(); setTheme(S.sql.theme.name, S.sql.theme.reason); }
}
async function loadSchema() {
  const d = await api("/api/schema");
  $("lib-schema").innerHTML = Object.entries(d.schema).map(([t, cols]) => `<div class="lib-group">▤ ${esc(t)}</div>` +
    cols.map(c => `<div class="lib-col">${esc(c)}</div>`).join("")).join("");
  $("lib-schema").querySelectorAll(".lib-col").forEach(el => el.onclick = () => insertAtCursor(el.textContent + " "));
}
function insertAtCursor(text) {
  const ta = $("sql"), s = ta.selectionStart;
  ta.value = ta.value.slice(0, s) + text + ta.value.slice(ta.selectionEnd); ta.selectionStart = ta.selectionEnd = s + text.length; ta.focus(); highlight();
}
async function runSql(confirmIt = true) {
  const text = $("sql").value.trim();
  if (!text) return sqlError("The editor is empty - type a query first.");
  const words = new Set(text.toLowerCase().match(/[a-z]+/g));
  const risky = ["insert", "update", "delete", "drop", "alter", "replace", "create"].filter(w => words.has(w));
  if (risky.length && confirmIt) {
    let extra = words.has("drop") && /weather_data/i.test(text) ? "\n\nWARNING: dropping weather_data empties the dashboard (use 'Reset database' to restore)." : "";
    if (!confirm(`This query will change climate.db (${risky.join(", ").toUpperCase()}).\nAll dashboard pages will use the new data.${extra}\n\nContinue?`)) return;
  }
  $("sql-msg").className = "small muted"; $("sql-msg").textContent = "Running query...";
  let d;
  try { d = await api("/api/sql", { sql: text, country: S.country }); } catch (e) { return sqlError(e.message); }
  S.sql = d;
  if (!S.history.length || S.history[S.history.length - 1] !== text) {
    S.history.push(text);
    $("lib-history").innerHTML = S.history.slice().reverse().map((h, i) => `<div class="lib-item mono" data-i="${S.history.length - 1 - i}">${esc(h.replace(/\s+/g, " ").slice(0, 90))}</div>`).join("");
    $("lib-history").querySelectorAll(".lib-item").forEach(el => el.onclick = () => { $("sql").value = S.history[+el.dataset.i]; highlight(); });
  }
  if (d.kind === "select") {
    $("res-title").textContent = `Results • ${d.rowcount} row(s)`;
    $("sql-table").innerHTML = `<tr>${d.columns.map(c => `<th>${esc(c)}</th>`).join("")}</tr>` + d.rows.slice(0, 1500).map(r =>
      `<tr>${r.map(v => `<td>${v == null ? '<span class="faint">NULL</span>' : esc(typeof v === "number" && !Number.isInteger(v) ? v.toFixed(2) : v)}</td>`).join("")}</tr>`).join("");
    const ci = d.columns.map(c => c.toLowerCase()).indexOf("country");
    if (ci >= 0) $("sql-table").querySelectorAll("tr").forEach((tr, i) => i && (tr.ondblclick = () => setCountryAndGo(d.rows[i - 1][ci])));
    S.redraw.sql = () => Charts.sqlAuto("sql-chart", d.columns, d.rows);
    S.redraw.sql();
  }
  $("sql-msg").textContent = "✔ " + d.message;
  const th = THEMES[d.theme.name];
  $("sql-chip").textContent = `${th.sym}  ${th.label}`; $("sql-chip").style.background = th.accent; $("sql-chip").style.color = th.text;
  setTheme(d.theme.name, d.theme.reason);
  if (d.data_changed) {
    loadSchema(); updateDataInfo(d.rows_total);
    if (d.countries) fillCountries(d.countries);
    toast("Dashboard updated", "SQL change applied to climate.db. Every page now uses the new data.", 0, 4000);
    showAlerts(d.alerts);
  }
}
function sqlError(m) { $("sql-msg").className = "small err"; $("sql-msg").textContent = "✖ " + m; toast("Query failed", m, 2, 5000); }
function setCountryAndGo(c) { if (S.meta.countries.includes(c)) { S.country = c; $("country").value = c; go("overview"); } }

// ============================================================== ANALYTICS
function chips(list) { $("an-chips").innerHTML = list.map(([k, v, col]) => `<div class="c"><div>${k.toUpperCase()}</div><div style="${col ? "color:" + col : ""}">${esc(v)}</div></div>`).join(""); }
async function loadAnalytics() {
  if (!$("an-mode").innerHTML) seg("an-mode", [["country", "Region insights"], ["global", "Global hotspots"]], S.anMode, v => { S.anMode = v; loadAnalytics(); });
  $("an-country").classList.toggle("hidden", S.anMode !== "country");
  $("an-global").classList.toggle("hidden", S.anMode !== "global");
  if (S.anMode === "country") {
    $("an-title").textContent = `Analytics • ${S.country}`;
    const d = await api(`/api/analytics/country?country=${encodeURIComponent(S.country)}`).catch(e => status(e.message, true));
    if (!d) return;
    const s = d.stats;
    chips([["30-day mean", `${s.mean_c.toFixed(1)}°C / ${s.mean_f.toFixed(0)}°F`, Charts.tempColor(s.mean_c)], ["hottest (reduce)", `${s.hottest_c.toFixed(1)}°C`, Charts.tempColor(s.hottest_c)],
           ["coldest (reduce)", `${s.coldest_c.toFixed(1)}°C`, Charts.tempColor(s.coldest_c)], ["heatwave days (filter)", s.heatwave_days], ["rainy days", s.rainy_days],
           ["longest ≥ 40° spell", `${d.streak} days`], ["levels seen (set)", s.levels_seen.join(", ")]]);
    $("an-sub").textContent = `${d.records.toLocaleString()} readings • ${d.span}`;
    const draw = () => {
      const months = ["J", "F", "M", "A", "M ", "J ", "J  ", "A ", "S", "O", "N", "D"];
      const full = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      Charts.heatmap("an-cal", { rows: d.matrix.years.map(String), cols: months, values: d.matrix.values, colorFn: Charts.tempColor,
        legend: { min: -25, max: 47 }, tipFmt: (r, c, v) => `<b>${full[months.indexOf(c)]} ${r}</b><br>average ${v.toFixed(1)}°C` });
      Charts.boxes("an-season", { groups: Object.entries(d.seasons).map(([name, g]) => ({ name, ...g })) });
      Charts.windRose("an-rose", d.rose);
      const div = d3.scaleLinear().domain([-1, 0, 1]).range(["#3987e5", "#6f7d8f", "#d95926"]);
      Charts.heatmap("an-corr", { rows: d.corr.labels, cols: d.corr.labels, values: d.corr.values, colorFn: div, fmt: v => (v >= 0 ? "+" : "") + v.toFixed(2),
        legend: { min: -1, max: 1 }, tipFmt: (r, c, v) => `<b>${r} vs ${c}</b><br>correlation ${v.toFixed(2)}` });
    };
    S.redraw.analytics = draw; draw();
    setTheme(d.theme.name, d.theme.reason);
  } else {
    $("an-title").textContent = "Analytics • World";
    const d = await api("/api/analytics/global").catch(e => status(e.message, true));
    if (!d) return;
    const c = d.chips;
    chips([["countries tracked", c.tracked], ["in heatwave now", c.above, c.above ? "#ff4d4f" : null], ["below freezing now", c.below],
           ["hottest now", c.hottest, Charts.tempColor(c.hottest_t)], ["coldest now", c.coldest, Charts.tempColor(c.coldest_t)], ["top hotspot (60 d)", c.top_hotspot]]);
    $("an-sub").textContent = `${d.rows.toLocaleString()} readings from ${d.countries} countries`;
    const draw = () => {
      Charts.hbars("an-hot", { labels: d.hot.map(h => h.country), values: d.hot.map(h => h.heat_days), colors: d.hot.map(h => Charts.tempColor(h.max_temp)),
        notes: d.hot.map(h => `${h.heat_days} d   max ${h.max_temp.toFixed(1)}°`), xLabel: `readings ≥ ${S.meta.thresholds.heat_c}°C in the last 60 days`,
        tipFmt: i => `${d.hot[i].heat_days} heatwave readings<br>max ${d.hot[i].max_temp.toFixed(1)}°C` });
      Charts.scatter("an-band", { points: d.snapshot.map(p => ({ x: p.lon, y: p.temp, label: p.country })), xDomain: [-180, 180],
        xLabel: "Longitude (°E) - each dot is a country's latest reading",
        bands: [{ from: S.meta.thresholds.heat_c, to: 60, color: "#ff4d4f" }, { from: -60, to: 10, color: "#4aa8ff" }] });
      Charts.hbars("an-cold", { labels: d.cold.map(h => h.country), values: d.cold.map(h => h.avg_temp), colors: d.cold.map(h => Charts.tempColor(h.avg_temp)),
        notes: d.cold.map(h => `${h.avg_temp.toFixed(1)}°  (min ${h.min_temp.toFixed(0)}°)`), xLabel: "average °C, last 60 days" });
      Charts.timeSeries("an-pulse", { yLabel: "global °C", series: [{ name: "Weekly global mean", dates: d.weekly.dates, values: d.weekly.temp, color: Charts.css("line"), glow: true, area: true }] });
    };
    S.redraw.analytics = draw; draw();
    setTheme(d.theme.name, d.theme.reason);
  }
}

// ========================================================= ALERTS & AWS
const THRESH = [["heat_c", "Heatwave °C"], ["wind_kph", "High wind km/h"], ["severe_heat_c", "Severe heat °C"], ["heat_index_c", "Heat index °C"], ["cold_c", "Cold wave °C"], ["rain_mm", "Rain mm"]];
let monTimer = null;
function loadAlerts() {
  if (!$("watch").options.length) {
    const def = ["India", "Kuwait", "Pakistan", "Saudi Arabia", "Iceland", "Russia"];
    $("watch").innerHTML = S.meta.countries.map(c => `<option ${def.includes(c) ? "selected" : ""}>${esc(c)}</option>`).join("");
    $("thresholds").innerHTML = THRESH.map(([k, t]) => `<span>${t}</span><input type="number" step="0.5" data-k="${k}" value="${S.meta.thresholds[k]}">`).join("");
    $("thresholds").querySelectorAll("input").forEach(inp => inp.onchange = async () => {
      const d = await api("/api/thresholds", { [inp.dataset.k]: inp.value }); S.meta.thresholds = d.thresholds; status(`Threshold ${inp.dataset.k} = ${inp.value}`);
    });
  }
  loadAlertLog();
  S.redraw.alerts = () => Charts.liveLines("al-live", S.streams || {}, S.meta.thresholds.heat_c);
  S.redraw.alerts();
}
async function loadAlertLog() {
  const d = await api("/api/alerts");
  $("al-log").innerHTML = `<tr><th>TIME</th><th>COUNTRY</th><th>TYPE</th><th>SEVERITY</th><th>TEMP</th><th>SOURCE</th></tr>` +
    d.rows.map(r => `<tr><td>${esc(String(r[1]).slice(5))}</td><td>${esc(r[2])}</td><td>${esc(r[3])}</td><td class="${/SEVERE|EXTREME|STORM|HEAVY/.test(r[4]) ? "l3" : "l2"}">${esc(r[4])}</td><td>${r[5] ?? ""}</td><td>${esc(r[7])}</td></tr>`).join("");
}
async function toggleMonitor() {
  if (S.monRunning) {
    await api("/api/monitor/stop", {}); S.monRunning = false;
    $("mon-toggle").textContent = "▶ Start AWS monitor"; $("mon-state").textContent = "● monitor stopped"; $("mon-state").style.color = "";
    clearInterval(monTimer); pollMonitor(); return;
  }
  const sel = [...$("watch").selectedOptions].map(o => o.value).slice(0, 6);
  if (!sel.length) return toast("Pick stations", "Select at least one country in the watch-list.", 1);
  try { await api("/api/monitor/start", { countries: sel }); } catch (e) { return toast("Monitor", e.message, 2); }
  S.monRunning = true; S.monSince = 0; $("al-feed").innerHTML = "";
  $("mon-toggle").textContent = "■ Stop AWS monitor";
  $("mon-state").textContent = `● LIVE • ${sel.length} stations • 3 sensor threads`; $("mon-state").style.color = "#3ecf8e";
  monTimer = setInterval(pollMonitor, 1000);
}
async function pollMonitor() {
  let d; try { d = await api(`/api/monitor/poll?since=${S.monSince}`); } catch (e) { return; }
  if (d.events.length) {
    S.monSince = d.events[d.events.length - 1].id;
    $("al-feed").insertAdjacentHTML("afterbegin", d.events.reverse().map(e => `<span class="${e.kind}">${esc(e.text)}</span>`).join("\n") + "\n");
    if ($("al-feed").childElementCount > 400) $("al-feed").innerHTML = $("al-feed").innerHTML.split("\n").slice(0, 300).join("\n");
  }
  S.streams = d.streams;
  $("al-stations").innerHTML = `<tr><th>STATION</th><th>TEMP</th><th>HUMIDITY</th><th>WIND</th><th>STATUS</th></tr>` +
    Object.entries(d.live).map(([c, s]) => { const lv = s.level || 0;
      return `<tr><td>${esc(c)}</td><td>${s.temperature != null ? s.temperature.toFixed(1) + "°" : "-"}</td><td>${s.humidity != null ? s.humidity.toFixed(0) + "%" : "-"}</td>
      <td>${s.wind_kph != null ? s.wind_kph.toFixed(0) : "-"}</td><td class="l${lv}">${STATUS[lv][1]} ${esc(s.status || "waiting...")}${s.fault ? ` <span class="faint">(fault ${s.fault})</span>` : ""}</td></tr>`; }).join("");
  $("al-stats").textContent = `threads alive: ${d.stats.threads} • readings: ${d.stats.readings} • faults caught: ${d.stats.faults}`;
  if (S.page === "alerts") S.redraw.alerts();
  if (d.alerts.length) {
    loadAlertLog();
    d.alerts.forEach(a => {
      if (!$("popups").checked) return;
      if (a.level >= 3 && a.actions) modal(`${titleCase(a.label)} - ${a.country}`, a.message, a.actions);
      else toast(`AWS ${a.country}: ${a.label}`, a.message, a.level);
    });
    const a = d.alerts[d.alerts.length - 1];
    const th = /Heat/.test(a.analyzer) ? "blaze" : a.analyzer === "Cold Wave" ? "frost" : a.analyzer === "Wind" ? "gale" : null;
    if (th) setTheme(th, `AWS sensor: ${a.label.toLowerCase()} at ${a.country}`);
  }
}

// ================================================================ PROJECT
function loadProject() {
  const m = S.meta;
  $("pj-usecase").textContent = `${m.use_case.id} • ${m.use_case.title}`;
  $("pj-student").innerHTML = ["name", "roll", "batch", "class", "course", "college"].map(k => `<tr><td>${k.toUpperCase()}</td><td>${esc(m.student[k])}</td></tr>`).join("");
  $("pj-phases").innerHTML = m.phases.map(([n, t, w, f]) => `<div class="card"><div class="tiny" style="color:var(--accent)">PHASE ${n}</div><h3>${esc(t)}</h3><p>${esc(w)}</p><div class="where">${esc(f)}</div></div>`).join("");
  $("pj-exps").innerHTML = m.experiments.map(([n, t, w, f]) => `<div class="card"><div><span class="tag">EXP ${n}</span><b>${esc(t)}</b></div><p>${esc(w)}</p><div class="where">→ ${esc(f)}</div></div>`).join("");
  $("pj-demo").innerHTML = m.demo.map(x => `<li>${esc(x)}</li>`).join("");
  const r = m.clean_report;
  $("pj-clean").textContent = r && r.raw_rows ? [`Raw rows in CSV            ${r.raw_rows.toLocaleString()}`, `Invalid dates / values     ${r.bad_dates_or_values}`,
    `Out-of-range sensor values ${r.out_of_range}`, `Rare / mis-spelt countries ${r.rare_country_rows}`, `Duplicate readings         ${r.duplicates.toLocaleString()}`,
    `Clean rows stored          ${r.clean_rows.toLocaleString()}  (${r.countries} countries)`].join("\n")
    : `Database built on an earlier run.\nRows now in weather_data   ${m.rows.toLocaleString()}\nCountries                  ${m.n_countries}\n(Use 'Reset database' in the SQL Lab to rebuild\n and see the full cleaning report.)`;
  S.redraw.project = null;
}

// ================================================================== SETUP
function fillCountries(list) {
  S.meta.countries = list;
  $("country").innerHTML = list.map(c => `<option ${c === S.country ? "selected" : ""}>${esc(c)}</option>`).join("");
}
function updateDataInfo(rows) {
  const m = S.meta; if (rows) m.rows = rows;
  $("data-info").innerHTML = `DATA ${m.rows.toLocaleString()} readings<br>${m.n_countries} countries<br>latest reading ${m.latest.slice(0, 10)}<br>source V_S_DATA_SET_CLIMATE.csv`;
}
function wire() {
  document.querySelectorAll("#nav a").forEach(a => a.onclick = () => go(a.dataset.page));
  document.querySelectorAll("[data-goto]").forEach(b => b.onclick = () => go(b.dataset.goto));
  $("country").onchange = e => setCountry(e.target.value);
  $("quick").innerHTML = ["India", "Kuwait", "Pakistan", "Iceland", "Russia", "Brazil"].filter(c => S.meta.countries.includes(c)).map(c => `<button>${c}</button>`).join("");
  $("quick").querySelectorAll("button").forEach(b => b.onclick = () => setCountry(b.textContent));
  $("swatches").innerHTML = Object.entries(THEMES).map(([k, t]) => `<button data-theme="${k}" title="${t.label}" style="background:${t.accent};border-color:${t.accent2};color:${t.text}">${t.sym}</button>`).join("");
  $("swatches").querySelectorAll("button").forEach(b => b.onclick = () => { S.auto = false; $("auto-theme").checked = false; setTheme(b.dataset.theme, `Manual: ${THEMES[b.dataset.theme].label} theme`, true); });
  $("auto-theme").onchange = e => { S.auto = e.target.checked; if (S.auto) go(S.page); };
  $("stop-server").onclick = async () => {
    if (!confirm("Stop the HeatGuard AI server?\nYou can start it again with START_DASHBOARD.bat.")) return;
    try { await api("/api/shutdown", {}); } catch (e) { /* server is closing */ }
    document.body.innerHTML = `<div style="grid-column:1/-1;grid-row:1/-1;display:grid;place-items:center;text-align:center"><div><h1>Server stopped</h1><p class="muted">You can close this tab. Double-click START_DASHBOARD.bat to open the dashboard again.</p></div></div>`;
  };
  seg("fc-horizon", [[7, "7 days"], [14, "14 days"], [30, "30 days"]], S.horizon, v => { S.horizon = +v; loadForecast(); });
  seg("fc-model", S.meta.models.map(m => [m, SHORT[m] || m]), S.model, v => { S.model = v; loadForecast(); });
  seg("fc-stake", S.meta.stakeholders.map(s => [s, s]), S.stake, v => { S.stake = v; showStake(); });
  $("fc-run").onclick = loadForecast;
  $("fc-save").onclick = async () => { if (!S.forecast) return; const d = await api("/api/forecast/save", { country: S.forecast.country, horizon: S.forecast.horizon, model: S.forecast.model });
    toast("Forecast saved to SQLite", `${d.saved} rows added to the 'forecasts' table. Try: SELECT * FROM forecasts in the SQL Lab.`, 0); };
  $("fc-csv").onclick = () => { const f = S.forecast; if (!f) return;
    exportCsv(`forecast_${f.country}.csv`, ["date", "temp_c", "low_c", "high_c", "humidity_pct", "rain_chance_pct", "risk", "message"],
      f.dates.map((d, i) => [d, f.temp[i].toFixed(1), f.low[i].toFixed(1), f.high[i].toFixed(1), f.humidity[i].toFixed(0), (f.rain[i] * 100).toFixed(0), f.risk_label[i], f.messages[i]])); };
  $("sql").addEventListener("input", highlight);
  $("sql").addEventListener("scroll", () => { $("sql-hl").scrollTop = $("sql").scrollTop; });
  $("sql").addEventListener("keydown", e => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); runSql(); }
    if (e.key === "Tab") { e.preventDefault(); insertAtCursor("    "); }
  });
  $("sql-run").onclick = () => runSql();
  $("sql-clear").onclick = () => { $("sql").value = ""; highlight(); $("sql").focus(); };
  $("sql-csv").onclick = () => S.sql && S.sql.kind === "select" && exportCsv("query_result.csv", S.sql.columns, S.sql.rows);
  $("sql-reset").onclick = async () => {
    if (!confirm("Rebuild climate.db from the original CSV file?\nAll changes to weather_data will be lost.")) return;
    $("sql-msg").textContent = "Rebuilding database from CSV (about 10 seconds)...";
    const d = await api("/api/reset", {}); S.meta.clean_report = d.report; updateDataInfo(d.rows); loadSchema();
    $("sql-msg").textContent = "✔ Database rebuilt from CSV"; toast("Database rebuilt", `${d.rows.toLocaleString()} clean rows restored.`, 0);
  };
  $("mon-toggle").onclick = toggleMonitor;
  $("mon-scan").onclick = async () => { const d = await api("/api/scan", {}); loadAlertLog(); pollMonitor();
    toast("Scan complete", `${d.count} warnings found in the latest reading of ${d.countries} countries.`, d.count ? 2 : 0); };
  document.querySelectorAll("[data-inject]").forEach(b => b.onclick = async () => {
    if (!S.monRunning) return toast("Monitor is off", "Start the AWS monitor first.", 1);
    await api("/api/monitor/inject", { kind: b.dataset.inject, country: S.country }); });
  document.addEventListener("keydown", e => { if (e.key === "Escape") $("modal").classList.add("hidden"); });
  // redraw charts whenever their box changes size (window resize, content loading below, etc.)
  let rt; const sizes = new Map();
  const ro = new ResizeObserver(entries => {
    let changed = false;
    entries.forEach(e => {
      const k = e.target, s = [Math.round(e.contentRect.width), Math.round(e.contentRect.height)], old = sizes.get(k);
      if (!old || Math.abs(old[0] - s[0]) > 3 || Math.abs(old[1] - s[1]) > 3) { sizes.set(k, s); if (old) changed = true; }
    });
    if (changed) { clearTimeout(rt); rt = setTimeout(redrawCharts, 180); }
  });
  document.querySelectorAll(".chart").forEach(el => ro.observe(el));
  setInterval(() => $("clock").textContent = new Date().toLocaleString("en-GB", { weekday: "short", day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" }), 1000);
}

async function boot() {
  Particles.start();
  for (;;) {                     // wait until the Python back end has loaded the data
    try {
      const s = await api("/api/status");
      $("splash-fill").style.width = Math.max(3, s.progress * 100) + "%";
      $("splash-msg").textContent = s.error ? "Error: " + s.error : s.message;
      if (s.ready) break;
    } catch (e) { $("splash-msg").textContent = "Waiting for the Python server..."; }
    await new Promise(r => setTimeout(r, 400));
  }
  S.meta = await api("/api/meta");
  S.country = S.meta.default_country;
  fillCountries(S.meta.countries); updateDataInfo(); wire();
  $("splash").style.transition = "opacity .5s"; $("splash").style.opacity = 0; setTimeout(() => $("splash").remove(), 500);
  const start = (location.hash || "#overview").slice(1);
  go(["overview", "forecast", "sql", "analytics", "alerts", "project"].includes(start) ? start : "overview");
  setTimeout(async () => {
    const st = await api("/api/startup");
    if (st.hot.length) toast(`Heatwave watch: ${st.hot.length} countr${st.hot.length === 1 ? "y" : "ies"} ≥ ${S.meta.thresholds.heat_c}°C now`,
      st.hot.slice(0, 4).map(h => `${h.country} ${h.temperature.toFixed(0)}°`).join(", "), 2, 9000);
    if (st.cold.length) toast(`Cold watch: ${st.cold.length} below 0°C`, st.cold.slice(0, 4).map(h => h.country).join(", "), 1, 8000);
    toast("HeatGuard AI is live", `${st.rows.toLocaleString()} readings from ${st.countries} countries loaded from SQLite.`, 0, 5000);
  }, 1200);
}
boot();
