"""AI Forecast Lab - Phase II prediction + Phase V advisories."""
import csv
import tkinter as tk
from datetime import datetime
from tkinter import ttk, filedialog

import numpy as np

from ...advisories import STAKEHOLDERS, build_advisory
from ...forecaster import MODEL_CHOICES
from ..app import BasePage
from ..charts import ChartPanel, draw_forecast, draw_rain, draw_humidity, draw_backtest
from ..themes import STATUS
from ..widgets import Card, Segmented

SHORT = {"AI Ensemble": "AI Ensemble", "Random Forest (ML)": "Random Forest", "Seasonal-Trend AR": "Seasonal AR"}
KIND_SYMBOL = {"sun": "☀", "heat": "♨", "partly": "⛅", "cloud": "☁", "rain": "☂",
               "storm": "⚡", "snow": "❄", "wind": "≋", "fog": "▒"}


class ForecastPage(BasePage):
    def build(self):
        pad = 14
        self.horizon = 14
        self.model = "AI Ensemble"
        self.result = None
        self.stake = STAKEHOLDERS[0]
        for c, w in ((0, 3), (1, 3), (2, 2)):
            self.grid_columnconfigure(c, weight=w, uniform="fc")
        self.grid_rowconfigure(2, weight=5)
        self.grid_rowconfigure(3, weight=3)
        self.grid_rowconfigure(4, weight=3)

        # ---------------------------------------------------------- controls
        bar = self.frame(self)
        bar.grid(row=0, column=0, columnspan=3, sticky="ew", padx=pad, pady=(12, 6))
        self.title = self.label(bar, "AI Forecast Lab", "h1", bg="bg")
        self.title.pack(side="left")
        self.label(bar, "HORIZON", "tiny", fg="faint", bg="bg").pack(side="left", padx=(24, 6))
        Segmented(bar, self.tm, [(7, "7 days"), (14, "14 days"), (30, "30 days")], self._set_horizon,
                  value=14).pack(side="left")
        self.label(bar, "MODEL", "tiny", fg="faint", bg="bg").pack(side="left", padx=(18, 6))
        Segmented(bar, self.tm, [(m, SHORT[m]) for m in MODEL_CHOICES], self._set_model,
                  value=self.model).pack(side="left")
        self.button(bar, "▶  Run forecast", self.run).pack(side="right")
        self.progress = ttk.Progressbar(bar, mode="indeterminate", length=120, style="Accent.Horizontal.TProgressbar")

        # ---------------------------------------------------------- advisory
        self.adv = self.frame(self, bg="card", highlightthickness=1)
        self.tm.bind(self.adv, highlightbackground="border")
        self.adv.grid(row=1, column=0, columnspan=3, sticky="ew", padx=pad, pady=(0, 8))
        self.adv_strip = tk.Frame(self.adv, width=6, bg=STATUS[0][0])
        self.adv_strip.pack(side="left", fill="y")
        self.adv_icon = tk.Label(self.adv, text=STATUS[0][1], font=self.fonts["symbol_big"], fg=STATUS[0][0])
        self.tm.bind(self.adv_icon, bg="card")
        self.adv_icon.pack(side="left", padx=(14, 10))
        txt = self.frame(self.adv, bg="card")
        txt.pack(side="left", fill="x", expand=True, pady=8)
        self.adv_head = self.label(txt, "Run the AI model to generate an early warning", "h3", anchor="w")
        self.adv_head.pack(fill="x")
        self.adv_body = self.label(txt, "", "small", fg="muted", anchor="w", justify="left", wraplength=1000)
        self.adv_body.pack(fill="x")

        # ------------------------------------------------------------ charts
        main = Card(self, self.tm, "Temperature forecast", "observed (60 days) + AI forecast with 80% band")
        main.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=(pad, 6), pady=(0, 8))
        self.main_chart = ChartPanel(main.body, self.tm, figsize=(7, 3))
        self.main_chart.pack(fill="both", expand=True)

        acc = Card(self, self.tm, "Model accuracy", "backtest: hide last 30 days, predict them")
        acc.grid(row=2, column=2, sticky="nsew", padx=(6, pad), pady=(0, 8))
        self.metric_box = self.frame(acc.body, bg="card")
        self.metric_box.pack(fill="x")
        self.bt_chart = ChartPanel(acc.body, self.tm, figsize=(4, 2))
        self.bt_chart.pack(fill="both", expand=True, pady=(6, 0))

        rain = Card(self, self.tm, "Chance of rain", "logistic regression • per day")
        rain.grid(row=3, column=0, sticky="nsew", padx=(pad, 6), pady=(0, 8))
        self.rain_chart = ChartPanel(rain.body, self.tm, figsize=(4, 1.8))
        self.rain_chart.pack(fill="both", expand=True)

        hum = Card(self, self.tm, "Humidity forecast", "seasonal-trend model")
        hum.grid(row=3, column=1, sticky="nsew", padx=6, pady=(0, 8))
        self.hum_chart = ChartPanel(hum.body, self.tm, figsize=(4, 1.8))
        self.hum_chart.pack(fill="both", expand=True)

        adv = Card(self, self.tm, "Stakeholder advisory", "Phase V • who should do what")
        adv.grid(row=3, column=2, sticky="nsew", padx=(6, pad), pady=(0, 8))
        Segmented(adv.body, self.tm, [(s, s) for s in STAKEHOLDERS], self._set_stake, value=self.stake,
                  font=self.fonts["tiny"], padx=7).pack(anchor="w")
        self.stake_txt = self.label(adv.body, "", "body", anchor="nw", justify="left", wraplength=380)
        self.stake_txt.pack(fill="both", expand=True, pady=(10, 0))
        self.stake_txt.bind("<Configure>", lambda e: self.stake_txt.configure(wraplength=max(200, e.width - 8)))

        days = Card(self, self.tm, "Day-by-day forecast messages", "double-click a day for details")
        self.button(days.tools, "\u21E9  Export CSV", self.export_csv, kind="ghost",
                    font=self.fonts["small_bold"]).pack(side="right", padx=(6, 0))
        self.button(days.tools, "\u2714  Save to database", self.save_db, kind="ghost",
                    font=self.fonts["small_bold"]).pack(side="right")
        days.grid(row=4, column=0, columnspan=3, sticky="nsew", padx=pad, pady=(0, 12))
        cols = ("date", "sky", "temp", "range", "rain", "humidity", "risk", "message")
        self.table = ttk.Treeview(days.body, columns=cols, show="headings", height=5)
        widths = {"date": 96, "sky": 44, "temp": 70, "range": 80, "rain": 64, "humidity": 76, "risk": 130, "message": 700}
        for c in cols:
            self.table.heading(c, text=c.upper())
            self.table.column(c, width=self.app.px(widths[c]), anchor="w" if c in ("message", "risk", "date") else "center",
                              stretch=c == "message")
        vsb = ttk.Scrollbar(days.body, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=vsb.set)
        self.table.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.table.bind("<Double-1>", self._day_details)
        self.charts = [self.main_chart, self.bt_chart, self.rain_chart, self.hum_chart]
        self.tm.watch(self.table, self._tag_colors)
        self._tag_colors()

    def _tag_colors(self):
        for lvl in range(4):
            self.table.tag_configure(f"lvl{lvl}", foreground=STATUS[lvl][0] if lvl >= 2 else self.tm.p["text"])

    # ----------------------------------------------------------- controls
    def _set_horizon(self, v):
        self.horizon = v
        self.run()

    def _set_model(self, v):
        self.model = v
        self.run()

    def _set_stake(self, v):
        self.stake = v
        self._show_stake()

    def refresh(self):
        self.run()

    def run(self):
        country, horizon, model = self.app.country, self.horizon, self.model
        self.title.configure(text=f"AI Forecast Lab • {country}")
        self.adv_head.configure(text=f"Training {model} on {country}'s history...")
        self.adv_body.configure(text="Fitting seasonal-trend regression, random forest, humidity, wind and rain models "
                                     "+ 30-day backtest. This takes a few seconds.")
        self.progress.pack(side="right", padx=10)
        self.progress.start(12)
        self.app.set_status(f"Training forecast models for {country}...")

        def done(res):
            self.progress.stop()
            self.progress.pack_forget()
            if country != self.app.country:
                return
            self.show(res)

        def fail(exc):
            self.progress.stop()
            self.progress.pack_forget()
            self.adv_head.configure(text="Forecast failed")
            self.adv_body.configure(text=str(exc))

        self.app.run_bg(lambda: self.app.engine.run(country, horizon, model, backtest=True), done, fail)

    # ------------------------------------------------------------- render
    def show(self, r):
        self.result = r
        heat = self.app.thresholds["heat_c"]
        self.main_chart.set_draw(lambda fig, p: draw_forecast(fig, p, r, heat))
        self.rain_chart.set_draw(lambda fig, p: draw_rain(fig, p, r))
        self.hum_chart.set_draw(lambda fig, p: draw_humidity(fig, p, r))
        self.bt_chart.set_draw(lambda fig, p: draw_backtest(fig, p, r.metrics))
        self._metrics(r.metrics)

        headline, level, self.advice = build_advisory(r)
        color, sym, _ = STATUS[level]
        self.adv_strip.configure(bg=color)
        self.adv_icon.configure(text=sym, fg=color)
        self.adv_head.configure(text=headline)
        self.adv_body.configure(text=r.summary)
        self._show_stake()

        self.table.delete(*self.table.get_children())
        for i, d in enumerate(r.dates):
            self.table.insert("", "end", iid=str(i), tags=(f"lvl{r.risk_level[i]}",), values=(
                d.strftime("%a %d %b"), KIND_SYMBOL.get(r.kind[i], ""), f"{r.temp[i]:.1f}\N{DEGREE SIGN}C",
                f"{r.temp_low[i]:.0f}-{r.temp_high[i]:.0f}\N{DEGREE SIGN}", f"{r.rain_prob[i]:.0%}",
                f"{r.humidity[i]:.0f}%", f"{STATUS[r.risk_level[i]][1]} {r.risk_label[i]}",
                r.messages[i].split("->")[-1].strip()))
        self.app.set_status(f"Forecast ready • {r.country} • {r.model_name} • {r.horizon} days")
        self.apply_auto_theme()
        if level >= 2:
            self.app.toasts.show(f"Early warning • {r.country}", headline, level=level, duration=8000)

    def _metrics(self, metrics):
        for w in self.metric_box.winfo_children():
            w.destroy()
        heads = ("MODEL", "MAE", "RMSE", "±3\N{DEGREE SIGN}C ACC")
        for j, h in enumerate(heads):
            self.label(self.metric_box, h, "tiny", fg="faint").grid(row=0, column=j, sticky="w", padx=(0, 10))
        rows = [(k, v) for k, v in metrics.items() if not k.startswith("_")]
        best = min(rows, key=lambda kv: kv[1]["MAE"])[0] if rows else None
        for i, (name, m) in enumerate(rows, start=1):
            fg = "accent" if name == best else "text"
            vals = (("★ " if name == best else "") + SHORT.get(name, name), f"{m['MAE']:.2f}\N{DEGREE SIGN}",
                    f"{m['RMSE']:.2f}\N{DEGREE SIGN}", f"{m['within3']:.0f}%")
            for j, v in enumerate(vals):
                self.label(self.metric_box, v, "small_bold" if j == 0 else "small", fg=fg).grid(
                    row=i, column=j, sticky="w", padx=(0, 10), pady=1)
        self.metric_box.grid_columnconfigure(0, weight=1)

    def _show_stake(self):
        if getattr(self, "advice", None):
            self.stake_txt.configure(text=self.advice.get(self.stake, ""))

    def apply_auto_theme(self):
        r = self.result
        if r is None:
            return
        if max(r.risk_level) >= 2 and any("HEAT" in lab for lab in r.risk_label) or np.max(r.temp) >= 35:
            name, why = "blaze", f"forecast peak {np.max(r.temp):.1f}\N{DEGREE SIGN}C"
        elif np.min(r.temp) <= 8:
            name, why = "frost", f"forecast low {np.min(r.temp):.1f}\N{DEGREE SIGN}C"
        elif np.mean(r.rain_prob) >= 0.5:
            name, why = "monsoon", f"rain likely ({np.mean(r.rain_prob):.0%} average chance)"
        elif np.mean(r.wind) >= 25:
            name, why = "gale", f"windy ({np.mean(r.wind):.0f} km/h average)"
        else:
            name, why = "solar", "moderate forecast"
        self.app.auto_theme(name, f"{r.country} forecast: {why}")

    # ----------------------------------------------------------- actions
    def _day_details(self, _e):
        sel = self.table.selection()
        if not sel or not self.result:
            return
        i = int(sel[0])
        r = self.result
        self.app.toasts.show(f"{r.dates[i]:%A %d %B}", r.messages[i], level=r.risk_level[i], duration=9000)

    def save_db(self):
        r = self.result
        if not r:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = [(now, r.country, d.strftime("%Y-%m-%d"), r.model_name, round(float(r.temp[i]), 2),
                 round(float(r.temp_low[i]), 2), round(float(r.temp_high[i]), 2), round(float(r.humidity[i]), 1),
                 round(float(r.rain_prob[i]) * 100, 1), r.risk_label[i]) for i, d in enumerate(r.dates)]
        self.app.db.insert_forecasts(rows)
        self.app.toasts.show("Forecast saved to SQLite", f"{len(rows)} rows added to the 'forecasts' table. "
                             "Try: SELECT * FROM forecasts in the SQL Lab.", level=0)

    def export_csv(self):
        r = self.result
        if not r:
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=f"forecast_{r.country}.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["date", "temp_c", "low_c", "high_c", "humidity_pct", "rain_chance_pct", "risk", "message"])
            for row, msg in zip(r.table_rows(), r.messages):
                w.writerow(list(row) + [msg])
        self.app.toasts.show("Exported", path, level=0)
