"""
widgets.py  -  Custom Tkinter widgets  (Experiment 7: GUI + Canvas drawing)
===========================================================================
Everything here is drawn by hand on a tkinter Canvas with create_oval,
create_line, create_polygon, create_arc, create_rectangle and create_text:
weather icons, the KPI tiles, the temperature dial, the animated banner
(fire embers / snow / wind / rain), toasts and alert pop-ups.
"""
import math
import random
import time
import tkinter as tk
from tkinter import ttk

from .themes import STATUS, blend


# ------------------------------------------------------------------ helpers
TEMP_STOPS = ((-25, "#3f5fd8"), (0, "#4aa8ff"), (12, "#79d3dc"), (22, "#ffd36b"),
              (31, "#ff9a2e"), (39, "#ff4d1a"), (47, "#c3001f"))


def temp_color(t):
    """Semantic temperature colour: cold blue -> hot red."""
    if t is None:
        return "#888888"
    if t <= TEMP_STOPS[0][0]:
        return TEMP_STOPS[0][1]
    for (t0, c0), (t1, c1) in zip(TEMP_STOPS, TEMP_STOPS[1:]):
        if t <= t1:
            return blend(c0, c1, (t - t0) / (t1 - t0))
    return TEMP_STOPS[-1][1]


def ui_scale(widget):
    """The UI scale chosen by the app (1.0 = 96 dpi layout)."""
    try:
        return getattr(widget.winfo_toplevel(), "S", 1.0)
    except tk.TclError:
        return 1.0


def fit_text(font, text, room):
    """Cut text with an ellipsis so it fits in `room` pixels."""
    text = str(text)
    while len(text) > 4 and font.measure(text) > room:
        text = text[:-2].rstrip() + "…"
    return text


def rounded_rect(canvas, x1, y1, x2, y2, r=12, **kw):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


def _cloud(c, cx, cy, s, color, tag):
    c.create_oval(cx - .62 * s, cy - .05 * s, cx - .12 * s, cy + .42 * s, fill=color, outline="", tags=tag)
    c.create_oval(cx - .38 * s, cy - .42 * s, cx + .22 * s, cy + .30 * s, fill=color, outline="", tags=tag)
    c.create_oval(cx + .02 * s, cy - .20 * s, cx + .58 * s, cy + .42 * s, fill=color, outline="", tags=tag)
    c.create_rectangle(cx - .38 * s, cy + .12 * s, cx + .34 * s, cy + .42 * s, fill=color, outline="", tags=tag)


def _sun(c, cx, cy, s, core="#ffb020", ray="#ffcf5a", tag="icon", rot=0.0):
    w = max(2, int(s * .09))
    for i in range(8):
        a = rot + i * math.pi / 4
        c.create_line(cx + math.cos(a) * s * .58, cy + math.sin(a) * s * .58,
                      cx + math.cos(a) * s * .86, cy + math.sin(a) * s * .86,
                      fill=ray, width=w, capstyle="round", tags=tag)
    c.create_oval(cx - .42 * s, cy - .42 * s, cx + .42 * s, cy + .42 * s, fill=core, outline="", tags=tag)


def draw_icon(c, kind, cx, cy, s, tag="icon"):
    """Draw a weather icon of 'radius' s centred on (cx, cy)."""
    if kind == "sun":
        _sun(c, cx, cy, s, tag=tag)
    elif kind == "heat":
        _sun(c, cx, cy - .08 * s, s * .9, core="#ff5a1f", ray="#ffb000", tag=tag)
        for k in (-1, 0, 1):
            x = cx + k * .32 * s
            c.create_line(x, cy + .62 * s, x + .08 * s, cy + .72 * s, x - .02 * s, cy + .82 * s, x + .06 * s,
                          cy + .94 * s, fill="#ff7a29", width=2, smooth=True, tags=tag)
    elif kind == "partly":
        _sun(c, cx - .25 * s, cy - .22 * s, s * .62, tag=tag)
        _cloud(c, cx + .12 * s, cy + .12 * s, s * .82, "#dfe7f1", tag)
    elif kind == "cloud":
        _cloud(c, cx, cy, s, "#cfd9e6", tag)
    elif kind in ("rain", "storm"):
        _cloud(c, cx, cy - .18 * s, s * .95, "#8e9bb3" if kind == "storm" else "#bfcbe0", tag)
        if kind == "storm":
            c.create_polygon(cx - .02 * s, cy + .18 * s, cx - .22 * s, cy + .58 * s, cx - .02 * s, cy + .55 * s,
                             cx - .12 * s, cy + .92 * s, cx + .22 * s, cy + .42 * s, cx + .02 * s, cy + .45 * s,
                             cx + .12 * s, cy + .18 * s, fill="#ffd23f", outline="", tags=tag)
        else:
            for k in (-1, 0, 1):
                x = cx + k * .3 * s
                c.create_line(x, cy + .38 * s, x - .1 * s, cy + .7 * s, fill="#5aa9ff",
                              width=max(2, int(s * .08)), capstyle="round", tags=tag)
    elif kind == "snow":
        _cloud(c, cx, cy - .18 * s, s * .95, "#dbe7f5", tag)
        for k in (-1, 0, 1):
            x, y = cx + k * .3 * s, cy + .58 * s + (k % 2) * .12 * s
            r = .07 * s + 1
            c.create_oval(x - r, y - r, x + r, y + r, fill="#ffffff", outline="", tags=tag)
    elif kind == "fog":
        for k in range(3):
            y = cy - .3 * s + k * .3 * s
            c.create_line(cx - .7 * s, y, cx + .7 * s, y, fill="#b9c3cf", width=max(2, int(s * .1)),
                          capstyle="round", tags=tag)
    elif kind == "wind":
        for k, ln in enumerate((0.8, 1.0, 0.6)):
            y = cy - .35 * s + k * .35 * s
            c.create_line(cx - .75 * s, y, cx + (ln - .45) * s, y, cx + (ln - .25) * s, y - .18 * s,
                          cx + (ln - .45) * s, y - .3 * s, fill="#9fe8d6", width=max(2, int(s * .09)),
                          smooth=True, capstyle="round", tags=tag)
    elif kind == "drop":
        c.create_polygon(cx, cy - .8 * s, cx + .5 * s, cy + .1 * s, cx + .45 * s, cy + .55 * s, cx, cy + .78 * s,
                         cx - .45 * s, cy + .55 * s, cx - .5 * s, cy + .1 * s, smooth=True,
                         fill="#4aa8ff", outline="", tags=tag)
    elif kind == "gauge":
        c.create_arc(cx - .8 * s, cy - .7 * s, cx + .8 * s, cy + .9 * s, start=0, extent=180, style="arc",
                     outline="#ffb020", width=max(2, int(s * .14)), tags=tag)
        c.create_line(cx, cy + .1 * s, cx + .45 * s, cy - .4 * s, fill="#ff5a1f", width=2, tags=tag)
    elif kind == "leaf":
        c.create_oval(cx - .7 * s, cy - .45 * s, cx + .7 * s, cy + .45 * s, fill="#3ecf8e", outline="", tags=tag)
        c.create_line(cx - .6 * s, cy + .3 * s, cx + .6 * s, cy - .3 * s, fill="#13573a", width=2, tags=tag)
    elif kind == "thermo":
        c.create_rectangle(cx - .14 * s, cy - .8 * s, cx + .14 * s, cy + .35 * s, fill="#ffe1c2", outline="", tags=tag)
        c.create_oval(cx - .32 * s, cy + .2 * s, cx + .32 * s, cy + .84 * s, fill="#ff4d1a", outline="", tags=tag)
        c.create_rectangle(cx - .06 * s, cy - .3 * s, cx + .06 * s, cy + .4 * s, fill="#ff4d1a", outline="", tags=tag)


# ================================================================= basics
class Card(tk.Frame):
    """A bordered panel with an optional title row and a body frame."""

    def __init__(self, parent, tm, title=None, subtitle=None, pad=12):
        super().__init__(parent, highlightthickness=1, bd=0)
        self.tm = tm
        tm.bind(self, bg="card", highlightbackground="border", highlightcolor="border")
        self.header = None
        if title:
            self.header = tk.Frame(self)
            tm.bind(self.header, bg="card")
            self.header.pack(fill="x", padx=pad, pady=(pad - 2, 4))
            self.title_lbl = tm.bind(tk.Label(self.header, text=title, font=parent.winfo_toplevel().fonts["h3"],
                                              anchor="w"), bg="card", fg="text")
            self.title_lbl.pack(side="left")
            if subtitle:
                self.sub_lbl = tm.bind(tk.Label(self.header, text=subtitle, anchor="w",
                                                font=parent.winfo_toplevel().fonts["small"]), bg="card", fg="faint")
                self.sub_lbl.pack(side="left", padx=(8, 0), pady=(2, 0))
            self.tools = tk.Frame(self.header)
            tm.bind(self.tools, bg="card")
            self.tools.pack(side="right")
        self.body = tk.Frame(self)
        tm.bind(self.body, bg="card")
        self.body.pack(fill="both", expand=True, padx=pad, pady=(0 if title else pad, pad))

    def set_title(self, text):
        if self.header:
            self.title_lbl.configure(text=text)


class HoverButton(tk.Label):
    """Flat, theme-aware button (a Label, so colours work on Windows AND macOS)."""

    KINDS = {
        "primary": ("accent", "accent2", "accent_text"),
        "ghost": ("card_hi", "border", "text"),
        "subtle": ("card", "card_hi", "muted"),
    }

    def __init__(self, parent, tm, text, command=None, kind="primary", font=None, padx=14, pady=6):
        fonts = parent.winfo_toplevel().fonts
        super().__init__(parent, text=text, cursor="hand2", padx=padx, pady=pady,
                         font=font or fonts["body_bold"])
        self.tm, self.command, self.kind = tm, command, kind
        self.base, self.hover, fg = self.KINDS[kind]
        tm.bind(self, bg=self.base, fg=fg)
        self.bind("<Enter>", lambda e: self.configure(bg=self.tm.p[self.hover]))
        self.bind("<Leave>", lambda e: self.configure(bg=self.tm.p[self.base]))
        self.bind("<Button-1>", self._click)
        self.enabled = True

    def _click(self, _e=None):
        if self.enabled and self.command:
            self.command()

    def set_enabled(self, flag):
        self.enabled = flag
        self.configure(cursor="hand2" if flag else "arrow")


class Segmented(tk.Frame):
    """Pill-style option picker (e.g. 7 / 14 / 30 days)."""

    def __init__(self, parent, tm, options, command=None, value=None, font=None, padx=12):
        super().__init__(parent, highlightthickness=1, bd=0)
        self.tm, self.command = tm, command
        tm.bind(self, bg="card_hi", highlightbackground="border")
        self.value = value if value is not None else options[0][0]
        self.items = {}
        fonts = parent.winfo_toplevel().fonts
        for val, text in options:
            lbl = tk.Label(self, text=text, padx=padx, pady=4, cursor="hand2", font=font or fonts["small_bold"])
            lbl.pack(side="left")
            lbl.bind("<Button-1>", lambda e, v=val: self.set(v, fire=True))
            self.items[val] = lbl
        tm.watch(self, self.refresh)
        self.refresh()

    def set(self, value, fire=False):
        self.value = value
        self.refresh()
        if fire and self.command:
            self.command(value)

    def refresh(self):
        p = self.tm.p
        for val, lbl in self.items.items():
            on = val == self.value
            lbl.configure(bg=p["accent"] if on else p["card_hi"], fg=p["accent_text"] if on else p["muted"])


class NavButton(tk.Frame):
    def __init__(self, parent, tm, symbol, text, command):
        super().__init__(parent, cursor="hand2")
        self.tm, self.command, self.active = tm, command, False
        fonts = parent.winfo_toplevel().fonts
        self.bar = tk.Frame(self, width=4)
        self.bar.pack(side="left", fill="y")
        self.sym = tk.Label(self, text=symbol, font=fonts["symbol"], width=2)
        self.sym.pack(side="left", padx=(10, 4), pady=9)
        self.lbl = tk.Label(self, text=text, font=fonts["body_bold"], anchor="w")
        self.lbl.pack(side="left", fill="x", expand=True)
        for w in (self, self.sym, self.lbl, self.bar):
            w.bind("<Button-1>", lambda e: self.command())
            w.bind("<Enter>", lambda e: self._hover(True))
            w.bind("<Leave>", lambda e: self._hover(False))
        tm.watch(self, self.refresh)
        self.refresh()

    def _hover(self, on):
        if not self.active:
            bg = self.tm.p["card"] if on else self.tm.p["panel"]
            for w in (self, self.sym, self.lbl):
                w.configure(bg=bg)

    def set_active(self, flag):
        self.active = flag
        self.refresh()

    def refresh(self):
        p = self.tm.p
        bg = p["card_hi"] if self.active else p["panel"]
        for w in (self, self.sym, self.lbl):
            w.configure(bg=bg)
        self.bar.configure(bg=p["accent"] if self.active else p["panel"])
        self.sym.configure(fg=p["accent"] if self.active else p["faint"])
        self.lbl.configure(fg=p["text"] if self.active else p["muted"])


class StatusBadge(tk.Label):
    """Coloured pill: icon + label (status is never shown by colour alone)."""

    def __init__(self, parent, level=0, text=None):
        fonts = parent.winfo_toplevel().fonts
        super().__init__(parent, font=fonts["small_bold"], padx=10, pady=3)
        self.set(level, text)

    def set(self, level, text=None):
        color, icon, name = STATUS[level]
        self.configure(text=f"{icon}  {text or name}", bg=color, fg="#140a04")


class ScrollFrame(tk.Frame):
    """A frame with a vertical scrollbar (mouse-wheel aware)."""

    def __init__(self, parent, tm, bg_key="bg"):
        super().__init__(parent)
        tm.bind(self, bg=bg_key)
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0)
        tm.bind(self.canvas, bg=bg_key)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas)
        tm.bind(self.inner, bg=bg_key)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")
        self.bind_all_wheel()

    def bind_all_wheel(self):
        def on_wheel(e):
            delta = -1 if (getattr(e, "num", 0) == 4 or e.delta > 0) else 1
            self.canvas.yview_scroll(delta * 2, "units")

        self.canvas.bind("<Enter>", lambda e: (self.canvas.bind_all("<MouseWheel>", on_wheel),
                                               self.canvas.bind_all("<Button-4>", on_wheel),
                                               self.canvas.bind_all("<Button-5>", on_wheel)))
        self.canvas.bind("<Leave>", lambda e: (self.canvas.unbind_all("<MouseWheel>"),
                                               self.canvas.unbind_all("<Button-4>"),
                                               self.canvas.unbind_all("<Button-5>")))


# ============================================================ canvas widgets
class KpiTile(tk.Canvas):
    """Big number tile: icon, label, value, unit, a mini meter and a note."""

    def __init__(self, parent, tm, label, icon="sun", unit="", height=104, meter_range=(0, 100)):
        self.k = ui_scale(parent)
        super().__init__(parent, height=int(height * self.k), highlightthickness=0, bd=0)
        self.tm, self.label, self.icon, self.unit = tm, label, icon, unit
        self.value, self.note, self.level = "--", "", None
        self.meter = None
        self.meter_range = meter_range
        self.meter_color = None
        self.fonts = parent.winfo_toplevel().fonts
        tm.bind(self, bg="bg")
        self.bind("<Configure>", lambda e: self.redraw())
        tm.watch(self, self.redraw)

    def update_value(self, value, note="", level=None, meter=None, meter_color=None):
        self.value, self.note, self.level = value, note, level
        self.meter, self.meter_color = meter, meter_color
        self.redraw()

    def redraw(self):
        p, f = self.tm.p, self.fonts
        self.delete("all")
        k = self.k
        w, h = max(self.winfo_width(), 60), max(self.winfo_height(), 60)
        m = 16 * k                                                   # side margin
        rounded_rect(self, 1, 1, w - 1, h - 1, r=14 * k, fill=p["card"], outline=p["border"])
        self.create_line(m, 2, m + 40 * k, 2, fill=p["accent"], width=3, capstyle="round")
        draw_icon(self, self.icon, m + 10 * k, 27 * k, 11 * k)
        self.create_text(m + 28 * k, 27 * k, text=fit_text(f["small_bold"], self.label.upper(), w - m - 46 * k),
                         anchor="w", fill=p["muted"], font=f["small_bold"])
        vid = self.create_text(m, h * 0.55, text=str(self.value), anchor="w", fill=p["text"], font=f["kpi"])
        box = self.bbox(vid)
        x2 = box[2] if box else 80
        self.create_text(x2 + 4 * k, h * 0.55 + 4 * k, text=self.unit, anchor="w", fill=p["muted"], font=f["body"])
        if self.meter is not None:
            lo, hi = self.meter_range
            frac = max(0.0, min(1.0, (self.meter - lo) / (hi - lo)))
            y = h - 30 * k
            rounded_rect(self, m, y, w - m, y + 5 * k, r=2, fill=p["card_hi"], outline="")
            if frac > 0.01:
                rounded_rect(self, m, y, m + (w - 2 * m) * frac, y + 5 * k, r=2,
                             fill=self.meter_color or p["accent"], outline="")
        if self.note:
            color = STATUS[self.level][0] if self.level is not None else p["faint"]
            yy = h - 14 * k
            if self.level is not None:
                self.create_oval(m, yy - 4 * k, m + 8 * k, yy + 4 * k, fill=color, outline="")
                self.create_text(m + 14 * k, yy, text=fit_text(f["small"], self.note, w - 2 * m - 14 * k),
                                 anchor="w", fill=p["muted"], font=f["small"])
            else:
                self.create_text(m, yy, text=fit_text(f["small"], self.note, w - 2 * m), anchor="w",
                                 fill=p["faint"], font=f["small"])


class TemperatureDial(tk.Canvas):
    """A 270-degree gauge from -10 C to 50 C with a needle."""

    LOW, HIGH = -10, 50

    def __init__(self, parent, tm, size=250):
        self.k = ui_scale(parent)
        size = int(size * self.k)
        super().__init__(parent, width=size, height=size - int(20 * self.k), highlightthickness=0, bd=0)
        self.tm = tm
        self.fonts = parent.winfo_toplevel().fonts
        self.value, self.feels, self.caption = None, None, ""
        self.shown = self.LOW
        tm.bind(self, bg="card")
        self.bind("<Configure>", lambda e: self.redraw())
        tm.watch(self, self.redraw)
        self._anim = None

    def set_value(self, value, feels=None, caption=""):
        self.value, self.feels, self.caption = value, feels, caption
        if self._anim:
            self.after_cancel(self._anim)
        self._step()

    def _step(self):
        if self.value is None:
            return
        diff = self.value - self.shown
        if abs(diff) < 0.15:
            self.shown = self.value
            self.redraw()
            return
        self.shown += diff * 0.18
        self.redraw()
        self._anim = self.after(16, self._step)

    def _angle(self, t):
        frac = (min(max(t, self.LOW), self.HIGH) - self.LOW) / (self.HIGH - self.LOW)
        return 225 - frac * 270

    def redraw(self):
        p, f = self.tm.p, self.fonts
        k = self.k
        self.delete("all")
        w, h = max(self.winfo_width(), 120), max(self.winfo_height(), 120)
        cx, cy = w / 2, h / 2 + 10 * k
        r = min(w, h) / 2 - 18 * k
        box = (cx - r, cy - r, cx + r, cy + r)
        steps, band = 60, 14 * k
        for i in range(steps):
            t0 = self.LOW + (self.HIGH - self.LOW) * i / steps
            a0 = self._angle(t0)
            self.create_arc(*box, start=a0 - 270 / steps - 0.4, extent=270 / steps + 0.8, style="arc",
                            outline=blend(temp_color(t0), p["card"], 0.62), width=band)
        if self.value is not None:
            for i in range(steps):
                t0 = self.LOW + (self.HIGH - self.LOW) * i / steps
                if t0 > self.shown:
                    break
                a0 = self._angle(t0)
                self.create_arc(*box, start=a0 - 270 / steps - 0.4, extent=270 / steps + 0.8, style="arc",
                                outline=temp_color(t0), width=band)
        for t in range(self.LOW, self.HIGH + 1, 10):
            a = math.radians(self._angle(t))
            x1, y1 = cx + math.cos(a) * (r - 14 * k), cy - math.sin(a) * (r - 14 * k)
            x2, y2 = cx + math.cos(a) * (r - 22 * k), cy - math.sin(a) * (r - 22 * k)
            self.create_line(x1, y1, x2, y2, fill=p["faint"], width=2)
            tx, ty = cx + math.cos(a) * (r - 34 * k), cy - math.sin(a) * (r - 34 * k)
            self.create_text(tx, ty, text=str(t), fill=p["faint"], font=f["tiny"])
        a = math.radians(self._angle(40))
        self.create_line(cx + math.cos(a) * (r + 9 * k), cy - math.sin(a) * (r + 9 * k), cx + math.cos(a) * (r - 9 * k),
                         cy - math.sin(a) * (r - 9 * k), fill=STATUS[3][0], width=3)
        self.create_text(cx + math.cos(a) * (r + 18 * k), cy - math.sin(a) * (r + 18 * k) - 2, text="HW",
                         fill=STATUS[3][0], font=f["tiny"])
        if self.value is not None:
            a = math.radians(self._angle(self.shown))
            nx, ny = cx + math.cos(a) * (r - 26 * k), cy - math.sin(a) * (r - 26 * k)
            self.create_line(cx, cy, nx, ny, fill=p["text"], width=3, capstyle="round")
            self.create_oval(cx - 7 * k, cy - 7 * k, cx + 7 * k, cy + 7 * k, fill=temp_color(self.shown),
                             outline=p["card"], width=2)
            self.create_text(cx, cy + r * 0.42, text=f"{self.value:.1f}\N{DEGREE SIGN}C", fill=p["text"],
                             font=f["h1"])
            sub = f"feels like {self.feels:.0f}\N{DEGREE SIGN}C" if self.feels is not None else ""
            self.create_text(cx, cy + r * 0.42 + 26 * k, text=sub, fill=p["muted"], font=f["small"])
        if self.caption:
            self.create_text(cx, 12 * k, text=self.caption, fill=p["muted"], font=f["small_bold"])


class DayCard(tk.Canvas):
    """One forecast day: weekday, icon, temperature, rain chance, risk dot."""

    def __init__(self, parent, tm, width=110, height=160):
        k = ui_scale(parent)
        super().__init__(parent, width=int(width * k), height=int(height * k), highlightthickness=0, bd=0)
        self.tm = tm
        self.fonts = parent.winfo_toplevel().fonts
        self.data = None
        tm.bind(self, bg="card")
        self.bind("<Configure>", lambda e: self.redraw())
        tm.watch(self, self.redraw)

    def set(self, day, date_txt, kind, temp, low, high, rain, level, label):
        self.data = (day, date_txt, kind, temp, low, high, rain, level, label)
        self.redraw()

    def redraw(self):
        self.delete("all")
        if not self.data:
            return
        p, f = self.tm.p, self.fonts
        day, date_txt, kind, temp, low, high, rain, level, label = self.data
        w, h = max(self.winfo_width(), 60), max(self.winfo_height(), 100)
        u = h / 160.0
        rounded_rect(self, 2, 2, w - 2, h - 2, r=12, fill=p["card_hi"], outline=p["border"])
        if level >= 2:
            rounded_rect(self, 2, 2, w - 2, h - 2, r=12, fill="", outline=STATUS[level][0], width=2)
        self.create_text(w / 2, 16 * u, text=day, fill=p["text"], font=f["small_bold"])
        self.create_text(w / 2, 31 * u, text=date_txt, fill=p["faint"], font=f["tiny"])
        draw_icon(self, kind, w / 2, 60 * u, 16 * u)
        self.create_text(w / 2, 94 * u, text=f"{temp:.0f}\N{DEGREE SIGN}", fill=temp_color(temp), font=f["h2"])
        self.create_text(w / 2, 114 * u, text=f"{low:.0f}\N{DEGREE SIGN} / {high:.0f}\N{DEGREE SIGN}",
                         fill=p["muted"], font=f["tiny"])
        self.create_text(w / 2, 131 * u, text=f"\u2602 {rain:.0%}", fill="#8cc4ff", font=f["tiny"])
        bar_w = (w - 28) * rain
        rounded_rect(self, 14, h - 14 * u, w - 14, h - 14 * u + 5, r=2, fill=p["border"], outline="")
        if bar_w > 2:
            rounded_rect(self, 14, h - 14 * u, 14 + bar_w, h - 14 * u + 5, r=2, fill="#5aa9ff", outline="")


class RiskRow(tk.Canvas):
    """One analyzer result: icon + name + level pill + message."""

    def __init__(self, parent, tm, height=44):
        self.k = ui_scale(parent)
        super().__init__(parent, height=int(height * self.k), highlightthickness=0, bd=0)
        self.tm = tm
        self.fonts = parent.winfo_toplevel().fonts
        self.res = None
        tm.bind(self, bg="card")
        self.bind("<Configure>", lambda e: self.redraw())
        tm.watch(self, self.redraw)

    def set(self, result):
        self.res = result
        self.redraw()

    def redraw(self):
        self.delete("all")
        if not self.res:
            return
        p, f, r = self.tm.p, self.fonts, self.res
        k = self.k
        w, h = max(self.winfo_width(), 100), max(self.winfo_height(), 30)
        icon = {"heat": "heat", "snow": "snow", "drop": "drop", "wind": "wind", "rain": "rain"}.get(r.icon, "sun")
        draw_icon(self, icon, 18 * k, h / 2, 10 * k)
        color, sym, _ = STATUS[r.level]
        pill = f"{sym} {r.label}"
        tw = f["tiny"].measure(pill) + 20 * k
        self.create_text(38 * k, h / 2 - 8 * k, text=r.analyzer, anchor="w", fill=p["text"], font=f["small_bold"])
        self.create_text(38 * k, h / 2 + 9 * k, text=fit_text(f["tiny"], r.message, max(60, w - tw - 50 * k)),
                         anchor="w", fill=p["muted"], font=f["tiny"])
        rounded_rect(self, w - tw - 4, h / 2 - 10 * k, w - 4, h / 2 + 10 * k, r=10 * k, fill=color, outline="")
        self.create_text(w - tw / 2 - 4, h / 2, text=pill, fill="#140a04", font=f["tiny"])
        self.create_line(0, h - 1, w, h - 1, fill=p["border"])


class Logo(tk.Canvas):
    """The project logo from Experiment 7 - sun + warning sign in a ring,
    now animated (rays rotate, ring pulses)."""

    def __init__(self, parent, tm, size=64, animate=True, bg_key="panel"):
        size = int(size * ui_scale(parent))
        super().__init__(parent, width=size, height=size, highlightthickness=0, bd=0)
        self.tm, self.size, self.rot = tm, size, 0.0
        tm.bind(self, bg=bg_key)
        tm.watch(self, self.redraw)
        self.redraw()
        if animate:
            self._tick()

    def _tick(self):
        self.rot += 0.03
        self.redraw()
        self.after(60, self._tick)

    def redraw(self):
        p = self.tm.p
        self.delete("all")
        s = self.size
        cx = cy = s / 2
        pulse = 1 + 0.04 * math.sin(self.rot * 4)
        R = s * 0.46 * pulse
        self.create_oval(cx - R, cy - R, cx + R, cy + R, outline=p["accent"], width=max(2, s // 28))
        for i in range(8):
            a = self.rot + i * math.pi / 4
            self.create_line(cx + math.cos(a) * s * .26, cy + math.sin(a) * s * .26, cx + math.cos(a) * s * .38,
                             cy + math.sin(a) * s * .38, fill=p["accent2"], width=max(2, s // 26), capstyle="round")
        self.create_oval(cx - s * .21, cy - s * .21, cx + s * .21, cy + s * .21, fill=p["accent"], outline="")
        t = s * .12
        self.create_polygon(cx, cy - t, cx + t, cy + t * .8, cx - t, cy + t * .8, fill="#e8231b", outline="")
        self.create_text(cx, cy + t * .15, text="!", fill="white", font=("Arial", max(6, int(s * .11)), "bold"))


# ==================================================== animated header banner
class ParticleBanner(tk.Canvas):
    """Gradient header with particles that match the theme:
       solar = drifting sun-dust, blaze = rising embers, frost = snowfall,
       gale = wind streaks, monsoon = rain + lightning."""

    def __init__(self, parent, tm, height=92):
        super().__init__(parent, height=height, highlightthickness=0, bd=0)
        self.tm = tm
        self.fonts = parent.winfo_toplevel().fonts
        self.parts = []
        self.mode = None
        self.clock_txt = ""
        self.right_text = ""
        self.flash = 0
        self.emblem_rot = 0.0
        self.bind("<Configure>", lambda e: self.rebuild())
        tm.watch(self, self.rebuild)
        self.after(200, self._tick)

    # -------------------------------------------------------------- layout
    def rebuild(self):
        self.delete("all")
        self.parts = []
        self.mode = self.tm.name
        p, f = self.tm.p, self.fonts
        w, h = max(self.winfo_width(), 400), max(self.winfo_height(), 60)
        bands = 46
        for i in range(bands):
            c = blend(p["banner_top"], p["banner_bottom"], i / (bands - 1))
            y0 = h * i / bands
            self.create_rectangle(0, y0, w, y0 + h / bands + 1, fill=c, outline="", tags="bgfill")
        z = h / 92.0                                     # banner scale
        self.z = z
        ex = w - 80 * z                                  # emblem centre x
        for k in range(6):
            r = (120 - k * 18) * z
            self.create_oval(ex - r, h / 2 - r, ex + r, h / 2 + r,
                             fill=blend(p["banner_bottom"], p["accent"], 0.05 + k * 0.035), outline="", tags="bgfill")
        self.create_rectangle(0, 0, w, h, fill="white", outline="", stipple="gray12", state="hidden", tags="flash")
        self.create_line(0, h - 1, w, h - 1, fill=p["accent"], width=2, tags="fg")
        # emblem + text
        self._emblem(ex, h / 2)
        self.create_text(84 * z, h / 2 - 13 * z, text="HEATGUARD AI", anchor="w", fill=p["text"], font=f["h1"],
                         tags="fg")
        self.create_text(86 * z, h / 2 + 15 * z,
                         text="Climate Intelligence for Heatwave Monitoring, Prediction & Early Warning   \u2022   KJS-CES-01",
                         anchor="w", fill=p["muted"], font=f["small"], tags="fg")
        self._logo(42 * z, h / 2, 28 * z)
        tx = w - 150 * z
        self.create_text(tx, h / 2 - 20 * z, text=f"{p['symbol']}  {p['label']} MODE", anchor="e",
                         fill=p["accent2"], font=f["h3"], tags=("fg", "chip"))
        self.create_text(tx, h / 2 + 2 * z, text=self.tm.reason[:70], anchor="e", fill=p["muted"],
                         font=f["small"], tags=("fg", "reason"))
        self.create_text(tx, h / 2 + 22 * z, text=self.clock_txt, anchor="e", fill=p["faint"], font=f["tiny"],
                         tags=("fg", "clock"))
        n = {"solar": 34, "blaze": 70, "frost": 70, "gale": 26, "monsoon": 90}.get(self.mode, 30)
        for _ in range(n):
            self._spawn(w, h, initial=True)
        self.tag_raise("fg")

    def _logo(self, cx, cy, r):
        p = self.tm.p
        self.create_oval(cx - r, cy - r, cx + r, cy + r, outline=p["accent"], width=2, tags=("fg", "logo"))
        self.create_oval(cx - r * .55, cy - r * .55, cx + r * .55, cy + r * .55, fill=p["accent"], outline="",
                         tags=("fg", "logo"))
        t = r * .3
        self.create_polygon(cx, cy - t, cx + t, cy + t * .8, cx - t, cy + t * .8, fill="#e8231b", outline="",
                            tags=("fg", "logo"))

    def _emblem(self, cx, cy):
        p = self.tm.p
        z = getattr(self, "z", 1.0)
        self.delete("emblem")
        m = self.mode
        tag = ("emblem",)
        rot = self.emblem_rot
        lw = max(2, int(3 * z))
        if m in ("solar", "blaze"):
            core = "#ffb020" if m == "solar" else "#ff4d1a"
            for i in range(12):
                a = rot + i * math.pi / 6
                self.create_line(cx + math.cos(a) * 30 * z, cy + math.sin(a) * 30 * z, cx + math.cos(a) * 44 * z,
                                 cy + math.sin(a) * 44 * z, fill=p["accent2"], width=lw, capstyle="round", tags=tag)
            self.create_oval(cx - 24 * z, cy - 24 * z, cx + 24 * z, cy + 24 * z, fill=core, outline="", tags=tag)
        elif m == "frost":
            for i in range(6):
                a = rot + i * math.pi / 3
                x2, y2 = cx + math.cos(a) * 40 * z, cy + math.sin(a) * 40 * z
                self.create_line(cx, cy, x2, y2, fill=p["accent2"], width=lw, tags=tag)
                for side in (-1, 1):
                    b = a + side * 0.6
                    mx, my = cx + math.cos(a) * 24 * z, cy + math.sin(a) * 24 * z
                    self.create_line(mx, my, mx + math.cos(b) * 11 * z, my + math.sin(b) * 11 * z, fill=p["accent2"],
                                     width=2, tags=tag)
        elif m == "gale":
            for k in range(3):
                y = cy + (k - 1) * 18 * z
                off = math.sin(rot * 3 + k) * 6 * z
                self.create_line(cx - 48 * z + off, y, cx + 10 * z + off, y, cx + 26 * z + off, y - 10 * z,
                                 cx + 14 * z + off, y - 20 * z,
                                 fill=p["accent2"], width=lw, smooth=True, capstyle="round", tags=tag)
        elif m == "monsoon":
            _cloud(self, cx, cy - 6 * z, 40 * z, "#b8c6ea", "emblem")
            for k in (-1, 0, 1):
                off = ((rot * 60 + k * 9) % 18) * z
                x = cx + k * 14 * z
                self.create_line(x, cy + 14 * z + off, x - 4 * z, cy + 24 * z + off, fill="#7fb6ff", width=lw,
                                 tags=tag)
        self.tag_raise("emblem", "bgfill")

    # ----------------------------------------------------------- particles
    def _spawn(self, w, h, initial=False):
        p = self.tm.p
        col = random.choice(p["particles"])
        m = self.mode
        if m == "blaze":
            x, y = random.uniform(0, w), (random.uniform(0, h) if initial else h + 4)
            r = random.uniform(1.2, 3.4)
            item = self.create_oval(x - r, y - r, x + r, y + r, fill=col, outline="")
            d = {"id": item, "vx": random.uniform(-.3, .3), "vy": random.uniform(-1.6, -.5),
                 "phase": random.uniform(0, 6.28), "life": random.uniform(0.5, 1.0)}
        elif m == "frost":
            x, y = random.uniform(0, w), (random.uniform(0, h) if initial else -6)
            if random.random() < 0.25:
                item = self.create_text(x, y, text="❄", fill=col,
                                        font=(self.fonts["symbol_family"], random.randint(7, 12)))
            else:
                r = random.uniform(1, 2.4)
                item = self.create_oval(x - r, y - r, x + r, y + r, fill=col, outline="")
            d = {"id": item, "vx": random.uniform(-.2, .2), "vy": random.uniform(.35, 1.1),
                 "phase": random.uniform(0, 6.28), "life": 1}
        elif m == "gale":
            x, y = (random.uniform(0, w) if initial else -130), random.uniform(6, h - 6)
            ln = random.uniform(40, 130)
            item = self.create_line(x, y, x + ln * .5, y - 3, x + ln, y, fill=col, width=random.choice((1, 1, 2)),
                                    smooth=True, capstyle="round")
            d = {"id": item, "vx": random.uniform(4, 9), "vy": 0, "phase": random.uniform(0, 6.28), "life": 1}
        elif m == "monsoon":
            x, y = random.uniform(0, w + 40), (random.uniform(0, h) if initial else -14)
            ln = random.uniform(8, 16)
            item = self.create_line(x, y, x - ln * .25, y + ln, fill=col, width=1)
            d = {"id": item, "vx": -1.6, "vy": random.uniform(7, 11), "phase": 0, "life": 1}
        else:
            x, y = random.uniform(0, w), (random.uniform(0, h) if initial else h + 4)
            r = random.uniform(1.0, 2.6)
            item = self.create_oval(x - r, y - r, x + r, y + r, fill=col, outline="")
            d = {"id": item, "vx": random.uniform(.1, .5), "vy": random.uniform(-.45, -.15),
                 "phase": random.uniform(0, 6.28), "life": 1}
        self.tag_lower(item, "fg")
        self.parts.append(d)

    def _tick(self):
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        if self.winfo_viewable():
            w, h = self.winfo_width(), self.winfo_height()
            t = time.time()
            current, self.parts = self.parts, []
            for d in current:
                sway = math.sin(t * 2 + d["phase"]) * (0.6 if self.mode in ("blaze", "frost", "solar") else 0)
                self.move(d["id"], d["vx"] + sway, d["vy"])
                c = self.coords(d["id"])
                if not c:
                    continue
                x, y = c[0], c[1]
                if self.mode == "blaze":
                    d["life"] -= 0.006
                    if d["life"] < 0.35 and random.random() < 0.05:
                        self.itemconfigure(d["id"], fill=blend(random.choice(self.tm.p["particles"]),
                                                               self.tm.p["banner_top"], 0.5))
                if y < -10 or y > h + 20 or x > w + 140 or x < -150 or d["life"] <= 0:
                    self.delete(d["id"])
                    self._spawn(w, h)
                else:
                    self.parts.append(d)
            self.emblem_rot += 0.02
            self._emblem(w - 80 * getattr(self, "z", 1.0), h / 2)
            self.tag_raise("fg")
            if self.mode == "monsoon":
                if self.flash > 0:
                    self.flash -= 1
                    if self.flash == 0:
                        self.itemconfigure("flash", state="hidden")
                elif random.random() < 0.006:
                    self.flash = 3
                    self.itemconfigure("flash", state="normal")
            now = time.strftime("%a %d %b %Y   %H:%M:%S")
            if now != self.clock_txt:
                self.clock_txt = now
                self.itemconfigure("clock", text=now)
        self.after(40, self._tick)

    def set_reason(self, text):
        self.itemconfigure("reason", text=text[:70])


# ================================================================ pop-ups
class ToastManager:
    """Small notification cards that slide in at the bottom-right."""

    def __init__(self, root, tm):
        self.root, self.tm = root, tm
        self.active = []

    def show(self, title, message, level=1, duration=6500):
        color, sym, _ = STATUS[level]
        p, f = self.tm.p, self.root.fonts
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        try:
            win.attributes("-topmost", True)
            win.attributes("-alpha", 0.0)
        except tk.TclError:
            pass
        outer = tk.Frame(win, bg=color, padx=0, pady=0)
        outer.pack(fill="both", expand=True)
        body = tk.Frame(outer, bg=p["card_hi"], highlightthickness=1, highlightbackground=color)
        body.pack(fill="both", expand=True, padx=(5, 0))
        tk.Label(body, text=sym, bg=p["card_hi"], fg=color, font=f["symbol_big"]).pack(side="left", padx=(12, 6))
        txt = tk.Frame(body, bg=p["card_hi"])
        txt.pack(side="left", fill="both", expand=True, pady=10, padx=(0, 12))
        tk.Label(txt, text=title, bg=p["card_hi"], fg=p["text"], font=f["body_bold"], anchor="w",
                 justify="left").pack(fill="x")
        tk.Label(txt, text=message, bg=p["card_hi"], fg=p["muted"], font=f["small"], anchor="w", justify="left",
                 wraplength=int(300 * ui_scale(self.root))).pack(fill="x")
        tk.Label(body, text="✕", bg=p["card_hi"], fg=p["faint"], font=f["small"]).pack(side="top", anchor="ne",
                                                                                            padx=6, pady=4)
        for wdg in [win, outer, body, txt] + list(body.winfo_children()) + list(txt.winfo_children()):
            wdg.bind("<Button-1>", lambda e, w=win: self.close(w))
        win.update_idletasks()
        self.active.append(win)
        self._layout(slide_new=win)
        win.after(duration, lambda: self.close(win))
        try:
            self.root.bell()
        except tk.TclError:
            pass

    def _layout(self, slide_new=None):
        self.root.update_idletasks()
        rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        y = ry + rh - 40
        for win in reversed(self.active):
            if not win.winfo_exists():
                continue
            k = ui_scale(self.root)
            wh = max(win.winfo_reqheight(), int(70 * k))
            ww = int(380 * k)
            y -= wh + 10
            x = rx + rw - ww - 24
            if win is slide_new:
                self._slide(win, x + 60, x, y, ww, wh, 0)
            else:
                win.geometry(f"{ww}x{wh}+{x}+{y}")

    def _slide(self, win, x0, x1, y, ww, wh, step):
        if not win.winfo_exists():
            return
        t = min(1.0, step / 10)
        ease = 1 - (1 - t) ** 3
        x = int(x0 + (x1 - x0) * ease)
        win.geometry(f"{ww}x{wh}+{x}+{y}")
        try:
            win.attributes("-alpha", 0.15 + 0.85 * ease)
        except tk.TclError:
            pass
        if step < 10:
            win.after(16, self._slide, win, x0, x1, y, ww, wh, step + 1)

    def close(self, win):
        if win in self.active:
            self.active.remove(win)
        try:
            win.destroy()
        except tk.TclError:
            pass
        self._layout()


class AlertDialog(tk.Toplevel):
    """Big modal early-warning pop-up with a flashing border."""

    def __init__(self, root, tm, title, message, level=3, actions=None):
        super().__init__(root)
        self.tm = tm
        p, f = tm.p, root.fonts
        color, sym, name = STATUS[level]
        self.title(f"{name.upper()} ALERT - HeatGuard AI")
        self.configure(bg=color)
        self.transient(root)
        self.resizable(False, False)
        self.frame = tk.Frame(self, bg=p["card"], padx=26, pady=20)
        self.frame.pack(fill="both", expand=True, padx=4, pady=4)
        top = tk.Frame(self.frame, bg=p["card"])
        top.pack(fill="x")
        cv = tk.Canvas(top, width=74, height=66, bg=p["card"], highlightthickness=0)
        cv.pack(side="left")
        cv.create_polygon(37, 4, 72, 62, 2, 62, fill=color, outline="")
        cv.create_text(37, 40, text="!", fill="#140a04", font=("Arial", 26, "bold"))
        head = tk.Frame(top, bg=p["card"])
        head.pack(side="left", padx=14)
        tk.Label(head, text=f"{name.upper()}  EARLY WARNING", bg=p["card"], fg=color, font=f["small_bold"]).pack(anchor="w")
        tk.Label(head, text=title, bg=p["card"], fg=p["text"], font=f["h2"], wraplength=420, justify="left").pack(anchor="w")
        tk.Label(self.frame, text=message, bg=p["card"], fg=p["muted"], font=f["body"], wraplength=500,
                 justify="left").pack(anchor="w", pady=(14, 6))
        for line in actions or []:
            tk.Label(self.frame, text=f"•  {line}", bg=p["card"], fg=p["text"], font=f["small"], wraplength=500,
                     justify="left").pack(anchor="w", pady=1)
        btn = tk.Label(self.frame, text="ACKNOWLEDGE", bg=color, fg="#140a04", font=f["body_bold"], padx=20, pady=8,
                       cursor="hand2")
        btn.pack(anchor="e", pady=(16, 0))
        btn.bind("<Button-1>", lambda e: self.destroy())
        self.bind("<Return>", lambda e: self.destroy())
        self.bind("<Escape>", lambda e: self.destroy())
        self.update_idletasks()
        x = root.winfo_rootx() + (root.winfo_width() - self.winfo_reqwidth()) // 2
        y = root.winfo_rooty() + (root.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self._colors = (color, p["card_hi"])
        self._flash(0)
        try:
            self.grab_set()
            root.bell()
        except tk.TclError:
            pass
        self.focus_force()

    def _flash(self, n):
        if not self.winfo_exists():
            return
        self.configure(bg=self._colors[n % 2])
        if n < 9:
            self.after(260, self._flash, n + 1)
        else:
            self.configure(bg=self._colors[0])
