"""Project & Experiments - explains where every experiment lives (for the viva)."""
import tkinter as tk

from ...config import STUDENT, USE_CASE_ID, USE_CASE_TITLE
from ..app import BasePage
from ..widgets import Card, Logo, ScrollFrame

from ...project_info import PHASES, EXPERIMENTS, DEMO  # noqa: E402,F401


class ProjectPage(BasePage):
    def build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        sf = ScrollFrame(self, self.tm)
        sf.grid(row=0, column=0, sticky="nsew")
        root = sf.inner
        pad = 18

        hero = Card(root, self.tm)
        hero.pack(fill="x", padx=pad, pady=(14, 8))
        Logo(hero.body, self.tm, size=120, bg_key="card").pack(side="left", padx=(4, 20))
        txt = self.frame(hero.body, bg="card")
        txt.pack(side="left", fill="both", expand=True)
        self.label(txt, "HeatGuard AI", "hero").pack(anchor="w")
        self.label(txt, f"{USE_CASE_ID}  •  {USE_CASE_TITLE}", "body", fg="accent2").pack(anchor="w")
        self.label(txt, "Python mini project: a database-driven Tkinter dashboard that monitors, forecasts and "
                        "warns about heatwaves.", "small", fg="muted").pack(anchor="w", pady=(6, 0))
        info = self.frame(hero.body, bg="card")
        info.pack(side="right", padx=10)
        for k in ("name", "roll", "batch", "class", "course", "college"):
            row = self.frame(info, bg="card")
            row.pack(anchor="w")
            self.label(row, f"{k.upper():<8}", "tiny", fg="faint", width=9, anchor="w").pack(side="left")
            self.label(row, STUDENT[k], "small_bold").pack(side="left")

        self.label(root, "HOW THE USE CASE MAPS TO THE DASHBOARD", "small_bold", fg="faint", bg="bg").pack(
            anchor="w", padx=pad + 4, pady=(10, 4))
        ph = self.frame(root)
        ph.pack(fill="x", padx=pad - 4)
        for i, (num, title, what, where) in enumerate(PHASES):
            c = Card(ph, self.tm, pad=12)
            c.grid(row=0, column=i, sticky="nsew", padx=4)
            ph.grid_columnconfigure(i, weight=1, uniform="ph")
            self.label(c.body, f"PHASE {num}", "tiny", fg="accent").pack(anchor="w")
            self.label(c.body, title, "h3").pack(anchor="w")
            self.wrap(self.label(c.body, what, "small", fg="muted", justify="left", anchor="w")).pack(fill="x", pady=4)
            self.wrap(self.label(c.body, where, "tiny", fg="faint", justify="left", anchor="w")).pack(fill="x")

        self.label(root, "EXPERIMENTS 1-8 INSIDE THIS PROJECT", "small_bold", fg="faint", bg="bg").pack(
            anchor="w", padx=pad + 4, pady=(16, 4))
        ex = self.frame(root)
        ex.pack(fill="x", padx=pad - 4)
        for i, (num, title, what, where) in enumerate(EXPERIMENTS):
            c = Card(ex, self.tm, pad=12)
            c.grid(row=i // 4, column=i % 4, sticky="nsew", padx=4, pady=4)
            ex.grid_columnconfigure(i % 4, weight=1, uniform="ex")
            top = self.frame(c.body, bg="card")
            top.pack(fill="x")
            badge = tk.Label(top, text=f" EXP {num} ", font=self.fonts["small_bold"])
            self.tm.bind(badge, bg="accent", fg="accent_text")
            badge.pack(side="left")
            self.label(top, title, "body_bold").pack(side="left", padx=8)
            self.wrap(self.label(c.body, what, "small", fg="muted", justify="left", anchor="w")).pack(fill="x", pady=(6, 4))
            self.label(c.body, f"→ {where}", "tiny", fg="accent2").pack(anchor="w")

        bottom = self.frame(root)
        bottom.pack(fill="x", padx=pad - 4, pady=(12, 18))
        bottom.grid_columnconfigure(0, weight=1, uniform="b")
        bottom.grid_columnconfigure(1, weight=1, uniform="b")
        demo = Card(bottom, self.tm, "Viva demo script", "6 steps, about 3 minutes")
        demo.grid(row=0, column=0, sticky="nsew", padx=4)
        for i, line in enumerate(DEMO, 1):
            self.wrap(self.label(demo.body, f"{i}.  {line}", "small", fg="text", justify="left", anchor="w")).pack(
                fill="x", pady=2)
        self.clean = Card(bottom, self.tm, "Data cleaning report", "Phase I")
        self.clean.grid(row=0, column=1, sticky="nsew", padx=4)
        self.clean_lbl = self.label(self.clean.body, "", "small", fg="muted", justify="left", anchor="nw")
        self.clean_lbl.pack(anchor="w")

    @staticmethod
    def wrap(lbl):
        """Re-wrap the text whenever the label is resized."""
        lbl.bind("<Configure>", lambda e: lbl.configure(wraplength=max(120, e.width - 6)))
        return lbl

    def refresh(self):
        rep = self.app.dm.clean_report
        df = self.app.dm.df
        if rep:
            text = (f"Raw rows in CSV            {rep['raw_rows']:,}\n"
                    f"Invalid dates / values     {rep['bad_dates_or_values']:,}\n"
                    f"Out-of-range sensor values {rep['out_of_range']:,}\n"
                    f"Rare / mis-spelt countries {rep['rare_country_rows']:,}\n"
                    f"Duplicate readings         {rep['duplicates']:,}\n"
                    f"Clean rows stored          {rep['clean_rows']:,}  ({rep['countries']} countries)")
        else:
            text = (f"The database was already built on an earlier run.\n"
                    f"Rows now in weather_data   {len(df):,}\n"
                    f"Countries                  {df['country'].nunique()}\n"
                    f"Date range                 {df['ts'].min():%d %b %Y} - {df['ts'].max():%d %b %Y}\n"
                    f"(Use 'Reset database' in the SQL Lab to rebuild and see the full cleaning report.)")
        self.clean_lbl.configure(text=text, font=self.fonts["mono_small"])

    def on_country(self):
        pass
