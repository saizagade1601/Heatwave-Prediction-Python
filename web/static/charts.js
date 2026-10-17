/* =====================================================================
   charts.js  -  small chart toolkit built on D3 (bundled, works offline)
   Colour rules: temperature always uses the same cold-blue -> hot-red
   scale; theme colours only style lines, bands and chrome.
   ===================================================================== */
const Charts = (() => {
  const TEMP_STOPS = [[-25, "#3f5fd8"], [0, "#4aa8ff"], [12, "#79d3dc"], [22, "#ffd36b"], [31, "#ff9a2e"], [39, "#ff4d1a"], [47, "#c3001f"]];
  const CATEGORICAL = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#9085e9"];
  const STATUS = ["#3ecf8e", "#f2c94c", "#ff8c2a", "#ff4d4f"];
  let uid = 0;

  const css = n => getComputedStyle(document.body).getPropertyValue("--" + n).trim();
  const parse = d3.timeParse("%Y-%m-%d");
  const fmtDay = d3.timeFormat("%a %d %b %Y");

  function tempColor(t) {
    if (t == null || isNaN(t)) return "#888";
    if (t <= TEMP_STOPS[0][0]) return TEMP_STOPS[0][1];
    for (let i = 1; i < TEMP_STOPS.length; i++) {
      const [t0, c0] = TEMP_STOPS[i - 1], [t1, c1] = TEMP_STOPS[i];
      if (t <= t1) return d3.interpolateRgb(c0, c1)((t - t0) / (t1 - t0));
    }
    return TEMP_STOPS[TEMP_STOPS.length - 1][1];
  }

  // ---------------------------------------------------------- basics
  function frame(el, m = { t: 26, r: 18, b: 30, l: 44 }) {
    const box = typeof el === "string" ? document.getElementById(el) : el;
    box.innerHTML = "";
    const W = Math.max(box.clientWidth, 200), H = Math.max(box.clientHeight, 160);
    const svg = d3.select(box).append("svg").attr("width", W).attr("height", H);
    const defs = svg.append("defs");
    const f = defs.append("filter").attr("id", "glow" + (++uid)).attr("x", "-20%").attr("y", "-50%").attr("width", "140%").attr("height", "200%");
    f.append("feGaussianBlur").attr("stdDeviation", 3.2).attr("result", "b");
    const mg = f.append("feMerge"); mg.append("feMergeNode").attr("in", "b"); mg.append("feMergeNode").attr("in", "SourceGraphic");
    const g = svg.append("g").attr("transform", `translate(${m.l},${m.t})`);
    return { box, svg, defs, g, w: W - m.l - m.r, h: H - m.t - m.b, W, H, m, glow: `url(#glow${uid})` };
  }

  function gradient(defs, color, top = 0.35) {
    const id = "grad" + (++uid);
    const lg = defs.append("linearGradient").attr("id", id).attr("x1", 0).attr("x2", 0).attr("y1", 0).attr("y2", 1);
    lg.append("stop").attr("offset", "0%").attr("stop-color", color).attr("stop-opacity", top);
    lg.append("stop").attr("offset", "100%").attr("stop-color", color).attr("stop-opacity", 0);
    return `url(#${id})`;
  }

  function axes(F, x, y, { xTicks = 7, yTicks = 6, xFmt = null, yFmt = null, yLabel = "", grid = "y" } = {}) {
    const { g, w, h } = F;
    if (grid === "y" || grid === "both")
      g.append("g").attr("class", "grid").call(d3.axisLeft(y).ticks(yTicks).tickSize(-w).tickFormat(""));
    if (grid === "x" || grid === "both")
      g.append("g").attr("class", "grid").attr("transform", `translate(0,${h})`).call(d3.axisBottom(x).ticks(xTicks).tickSize(-h).tickFormat(""));
    const xa = d3.axisBottom(x).ticks(xTicks).tickSizeOuter(0); if (xFmt) xa.tickFormat(xFmt);
    const ya = d3.axisLeft(y).ticks(yTicks).tickSizeOuter(0); if (yFmt) ya.tickFormat(yFmt);
    g.append("g").attr("class", "axis").attr("transform", `translate(0,${h})`).call(xa);
    g.append("g").attr("class", "axis").call(ya);
    if (yLabel) g.append("text").attr("x", -F.m.l + 4).attr("y", -10).text(yLabel).style("font-size", "10.5px");
  }

  function legend(F, items) {
    let x = 0;
    const lg = F.g.append("g").attr("transform", `translate(0,${-16})`);
    items.forEach(it => {
      const gi = lg.append("g").attr("transform", `translate(${x},0)`);
      if (it.type === "band") gi.append("rect").attr("x", 0).attr("y", -5).attr("width", 16).attr("height", 9).attr("fill", it.color).attr("opacity", .35);
      else if (it.type === "dot") gi.append("circle").attr("cx", 8).attr("cy", 0).attr("r", 4).attr("fill", it.color);
      else gi.append("line").attr("x1", 0).attr("x2", 16).attr("y1", 0).attr("y2", 0).attr("stroke", it.color)
        .attr("stroke-width", it.width || 2.4).attr("stroke-dasharray", it.dash || null);
      const t = gi.append("text").attr("x", 21).attr("y", 4).text(it.name);
      x += 30 + t.node().getComputedTextLength();
    });
  }

  const tip = {
    el: () => document.getElementById("tooltip"),
    show(html, ev) {
      const t = this.el(); t.innerHTML = html; t.classList.remove("hidden");
      const r = t.getBoundingClientRect();
      let x = ev.clientX + 16, y = ev.clientY + 14;
      if (x + r.width > innerWidth - 10) x = ev.clientX - r.width - 16;
      if (y + r.height > innerHeight - 10) y = ev.clientY - r.height - 14;
      t.style.left = x + "px"; t.style.top = y + "px";
    },
    hide() { this.el().classList.add("hidden"); }
  };

  function drawIn(path) {          // animated line drawing
    const n = path.node(); if (!n || !n.getTotalLength) return;
    const L = n.getTotalLength();
    path.attr("stroke-dasharray", `${L} ${L}`).attr("stroke-dashoffset", L)
      .transition().duration(900).ease(d3.easeCubicOut).attr("stroke-dashoffset", 0)
      .on("end", function () { d3.select(this).attr("stroke-dasharray", null); });
  }

  // ------------------------------------------------- time series chart
  /* opts.series: [{name, dates, values, color, style:'line'|'thin'|'dash'|'dots', glow, area, markers(colorFn)}]
     opts.band: {dates, low, high, color, name}   opts.thresholds: [{y,label,color}]
     opts.shade: {from,to}  opts.vline: {date,label}  opts.peak: {date,value,text} */
  function timeSeries(el, opts) {
    const F = frame(el, { t: 30, r: 20, b: 28, l: 44 });
    const { g, w, h } = F;
    const all = [];
    opts.series.forEach(s => s.dates.forEach((d, i) => s.values[i] != null && all.push([parse(d), s.values[i]])));
    if (opts.band) opts.band.dates.forEach((d, i) => { all.push([parse(d), opts.band.low[i]]); all.push([parse(d), opts.band.high[i]]); });
    if (!all.length) return;
    let [y0, y1] = d3.extent(all, d => d[1]);
    (opts.thresholds || []).forEach(t => { if (y1 >= t.y - 5) y1 = Math.max(y1, t.y + 2); });
    const pad = (y1 - y0) * 0.08 + 0.5;
    const x = d3.scaleTime().domain(d3.extent(all, d => d[0])).range([0, w]);
    const y = d3.scaleLinear().domain([opts.yMin ?? y0 - pad, opts.yMax ?? y1 + pad]).nice().range([h, 0]);
    if (opts.shade) g.append("rect").attr("x", x(parse(opts.shade.from)) - 4).attr("width", w - x(parse(opts.shade.from)) + 4)
      .attr("y", 0).attr("height", h).attr("fill", css("accent")).attr("opacity", .06);
    axes(F, x, y, { yLabel: opts.yLabel || "°C", xTicks: Math.max(3, Math.floor(w / 95)) });
    (opts.thresholds || []).forEach(t => {
      if (t.y > y.domain()[1] || t.y < y.domain()[0]) return;
      g.append("line").attr("x1", 0).attr("x2", w).attr("y1", y(t.y)).attr("y2", y(t.y)).attr("stroke", t.color)
        .attr("stroke-dasharray", "3 3").attr("opacity", .9);
      g.append("text").attr("x", 4).attr("y", y(t.y) - 4).text(t.label).style("fill", t.color).style("font-size", "10.5px");
    });
    if (opts.band) {
      const b = opts.band, pts = b.dates.map((d, i) => [parse(d), b.low[i], b.high[i]]);
      g.append("path").datum(pts).attr("fill", b.color).attr("opacity", .18)
        .attr("d", d3.area().x(d => x(d[0])).y0(d => y(d[1])).y1(d => y(d[2])).curve(d3.curveMonotoneX));
    }
    opts.series.forEach(s => {
      const pts = s.dates.map((d, i) => [parse(d), s.values[i]]).filter(p => p[1] != null);
      if (s.area) g.append("path").datum(pts).attr("fill", gradient(F.defs, s.color, .32))
        .attr("d", d3.area().x(d => x(d[0])).y0(h).y1(d => y(d[1])).curve(d3.curveMonotoneX));
      if (s.style === "dots") {
        g.selectAll(null).data(pts).join("circle").attr("cx", d => x(d[0])).attr("cy", d => y(d[1])).attr("r", 2.2)
          .attr("fill", s.color).attr("opacity", .75);
        return;
      }
      const line = d3.line().x(d => x(d[0])).y(d => y(d[1])).curve(s.style === "thin" ? d3.curveLinear : d3.curveMonotoneX);
      const p = g.append("path").datum(pts).attr("fill", "none").attr("stroke", s.color)
        .attr("stroke-width", s.style === "thin" ? 1 : (s.width || 2.4)).attr("opacity", s.style === "thin" ? .6 : 1)
        .attr("stroke-dasharray", s.style === "dash" ? "5 4" : null).attr("stroke-linecap", "round")
        .attr("filter", s.glow ? F.glow : null).attr("d", line);
      if (s.glow) drawIn(p);
      if (s.markers) g.selectAll(null).data(pts).join("circle").attr("cx", d => x(d[0])).attr("cy", d => y(d[1]))
        .attr("r", 4.2).attr("fill", d => s.markers(d[1])).attr("stroke", css("card")).attr("stroke-width", 1.5);
      if (s.hot != null) g.selectAll(null).data(pts.filter(d => d[1] >= s.hot)).join("circle").attr("cx", d => x(d[0]))
        .attr("cy", d => y(d[1])).attr("r", 3.6).attr("fill", STATUS[3]).attr("stroke", css("card"));
    });
    if (opts.vline) {
      const vx = x(parse(opts.vline.date));
      g.append("line").attr("x1", vx).attr("x2", vx).attr("y1", 0).attr("y2", h).attr("stroke", css("faint")).attr("stroke-dasharray", "2 3");
      g.append("text").attr("x", vx + 5).attr("y", h - 6).text(opts.vline.label).style("font-size", "10.5px");
    }
    if (opts.peak) g.append("text").attr("x", x(parse(opts.peak.date))).attr("y", y(opts.peak.value) - 12).attr("text-anchor", "middle")
      .text(opts.peak.text).style("fill", css("text")).style("font-weight", 700);
    legend(F, opts.legend || opts.series.filter(s => s.name).map(s => ({ name: s.name, color: s.color, dash: s.style === "dash" ? "5 4" : null })));
    hoverLayer(F, x, y, opts);
  }

  function hoverLayer(F, x, y, opts) {
    const { g, w, h } = F;
    const lookup = new Map();
    const add = (d, name, v, color, fmt) => {
      if (v == null || isNaN(v)) return;
      if (!lookup.has(d)) lookup.set(d, []);
      lookup.get(d).push({ name, v, color, fmt });
    };
    opts.series.filter(s => s.name && s.style !== "dots").forEach(s => s.dates.forEach((d, i) => add(d, s.name, s.values[i], s.color, s.fmt)));
    if (opts.band) opts.band.dates.forEach((d, i) => add(d, "80% range", `${opts.band.low[i].toFixed(1)} – ${opts.band.high[i].toFixed(1)}°C`, opts.band.color, "raw"));
    const keys = [...lookup.keys()].sort();
    if (!keys.length) return;
    const xs = keys.map(k => x(parse(k)));
    const vl = g.append("line").attr("y1", 0).attr("y2", h).attr("stroke", css("muted")).attr("stroke-dasharray", "3 3").style("display", "none");
    const dots = g.append("g");
    g.append("rect").attr("width", w).attr("height", h).attr("fill", "transparent")
      .on("mousemove", ev => {
        const [mx] = d3.pointer(ev);
        const i = d3.minIndex(xs, v => Math.abs(v - mx));
        const k = keys[i], items = lookup.get(k);
        vl.attr("x1", xs[i]).attr("x2", xs[i]).style("display", null);
        dots.selectAll("*").remove();
        items.filter(it => typeof it.v === "number").forEach(it => dots.append("circle").attr("cx", xs[i]).attr("cy", y(it.v))
          .attr("r", 5).attr("fill", it.color).attr("stroke", css("card")).attr("stroke-width", 2));
        tip.show(`<b>${fmtDay(parse(k))}</b><br>` + items.map(it => `<span class="dot" style="background:${it.color}"></span>${it.name}: <b>${
          it.fmt === "raw" ? it.v : (it.fmt ? it.fmt(it.v) : it.v.toFixed(1) + "°C")}</b>`).join("<br>"), ev);
      })
      .on("mouseleave", () => { vl.style("display", "none"); dots.selectAll("*").remove(); tip.hide(); });
  }

  // --------------------------------------------------------------- bars
  function hbars(el, { labels, values, colors, fmt = v => v.toFixed(1), xLabel = "", notes = null, tipFmt = null }) {
    const longest = d3.max(labels, l => String(l).length) || 6;
    const F = frame(el, { t: 10, r: 70, b: 30, l: Math.min(170, 14 + longest * 6.6) });
    const { g, w, h } = F;
    const lo = Math.min(0, d3.min(values) * 1.2), hi = Math.max(0, d3.max(values));
    const x = d3.scaleLinear().domain([lo, hi === lo ? 1 : hi]).nice().range([0, w]);
    const y = d3.scaleBand().domain(labels).range([0, h]).padding(.22);
    axes(F, x, y, { grid: "x", xTicks: 5 });
    g.selectAll(".axis").filter((d, i) => i === 1).call(d3.axisLeft(y).tickSize(0)).select("path").remove();
    g.selectAll(null).data(values).join("rect").attr("y", (d, i) => y(labels[i])).attr("height", y.bandwidth())
      .attr("x", x(0)).attr("width", 0).attr("rx", 3).attr("fill", (d, i) => colors[i])
      .on("mousemove", (ev, d) => { const i = values.indexOf(d); tip.show(`<b>${labels[i]}</b><br>${tipFmt ? tipFmt(i) : fmt(d)}`, ev); })
      .on("mouseleave", () => tip.hide())
      .transition().duration(700).delay((d, i) => i * 25)
      .attr("x", d => x(Math.min(0, d))).attr("width", d => Math.abs(x(d) - x(0)));
    g.selectAll(null).data(values).join("text").attr("y", (d, i) => y(labels[i]) + y.bandwidth() / 2 + 4)
      .attr("x", d => d >= 0 ? x(d) + 5 : x(d) - 5).attr("text-anchor", d => d >= 0 ? "start" : "end")
      .text((d, i) => notes ? notes[i] : fmt(d)).style("font-size", "10.5px");
    if (xLabel) g.append("text").attr("x", w / 2).attr("y", h + 27).attr("text-anchor", "middle").text(xLabel);
  }

  function vbars(el, { dates, values, colorFn, yMax = 100, ref = null, fmt = v => v.toFixed(0) + "%", yLabel = "" }) {
    const F = frame(el, { t: 22, r: 14, b: 28, l: 40 });
    const { g, w, h } = F;
    const x = d3.scaleBand().domain(dates).range([0, w]).padding(.2);
    const y = d3.scaleLinear().domain([0, yMax]).range([h, 0]);
    axes(F, d3.scaleLinear().range([0, w]), y, { yLabel, yFmt: d => d + "%" });
    g.selectAll(".axis").filter((d, i) => i === 0).call(d3.axisBottom(x).tickValues(dates.filter((d, i) => i % Math.ceil(dates.length / 8) === 0))
      .tickFormat(d => d3.timeFormat("%d %b")(parse(d))).tickSizeOuter(0));
    if (ref) {
      g.append("line").attr("x1", 0).attr("x2", w).attr("y1", y(ref.v)).attr("y2", y(ref.v)).attr("stroke", css("faint")).attr("stroke-dasharray", "3 3");
      g.append("text").attr("x", 2).attr("y", y(ref.v) - 4).text(ref.label).style("font-size", "10px");
    }
    g.selectAll(null).data(values).join("rect").attr("x", (d, i) => x(dates[i])).attr("width", x.bandwidth())
      .attr("y", h).attr("height", 0).attr("rx", 3).attr("fill", d => colorFn(d))
      .on("mousemove", (ev, d) => { const i = values.indexOf(d); tip.show(`<b>${fmtDay(parse(dates[i]))}</b><br>${fmt(d)}`, ev); })
      .on("mouseleave", () => tip.hide())
      .transition().duration(700).delay((d, i) => i * 20).attr("y", d => y(d)).attr("height", d => h - y(d));
    g.selectAll(null).data(values).join("text").attr("x", (d, i) => x(dates[i]) + x.bandwidth() / 2).attr("y", d => y(d) - 4)
      .attr("text-anchor", "middle").text(d => d >= 60 ? fmt(d) : "").style("font-size", "10px").style("fill", css("text"));
  }

  // ------------------------------------------------------------ heatmap
  function heatmap(el, { rows, cols, values, colorFn, fmt = v => v.toFixed(0), legend: lg = null, tipFmt = null }) {
    const F = frame(el, { t: 12, r: lg ? 56 : 12, b: 46, l: 70 });
    const { g, w, h } = F;
    const x = d3.scaleBand().domain(cols).range([0, w]).padding(.06);
    const y = d3.scaleBand().domain(rows).range([0, h]).padding(.06);
    rows.forEach((r, i) => cols.forEach((c, j) => {
      const v = values[i][j];
      if (v == null) return;
      const fill = colorFn(v);
      g.append("rect").attr("x", x(c)).attr("y", y(r)).attr("width", x.bandwidth()).attr("height", y.bandwidth()).attr("rx", 4)
        .attr("fill", fill).attr("opacity", 0).on("mousemove", ev => tip.show(tipFmt ? tipFmt(r, c, v) : `<b>${r} • ${c}</b><br>${fmt(v)}`, ev))
        .on("mouseleave", () => tip.hide()).transition().duration(500).delay((i * cols.length + j) * 6).attr("opacity", 1);
      const lum = d3.hsl(fill).l;
      if (x.bandwidth() > 22 && y.bandwidth() > 14)
        g.append("text").attr("x", x(c) + x.bandwidth() / 2).attr("y", y(r) + y.bandwidth() / 2 + 4).attr("text-anchor", "middle")
          .text(fmt(v)).style("fill", lum > .6 ? "#1a0d04" : "#fff").style("font-size", "10.5px").style("pointer-events", "none");
    }));
    g.append("g").attr("class", "axis").attr("transform", `translate(0,${h})`).call(d3.axisBottom(x).tickSize(0)).select("path").remove();
    g.append("g").attr("class", "axis").call(d3.axisLeft(y).tickSize(0)).select("path").remove();
    if (lg) {
      const id = "lg" + (++uid), gr = F.defs.append("linearGradient").attr("id", id).attr("x1", 0).attr("x2", 0).attr("y1", 1).attr("y2", 0);
      d3.range(0, 1.01, .1).forEach(t => gr.append("stop").attr("offset", t * 100 + "%").attr("stop-color", colorFn(lg.min + t * (lg.max - lg.min))));
      g.append("rect").attr("x", w + 16).attr("y", 0).attr("width", 10).attr("height", h).attr("rx", 3).attr("fill", `url(#${id})`);
      const s = d3.scaleLinear().domain([lg.min, lg.max]).range([h, 0]);
      g.append("g").attr("class", "axis").attr("transform", `translate(${w + 28},0)`).call(d3.axisRight(s).ticks(5).tickSize(3)).select("path").remove();
    }
  }

  // ----------------------------------------------------------- wind rose
  function windRose(el, { table, bins }) {
    const F = frame(el, { t: 10, r: 10, b: 10, l: 10 });
    const { g, w, h } = F;
    const R = Math.min(w * .62, h) / 2 - 16, cx = R + 26, cy = h / 2;
    const n = table[0].length, totals = d3.range(n).map(j => d3.sum(table, r => r[j]));
    const r = d3.scaleLinear().domain([0, d3.max(totals) || 1]).nice().range([R * .08, R]);
    const colors = [css("seq1"), css("seq2"), css("seq3"), css("seq4")];
    const c = g.append("g").attr("transform", `translate(${cx},${cy})`);
    r.ticks(4).slice(1).forEach(t => {
      c.append("circle").attr("r", r(t)).attr("fill", "none").attr("stroke", css("grid"));
      c.append("text").attr("x", 3).attr("y", -r(t) - 2).text(t + "%").style("font-size", "9.5px");
    });
    ["N", "E", "S", "W"].forEach((d, i) => {
      const a = i * Math.PI / 2;
      c.append("text").attr("x", Math.sin(a) * (R + 12)).attr("y", -Math.cos(a) * (R + 12) + 4).attr("text-anchor", "middle").text(d)
        .style("font-weight", 700);
    });
    const step = 2 * Math.PI / n;
    for (let j = 0; j < n; j++) {
      let base = 0;
      table.forEach((row, k) => {
        const v = row[j];
        const arc = d3.arc().innerRadius(r(base)).outerRadius(r(base + v)).startAngle(j * step - step * .44).endAngle(j * step + step * .44).padAngle(.01);
        c.append("path").attr("d", arc).attr("fill", colors[k]).attr("stroke", css("card")).attr("stroke-width", 1)
          .on("mousemove", ev => tip.show(`<b>${["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"][j]}</b> • ${bins[k]}<br>${v.toFixed(1)}% of readings`, ev))
          .on("mouseleave", () => tip.hide());
        base += v;
      });
    }
    const lg = g.append("g").attr("transform", `translate(${cx + R + 40},${cy - 40})`);
    bins.forEach((b, k) => {
      lg.append("rect").attr("y", k * 20).attr("width", 14).attr("height", 10).attr("rx", 2).attr("fill", colors[k]);
      lg.append("text").attr("x", 20).attr("y", k * 20 + 9).text(b);
    });
  }

  // ---------------------------------------------------------- box plots
  function boxes(el, { groups }) {
    const F = frame(el, { t: 24, r: 14, b: 28, l: 40 });
    const { g, w, h } = F;
    const x = d3.scaleBand().domain(groups.map(d => d.name)).range([0, w]).padding(.35);
    const y = d3.scaleLinear().domain([d3.min(groups, d => d.min) - 2, d3.max(groups, d => d.max) + 3]).nice().range([h, 0]);
    axes(F, d3.scaleLinear().range([0, w]), y, { yLabel: "°C" });
    g.selectAll(".axis").filter((d, i) => i === 0).call(d3.axisBottom(x).tickSize(0));
    groups.forEach(gr => {
      const cx = x(gr.name), bw = x.bandwidth(), col = tempColor(gr.mean);
      (gr.values || []).forEach(v => g.append("circle").attr("cx", cx + bw / 2 + (Math.random() - .5) * bw * 1.1).attr("cy", y(v))
        .attr("r", 1.8).attr("fill", col).attr("opacity", .33));
      g.append("line").attr("x1", cx + bw / 2).attr("x2", cx + bw / 2).attr("y1", y(gr.min)).attr("y2", y(gr.max)).attr("stroke", css("muted"));
      g.append("rect").attr("x", cx + bw * .2).attr("width", bw * .6).attr("y", y(gr.q3)).attr("height", Math.max(1, y(gr.q1) - y(gr.q3)))
        .attr("rx", 4).attr("fill", col).attr("opacity", .9)
        .on("mousemove", ev => tip.show(`<b>${gr.name}</b><br>median ${gr.median.toFixed(1)}°C<br>middle 50%: ${gr.q1.toFixed(1)} – ${gr.q3.toFixed(1)}°C<br>range ${gr.min.toFixed(1)} – ${gr.max.toFixed(1)}°C<br>${gr.n} readings`, ev))
        .on("mouseleave", () => tip.hide());
      g.append("line").attr("x1", cx + bw * .2).attr("x2", cx + bw * .8).attr("y1", y(gr.median)).attr("y2", y(gr.median)).attr("stroke", css("card")).attr("stroke-width", 2.5);
      g.append("text").attr("x", cx + bw / 2).attr("y", y(gr.max) - 6).attr("text-anchor", "middle").text(`avg ${gr.mean.toFixed(1)}°`).style("fill", css("text"));
    });
  }

  // ------------------------------------------------------------ scatter
  function scatter(el, { points, xLabel, yLabel = "°C", bands = [], label = 3, xDomain = null }) {
    const F = frame(el, { t: 14, r: 20, b: 40, l: 44 });
    const { g, w, h } = F;
    const x = d3.scaleLinear().domain(xDomain || d3.extent(points, p => p.x)).nice().range([0, w]);
    const y = d3.scaleLinear().domain(d3.extent(points, p => p.y)).nice().range([h, 0]);
    bands.forEach(b => {
      const a = Math.max(y.domain()[0], b.from), z = Math.min(y.domain()[1], b.to);
      if (z > a) g.append("rect").attr("x", 0).attr("width", w).attr("y", y(z)).attr("height", y(a) - y(z)).attr("fill", b.color).attr("opacity", .08);
    });
    axes(F, x, y, { grid: "both", yLabel });
    g.append("text").attr("x", w / 2).attr("y", h + 34).attr("text-anchor", "middle").text(xLabel);
    g.selectAll(null).data(points).join("circle").attr("cx", p => x(p.x)).attr("cy", p => y(p.y)).attr("r", 0)
      .attr("fill", p => tempColor(p.y)).attr("stroke", css("card")).attr("stroke-width", 1.2)
      .on("mousemove", (ev, p) => tip.show(`<b>${p.label}</b><br>${p.y.toFixed(1)}°C • lon ${p.x.toFixed(1)}`, ev))
      .on("mouseleave", () => tip.hide()).transition().duration(600).delay((p, i) => i * 3).attr("r", 5);
    const sorted = [...points].sort((a, b) => a.y - b.y);
    [...sorted.slice(0, label), ...sorted.slice(-label - 1)].forEach(p =>
      g.append("text").attr("x", x(p.x) + 7).attr("y", y(p.y) - 5).text(p.label).style("fill", css("text")).style("font-size", "10.5px"));
  }

  // -------------------------------------------------------- multi line
  function liveLines(el, streams, threshold) {
    const names = Object.keys(streams).slice(0, 6);
    if (!names.length || !names.some(n => streams[n].length)) { empty(el, "Start the AWS monitor to stream live sensor readings"); return; }
    const F = frame(el, { t: 30, r: names.length <= 4 ? 110 : 20, b: 30, l: 40 });
    const { g, w, h } = F;
    const all = names.flatMap(n => streams[n]);
    const x = d3.scaleLinear().domain([0, 79]).range([0, w]);
    const y = d3.scaleLinear().domain([Math.min(d3.min(all), threshold - 5) - 2, Math.max(d3.max(all), threshold) + 2]).nice().range([h, 0]);
    axes(F, x, y, { yLabel: "°C", xFmt: () => "" });
    g.append("line").attr("x1", 0).attr("x2", w).attr("y1", y(threshold)).attr("y2", y(threshold)).attr("stroke", STATUS[3]).attr("stroke-dasharray", "3 3");
    g.append("text").attr("x", 4).attr("y", y(threshold) - 4).text(`Heatwave ${threshold}°C`).style("fill", STATUS[3]).style("font-size", "10.5px");
    names.forEach((n, k) => {
      const v = streams[n]; if (!v.length) return;
      const off = 80 - v.length;
      g.append("path").datum(v).attr("fill", "none").attr("stroke", CATEGORICAL[k]).attr("stroke-width", 2.2)
        .attr("d", d3.line().x((d, i) => x(i + off)).y(d => y(d)).curve(d3.curveMonotoneX));
      g.append("circle").attr("cx", x(79)).attr("cy", y(v[v.length - 1])).attr("r", 4.5).attr("fill", CATEGORICAL[k]);
      if (names.length <= 4) g.append("text").attr("x", x(79) + 8).attr("y", y(v[v.length - 1]) + 4).text(`${n} ${v[v.length - 1].toFixed(1)}°`)
        .style("fill", CATEGORICAL[k]).style("font-size", "10.5px").style("font-weight", 700);
    });
    legend(F, names.map((n, k) => ({ name: n, color: CATEGORICAL[k] })));
  }

  // -------------------------------------------------------------- gauge
  function gauge(el, value, feels, caption) {
    const box = document.getElementById(el); box.innerHTML = "";
    const W = Math.max(box.clientWidth, 200), H = Math.max(box.clientHeight, 200);
    const svg = d3.select(box).append("svg").attr("width", W).attr("height", H);
    const R = Math.min(W, H) / 2 - 22, cx = W / 2, cy = H / 2 + 12, LOW = -10, HIGH = 50;
    const ang = t => (-135 + (Math.min(Math.max(t, LOW), HIGH) - LOW) / (HIGH - LOW) * 270) * Math.PI / 180;
    const g = svg.append("g").attr("transform", `translate(${cx},${cy})`);
    const seg = 60;
    for (let i = 0; i < seg; i++) {
      const t0 = LOW + (HIGH - LOW) * i / seg, t1 = LOW + (HIGH - LOW) * (i + 1) / seg;
      g.append("path").attr("d", d3.arc().innerRadius(R - 14).outerRadius(R).startAngle(ang(t0)).endAngle(ang(t1) + .01))
        .attr("fill", tempColor(t0)).attr("opacity", .22);
    }
    const fill = g.append("g");
    for (let t = LOW; t <= HIGH; t += 10) {
      const a = ang(t);
      g.append("line").attr("x1", Math.sin(a) * (R - 18)).attr("y1", -Math.cos(a) * (R - 18)).attr("x2", Math.sin(a) * (R - 25)).attr("y2", -Math.cos(a) * (R - 25)).attr("stroke", css("faint")).attr("stroke-width", 2);
      g.append("text").attr("x", Math.sin(a) * (R - 36)).attr("y", -Math.cos(a) * (R - 36) + 4).attr("text-anchor", "middle").text(t).style("font-size", "10px");
    }
    const a40 = ang(40);
    g.append("line").attr("x1", Math.sin(a40) * (R + 8)).attr("y1", -Math.cos(a40) * (R + 8)).attr("x2", Math.sin(a40) * (R - 20)).attr("y2", -Math.cos(a40) * (R - 20)).attr("stroke", STATUS[3]).attr("stroke-width", 3);
    g.append("text").attr("x", Math.sin(a40) * (R + 18)).attr("y", -Math.cos(a40) * (R + 18)).attr("text-anchor", "middle").text("HW").style("fill", STATUS[3]).style("font-size", "10px").style("font-weight", 700);
    const needle = g.append("line").attr("x1", 0).attr("y1", 0).attr("stroke", css("text")).attr("stroke-width", 3).attr("stroke-linecap", "round");
    const hub = g.append("circle").attr("r", 7).attr("stroke", css("card")).attr("stroke-width", 2);
    g.append("text").attr("y", R * .45).attr("text-anchor", "middle").text(`${value.toFixed(1)}°C`).style("fill", css("text"))
      .style("font-size", "30px").style("font-weight", 700).style("font-family", "var(--display)");
    g.append("text").attr("y", R * .45 + 22).attr("text-anchor", "middle").text(feels != null ? `feels like ${feels.toFixed(0)}°C` : "");
    svg.append("text").attr("x", cx).attr("y", 14).attr("text-anchor", "middle").text(caption).style("font-weight", 700);
    d3.transition().duration(1300).ease(d3.easeCubicOut).tween("needle", () => {
      const it = d3.interpolate(LOW, value);
      return t => {
        const v = it(t), a = ang(v);
        needle.attr("x2", Math.sin(a) * (R - 30)).attr("y2", -Math.cos(a) * (R - 30));
        hub.attr("fill", tempColor(v));
        fill.selectAll("*").remove();
        fill.append("path").attr("d", d3.arc().innerRadius(R - 14).outerRadius(R).startAngle(ang(LOW)).endAngle(a).cornerRadius(3))
          .attr("fill", tempColor(v));
      };
    });
  }

  function empty(el, text) {
    const box = typeof el === "string" ? document.getElementById(el) : el;
    box.innerHTML = `<div style="position:absolute;inset:0;display:grid;place-items:center;color:var(--faint);text-align:center;padding:20px">${text}</div>`;
  }

  // ------------------------------------------------- auto chart for SQL
  function sqlAuto(el, columns, rows) {
    if (!rows || !rows.length) return empty(el, "Run a SELECT query to see an automatic chart here");
    const isNum = j => rows.some(r => typeof r[j] === "number") && rows.every(r => r[j] == null || typeof r[j] === "number");
    const skip = c => ["id", "alert_id", "longitude", "month", "year", "wind_degree", "aqi_index", "is_rain"].includes(c.toLowerCase());
    const numCols = columns.map((c, j) => j).filter(j => isNum(j) && !skip(columns[j]));
    const txtCols = columns.map((c, j) => j).filter(j => !isNum(j) && !["id", "alert_id"].includes(columns[j].toLowerCase()));
    if (!numCols.length) return empty(el, "No numeric column in this result to chart");
    const pref = numCols.find(j => /temp|max|min|avg|count|rain|wind|humid|precip|days|total|heat/i.test(columns[j]));
    const yj = pref ?? numCols[0], yName = columns[yj];
    const isTemp = /temp|heat/i.test(yName);
    const lj = txtCols[0];
    const looksDate = lj != null && /^\d{4}-\d{2}/.test(String(rows[0][lj]));
    if (looksDate && rows.length > 2) {
      const pts = rows.filter(r => r[yj] != null).map(r => [String(r[lj]).slice(0, 10).length === 7 ? r[lj] + "-01" : String(r[lj]).slice(0, 10), r[yj]])
        .sort((a, b) => a[0] < b[0] ? -1 : 1);
      return timeSeries(el, { yLabel: yName, series: [{ name: yName, dates: pts.map(p => p[0]), values: pts.map(p => p[1]), color: css("line"),
        glow: true, area: true, fmt: v => v.toFixed(2), markers: isTemp ? tempColor : null }] });
    }
    const top = rows.slice(0, 25);
    const labels = top.map((r, i) => lj != null ? String(r[lj]).slice(0, 24) + (labelsDup(top, lj, i) ? ` #${i + 1}` : "") : `#${i + 1}`);
    const vals = top.map(r => +r[yj] || 0);
    const accent = css("accent"), card = css("card");
    hbars(el, { labels, values: vals, xLabel: yName + (rows.length > 25 ? `  (top 25 of ${rows.length})` : ""),
      colors: vals.map((v, i) => isTemp ? tempColor(v) : d3.interpolateRgb(accent, card)(i / Math.max(1, vals.length) * .55)) });
  }
  const labelsDup = (rows, j, i) => rows.findIndex(r => r[j] === rows[i][j]) !== i;

  return { css, tempColor, timeSeries, hbars, vbars, heatmap, windRose, boxes, scatter, liveLines, gauge, empty, sqlAuto,
           STATUS, CATEGORICAL, tip, parse };
})();
