"""Command Center - live status of the selected region (Phase IV/V)."""

from ...analyzers import run_all
from ...exceptions import HeatGuardError
from ...forecaster import SeasonalTrendForecaster
from ...text_tools import condition_kind
from ..app import BasePage
from ..charts import ChartPanel, draw_trend
from ..themes import STATUS
from ..widgets import Card, KpiTile, TemperatureDial, RiskRow, DayCard, StatusBadge, temp_color

EPA = {1: ("Good", 0), 2: ("Moderate", 1), 3: ("Unhealthy (sensitive)", 2), 4: ("Unhealthy", 3),
       5: ("Very unhealthy", 3), 6: ("Hazardous", 3)}


class OverviewPage(BasePage):
    def build(self):
        pad = 14
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)
        self.grid_rowconfigure(2, weight=1)

        head = self.frame(self)
        head.grid(row=0, column=0, columnspan=3, sticky="ew", padx=pad, pady=(12, 6))
        self.title = self.label(head, "", "h1", bg="bg")
        self.title.pack(side="left")
        self.subtitle = self.label(head, "", "small", fg="muted", bg="bg")
        self.subtitle.pack(side="left", padx=14, pady=(10, 0))
        self.badge = StatusBadge(head, 0)
        self.badge.pack(side="right", pady=(6, 0))
        self.label(head, "OVERALL RISK", "tiny", fg="faint", bg="bg").pack(side="right", padx=8, pady=(8, 0))

        kpis = self.frame(self)
        kpis.grid(row=1, column=0, columnspan=3, sticky="ew", padx=pad - 4)
        specs = [("Temperature", "thermo", "\N{DEGREE SIGN}C", (-10, 50)), ("Feels like", "heat", "\N{DEGREE SIGN}C", (-10, 60)),
                 ("Humidity", "drop", "%", (0, 100)), ("Wind", "wind", "km/h", (0, 80)),
                 ("Rain", "rain", "mm", (0, 20)), ("Air quality", "leaf", "O₃ µg/m³", (0, 250))]
        self.tiles = []
        for i, (lab, icon, unit, rng) in enumerate(specs):
            t = KpiTile(kpis, self.tm, lab, icon, unit, meter_range=rng)
            t.grid(row=0, column=i, sticky="ew", padx=4, pady=4)
            kpis.grid_columnconfigure(i, weight=1, uniform="kpi")
            self.tiles.append(t)

        dial_card = Card(self, self.tm, "Live temperature", "latest station reading")
        dial_card.grid(row=2, column=0, sticky="nsew", padx=(pad, 6), pady=8)
        self.dial = TemperatureDial(dial_card.body, self.tm, size=250)
        self.dial.pack(fill="both", expand=True)
        self.normal_lbl = self.label(dial_card.body, "", "small", fg="muted")
        self.normal_lbl.pack(pady=(4, 0))

        trend = Card(self, self.tm, "Temperature trend", "last 180 days • hover for values")
        trend.grid(row=2, column=1, sticky="nsew", padx=6, pady=8)
        self.trend = ChartPanel(trend.body, self.tm, figsize=(6, 2.8))
        self.trend.pack(fill="both", expand=True)
        self.charts.append(self.trend)

        risk = Card(self, self.tm, "Risk matrix", "5 analyzers • polymorphism")
        risk.grid(row=2, column=2, sticky="nsew", padx=(6, pad), pady=8)
        risk.configure(width=self.app.px(360))
        self.risk_rows = []
        for _ in range(5):
            r = RiskRow(risk.body, self.tm, height=46)
            r.configure(width=self.app.px(330))
            r.pack(fill="x")
            self.risk_rows.append(r)

        outlook = Card(self, self.tm, "AI 7-day outlook", "ensemble model • temperature, rain chance, risk")
        outlook.grid(row=3, column=0, columnspan=3, sticky="ew", padx=pad, pady=(0, 12))
        self.button(outlook.tools, "Open Forecast Lab  →", lambda: self.app.show_page("forecast"),
                    kind="ghost", font=self.fonts["small_bold"]).pack(side="right")
        row = self.frame(outlook.body, bg="card")
        row.pack(fill="x")
        self.days = []
        for i in range(7):
            d = DayCard(row, self.tm, width=108, height=160)
            d.grid(row=0, column=i, padx=3, sticky="ew")
            row.grid_columnconfigure(i, weight=1, uniform="day")
            self.days.append(d)
        side = self.frame(row, bg="card")
        side.grid(row=0, column=7, sticky="nsew", padx=(14, 0))
        row.grid_columnconfigure(7, weight=3)
        self.outlook_head = self.label(side, "AI model is training...", "h3", anchor="w", justify="left")
        self.outlook_head.pack(fill="x", anchor="w")
        self.outlook_txt = self.label(side, "", "small", fg="muted", anchor="w", justify="left", wraplength=360)
        self.outlook_txt.pack(fill="x", anchor="w", pady=(6, 0))

    # -------------------------------------------------------------- data
    def refresh(self):
        country = self.app.country
        try:
            rec = self.app.dm.latest(country)
            daily = self.app.dm.daily(country)
        except HeatGuardError as exc:
            self.title.configure(text=country)
            self.subtitle.configure(text=str(exc))
            return
        self.rec = rec
        t, hum = float(rec["temperature"]), float(rec["humidity"])
        wind, rain = float(rec["wind_kph"]), float(rec["precip_mm"])
        hi = float(rec["heat_index"]) if rec["heat_index"] is not None else t
        self.title.configure(text=country)
        self.subtitle.configure(text=f"Last reading {rec['ts']:%a %d %b %Y, %H:%M}  •  {rec['condition']}  "
                                     f"•  {rec['season']} season  •  lon {rec['longitude']:.2f}")
        reading = {"temperature": t, "normal": rec["normal"], "humidity": hum, "wind_kph": wind, "precip_mm": rain}
        results = run_all(reading)
        for row, res in zip(self.risk_rows, results):
            row.set(res)
        top = max(r.level for r in results)
        worst = max(results, key=lambda r: r.level)
        self.badge.set(top, worst.label if top > 0 else "ALL CLEAR")

        normal = rec["normal"]
        dep = "" if normal is None else f" • normal {normal:.1f}\N{DEGREE SIGN}"
        lvl_t = results[0].level if t >= 25 else results[2].level
        self.tiles[0].update_value(f"{t:.1f}", f"{rec['temp_change']:+.1f}\N{DEGREE SIGN} vs previous{dep}",
                                   lvl_t, meter=t, meter_color=temp_color(t))
        self.tiles[1].update_value(f"{hi:.0f}", results[1].label.title(), results[1].level, meter=hi,
                                   meter_color=temp_color(hi))
        self.tiles[2].update_value(f"{hum:.0f}", "Muggy" if hum >= 70 else "Dry" if hum <= 30 else "Comfortable",
                                   None, meter=hum, meter_color="#4aa8ff")
        gust = float(rec["gust_mph"] or 0) * 1.609
        self.tiles[3].update_value(f"{wind:.0f}", f"{rec['wind_direction']} • gusts {gust:.0f} km/h",
                                   results[3].level, meter=wind, meter_color="#3fe0b0")
        kind = condition_kind(rec["condition"], t, wind)
        self.tiles[4].icon = kind if kind in ("rain", "storm", "snow", "sun", "cloud", "partly", "fog") else "rain"
        self.tiles[4].update_value(f"{rain:.1f}", str(rec["condition"])[:26], results[4].level, meter=rain,
                                   meter_color="#5aa9ff")
        epa_name, epa_lvl = EPA.get(int(rec["aqi_index"] or 1), ("Unknown", 0))
        self.tiles[5].update_value(f"{float(rec['ozone'] or 0):.0f}", f"US-EPA {int(rec['aqi_index'] or 1)} • {epa_name}",
                                   epa_lvl, meter=float(rec["ozone"] or 0), meter_color="#3ecf8e")
        self.dial.set_value(t, hi, caption=f"{country.upper()}  •  {rec['ts']:%d %b %H:%M}")
        self.normal_lbl.configure(text="" if normal is None else
                                  f"Seasonal normal {normal:.1f}\N{DEGREE SIGN}C  •  departure {t - normal:+.1f}\N{DEGREE SIGN}C")

        try:
            base = SeasonalTrendForecaster().fit(daily["temp"]).baseline(daily.tail(180).index)
        except HeatGuardError:
            base = None
        heat = self.app.thresholds["heat_c"]
        self.trend.set_draw(lambda fig, p: draw_trend(fig, p, daily, base, heat))

        self.apply_auto_theme()
        self.app.raise_alert(country, results, t, source="latest reading")
        self._load_outlook(country)

    def apply_auto_theme(self):
        if getattr(self, "rec", None) is not None:
            name, reason = self.theme_for_reading(self.rec)
            self.app.auto_theme(name, f"{self.app.country}: {reason}")

    def _load_outlook(self, country):
        self.outlook_head.configure(text="AI ensemble is training on this region...")
        self.outlook_txt.configure(text="Seasonal-trend model + random forest are learning from the history.")
        engine = self.app.engine

        def done(res):
            if country != self.app.country:
                return
            for card, i in zip(self.days, range(7)):
                d = res.dates[i]
                card.set(d.strftime("%a"), d.strftime("%d %b"), res.kind[i], res.temp[i], res.temp_low[i],
                         res.temp_high[i], float(res.rain_prob[i]), res.risk_level[i], res.risk_label[i])
            worst = max(res.risk_level)
            head = {0: "Calm week ahead", 1: "Warm spell ahead - stay alert", 2: "Early warning issued",
                    3: "Severe early warning"}[worst]
            wet = int(sum(p >= 0.5 for p in res.rain_prob[:7]))
            if worst == 0 and wet >= 4:
                head = f"Wet week ahead - rain likely on {wet} of 7 days"
            self.outlook_head.configure(text=f"{STATUS[worst][1]}  {head}")
            self.outlook_txt.configure(text=res.summary)
            if worst >= 2:
                days = [f"{d:%a %d}" for d, lv in zip(res.dates, res.risk_level) if lv >= 2]
                key = (country, "forecast", tuple(days))
                if key not in self.app.alerted:
                    self.app.alerted.add(key)
                    label = res.risk_label[res.risk_level.index(worst)]
                    self.app.toasts.show(f"Forecast early warning • {country}",
                                         f"{label.title()} expected on {', '.join(days[:4])}.", level=worst,
                                         duration=9000)
                    self.app.db.insert_alert(country, "Forecast", label, float(max(res.temp)),
                                             f"{label} forecast for {', '.join(days)}", "AI forecast")

        def fail(exc):
            self.outlook_head.configure(text="Forecast unavailable")
            self.outlook_txt.configure(text=str(exc))

        self.app.run_bg(lambda: engine.run(country, 7, "AI Ensemble", backtest=False), done, fail)
