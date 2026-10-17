"""
SQL Lab  -  Experiment 8 inside the dashboard
=============================================
Type any SQLite query, press Run (or Ctrl+Enter):
  * results appear in a table + an automatic chart
  * the WHOLE dashboard theme changes to match the query
      MAX(temperature) -> fire,  MIN(temperature) -> ice,
      wind -> wind,  rain / precip / humidity -> monsoon
  * INSERT / UPDATE / DELETE change climate.db and every page refreshes
"""
import csv
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from ...exceptions import QueryError
from ...text_tools import sql_keyword_list
from ..app import BasePage
from ..charts import ChartPanel, draw_sql
from ..themes import ThemeDetector, PALETTES
from ..widgets import Card, Segmented

from ...sql_presets import PRESETS  # noqa: E402

KEYWORDS = sql_keyword_list()


class SqlLabPage(BasePage):
    def build(self):
        pad = 14
        self.history = []
        self.last = None
        self.grid_columnconfigure(0, weight=0, minsize=self.app.px(300))
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        head = self.frame(self)
        head.grid(row=0, column=0, columnspan=2, sticky="ew", padx=pad, pady=(12, 6))
        self.label(head, "SQL Lab", "h1", bg="bg").pack(side="left")
        self.label(head, "Experiment 8  •  SQLite database climate.db  •  the theme reacts to your query",
                   "small", fg="muted", bg="bg").pack(side="left", padx=14, pady=(10, 0))

        # ----------------------------------------------------------- library
        lib = Card(self, self.tm, "Query library")
        lib.grid(row=1, column=0, rowspan=2, sticky="nsew", padx=(pad, 6), pady=(0, 12))
        self.tabs = Segmented(lib.body, self.tm, [("lib", "Presets"), ("schema", "Schema"), ("hist", "History")],
                              self._tab, value="lib", padx=10)
        self.tabs.pack(fill="x", pady=(0, 8))
        self.tab_host = self.frame(lib.body, bg="card")
        self.tab_host.pack(fill="both", expand=True)

        self.preset_tree = ttk.Treeview(self.tab_host, show="tree", selectmode="browse")
        self.preset_tree.column("#0", width=self.app.px(280))
        self.preset_sql = {}
        for group, items in PRESETS:
            gid = self.preset_tree.insert("", "end", text=group, open=True, tags=("group",))
            for name, sql in items:
                iid = self.preset_tree.insert(gid, "end", text="   " + name)
                self.preset_sql[iid] = sql
        self.preset_tree.bind("<<TreeviewSelect>>", self._preset_pick)
        self.preset_tree.bind("<Double-1>", lambda e: self.run())

        self.schema_tree = ttk.Treeview(self.tab_host, show="tree")
        self.schema_tree.column("#0", width=self.app.px(280))
        self.schema_tree.bind("<Double-1>", self._schema_insert)

        self.hist_list = tk.Listbox(self.tab_host, activestyle="none", bd=0, highlightthickness=0,
                                    font=self.fonts["mono_small"])
        self.tm.bind(self.hist_list, bg="card", fg="text", selectbackground="accent", selectforeground="accent_text")
        self.hist_list.bind("<<ListboxSelect>>", self._hist_pick)
        self.tm.watch(self.preset_tree, self._tree_tags)
        self._tree_tags()
        self._tab("lib")

        # ------------------------------------------------------------ editor
        ed = Card(self, self.tm, "Query editor", "Ctrl+Enter to run • several statements separated by ;")
        ed.grid(row=1, column=1, sticky="nsew", padx=(6, pad), pady=(0, 8))
        self.button(ed.tools, "↺  Reset database", self.reset_db, kind="subtle",
                    font=self.fonts["small_bold"]).pack(side="right", padx=(6, 0))
        self.button(ed.tools, "✕  Clear", lambda: self.editor.delete("1.0", "end"), kind="ghost",
                    font=self.fonts["small_bold"]).pack(side="right", padx=(6, 0))
        self.button(ed.tools, "▶  RUN QUERY", self.run).pack(side="right")
        box = self.frame(ed.body, bg="card_hi", highlightthickness=1)
        self.tm.bind(box, highlightbackground="border")
        box.pack(fill="both", expand=True)
        self.gutter = tk.Text(box, width=3, height=8, bd=0, highlightthickness=0, font=self.fonts["mono"],
                              state="disabled", padx=6, pady=8, cursor="arrow", takefocus=0)
        self.tm.bind(self.gutter, bg="card_hi", fg="faint")
        self.gutter.pack(side="left", fill="y")
        self.editor = tk.Text(box, height=8, bd=0, highlightthickness=0, wrap="none", undo=True,
                              font=self.fonts["mono"], padx=8, pady=8)
        self.tm.bind(self.editor, bg="card_hi", fg="text", insertbackground="accent",
                     selectbackground="accent", selectforeground="accent_text")
        self.editor.pack(side="left", fill="both", expand=True)
        self.editor.insert("1.0", PRESETS[1][1][0][1])
        self.editor.bind("<Control-Return>", lambda e: (self.run(), "break")[1])
        self.editor.bind("<Command-Return>", lambda e: (self.run(), "break")[1])
        self.editor.bind("<KeyRelease>", lambda e: self._schedule_highlight())
        self.tm.watch(self.editor, self._highlight)
        self._highlight()

        st = self.frame(ed.body, bg="card")
        st.pack(fill="x", pady=(8, 0))
        self.msg = self.label(st, "Pick a preset on the left or write your own SELECT.", "small", fg="muted", anchor="w")
        self.msg.pack(side="left", fill="x", expand=True)
        self.theme_chip = tk.Label(st, text="", font=self.fonts["small_bold"], padx=10, pady=2)
        self.theme_chip.pack(side="right")

        # ----------------------------------------------------------- results
        res = self.frame(self)
        res.grid(row=2, column=1, sticky="nsew", padx=(6, pad), pady=(0, 12))
        res.grid_columnconfigure(0, weight=3, uniform="r")
        res.grid_columnconfigure(1, weight=2, uniform="r")
        res.grid_rowconfigure(0, weight=1)
        tcard = Card(res, self.tm, "Results")
        tcard.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.res_title = tcard
        self.button(tcard.tools, "⇩ CSV", self.export, kind="ghost", font=self.fonts["small_bold"]).pack(side="right")
        tf = self.frame(tcard.body, bg="card")
        tf.pack(fill="both", expand=True)
        self.table = ttk.Treeview(tf, show="headings")
        vsb = ttk.Scrollbar(tf, orient="vertical", command=self.table.yview)
        hsb = ttk.Scrollbar(tf, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.table.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tf.grid_rowconfigure(0, weight=1)
        tf.grid_columnconfigure(0, weight=1)
        self.table.bind("<Double-1>", self._row_to_dashboard)

        ccard = Card(res, self.tm, "Auto chart", "built from your result")
        ccard.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self.chart = ChartPanel(ccard.body, self.tm, figsize=(4, 3))
        self.chart.pack(fill="both", expand=True)
        self.chart.set_draw(lambda fig, p: draw_sql(fig, p, [], []))
        self.charts = [self.chart]

    def refresh(self):
        self._load_schema()
        if self.last is None:
            self.run(confirm=False)

    def on_country(self):
        pass                                    # the SQL Lab is not tied to one region

    def apply_auto_theme(self):
        if self.last is not None:
            name, reason = ThemeDetector.from_query(self.last.sql, self.last.columns, self.last.rows)
            self.app.auto_theme(name, reason)

    # ------------------------------------------------------------ tabs etc
    def _tab(self, which):
        for w in (self.preset_tree, self.schema_tree, self.hist_list):
            w.pack_forget()
        {"lib": self.preset_tree, "schema": self.schema_tree, "hist": self.hist_list}[which].pack(
            fill="both", expand=True)

    def _tree_tags(self):
        p = self.tm.p
        self.preset_tree.tag_configure("group", foreground=p["accent2"], font=self.fonts["small_bold"])
        self.schema_tree.tag_configure("table", foreground=p["accent2"], font=self.fonts["small_bold"])
        self.schema_tree.tag_configure("col", foreground=p["muted"])

    def _load_schema(self):
        self.schema_tree.delete(*self.schema_tree.get_children())
        try:
            schema = self.app.db.schema_overview()
        except Exception as exc:                          # noqa: BLE001
            self.schema_tree.insert("", "end", text=f"error: {exc}")
            return
        for table, cols in schema.items():
            tid = self.schema_tree.insert("", "end", text=f"▤  {table}", open=table == "weather_data",
                                          tags=("table",))
            for c in cols:
                self.schema_tree.insert(tid, "end", text=f"    {c}", tags=("col",))

    def _schema_insert(self, _e):
        sel = self.schema_tree.selection()
        if sel:
            word = self.schema_tree.item(sel[0], "text").replace("▤", "").replace("(view)", "").strip()
            self.editor.insert("insert", word + " ")
            self._highlight()

    def _preset_pick(self, _e):
        sel = self.preset_tree.selection()
        if sel and sel[0] in self.preset_sql:
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", self.preset_sql[sel[0]])
            self._highlight()

    def _hist_pick(self, _e):
        sel = self.hist_list.curselection()
        if sel:
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", self.history[-1 - sel[0]])
            self._highlight()

    # ---------------------------------------------------------- highlight
    def _schedule_highlight(self):
        if getattr(self, "_hl_job", None):
            self.after_cancel(self._hl_job)
        self._hl_job = self.after(150, self._highlight)

    def _highlight(self):
        p = self.tm.p
        ed = self.editor
        ed.tag_configure("kw", foreground=p["accent"], font=self.fonts["mono"])
        ed.tag_configure("str", foreground="#7ee0a1")
        ed.tag_configure("num", foreground="#ffd36b")
        ed.tag_configure("com", foreground=p["faint"])
        for tag in ("kw", "str", "num", "com"):
            ed.tag_remove(tag, "1.0", "end")
        text = ed.get("1.0", "end-1c")
        for m in re.finditer(r"[A-Za-z_]+", text):
            if m.group().lower() in KEYWORDS:
                ed.tag_add("kw", f"1.0+{m.start()}c", f"1.0+{m.end()}c")
        for m in re.finditer(r"\b\d+(\.\d+)?\b", text):
            ed.tag_add("num", f"1.0+{m.start()}c", f"1.0+{m.end()}c")
        for m in re.finditer(r"'[^']*'?", text):
            ed.tag_add("str", f"1.0+{m.start()}c", f"1.0+{m.end()}c")
        for m in re.finditer(r"--[^\n]*", text):
            ed.tag_add("com", f"1.0+{m.start()}c", f"1.0+{m.end()}c")
        lines = int(ed.index("end-1c").split(".")[0])
        self.gutter.configure(state="normal")
        self.gutter.delete("1.0", "end")
        self.gutter.insert("1.0", "\n".join(str(i) for i in range(1, lines + 1)))
        self.gutter.configure(state="disabled")

    # ---------------------------------------------------------------- run
    def run(self, confirm=True):
        self._highlight()
        sql = self.editor.get("1.0", "end-1c").strip()
        if not sql:
            self._error("The editor is empty - type a query first.")
            return
        words = set(re.findall(r"[a-z]+", sql.lower()))
        risky = words & {"insert", "update", "delete", "drop", "alter", "replace", "create"}
        if risky and confirm:
            extra = ""
            if "drop" in words and "weather_data" in sql.lower():
                extra = "\n\nWARNING: dropping weather_data empties the dashboard (use 'Reset database' to restore)."
            if not messagebox.askyesno("Modify the database?",
                                       f"This query will change climate.db ({', '.join(sorted(risky)).upper()}).\n"
                                       f"All dashboard pages will refresh with the new data.{extra}\n\nContinue?"):
                return
        self.msg.configure(text="Running query...", fg=self.tm.p["muted"])
        self.app.run_bg(lambda: self.app.db.run_query(sql), self._show, self._fail)

    def _fail(self, exc):
        self._error(f"SQL error: {exc}" if isinstance(exc, QueryError) else str(exc))

    def _error(self, text):
        self.msg.configure(text=f"✖  {text}", fg="#ff6b6b")
        self.app.toasts.show("Query failed", text[:180], level=2, duration=5000)

    def _show(self, res):
        self.last = res
        if not self.history or self.history[-1] != res.sql:
            self.history.append(res.sql)
            self.hist_list.insert(0, " " + " ".join(res.sql.split())[:80])
        if res.kind == "select":
            self._fill_table(res.columns, res.rows)
            self.res_title.set_title(f"Results  •  {res.rowcount} row(s)")
            self.chart.set_draw(lambda fig, p: draw_sql(fig, p, res.columns, res.rows))
        self.msg.configure(text=f"✔  {res.message}", fg=self.tm.p["muted"])
        name, reason = ThemeDetector.from_query(res.sql, res.columns, res.rows if res.kind == "select" else [])
        pal = PALETTES[name]
        self.theme_chip.configure(text=f"{pal['symbol']}  {pal['label']}", bg=pal["accent"], fg=pal["accent_text"])
        self.app.auto_theme(name, reason)
        if res.data_changed:
            self._load_schema()
            self.app.data_changed("SQL change applied to climate.db")

    def _fill_table(self, columns, rows):
        t = self.table
        t.delete(*t.get_children())
        t["columns"] = list(columns)
        f = self.fonts["small"]
        for c in columns:
            sample = [str(r[columns.index(c)]) for r in rows[:50]]
            width = min(260, max(f.measure(c) + 30, *(f.measure(s) + 20 for s in sample)) if sample else 100)
            t.heading(c, text=c)
            t.column(c, width=width, anchor="w", stretch=False)
        for i, r in enumerate(rows):
            vals = [("NULL" if v is None else (f"{v:.2f}" if isinstance(v, float) else v)) for v in r]
            t.insert("", "end", values=vals, tags=("odd" if i % 2 else "even",))
        t.tag_configure("odd", background=self.tm.p["card_hi"])
        t.tag_configure("even", background=self.tm.p["card"])

    def on_theme(self):
        super().on_theme()
        if self.last is not None and self.last.kind == "select":
            self.table.tag_configure("odd", background=self.tm.p["card_hi"])
            self.table.tag_configure("even", background=self.tm.p["card"])

    def _row_to_dashboard(self, _e):
        """Double-click a row with a 'country' column -> open it in the Command Center."""
        sel = self.table.selection()
        cols = [c.lower() for c in self.table["columns"]]
        if sel and "country" in cols:
            country = self.table.item(sel[0], "values")[cols.index("country")]
            if country in self.app.dm.countries():
                self.app.set_country(country)
                self.app.show_page("overview")

    # -------------------------------------------------------------- misc
    def reset_db(self):
        if not messagebox.askyesno("Reset database", "Rebuild climate.db from the original CSV file?\n"
                                                     "All changes to weather_data will be lost."):
            return
        self.msg.configure(text="Rebuilding database from CSV (about 10 seconds)...")
        self.app.run_bg(lambda: self.app.dm.prepare(force_rebuild=True),
                        lambda _: (self._load_schema(), self.app.data_changed("Database rebuilt from CSV")))

    def export(self):
        res = self.last
        if not res or not res.rows:
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="query_result.csv",
                                            filetypes=[("CSV", "*.csv")])
        if path:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(res.columns)
                w.writerows(res.rows)
            self.app.toasts.show("Exported", path, level=0)
