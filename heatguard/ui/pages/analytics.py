"""Analytics - Phase II region-wise & seasonal analysis + hotspot identification (Exp 6)."""

import matplotlib.dates as mdates
import numpy as np

from ... import analytics as an
from ...exceptions import HeatGuardError
from ..app import BasePage
from ..charts import (ChartPanel, draw_heat_calendar, draw_seasons, draw_wind_rose, draw_corr, draw_hotspots,
                      draw_world_band, style_ax, glow_line, gradient_fill, date_axis, Hover, _datefmt)
from ..widgets import Card, Segmented, temp_color


def draw_coldspots(fig, p, table):
    ax = fig.add_subplot(111)
    style_ax(ax, p, grid="x")
    t = table.iloc[::-1]
    y = np.arange(len(t))
    ax.barh(y, t["avg_temp"], color=[temp_color(v) for v in t["avg_temp"]], edgecolor=p["card"], lw=2,
            height=0.7, zorder=3)
    for yi, (avg, mn) in enumerate(zip(t["avg_temp"], t["min_temp"])):
        ax.text(avg + (0.3 if avg >= 0 else -0.3), yi, f"{avg:.1f}\N{DEGREE SIGN}  (min {mn:.0f}\N{DEGREE SIGN})",
                va="center", ha="left" if avg >= 0 else "right", color=p["muted"], fontsize=7.5)
    ax.set_yticks(y)
    ax.set_yticklabels(t.index)
    ax.axvline(0, color=p["border"], lw=1)
    lo, hi = min(0, t["avg_temp"].min()), max(0, t["avg_temp"].max())
    ax.set_xlim(lo - (hi - lo) * 0.45 - 1, hi + (hi - lo) * 0.45 + 1)
    ax.set_xlabel("average \N{DEGREE SIGN}C, last 60 days")


def draw_global_trend(fig, p, df):
    ax = fig.add_subplot(111)
    style_ax(ax, p)
    g = df.set_index("ts")["temperature"].resample("W").mean().dropna()
    x = mdates.date2num(g.index.to_pydatetime())
    y = g.values
    base = y.min() - 1.5
    gradient_fill(ax, x, y, p["line"], base, alpha=0.3)
    glow_line(ax, x, y, p["line"], lw=2)
    imax = int(np.argmax(y))
    ax.annotate(f"warmest week {y[imax]:.1f}\N{DEGREE SIGN}C", (x[imax], y[imax]), xytext=(0, 10),
                textcoords="offset points", ha="center", color=p["text"], fontsize=8)
    ax.set_xlim(x[0], x[-1])
    ax.set_ylim(base, y.max() + 1.5)
    ax.xaxis_date()
    date_axis(ax, (g.index[-1] - g.index[0]).days)
    ax.set_ylabel("global mean \N{DEGREE SIGN}C")
    return Hover(ax, x, [("Weekly mean", y, p["line"], "{:.2f}\N{DEGREE SIGN}C")], _datefmt)


class AnalyticsPage(BasePage):
    def build(self):
        pad = 14
        self.mode = "country"
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        head = self.frame(self)
        head.grid(row=0, column=0, sticky="ew", padx=pad, pady=(12, 6))
        self.title = self.label(head, "Analytics", "h1", bg="bg")
        self.title.pack(side="left")
        Segmented(head, self.tm, [("country", "Region insights"), ("global", "Global hotspots")], self._mode,
                  value="country").pack(side="left", padx=20, pady=(6, 0))
        self.sub = self.label(head, "", "small", fg="muted", bg="bg")
        self.sub.pack(side="left", pady=(8, 0))

        self.chips = self.frame(self)
        self.chips.grid(row=1, column=0, sticky="ew", padx=pad - 4, pady=(0, 6))

        self.host = self.frame(self)
        self.host.grid(row=2, column=0, sticky="nsew", padx=pad - 6, pady=(0, 10))
        self.country_grid = self._grid([
            ("Heat calendar", "average temperature by month and year"),
            ("Seasonal distribution", "4 IMD seasons • violin + box"),
            ("Wind rose", "direction frequency by speed"),
            ("What moves together", "correlation of weather variables")])
        self.global_grid = self._grid([
            ("Heatwave hotspots", "most readings ≥ 40\N{DEGREE SIGN}C, last 60 days"),
            ("World heat band", "latest reading of every country by longitude • hover"),
            ("Coldest regions", "lowest average temperature, last 60 days"),
            ("Global temperature pulse", "weekly mean of all countries")])
        self._mode("country")

    def _grid(self, specs):
        fr = self.frame(self.host)
        panels = []
        for i, (title, sub) in enumerate(specs):
            card = Card(fr, self.tm, title, sub)
            card.grid(row=i // 2, column=i % 2, sticky="nsew", padx=6, pady=6)
            ch = ChartPanel(card.body, self.tm, figsize=(4.5, 2.6))
            ch.pack(fill="both", expand=True)
            panels.append(ch)
        for k in range(2):
            fr.grid_columnconfigure(k, weight=1, uniform="a")
            fr.grid_rowconfigure(k, weight=1, uniform="b")
        fr.panels = panels
        return fr

    def _mode(self, mode):
        self.mode = mode
        for g in (self.country_grid, self.global_grid):
            g.pack_forget()
        (self.country_grid if mode == "country" else self.global_grid).pack(fill="both", expand=True)
        self.charts = self.country_grid.panels if mode == "country" else self.global_grid.panels
        if self.built:
            self.refresh()

    def refresh(self):
        if self.mode == "country":
            self._country()
        else:
            self._global()

    def _chip(self, title, value, color=None):
        box = self.frame(self.chips, bg="card", highlightthickness=1)
        self.tm.bind(box, highlightbackground="border")
        box.pack(side="left", padx=4, fill="y")
        self.label(box, title.upper(), "tiny", fg="faint").pack(anchor="w", padx=12, pady=(7, 0))
        lbl = self.label(box, value, "h3", fg="text")
        lbl.pack(anchor="w", padx=12, pady=(0, 7))
        if color:
            lbl.configure(fg=color)

    def _country(self):
        country = self.app.country
        self.title.configure(text=f"Analytics • {country}")
        try:
            rows = self.app.dm.country_rows(country)
            daily = self.app.dm.daily(country)
        except HeatGuardError as exc:
            self.sub.configure(text=str(exc))
            return
        stats = an.functional_summary(daily, days=30)
        streak = an.heatwave_streaks(daily)
        for w in self.chips.winfo_children():
            w.destroy()
        self._chip("30-day mean", f"{stats['mean_c']:.1f}\N{DEGREE SIGN}C / {stats['mean_f']:.0f}\N{DEGREE SIGN}F",
                   temp_color(stats["mean_c"]))
        self._chip("hottest (reduce)", f"{stats['hottest_c']:.1f}\N{DEGREE SIGN}C", temp_color(stats["hottest_c"]))
        self._chip("coldest (reduce)", f"{stats['coldest_c']:.1f}\N{DEGREE SIGN}C", temp_color(stats["coldest_c"]))
        self._chip("heatwave days (filter)", str(stats["heatwave_days"]))
        self._chip("rainy days", str(stats["rainy_days"]))
        self._chip("longest ≥ 40\N{DEGREE SIGN} spell", f"{streak} days")
        self._chip("levels seen (set)", ", ".join(stats["levels_seen"]))
        self.sub.configure(text=f"{len(rows):,} readings • {daily.index[0]:%b %Y} - {daily.index[-1]:%b %Y}")
        matrix = an.monthly_matrix(daily)
        table = an.seasonal_table(rows)
        rose, bins = an.wind_rose_bins(rows)
        corr = an.correlation(rows)
        p1, p2, p3, p4 = self.country_grid.panels
        p1.set_draw(lambda fig, p: draw_heat_calendar(fig, p, matrix))
        p2.set_draw(lambda fig, p: draw_seasons(fig, p, table))
        p3.set_draw(lambda fig, p: draw_wind_rose(fig, p, rose, bins))
        p4.set_draw(lambda fig, p: draw_corr(fig, p, corr))
        self.apply_auto_theme()

    def _global(self):
        self.title.configure(text="Analytics • World")
        df = self.app.dm.df
        hot = an.hotspots(df)
        cold = an.coldspots(df)
        snap = self.app.dm.latest_snapshot()
        for w in self.chips.winfo_children():
            w.destroy()
        above = int((snap["temperature"] >= self.app.thresholds["heat_c"]).sum())
        below = int((snap["temperature"] <= 0).sum())
        top = snap.loc[snap["temperature"].idxmax()]
        low = snap.loc[snap["temperature"].idxmin()]
        self._chip("countries tracked", str(len(snap)))
        self._chip("in heatwave now", str(above), "#ff4d4f" if above else None)
        self._chip("below freezing now", str(below))
        self._chip("hottest now", f"{top['country']} {top['temperature']:.1f}\N{DEGREE SIGN}", temp_color(top["temperature"]))
        self._chip("coldest now", f"{low['country']} {low['temperature']:.1f}\N{DEGREE SIGN}", temp_color(low["temperature"]))
        self._chip("top hotspot (60 d)", f"{hot.index[0]}")
        self.sub.configure(text=f"{len(df):,} readings from {df['country'].nunique()} countries")
        heat = self.app.thresholds["heat_c"]
        p1, p2, p3, p4 = self.global_grid.panels
        p1.set_draw(lambda fig, p: draw_hotspots(fig, p, hot, heat))
        p2.set_draw(lambda fig, p: draw_world_band(fig, p, snap, heat))
        p3.set_draw(lambda fig, p: draw_coldspots(fig, p, cold))
        p4.set_draw(lambda fig, p: draw_global_trend(fig, p, df))
        if above:
            self.app.auto_theme("blaze", f"Global view: {above} countries ≥ {heat:.0f}\N{DEGREE SIGN}C right now")
        else:
            self.app.auto_theme("solar", f"Global view: hottest now {top['country']} {top['temperature']:.1f}\N{DEGREE SIGN}C")

    def apply_auto_theme(self):
        if self.mode == "global":
            return
        try:
            rec = self.app.dm.latest(self.app.country)
        except HeatGuardError:
            return
        name, reason = self.theme_for_reading(rec)
        self.app.auto_theme(name, f"{self.app.country}: {reason}")
