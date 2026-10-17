"""
Alerts & AWS  -  Phase III (IoT stations) + Phase V (early warning)
====================================================================
Experiment 5 live: three sensor THREADS stream readings for the watch-list,
faulty values raise InvalidSensorValueError (caught + shown as FAULT),
threshold breaches pop up as toasts / a modal alert and go into the
SQLite 'alerts' table.
"""
import time
import tkinter as tk
from tkinter import ttk

from ...analyzers import run_all
from ...exceptions import HeatGuardError
from ...monitor import AWSNetwork
from ..app import BasePage
from ..charts import ChartPanel, draw_live
from ..themes import STATUS
from ..widgets import Card

DEFAULT_WATCH = ("India", "Kuwait", "Pakistan", "Saudi Arabia", "Iceland", "Russia")


class AlertsPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.network = AWSNetwork()
        self.streams = {}
        self.live = {}
        self.faults = 0
        self.readings = 0
        self.popups = tk.BooleanVar(value=True)
        self.last_alert = {}

    def build(self):
        pad = 14
        self.grid_columnconfigure(0, weight=3, uniform="al")
        self.grid_columnconfigure(1, weight=2, uniform="al")
        self.grid_rowconfigure(2, weight=3)
        self.grid_rowconfigure(3, weight=2)

        head = self.frame(self)
        head.grid(row=0, column=0, columnspan=2, sticky="ew", padx=pad, pady=(12, 6))
        self.label(head, "Alerts & IoT weather stations", "h1", bg="bg").pack(side="left")
        self.state_lbl = self.label(head, "●  monitor stopped", "small_bold", fg="faint", bg="bg")
        self.state_lbl.pack(side="left", padx=16, pady=(8, 0))

        # ------------------------------------------------------------ control
        ctl = Card(self, self.tm, "Control room", "watch-list • thresholds • demo triggers")
        ctl.grid(row=1, column=0, columnspan=2, sticky="ew", padx=pad, pady=(0, 8))
        body = ctl.body
        wl = self.frame(body, bg="card")
        wl.pack(side="left", fill="y")
        self.label(wl, "WATCH-LIST (Ctrl-click, max 6)", "tiny", fg="faint").pack(anchor="w")
        lf = self.frame(wl, bg="card")
        lf.pack(fill="y", expand=True)
        self.watch = tk.Listbox(lf, selectmode="extended", height=6, width=22, exportselection=False, bd=0,
                                highlightthickness=1, activestyle="none", font=self.fonts["small"])
        self.tm.bind(self.watch, bg="card_hi", fg="text", selectbackground="accent", selectforeground="accent_text",
                     highlightbackground="border")
        sb = ttk.Scrollbar(lf, orient="vertical", command=self.watch.yview)
        self.watch.configure(yscrollcommand=sb.set)
        self.watch.pack(side="left", fill="y")
        sb.pack(side="left", fill="y")
        for i, c in enumerate(self.app.dm.countries()):
            self.watch.insert("end", c)
            if c in DEFAULT_WATCH:
                self.watch.selection_set(i)

        th = self.frame(body, bg="card")
        th.pack(side="left", fill="y", padx=24)
        self.label(th, "ALERT THRESHOLDS (live)", "tiny", fg="faint").grid(row=0, column=0, columnspan=4, sticky="w")
        self.spins = {}
        specs = [("heat_c", "Heatwave \N{DEGREE SIGN}C", 30, 50), ("severe_heat_c", "Severe heat \N{DEGREE SIGN}C", 35, 55),
                 ("cold_c", "Cold wave \N{DEGREE SIGN}C", -20, 20), ("wind_kph", "High wind km/h", 10, 120),
                 ("heat_index_c", "Heat index \N{DEGREE SIGN}C", 30, 60), ("rain_mm", "Rain mm", 1, 50)]
        for i, (key, text, lo, hi) in enumerate(specs):
            r, c = 1 + i % 3, (i // 3) * 2
            self.label(th, text, "small", fg="muted").grid(row=r, column=c, sticky="w", pady=3, padx=(0, 6))
            var = tk.DoubleVar(value=self.app.thresholds[key])
            sp = ttk.Spinbox(th, from_=lo, to=hi, increment=0.5, width=6, textvariable=var,
                             command=lambda k=key, v=var: self._set_threshold(k, v))
            sp.bind("<KeyRelease>", lambda e, k=key, v=var: self._set_threshold(k, v))
            sp.grid(row=r, column=c + 1, sticky="w", padx=(0, 18))
            self.spins[key] = var

        act = self.frame(body, bg="card")
        act.pack(side="right", fill="y")
        row1 = self.frame(act, bg="card")
        row1.pack(anchor="e")
        self.start_btn = self.button(row1, "▶  Start AWS monitor", self.toggle)
        self.start_btn.pack(side="left")
        self.button(row1, "⌕  Scan latest data", self.scan, kind="ghost").pack(side="left", padx=(6, 0))
        self.label(act, "DEMO TRIGGERS - inject into the selected region (or first station)", "tiny", fg="faint").pack(
            anchor="e", pady=(12, 4))
        row2 = self.frame(act, bg="card")
        row2.pack(anchor="e")
        self.button(row2, "♨  Heat spike", lambda: self.inject("heat"), kind="ghost").pack(side="left")
        self.button(row2, "❄  Cold snap", lambda: self.inject("cold"), kind="ghost").pack(side="left", padx=6)
        self.button(row2, "≋  Wind gust", lambda: self.inject("wind"), kind="ghost").pack(side="left")
        cb = tk.Checkbutton(act, text="Pop-up alerts", variable=self.popups, font=self.fonts["small"], bd=0,
                            highlightthickness=0)
        self.tm.bind(cb, bg="card", fg="muted", activebackground="card", activeforeground="text", selectcolor="card_hi")
        cb.pack(anchor="e", pady=(10, 0))

        # ------------------------------------------------------------- live
        lc = Card(self, self.tm, "Live sensor stream", "temperature thread • one line per station")
        lc.grid(row=2, column=0, sticky="nsew", padx=(pad, 6), pady=(0, 8))
        self.live_chart = ChartPanel(lc.body, self.tm, figsize=(6, 2.6))
        self.live_chart.pack(fill="both", expand=True)
        self.live_chart.set_draw(lambda fig, p: draw_live(fig, p, self.streams, self.app.thresholds["heat_c"]))
        self.charts = [self.live_chart]

        tc = Card(self, self.tm, "Station status", "latest value from each sensor thread")
        tc.grid(row=2, column=1, sticky="nsew", padx=(6, pad), pady=(0, 8))
        cols = ("station", "temp", "humidity", "wind", "status")
        self.stations = ttk.Treeview(tc.body, columns=cols, show="headings", height=6)
        for c, w in zip(cols, (130, 70, 76, 70, 170)):
            self.stations.heading(c, text=c.upper())
            self.stations.column(c, width=self.app.px(w), anchor="w" if c in ("station", "status") else "center")
        self.stations.pack(fill="both", expand=True)
        self.thread_lbl = self.label(tc.body, "", "tiny", fg="faint", anchor="w")
        self.thread_lbl.pack(fill="x", pady=(6, 0))

        fc = Card(self, self.tm, "Event feed", "readings, faults (exceptions) and alerts")
        fc.grid(row=3, column=0, sticky="nsew", padx=(pad, 6), pady=(0, 12))
        self.feed = tk.Text(fc.body, height=8, bd=0, highlightthickness=0, font=self.fonts["mono_small"],
                            wrap="none", state="disabled")
        self.tm.bind(self.feed, bg="card", fg="muted")
        self.feed.pack(fill="both", expand=True)

        ac = Card(self, self.tm, "Alert log", "SQLite table: alerts")
        ac.grid(row=3, column=1, sticky="nsew", padx=(6, pad), pady=(0, 12))
        cols = ("time", "country", "type", "severity", "temp", "source")
        self.log = ttk.Treeview(ac.body, columns=cols, show="headings", height=6)
        for c, w in zip(cols, (120, 100, 80, 120, 50, 110)):
            self.log.heading(c, text=c.upper())
            self.log.column(c, width=self.app.px(w), anchor="w")
        vsb = ttk.Scrollbar(ac.body, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=vsb.set)
        self.log.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tm.watch(self.feed, self._feed_tags)
        self._feed_tags()
        self._poll()

    # ---------------------------------------------------------- helpers
    def _feed_tags(self):
        self.feed.tag_configure("fault", foreground=STATUS[2][0])
        self.feed.tag_configure("alert", foreground=STATUS[3][0])
        self.feed.tag_configure("ok", foreground=self.tm.p["muted"])
        self.feed.tag_configure("info", foreground=self.tm.p["accent2"])
        for lvl in range(4):
            self.stations.tag_configure(f"l{lvl}", foreground=STATUS[lvl][0] if lvl >= 1 else self.tm.p["text"])

    def _write(self, text, tag="ok"):
        self.feed.configure(state="normal")
        self.feed.insert("1.0", text + "\n", tag)
        if int(self.feed.index("end-1c").split(".")[0]) > 300:
            self.feed.delete("300.0", "end")
        self.feed.configure(state="disabled")

    def _set_threshold(self, key, var):
        try:
            self.app.thresholds[key] = float(var.get())
        except (tk.TclError, ValueError):
            return
        self.app.set_status(f"Threshold {key} = {self.app.thresholds[key]}")

    def watched(self):
        return [self.watch.get(i) for i in self.watch.curselection()][:6]

    def refresh(self):
        self._load_log()

    def on_country(self):
        pass

    def apply_auto_theme(self):
        hot = [c for c, s in self.live.items() if s.get("temperature", 0) >= self.app.thresholds["heat_c"]]
        if hot:
            self.app.auto_theme("blaze", f"AWS: heatwave reading at {', '.join(hot[:3])}")

    def _load_log(self):
        try:
            _, rows = self.app.db.recent_alerts(200)
        except Exception:                                # noqa: BLE001
            return
        self.log.delete(*self.log.get_children())
        for r in rows:
            self.log.insert("", "end", values=(r[1][5:], r[2], r[3], r[4], "" if r[5] is None else r[5], r[7]))

    # ------------------------------------------------------------ monitor
    def toggle(self):
        if self.network.running:
            self.network.stop()
            self.start_btn.configure(text="▶  Start AWS monitor")
            self.state_lbl.configure(text="●  monitor stopped", fg=self.tm.p["faint"])
            self._write("[system] monitor stopped - threads asked to exit", "info")
            return
        names = self.watched()
        if not names:
            self.app.toasts.show("Pick stations", "Select at least one country in the watch-list.", level=1)
            return
        base = {}
        for c in names:
            try:
                base[c] = self.app.dm.latest(c)
            except HeatGuardError:
                continue
        self.streams = {c: [] for c in base}
        self.live = {c: {} for c in base}
        self.network.start(base)
        self.start_btn.configure(text="■  Stop AWS monitor")
        self.state_lbl.configure(text=f"●  LIVE • {len(base)} stations • 3 sensor threads",
                                 fg=STATUS[0][0])
        self._write(f"[system] started {len(self.network.threads)} threads for: {', '.join(base)}", "info")
        for c, st in self.network.stations.items():
            self._write(f"[station] {st.describe()}", "info")

    def inject(self, kind):
        if not self.network.running:
            self.app.toasts.show("Monitor is off", "Start the AWS monitor first.", level=1)
            return
        states = self.network.states
        target = self.app.country if self.app.country in states else next(iter(states))
        self.network.inject(target, kind)
        self._write(f"[demo] injected {kind} event into {target}", "info")

    def _poll(self):
        if not self.winfo_exists():
            return
        changed = False
        for _ in range(200):
            try:
                msg = self.network.queue.get_nowait()
            except Exception:                            # queue.Empty
                break
            changed = True
            self._handle(msg)
        if changed:
            self._update_table()
            if self.visible:
                self.live_chart.render()
            self.thread_lbl.configure(text=f"threads alive: {sum(t.is_alive() for t in self.network.threads)}  •  "
                                           f"readings: {self.readings}  •  faults caught: {self.faults}")
        self.after(500, self._poll)

    def _handle(self, m):
        c = m["country"]
        if m["kind"] == "fault":
            self.faults += 1
            self._write(f"{m['time']}  FAULT  {c:<14} {m['extra']}  -> InvalidSensorValueError caught", "fault")
            self.live.setdefault(c, {})["fault"] = m["time"]
            return
        self.readings += 1
        key = {"temperature": "temperature", "humidity": "humidity", "wind": "wind_kph"}[m["sensor"]]
        state = self.live.setdefault(c, {})
        state[key] = m["value"]
        if m["sensor"] == "temperature":
            self.streams.setdefault(c, []).append(m["value"])
            self.streams[c] = self.streams[c][-80:]
            self._write(f"{m['time']}  read   {c:<14} temperature {m['value']:>6.1f} \N{DEGREE SIGN}C")
        if {"temperature", "humidity", "wind_kph"} <= state.keys():
            results = run_all({"temperature": state["temperature"], "humidity": state["humidity"],
                               "wind_kph": state["wind_kph"], "precip_mm": 0.0})
            alerts = [r for r in results if r.level >= 2]
            state["level"] = max(r.level for r in results)
            state["status"] = max(results, key=lambda r: r.level).label
            for r in alerts:
                k = (c, r.label)
                if k in self.last_alert and time.monotonic() - self.last_alert[k] < 45:
                    continue                      # cool-down: same alert at most every 45 s
                self.last_alert[k] = time.monotonic()
                self._write(f"{m['time']}  ALERT  {c:<14} {r.label}: {r.message}", "alert")
                if self.popups.get() and r.level >= 3:
                    # raise_alert stores it in SQLite and opens the modal pop-up
                    self.app.raise_alert(c, [r], state["temperature"], source=f"AWS {m['time']}")
                else:
                    self.app.db.insert_alert(c, r.analyzer, r.label, state["temperature"], r.message, "AWS sensor")
                    if self.popups.get():
                        self.app.toasts.show(f"AWS {c}: {r.label}", r.message, level=r.level)
                self._load_log()
                if r.analyzer in ("Heatwave", "Heat Stress"):
                    self.app.auto_theme("blaze", f"AWS sensor: {r.label.lower()} at {c}")
                elif r.analyzer == "Cold Wave":
                    self.app.auto_theme("frost", f"AWS sensor: {r.label.lower()} at {c}")
                elif r.analyzer == "Wind":
                    self.app.auto_theme("gale", f"AWS sensor: {r.label.lower()} at {c}")

    def _update_table(self):
        self.stations.delete(*self.stations.get_children())
        for c, s in self.live.items():
            lvl = s.get("level", 0)
            status = f"{STATUS[lvl][1]} {s.get('status', 'waiting...')}"
            if s.get("fault"):
                status += f"   (fault {s['fault']})"
            self.stations.insert("", "end", tags=(f"l{lvl}",), values=(
                c, f"{s['temperature']:.1f}\N{DEGREE SIGN}" if "temperature" in s else "-",
                f"{s['humidity']:.0f}%" if "humidity" in s else "-",
                f"{s['wind_kph']:.0f}" if "wind_kph" in s else "-", status))

    def scan(self):
        snap = self.app.dm.latest_snapshot()
        n = 0
        for _, rec in snap.iterrows():
            results = run_all({"temperature": float(rec["temperature"]), "humidity": float(rec["humidity"]),
                               "wind_kph": float(rec["wind_kph"]), "precip_mm": float(rec["precip_mm"])})
            for r in results:
                if r.level >= 2:
                    n += 1
                    self.app.db.insert_alert(rec["country"], r.analyzer, r.label, float(rec["temperature"]),
                                             r.message, "data scan")
                    self._write(f"[scan]  {rec['country']:<14} {r.label}: {r.message}", "alert")
        self._load_log()
        self.app.toasts.show("Scan complete", f"{n} warnings found in the latest reading of {len(snap)} countries.",
                             level=2 if n else 0)
