"""
app.py  -  Main window of HeatGuard AI
======================================
  +---------------------------------------------------------------+
  |  animated banner (theme particles, title, theme reason, clock)|
  +-----------+---------------------------------------------------+
  |  sidebar  |  page area (one page visible at a time)           |
  |  - pages  |                                                   |
  |  - region |                                                   |
  |  - theme  |                                                   |
  +-----------+---------------------------------------------------+
  |  status bar                                                   |
  +---------------------------------------------------------------+
Heavy work (loading data, training models, SQL) runs in background
threads; results come back through a queue polled by the GUI (Exp 5).
"""
import queue
import threading
import tkinter as tk
import traceback
from tkinter import ttk, messagebox

from ..config import APP_TITLE, DEFAULT_COUNTRY, THRESHOLDS
from ..data_manager import DataManager
from ..exceptions import HeatGuardError
from ..forecaster import ForecastEngine
from .charts import setup_matplotlib
from .fonts import build_fonts
from .themes import ThemeManager, ThemeDetector, PALETTES, THEME_ORDER
from .widgets import (Logo, NavButton, ParticleBanner, ToastManager, AlertDialog, HoverButton)

PAGES = (
    ("overview", "⌂", "Command Center"),
    ("forecast", "↗", "AI Forecast Lab"),
    ("sql", "⌨", "SQL Lab"),
    ("analytics", "▦", "Analytics"),
    ("alerts", "⚠", "Alerts & AWS"),
    ("project", "✦", "Project & Exps"),
)


class HeatGuardApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self._initial_geometry()
        build_fonts(self)
        setup_matplotlib(self.fonts)
        self.tm = ThemeManager(self)
        self.tm.bind(self, bg="bg")
        self.option_add("*Font", self.fonts["body"])

        self.dm = DataManager()
        self.db = self.dm.db
        self.engine = ForecastEngine(self.dm)
        self.toasts = ToastManager(self, self.tm)
        self.thresholds = THRESHOLDS                 # shared, editable from Alerts page
        self.country = DEFAULT_COUNTRY
        self.pages, self.nav = {}, {}
        self.current = None
        self.alerted = set()
        self._jobs = queue.Queue()
        self.tm.listen(self._on_theme)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._poll_jobs()
        self._splash()

    def _initial_geometry(self):
        """Pick one UI scale S so the layout fits the screen at any Windows
        display scaling (100 % / 125 % / 150 %). Fonts, canvas drawings and
        charts are all multiplied by S."""
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        dpi_scale = float(self.winfo_fpixels("1i")) / 96.0
        fit = min((sh - 80) / 960.0, sw / 1500.0)
        self.S = max(0.75, min(dpi_scale, fit, 2.0))
        self.tk.call("tk", "scaling", self.S * 96.0 / 72.0)      # pixels per point
        w, h = min(int(1600 * self.S), int(sw * 0.96)), min(int(980 * self.S), int(sh * 0.9))
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 3)}")
        self.minsize(min(int(1180 * self.S), sw - 40), min(int(720 * self.S), sh - 80))
        try:
            if sw <= 1920:
                self.state("zoomed")          # maximise on Windows
        except tk.TclError:
            pass

    def px(self, n):
        """Scale a pixel size by the UI scale."""
        return int(round(n * self.S))

    # ------------------------------------------------------- background jobs
    def run_bg(self, work, on_done=None, on_error=None):
        """Run work() in a thread; call on_done(result) back on the GUI thread."""
        def target():
            try:
                res = work()
            except Exception as exc:                       # noqa: BLE001
                traceback.print_exc()
                self._jobs.put((on_error or self._default_error, exc))
            else:
                if on_done:
                    self._jobs.put((on_done, res))
        threading.Thread(target=target, daemon=True).start()

    def _poll_jobs(self):
        try:
            while True:
                fn, arg = self._jobs.get_nowait()
                try:
                    fn(arg)
                except Exception:                          # noqa: BLE001
                    traceback.print_exc()
        except queue.Empty:
            pass
        self.after(60, self._poll_jobs)

    def _default_error(self, exc):
        self.set_status(f"Error: {exc}", error=True)
        self.toasts.show("Something went wrong", str(exc)[:200], level=2)

    # ---------------------------------------------------------------- splash
    def _splash(self):
        p, f = self.tm.p, self.fonts
        self.splash = tk.Frame(self, bg=p["bg"])
        self.splash.place(relx=0, rely=0, relwidth=1, relheight=1)
        box = tk.Frame(self.splash, bg=p["bg"])
        box.place(relx=0.5, rely=0.45, anchor="center")
        Logo(box, self.tm, size=130, bg_key="bg").pack()
        tk.Label(box, text="HEATGUARD AI", bg=p["bg"], fg=p["text"], font=f["hero"]).pack(pady=(18, 0))
        tk.Label(box, text="Climate Intelligence for Heatwave Monitoring, Prediction & Early Warning",
                 bg=p["bg"], fg=p["muted"], font=f["body"]).pack(pady=(4, 22))
        self.splash_bar = tk.Canvas(box, width=420, height=8, bg=p["card_hi"], highlightthickness=0)
        self.splash_bar.pack()
        self.splash_fill = self.splash_bar.create_rectangle(0, 0, 0, 8, fill=p["accent"], outline="")
        self.splash_msg = tk.Label(box, text="Starting...", bg=p["bg"], fg=p["faint"], font=f["small"])
        self.splash_msg.pack(pady=10)

        def progress(frac, msg):
            self._jobs.put((self._splash_progress, (frac, msg)))

        self.run_bg(lambda: self.dm.prepare(progress=progress), self._on_ready, self._on_load_error)

    def _splash_progress(self, args):
        frac, msg = args
        self.splash_bar.coords(self.splash_fill, 0, 0, 420 * frac, 8)
        self.splash_msg.configure(text=msg)

    def _on_load_error(self, exc):
        messagebox.showerror("HeatGuard AI - data problem", str(exc))
        self.splash_msg.configure(text=str(exc), fg="#ff4d4f")

    def _on_ready(self, _):
        if self.country not in self.dm.countries():
            self.country = self.dm.countries()[0]
        self._build_shell()
        self.splash.destroy()
        self.show_page("overview")
        self.after(900, self._startup_scan)

    # ----------------------------------------------------------------- shell
    def _build_shell(self):
        tm, f = self.tm, self.fonts
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.banner = ParticleBanner(self, tm, height=self.px(92))
        self.banner.grid(row=0, column=0, columnspan=2, sticky="ew")

        side = tk.Frame(self, width=self.px(232))
        tm.bind(side, bg="panel")
        side.grid(row=1, column=0, sticky="nsw")
        side.grid_propagate(False)
        side.pack_propagate(False)
        self._section(side, "NAVIGATE")
        for key, sym, text in PAGES:
            b = NavButton(side, tm, sym, text, command=lambda k=key: self.show_page(k))
            b.pack(fill="x")
            self.nav[key] = b

        self._section(side, "REGION")
        self.country_var = tk.StringVar(value=self.country)
        self.country_box = ttk.Combobox(side, textvariable=self.country_var, values=self.dm.countries(),
                                        state="readonly", font=f["body"], height=18)
        self.country_box.pack(fill="x", padx=16, pady=(0, 6))
        self.country_box.bind("<<ComboboxSelected>>", lambda e: self.set_country(self.country_var.get()))
        quick = tk.Frame(side)
        tm.bind(quick, bg="panel")
        quick.pack(fill="x", padx=16)
        for i, c in enumerate(("India", "Kuwait", "Pakistan", "Iceland", "Russia", "Brazil")):
            if c in self.dm.countries():
                lbl = tk.Label(quick, text=c, font=f["tiny"], padx=6, pady=2, cursor="hand2")
                tm.bind(lbl, bg="card_hi", fg="muted")
                lbl.grid(row=i // 3, column=i % 3, padx=2, pady=2, sticky="ew")
                lbl.bind("<Button-1>", lambda e, c=c: self.set_country(c))
                quick.grid_columnconfigure(i % 3, weight=1)

        self._section(side, "THEME")
        sw = tk.Frame(side)
        tm.bind(sw, bg="panel")
        sw.pack(fill="x", padx=16)
        for i, name in enumerate(THEME_ORDER):
            pal = PALETTES[name]
            d = self.px(34)
            c = tk.Canvas(sw, width=d, height=d, highlightthickness=0, cursor="hand2")
            tm.bind(c, bg="panel")
            c.create_oval(3, 3, d - 3, d - 3, fill=pal["accent"], outline=pal["accent2"], width=2)
            c.create_text(d / 2, d / 2, text=pal["symbol"], fill=pal["accent_text"], font=f["symbol"])
            c.grid(row=0, column=i, padx=1)
            c.bind("<Button-1>", lambda e, n=name: self.manual_theme(n))
        self.auto_lbl = tk.Label(side, text="", font=f["small"], anchor="w", cursor="hand2")
        tm.bind(self.auto_lbl, bg="panel", fg="muted")
        self.auto_lbl.pack(fill="x", padx=16, pady=(6, 0))
        self.auto_lbl.bind("<Button-1>", lambda e: self.toggle_auto())
        self._update_auto_label()

        self.data_lbl = tk.Label(side, text="", font=f["tiny"], justify="left", anchor="w")
        tm.bind(self.data_lbl, bg="panel", fg="faint")
        self.data_lbl.pack(side="bottom", fill="x", padx=16, pady=12)
        self._update_data_label()

        self.content = tk.Frame(self)
        tm.bind(self.content, bg="bg")
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        bar = tk.Frame(self, height=26)
        tm.bind(bar, bg="panel")
        bar.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.status_lbl = tk.Label(bar, text="Ready", font=f["small"], anchor="w")
        tm.bind(self.status_lbl, bg="panel", fg="muted")
        self.status_lbl.pack(side="left", padx=12, pady=3)
        self.db_lbl = tk.Label(bar, text="● SQLite connected  •  database/climate.db", font=f["small"])
        tm.bind(self.db_lbl, bg="panel", fg="faint")
        self.db_lbl.pack(side="right", padx=12)

    def _section(self, parent, text):
        lbl = tk.Label(parent, text=text, font=self.fonts["tiny"], anchor="w")
        self.tm.bind(lbl, bg="panel", fg="faint")
        lbl.pack(fill="x", padx=18, pady=(16, 6))

    def _update_data_label(self):
        df = self.dm.df
        latest = df["ts"].max().strftime("%d %b %Y") if not df.empty else "-"
        self.data_lbl.configure(text=f"DATA  {len(df):,} readings\n{df['country'].nunique()} countries\n"
                                     f"latest reading {latest}\nsource V_S_DATA_SET_CLIMATE.csv")

    def _update_auto_label(self):
        self.auto_lbl.configure(text=("☑  Auto theme ON  (follows data)" if self.tm.auto
                                      else "☐  Auto theme OFF  (click)"))

    # ----------------------------------------------------------------- pages
    def _make_page(self, key):
        from .pages.overview import OverviewPage
        from .pages.forecast import ForecastPage
        from .pages.sql_lab import SqlLabPage
        from .pages.analytics import AnalyticsPage
        from .pages.alerts import AlertsPage
        from .pages.project import ProjectPage
        cls = {"overview": OverviewPage, "forecast": ForecastPage, "sql": SqlLabPage,
               "analytics": AnalyticsPage, "alerts": AlertsPage, "project": ProjectPage}[key]
        page = cls(self.content, self)
        page.grid(row=0, column=0, sticky="nsew")
        return page

    def show_page(self, key):
        if key not in self.pages:
            self.set_status("Building page...")
            self.update_idletasks()
            self.pages[key] = self._make_page(key)
        for k, page in self.pages.items():
            if k != key:
                page.grid_remove()
                page.visible = False
        page = self.pages[key]
        page.grid()
        page.visible = True
        self.current = key
        for k, b in self.nav.items():
            b.set_active(k == key)
        page.on_show()
        self.set_status(f"{dict((k, t) for k, _, t in PAGES)[key]}  •  region: {self.country}")

    # -------------------------------------------------------- global events
    def set_country(self, country):
        if country not in self.dm.countries():
            return
        self.country = country
        self.country_var.set(country)
        for page in self.pages.values():
            page.country_dirty = True
        if self.current:
            self.pages[self.current].on_country()
            self.pages[self.current].country_dirty = False
        self.set_status(f"Region changed to {country}")

    def auto_theme(self, name, reason):
        if self.tm.auto:
            self.tm.set(name, reason)
        if hasattr(self, "banner"):
            self.banner.set_reason(reason if self.tm.auto else f"Manual theme  •  {reason}")

    def manual_theme(self, name):
        self.tm.auto = False
        self._update_auto_label()
        self.tm.set(name, f"Manual: {PALETTES[name]['tagline']}")

    def toggle_auto(self):
        self.tm.auto = not self.tm.auto
        self._update_auto_label()
        if self.tm.auto and self.current:
            self.pages[self.current].on_show()

    def _on_theme(self, palette, changed):
        if hasattr(self, "banner"):
            self.banner.set_reason(self.tm.reason)
        if not changed:
            return
        for page in self.pages.values():
            if page.visible:
                page.on_theme()
            else:
                page.theme_dirty = True

    def data_changed(self, note="Database changed"):
        """Called after INSERT / UPDATE / DELETE in the SQL Lab."""
        self.set_status(f"{note} - reloading dashboard data...")

        def done(_):
            self._update_data_label()
            vals = self.dm.countries()
            self.country_box.configure(values=vals)
            if self.country not in vals and vals:
                self.set_country(vals[0])
            for page in self.pages.values():
                page.data_dirty = True
                page.country_dirty = True
            self.set_status(f"{note} - all pages refreshed from climate.db")
            self.toasts.show("Dashboard updated", f"{note}. Every page now uses the new data.", level=0, duration=4000)
            self._check_country_alert(self.country)

        def fail(exc):
            self.set_status(str(exc), error=True)
            messagebox.showwarning("Database", f"{exc}\n\nOpen the SQL Lab and press 'Reset database'.")

        self.run_bg(self.dm.reload, done, fail)

    # --------------------------------------------------------------- alerts
    def raise_alert(self, country, results, temperature, source="dashboard", popup=True):
        """Show toasts / modal for analyzer results with level >= 2 and log them."""
        for r in results:
            if r.level < 2:
                continue
            key = (country, r.analyzer, r.label, source, round(float(temperature or 0)))
            if key in self.alerted:
                continue
            self.alerted.add(key)
            try:
                self.db.insert_alert(country, r.analyzer, r.label, temperature, r.message, source)
            except Exception:                              # noqa: BLE001
                pass
            if not popup:
                continue
            if r.level >= 3:
                from ..advisories import _ADVICE
                adv = _ADVICE.get(r.label, _ADVICE.get("SEVERE HEATWAVE"))
                AlertDialog(self, self.tm, f"{r.label.title()} - {country}", r.message, level=3,
                            actions=[f"{k}: {v}" for k, v in list(adv.items())[:3]])
            else:
                self.toasts.show(f"{r.label} • {country}", r.message, level=r.level)
        if "alerts" in self.pages:
            self.pages["alerts"].data_dirty = True

    def _check_country_alert(self, country):
        from ..analyzers import run_all
        try:
            rec = self.dm.latest(country)
        except HeatGuardError:
            return
        results = run_all({"temperature": float(rec["temperature"]), "normal": rec["normal"],
                           "humidity": float(rec["humidity"]), "wind_kph": float(rec["wind_kph"]),
                           "precip_mm": float(rec["precip_mm"])})
        self.raise_alert(country, results, rec["temperature"], source="latest reading")

    def _startup_scan(self):
        snap = self.dm.latest_snapshot()
        hot = snap[snap["temperature"] >= self.thresholds["heat_c"]].sort_values("temperature", ascending=False)
        cold = snap[snap["temperature"] <= self.thresholds["freeze_c"]]
        if len(hot):
            names = ", ".join(f"{c} {t:.0f}\N{DEGREE SIGN}" for c, t in zip(hot["country"].head(4), hot["temperature"].head(4)))
            self.toasts.show(f"Heatwave watch: {len(hot)} countr{'y' if len(hot) == 1 else 'ies'} ≥ "
                             f"{self.thresholds['heat_c']:.0f}\N{DEGREE SIGN}C now", names, level=2, duration=9000)
            for c, t in zip(hot["country"], hot["temperature"]):
                self.db.insert_alert(c, "Heatwave", "HEATWAVE", t, "Latest reading above heatwave threshold", "startup scan")
        if len(cold):
            self.toasts.show(f"Cold watch: {len(cold)} below 0\N{DEGREE SIGN}C", ", ".join(cold["country"].head(4)),
                             level=1, duration=8000)
        self.toasts.show("HeatGuard AI is live", f"{len(self.dm.df):,} readings from {self.dm.df['country'].nunique()} "
                         "countries loaded from SQLite.", level=0, duration=5000)

    # ----------------------------------------------------------------- misc
    def set_status(self, text, error=False):
        if hasattr(self, "status_lbl"):
            self.status_lbl.configure(text=text, fg="#ff6b6b" if error else self.tm.p["muted"])

    def _on_close(self):
        if "alerts" in self.pages:
            self.pages["alerts"].network.stop()
        self.destroy()


class BasePage(tk.Frame):
    """Common behaviour for every page."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app, self.tm, self.fonts = app, app.tm, app.fonts
        self.tm.bind(self, bg="bg")
        self.visible = False
        self.theme_dirty = self.data_dirty = self.country_dirty = False
        self.charts = []
        self.built = False

    def on_show(self):
        if not self.built:
            self.build()
            self.built = True
            self.refresh()
            self.country_dirty = self.data_dirty = self.theme_dirty = False
            return
        if self.country_dirty or self.data_dirty:
            self.country_dirty = self.data_dirty = False
            self.theme_dirty = False
            self.refresh()
        elif self.theme_dirty:
            self.theme_dirty = False
            self.on_theme()
        else:
            self.apply_auto_theme()

    def on_country(self):
        self.refresh()

    def on_theme(self):
        for c in self.charts:
            c.render()

    def build(self):
        pass

    def refresh(self):
        pass

    def apply_auto_theme(self):
        pass

    # small helpers
    def label(self, parent, text="", font="body", fg="text", bg="card", **kw):
        lbl = tk.Label(parent, text=text, font=self.fonts[font], **kw)
        self.tm.bind(lbl, bg=bg, fg=fg)
        return lbl

    def frame(self, parent, bg="bg", **kw):
        fr = tk.Frame(parent, **kw)
        self.tm.bind(fr, bg=bg)
        return fr

    def button(self, parent, text, command, kind="primary", **kw):
        return HoverButton(parent, self.tm, text, command, kind=kind, **kw)

    def theme_for_reading(self, rec):
        return ThemeDetector.from_temperature(float(rec["temperature"]), rec.get("condition", ""),
                                              float(rec.get("wind_kph", 0) or 0), float(rec.get("precip_mm", 0) or 0))
