"""
charts.py  -  Matplotlib charts embedded in Tkinter
===================================================
* ChartPanel  : a Tk frame holding one matplotlib Figure (FigureCanvasTkAgg),
                re-coloured on every theme change, with a hover tooltip.
* draw_* fns  : one function per chart.  Each takes (fig, palette, data).

Colour rules used everywhere
    temperature -> semantic scale (cold blue ... hot red), same in all themes
    sequential  -> one hue, light to dark (rain chance, wind rose)
    diverging   -> blue / grey / orange around 0 (correlations)
    categorical -> fixed order, never cycled (multi-series lines)
"""
import tkinter as tk

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.dates as mdates                          # noqa: E402
import numpy as np                                         # noqa: E402
import pandas as pd                                        # noqa: E402
from matplotlib import font_manager                        # noqa: E402
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg   # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, to_rgb     # noqa: E402
from matplotlib.figure import Figure                       # noqa: E402
from matplotlib.patches import Polygon                     # noqa: E402

from .themes import STATUS, blend                          # noqa: E402
from .widgets import TEMP_STOPS, temp_color                # noqa: E402

CATEGORICAL = ("#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#9085e9")
TEMP_CMAP = LinearSegmentedColormap.from_list(
    "temperature", [((t - TEMP_STOPS[0][0]) / (TEMP_STOPS[-1][0] - TEMP_STOPS[0][0]), c) for t, c in TEMP_STOPS])
DIVERGING = LinearSegmentedColormap.from_list("div", ["#3987e5", "#6f7d8f", "#d95926"])


def setup_matplotlib(fonts):
    names = {f.name for f in font_manager.fontManager.ttflist}
    for fam in (fonts.get("family"), "Segoe UI", "Inter", "Helvetica Neue", "Arial", "DejaVu Sans"):
        if fam in names:
            matplotlib.rcParams["font.family"] = fam
            break
    matplotlib.rcParams.update({"axes.unicode_minus": False, "font.size": 8.5, "axes.titlesize": 9,
                                "legend.fontsize": 8, "xtick.labelsize": 8, "ytick.labelsize": 8})


# ---------------------------------------------------------------- styling
def style_ax(ax, p, grid="y"):
    ax.set_facecolor(p["card"])
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(p["border"])
    ax.tick_params(colors=p["muted"], length=0, pad=5)
    ax.xaxis.label.set_color(p["muted"])
    ax.yaxis.label.set_color(p["muted"])
    if grid:
        ax.grid(axis=grid, color=p["grid"], linewidth=0.8, alpha=0.9)
        ax.set_axisbelow(True)


def legend(ax, p, loc="upper left", ncol=1):
    lg = ax.legend(loc=loc, frameon=False, ncol=ncol, handlelength=1.6, borderaxespad=0.2)
    for t in lg.get_texts():
        t.set_color(p["muted"])
    return lg


def glow_line(ax, x, y, color, lw=2.0, label=None, ls="-", zorder=4):
    for w, a in ((lw * 4, 0.05), (lw * 2.4, 0.10)):
        ax.plot(x, y, color=color, lw=w, alpha=a, ls=ls, solid_capstyle="round", zorder=zorder - 1)
    return ax.plot(x, y, color=color, lw=lw, ls=ls, label=label, solid_capstyle="round", zorder=zorder)[0]


def gradient_fill(ax, x, y, color, base, alpha=0.32, zorder=1):
    """Fill under a curve with a vertical fade (top = colour, bottom = clear)."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    z = np.empty((100, 1, 4))
    z[:, :, :3] = to_rgb(color)
    z[:, :, -1] = np.linspace(0, alpha, 100)[:, None]
    xmin, xmax, ymax = x.min(), x.max(), np.nanmax(y)
    im = ax.imshow(z, aspect="auto", extent=[xmin, xmax, base, ymax], origin="lower", zorder=zorder)
    xy = np.vstack([[xmin, base], np.column_stack([x, y]), [xmax, base], [xmin, base]])
    clip = Polygon(xy, facecolor="none", edgecolor="none", closed=True)
    ax.add_patch(clip)
    im.set_clip_path(clip)


def date_axis(ax, span_days):
    if span_days > 200:
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    elif span_days > 45:
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    else:
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=8))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))


def empty(fig, p, text):
    ax = fig.add_subplot(111)
    ax.set_facecolor(p["card"])
    ax.axis("off")
    ax.text(0.5, 0.5, text, ha="center", va="center", color=p["faint"], fontsize=10, transform=ax.transAxes,
            wrap=True)


class Hover:
    """Crosshair + tooltip: snaps to the nearest x and lists the values."""

    def __init__(self, ax, xs, series, xfmt=str, anchor=0):
        self.ax, self.xs, self.series, self.xfmt, self.anchor = ax, np.asarray(xs, dtype=float), series, xfmt, anchor


# ================================================================ ChartPanel
class ChartPanel(tk.Frame):
    def __init__(self, parent, tm, draw=None, figsize=(4, 2.4)):
        super().__init__(parent, bd=0, highlightthickness=0)
        self.tm = tm
        tm.bind(self, bg="card")
        root = parent.winfo_toplevel()
        dpi = 96.0 * getattr(root, "S", 1.0)
        self.fig = Figure(figsize=figsize, dpi=dpi, layout="constrained")
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.widget = self.canvas.get_tk_widget()
        self.widget.configure(highlightthickness=0, bd=0)
        tm.bind(self.widget, bg="card")
        self.widget.pack(fill="both", expand=True)
        self.draw_fn = draw
        self.hover = None
        self._hover_items = None
        self.dirty = False
        self.canvas.mpl_connect("motion_notify_event", self._on_move)
        self.canvas.mpl_connect("figure_leave_event", self._on_leave)

    def set_draw(self, fn, render=True):
        self.draw_fn = fn
        if render:
            self.render()

    def render(self):
        p = self.tm.p
        self.fig.clear()
        self.fig.set_facecolor(p["card"])
        self.hover, self._hover_items = None, None
        if self.draw_fn is None:
            self.canvas.draw_idle()
            return
        try:
            out = self.draw_fn(self.fig, p)
        except Exception as exc:                       # never let a chart crash the app
            self.fig.clear()
            empty(self.fig, p, f"Chart unavailable: {exc}")
            out = None
        if isinstance(out, Hover):
            self.hover = out
        self.canvas.draw_idle()
        self.dirty = False

    # ------------------------------------------------------------ tooltip
    def _ensure_items(self):
        if self._hover_items or not self.hover:
            return
        p, ax = self.tm.p, self.hover.ax
        line = ax.axvline(self.hover.xs[0], color=p["muted"], lw=0.8, ls=(0, (3, 3)), zorder=9, visible=False)
        dots = [ax.plot([], [], "o", ms=6, color=c, mec=p["card"], mew=1.5, zorder=10, visible=False)[0]
                for _, _, c, _ in self.hover.series]
        ann = ax.annotate("", xy=(0, 0), xytext=(12, 12), textcoords="offset points", zorder=11, fontsize=8,
                          color=p["text"], va="bottom",
                          bbox=dict(boxstyle="round,pad=0.5", fc=p["card_hi"], ec=p["border"], lw=1))
        ann.set_visible(False)
        self._hover_items = (line, dots, ann)

    def _on_move(self, event):
        if not self.hover or event.inaxes is not self.hover.ax or event.xdata is None:
            self._on_leave(None)
            return
        self._ensure_items()
        line, dots, ann = self._hover_items
        h = self.hover
        i = int(np.nanargmin(np.abs(h.xs - event.xdata)))
        x = h.xs[i]
        lines = [h.xfmt(x)]
        y_anchor = None
        for (label, ys, color, fmt), dot in zip(h.series, dots):
            v = ys[i] if i < len(ys) else np.nan
            if v is None or (isinstance(v, float) and np.isnan(v)):
                dot.set_visible(False)
                continue
            dot.set_data([x], [v])
            dot.set_visible(True)
            lines.append(f"{label}: {fmt.format(v)}")
            if y_anchor is None:
                y_anchor = v
        if y_anchor is None:
            return
        line.set_xdata([x, x])
        line.set_visible(True)
        ann.xy = (x, y_anchor)
        ann.set_text("\n".join(lines))
        xmin, xmax = h.ax.get_xlim()
        ann.set_position((-14, 12) if (x - xmin) / (xmax - xmin + 1e-9) > 0.7 else (12, 12))
        ann.set_horizontalalignment("right" if (x - xmin) / (xmax - xmin + 1e-9) > 0.7 else "left")
        ann.set_visible(True)
        self.canvas.draw_idle()

    def _on_leave(self, _event):
        if self._hover_items:
            line, dots, ann = self._hover_items
            if ann.get_visible():
                line.set_visible(False)
                ann.set_visible(False)
                for d in dots:
                    d.set_visible(False)
                self.canvas.draw_idle()


def _datefmt(x):
    return mdates.num2date(x).strftime("%a %d %b %Y")


# ================================================================== charts
def draw_trend(fig, p, daily, normal=None, heat=40.0, days=180):
    d = daily.tail(days)
    ax = fig.add_subplot(111)
    style_ax(ax, p)
    x = mdates.date2num(d.index.to_pydatetime())
    temp = d["temp"].values
    avg7 = d["temp"].rolling(7, min_periods=1).mean().values
    lo = min(np.nanmin(d["temp_min"].values), np.nanmin(temp)) - 2
    hi = max(np.nanmax(d["temp_max"].values), np.nanmax(temp)) + 3
    gradient_fill(ax, x, avg7, p["line"], lo, alpha=0.30)
    ax.plot(x, temp, color=p["muted"], lw=0.9, alpha=0.55, label="Daily reading", zorder=3)
    glow_line(ax, x, avg7, p["line"], lw=2.2, label="7-day average")
    if normal is not None:
        ax.plot(x, normal, color=p["accent2"], lw=1.1, ls=(0, (4, 3)), alpha=0.8, label="Seasonal normal", zorder=3)
    hot = temp >= heat
    if hot.any():
        ax.scatter(x[hot], temp[hot], s=22, color=STATUS[3][0], edgecolor=p["card"], lw=1, zorder=6,
                   label=f"≥ {heat:.0f}\N{DEGREE SIGN}C heatwave")
    if hi >= heat - 4:
        ax.axhline(heat, color=STATUS[3][0], lw=1, ls=(0, (2, 2)), alpha=0.8, zorder=2)
        ax.text(x[0], heat + 0.4, f" Heatwave threshold {heat:.0f}\N{DEGREE SIGN}C", color=STATUS[3][0],
                fontsize=7.5, va="bottom", zorder=7)
        hi = max(hi, heat + 3)
    ax.set_xlim(x[0], x[-1])
    ax.set_ylim(lo, hi)
    ax.xaxis_date()
    date_axis(ax, len(d))
    ax.set_ylabel("\N{DEGREE SIGN}C")
    legend(ax, p, ncol=4)
    series = [("Reading", temp, p["muted"], "{:.1f}\N{DEGREE SIGN}C"), ("7-day avg", avg7, p["line"], "{:.1f}\N{DEGREE SIGN}C")]
    return Hover(ax, x, series, _datefmt)


def draw_forecast(fig, p, r, heat=40.0):
    ax = fig.add_subplot(111)
    style_ax(ax, p)
    hist = r.history.tail(60)
    hx = mdates.date2num(hist.index.to_pydatetime())
    fx = mdates.date2num(r.dates.to_pydatetime())
    ax.axvspan(fx[0] - 0.5, fx[-1] + 0.5, color=p["accent"], alpha=0.05, lw=0)
    ax.plot(hx, hist["temp"].values, color=p["muted"], lw=1.2, alpha=0.9, label="Observed", zorder=4)
    ax.scatter(hx, hist["temp"].values, s=8, color=p["muted"], alpha=0.7, zorder=4)
    # connect last observation to the forecast
    cx = np.concatenate([[hx[-1]], fx])
    cy = np.concatenate([[hist["temp"].values[-1]], r.temp])
    clo = np.concatenate([[hist["temp"].values[-1]], r.temp_low])
    chi = np.concatenate([[hist["temp"].values[-1]], r.temp_high])
    ax.fill_between(cx, clo, chi, color=p["band"], alpha=0.16, lw=0, label="80% confidence band", zorder=2)
    glow_line(ax, cx, cy, p["line"], lw=2.4, label=f"AI forecast ({r.model_name})", zorder=5)
    ax.scatter(fx, r.temp, s=34, c=[temp_color(t) for t in r.temp], edgecolor=p["card"], lw=1.3, zorder=6)
    allx = np.concatenate([hx, fx])
    normal_hist = np.full(len(hx), np.nan)
    ax.plot(fx, r.normal, color=p["accent2"], lw=1.1, ls=(0, (4, 3)), alpha=0.8, label="Seasonal normal", zorder=3)
    ax.axvline(hx[-1], color=p["faint"], lw=1, ls=(0, (2, 3)))
    ymin = min(np.nanmin(hist["temp"].values), np.nanmin(r.temp_low)) - 2
    ymax = max(np.nanmax(hist["temp"].values), np.nanmax(r.temp_high)) + 3
    ax.text(hx[-1], ymax - 0.5, "  last observation → forecast", color=p["faint"], fontsize=7.5, va="top")
    if ymax >= heat - 5:
        ax.axhline(heat, color=STATUS[3][0], lw=1, ls=(0, (2, 2)), alpha=0.85)
        ax.text(hx[0], heat + 0.3, f" Heatwave {heat:.0f}\N{DEGREE SIGN}C", color=STATUS[3][0], fontsize=7.5, va="bottom")
        ymax = max(ymax, heat + 3)
    pk = int(np.argmax(r.temp))
    ax.annotate(f"peak {r.temp[pk]:.1f}\N{DEGREE SIGN}C", (fx[pk], r.temp[pk]), xytext=(0, 14),
                textcoords="offset points", ha="center", color=p["text"], fontsize=8, fontweight="bold")
    ax.set_xlim(allx[0] - 0.5, allx[-1] + 0.8)
    ax.set_ylim(ymin, ymax)
    ax.xaxis_date()
    date_axis(ax, len(allx))
    ax.set_ylabel("\N{DEGREE SIGN}C")
    legend(ax, p, ncol=4)
    xs = np.concatenate([hx, fx])
    obs = np.concatenate([hist["temp"].values, np.full(len(fx), np.nan)])
    fc = np.concatenate([np.full(len(hx), np.nan), r.temp])
    band = [f"{a:.0f}-{b:.0f}" for a, b in zip(r.temp_low, r.temp_high)]
    del normal_hist
    series = [("Observed", obs, p["muted"], "{:.1f}\N{DEGREE SIGN}C"), ("Forecast", fc, p["line"], "{:.1f}\N{DEGREE SIGN}C")]
    hv = Hover(ax, xs, series, _datefmt)
    hv.band = band
    return hv


def draw_rain(fig, p, r):
    ax = fig.add_subplot(111)
    style_ax(ax, p)
    x = mdates.date2num(r.dates.to_pydatetime())
    probs = r.rain_prob * 100
    seq = ["#1d3557", "#245a8f", "#2f7fd0", "#4aa8ff", "#8cc8ff"]
    cmap = LinearSegmentedColormap.from_list("rain", seq)
    ax.bar(x, probs, width=0.72, color=[cmap(v / 100) for v in probs], edgecolor=p["card"], lw=1, zorder=3)
    ax.axhline(50, color=p["faint"], lw=0.9, ls=(0, (3, 3)))
    ax.text(x[0] - 0.4, 51, "likely", color=p["faint"], fontsize=7, va="bottom")
    for xi, v in zip(x, probs):
        if v >= 60:
            ax.text(xi, v + 1.5, f"{v:.0f}%", ha="center", va="bottom", color=p["text"], fontsize=7)
    ax.set_ylim(0, 105)
    ax.set_xlim(x[0] - 0.7, x[-1] + 0.7)
    ax.xaxis_date()
    date_axis(ax, len(x))
    ax.set_ylabel("Rain chance %")
    return Hover(ax, x, [("Rain chance", probs, "#4aa8ff", "{:.0f}%")], _datefmt)


def draw_humidity(fig, p, r):
    ax = fig.add_subplot(111)
    style_ax(ax, p)
    x = mdates.date2num(r.dates.to_pydatetime())
    hum = np.asarray(r.humidity)
    ax.axhspan(30, 60, color=p["faint"], alpha=0.10, lw=0)
    ax.text(x[0], 31, " comfort zone 30-60%", color=p["faint"], fontsize=7, va="bottom")
    gradient_fill(ax, x, hum, "#5ab0ff", 0, alpha=0.28)
    glow_line(ax, x, hum, "#5ab0ff", lw=2.0)
    ax.scatter(x, hum, s=14, color="#5ab0ff", edgecolor=p["card"], lw=1, zorder=6)
    ax.set_ylim(0, 105)
    ax.set_xlim(x[0], x[-1])
    ax.xaxis_date()
    date_axis(ax, len(x))
    ax.set_ylabel("Humidity %")
    return Hover(ax, x, [("Humidity", hum, "#5ab0ff", "{:.0f}%"),
                         ("Heat index", np.array([h if h is not None else np.nan for h in r.heat_index]),
                          p["accent"], "{:.0f}\N{DEGREE SIGN}C")], _datefmt)


def draw_backtest(fig, p, metrics):
    if "_test" not in metrics:
        empty(fig, p, "Not enough history for a backtest")
        return None
    dates, actual = metrics["_test"]
    ax = fig.add_subplot(111)
    style_ax(ax, p)
    x = mdates.date2num(pd.DatetimeIndex(dates).to_pydatetime())
    ax.plot(x, actual, color=p["text"], lw=1.6, marker="o", ms=3, label="Actual", zorder=5)
    series = [("Actual", actual, p["text"], "{:.1f}\N{DEGREE SIGN}C")]
    for i, (name, m) in enumerate((k, v) for k, v in metrics.items() if not k.startswith("_")):
        if "pred" in m:
            ax.plot(x, m["pred"], color=CATEGORICAL[i], lw=1.4, label=name, zorder=4)
            series.append((name, m["pred"], CATEGORICAL[i], "{:.1f}\N{DEGREE SIGN}C"))
    ax.xaxis_date()
    date_axis(ax, len(x))
    ax.set_ylabel("\N{DEGREE SIGN}C")
    lg = ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, frameon=False, fontsize=7.5)
    for t in lg.get_texts():
        t.set_color(p["muted"])
    return Hover(ax, x, series, _datefmt)


def draw_heat_calendar(fig, p, matrix):
    ax = fig.add_subplot(111)
    style_ax(ax, p, grid=None)
    data = matrix.values.astype(float)
    vmin, vmax = np.nanmin(data), np.nanmax(data)
    im = ax.imshow(np.ma.masked_invalid(data), cmap=TEMP_CMAP, aspect="auto",
                   vmin=TEMP_STOPS[0][0], vmax=TEMP_STOPS[-1][0])
    for (i, j), v in np.ndenumerate(data):
        if not np.isnan(v):
            r, g, b = to_rgb(temp_color(v))
            light = (0.299 * r + 0.587 * g + 0.114 * b) > 0.55
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=8, color="#1a0d04" if light else "#ffffff")
    ax.set_xticks(range(12))
    ax.set_xticklabels(["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
    ax.set_yticks(range(len(matrix.index)))
    ax.set_yticklabels([str(y) for y in matrix.index])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks(np.arange(-.5, 12, 1), minor=True)
    ax.set_yticks(np.arange(-.5, len(matrix.index), 1), minor=True)
    ax.grid(which="minor", color=p["card"], linewidth=3)
    ax.tick_params(which="minor", length=0)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.outline.set_visible(False)
    cb.ax.tick_params(colors=p["muted"], length=0)
    cb.set_label("avg \N{DEGREE SIGN}C", color=p["muted"])
    ax.set_title(f"range {vmin:.0f} to {vmax:.0f}\N{DEGREE SIGN}C", color=p["faint"], fontsize=8, loc="right")


def draw_seasons(fig, p, table):
    ax = fig.add_subplot(111)
    style_ax(ax, p)
    names = [s for s, v in table.items() if v]
    data = [table[s] for s in names]
    if not data:
        empty(fig, p, "No seasonal data")
        return
    parts = ax.violinplot(data, showextrema=False, widths=0.8)
    for body, vals in zip(parts["bodies"], data):
        c = temp_color(np.mean(vals))
        body.set_facecolor(c)
        body.set_edgecolor(c)
        body.set_alpha(0.35)
    bp = ax.boxplot(data, widths=0.16, patch_artist=True, showfliers=False)
    for i, box in enumerate(bp["boxes"]):
        c = temp_color(np.mean(data[i]))
        box.set(facecolor=c, edgecolor=c)
    for part in ("whiskers", "caps"):
        for ln in bp[part]:
            ln.set(color=p["muted"], lw=1)
    for med in bp["medians"]:
        med.set(color=p["card"], lw=2)
    for i, vals in enumerate(data, start=1):
        ax.text(i, max(vals) + 1, f"avg {np.mean(vals):.1f}\N{DEGREE SIGN}", ha="center", color=p["text"], fontsize=8)
    ax.set_xticks(range(1, len(names) + 1))
    ax.set_xticklabels(names)
    ax.set_ylabel("\N{DEGREE SIGN}C")


def draw_wind_rose(fig, p, table, bins):
    ax = fig.add_subplot(111, projection="polar")
    ax.set_facecolor(p["card"])
    sectors = table.shape[1]
    theta = np.linspace(0, 2 * np.pi, sectors, endpoint=False)
    width = 2 * np.pi / sectors * 0.9
    seq = p["seq"][2:]
    bottom = np.zeros(sectors)
    labels = ["< 10 km/h", "10-20", "20-35", "35+ km/h"]
    for k in range(table.shape[0]):
        ax.bar(theta, table[k], width=width, bottom=bottom, color=seq[min(k, len(seq) - 1)],
               edgecolor=p["card"], lw=1, label=labels[k])
        bottom += table[k]
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_xticks(np.linspace(0, 2 * np.pi, 8, endpoint=False))
    ax.set_xticklabels(["N", "NE", "E", "SE", "S", "SW", "W", "NW"], color=p["muted"])
    ax.tick_params(colors=p["faint"])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.grid(color=p["grid"])
    ax.spines["polar"].set_color(p["border"])
    lg = ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), frameon=False, fontsize=7.5)
    for t in lg.get_texts():
        t.set_color(p["muted"])


def draw_corr(fig, p, corr):
    ax = fig.add_subplot(111)
    style_ax(ax, p, grid=None)
    im = ax.imshow(corr.values, cmap=DIVERGING, vmin=-1, vmax=1)
    n = len(corr)
    for i in range(n):
        for j in range(n):
            v = corr.values[i, j]
            ax.text(j, i, f"{v:+.2f}", ha="center", va="center", fontsize=7.5,
                    color="#ffffff" if abs(v) > 0.35 else p["text"])
    ax.set_xticks(range(n))
    ax.set_xticklabels(corr.columns, rotation=30, ha="right")
    ax.set_yticks(range(n))
    ax.set_yticklabels(corr.index)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks(np.arange(-.5, n, 1), minor=True)
    ax.set_yticks(np.arange(-.5, n, 1), minor=True)
    ax.grid(which="minor", color=p["card"], linewidth=2)
    ax.tick_params(which="minor", length=0)
    cb = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.02)
    cb.outline.set_visible(False)
    cb.ax.tick_params(colors=p["muted"], length=0)


def draw_hotspots(fig, p, table, heat=40.0):
    ax = fig.add_subplot(111)
    style_ax(ax, p, grid="x")
    t = table.iloc[::-1]
    y = np.arange(len(t))
    colors = [temp_color(v) for v in t["max_temp"]]
    ax.barh(y, t["heat_days"], color=colors, edgecolor=p["card"], lw=2, height=0.72, zorder=3)
    for yi, (days, mx) in enumerate(zip(t["heat_days"], t["max_temp"])):
        ax.text(days + 0.3, yi, f"{int(days)} d   max {mx:.1f}\N{DEGREE SIGN}", va="center", color=p["muted"], fontsize=7.5)
    ax.set_yticks(y)
    ax.set_yticklabels(t.index)
    ax.set_xlabel(f"readings ≥ {heat:.0f}\N{DEGREE SIGN}C in the last 60 days")
    ax.set_xlim(0, max(1, t["heat_days"].max()) * 1.35)


def draw_world_band(fig, p, snap, heat=40.0, cold=10.0):
    ax = fig.add_subplot(111)
    style_ax(ax, p, grid="both")
    x, y = snap["longitude"].values.astype(float), snap["temperature"].values.astype(float)
    ax.axhspan(heat, max(heat + 8, np.nanmax(y) + 2), color=STATUS[3][0], alpha=0.07, lw=0)
    ax.axhspan(min(cold - 8, np.nanmin(y) - 2), cold, color="#4aa8ff", alpha=0.07, lw=0)
    ax.scatter(x, y, s=46, c=[temp_color(v) for v in y], edgecolor=p["card"], lw=1.2, zorder=4)
    order = np.argsort(y)
    for idx in list(order[-4:]) + list(order[:3]):
        ax.annotate(snap["country"].values[idx], (x[idx], y[idx]), xytext=(6, 4), textcoords="offset points",
                    color=p["text"], fontsize=7.5)
    ax.set_xlabel("Longitude (\N{DEGREE SIGN}E)  -  each dot is a country's latest reading")
    ax.set_ylabel("\N{DEGREE SIGN}C")
    ax.set_xlim(-180, 180)
    names = snap["country"].values
    srt = np.argsort(x)
    hv = Hover(ax, x[srt], [("Temp", y[srt], p["accent"], "{:.1f}\N{DEGREE SIGN}C")],
               xfmt=lambda v, n=names[srt], xs=x[srt]: f"{n[int(np.argmin(np.abs(xs - v)))]}  (lon {v:.1f})")
    return hv


def draw_live(fig, p, streams, heat=40.0):
    ax = fig.add_subplot(111)
    style_ax(ax, p)
    if not streams:
        empty(fig, p, "Start the AWS monitor to stream live sensor readings")
        return
    top = 0
    lo = 99
    for i, (country, vals) in enumerate(list(streams.items())[:6]):
        v = np.array(vals[-60:], dtype=float)
        xs = np.arange(len(v))
        color = CATEGORICAL[i]
        ax.plot(xs, v, color=color, lw=1.8, label=country)
        ax.scatter([xs[-1]], [v[-1]], s=26, color=color, edgecolor=p["card"], zorder=5)
        if len(streams) <= 4:
            ax.text(xs[-1] + 0.8, v[-1], f"{country} {v[-1]:.1f}\N{DEGREE SIGN}", color=p["text"], fontsize=7.5,
                    va="center")
        top, lo = max(top, v.max()), min(lo, v.min())
    if top >= heat - 6:
        ax.axhline(heat, color=STATUS[3][0], lw=1, ls=(0, (2, 2)))
    ax.set_xlim(0, 75)
    ax.set_xlabel("sensor ticks (newest on the right)")
    ax.set_ylabel("\N{DEGREE SIGN}C")
    lg = ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=6, frameon=False, fontsize=7.5)
    for t in lg.get_texts():
        t.set_color(p["muted"])


def draw_sql(fig, p, columns, rows):
    """Auto-chart for any SQL result: picks a label column + a number column."""
    if not rows or not columns:
        empty(fig, p, "Run a SELECT query to see an automatic chart here")
        return None
    df = pd.DataFrame(rows, columns=columns)
    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and c.lower() not in ("id", "alert_id")
                and df[c].notna().any()]
    txt_cols = [c for c in df.columns if c not in num_cols and c.lower() not in ("id", "alert_id")]
    if not num_cols:
        empty(fig, p, "No numeric column in this result to chart")
        return None
    pref = [c for c in num_cols if any(k in c.lower() for k in ("temp", "max", "min", "avg", "count", "rain",
                                                                 "wind", "humid", "precip", "days", "total"))]
    ycol = pref[0] if pref else num_cols[0]
    is_temp = "temp" in ycol.lower() or "heat" in ycol.lower()
    label = txt_cols[0] if txt_cols else None
    datey = label is not None and (label.lower() in ("date", "month", "recorded_at", "day", "year", "forecast_date")
                                   or str(df[label].iloc[0])[:2] in ("19", "20"))
    ax = fig.add_subplot(111)
    if label is None and len(num_cols) >= 2:
        style_ax(ax, p, grid="both")
        xcol = [c for c in num_cols if c != ycol][0]
        ax.scatter(df[xcol], df[ycol], s=18, alpha=0.8,
                   c=[temp_color(v) for v in df[ycol]] if is_temp else p["accent"], edgecolor="none")
        ax.set_xlabel(xcol)
        ax.set_ylabel(ycol)
        return None
    if datey and len(df) > 2:
        style_ax(ax, p)
        d = df[[label, ycol]].dropna().copy()
        d["_x"] = pd.to_datetime(d[label].astype(str), errors="coerce")
        d = d.dropna(subset=["_x"]).sort_values("_x")
        if d.empty:
            empty(fig, p, "Could not read the dates in this result")
            return None
        x = mdates.date2num(d["_x"].dt.to_pydatetime())
        y = d[ycol].astype(float).values
        base = np.nanmin(y) - (np.nanmax(y) - np.nanmin(y)) * 0.15 - 0.5
        gradient_fill(ax, x, y, p["line"], base, alpha=0.3)
        glow_line(ax, x, y, p["line"], lw=2)
        if is_temp:
            ax.scatter(x, y, s=12, c=[temp_color(v) for v in y], zorder=6, edgecolor="none")
        ax.set_xlim(x[0], x[-1])
        ax.set_ylim(base, np.nanmax(y) + (np.nanmax(y) - np.nanmin(y)) * 0.12 + 0.5)
        ax.xaxis_date()
        date_axis(ax, (d["_x"].iloc[-1] - d["_x"].iloc[0]).days)
        ax.set_ylabel(ycol)
        return Hover(ax, x, [(ycol, y, p["line"], "{:,.2f}")], _datefmt)
    style_ax(ax, p, grid="x")
    d = df.head(25).copy()
    labels = d[label].astype(str).str.slice(0, 22) if label else [str(i + 1) for i in range(len(d))]
    y = d[ycol].astype(float).values
    pos = np.arange(len(d))[::-1]
    colors = [temp_color(v) for v in y] if is_temp else [blend(p["accent"], p["card"], 0.15 + 0.5 * i / max(1, len(y)))
                                                         for i in range(len(y))]
    ax.barh(pos, y, color=colors, edgecolor=p["card"], lw=2, height=0.74, zorder=3)
    span = (np.nanmax(np.abs(y)) or 1)
    for pi, v in zip(pos, y):
        ax.text(v + span * 0.01 if v >= 0 else v - span * 0.01, pi, f"{v:,.1f}", va="center",
                ha="left" if v >= 0 else "right", color=p["muted"], fontsize=7.5)
    ax.set_yticks(pos)
    ax.set_yticklabels(labels)
    ax.set_xlabel(ycol)
    lo = min(0, np.nanmin(y) * 1.15)
    ax.set_xlim(lo, max(0, np.nanmax(y)) * 1.15 + 0.01)
    if len(df) > 25:
        ax.set_title(f"top 25 of {len(df)} rows", color=p["faint"], fontsize=8, loc="right")
    return None
