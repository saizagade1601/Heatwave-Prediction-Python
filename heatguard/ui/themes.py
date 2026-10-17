"""
themes.py  -  Dynamic theme engine
===================================
Five moods, chosen automatically from what you look at:

    solar    default warm orange   (the brand look of the heatwave project)
    blaze    fire                  MAX / high temperatures, heatwaves
    frost    ice                   MIN / low temperatures, cold waves, snow
    gale     wind                  wind / gust queries, storms
    monsoon  rain                  rain / precipitation / humidity queries

Every themed widget registers itself with ThemeManager.bind(). When the theme
changes, the manager smoothly blends every colour from the old palette to
the new one (a short colour animation) and tells the pages to redraw charts.
"""
import re
import tkinter as tk
from tkinter import ttk

# Status colours are RESERVED for alert levels and never used as theme accents
STATUS = {
    0: ("#3ecf8e", "✔", "Normal"),
    1: ("#f2c94c", "▲", "Watch"),
    2: ("#ff8c2a", "⚠", "Warning"),
    3: ("#ff4d4f", "✖", "Severe"),
}

PALETTES = {
    "solar": {
        "label": "SOLAR", "symbol": "☀", "tagline": "Warm baseline - monitoring",
        "bg": "#140c07", "panel": "#1a100a", "card": "#21140c", "card_hi": "#2d1c10",
        "border": "#3b2617", "text": "#fff3e6", "muted": "#c9a68a", "faint": "#7f6250",
        "accent": "#ff8a1f", "accent2": "#ffc361", "accent_text": "#1a0d04",
        "banner_top": "#4a1f06", "banner_bottom": "#160d07", "grid": "#33210f",
        "line": "#ff9a3c", "band": "#ff8a1f", "particles": ["#ffb347", "#ff8a1f", "#ffd27a", "#ff7a00"],
        "seq": ["#2a1709", "#6b2d07", "#b4470b", "#ff8a1f", "#ffc361", "#fff0c9"],
    },
    "blaze": {
        "label": "BLAZE", "symbol": "♨", "tagline": "Fire mode - extreme heat",
        "bg": "#130504", "panel": "#1a0705", "card": "#240b07", "card_hi": "#33110a",
        "border": "#4d180c", "text": "#fff0e8", "muted": "#e8a68c", "faint": "#8f5241",
        "accent": "#ff4d1a", "accent2": "#ffb000", "accent_text": "#1a0502",
        "banner_top": "#701405", "banner_bottom": "#150504", "grid": "#3a120a",
        "line": "#ff5a24", "band": "#ff4d1a", "particles": ["#ff3d00", "#ff7a00", "#ffb000", "#ffd54f", "#ff5722"],
        "seq": ["#2b0703", "#6e1404", "#b82806", "#ff4d1a", "#ffb000", "#fff1b0"],
    },
    "frost": {
        "label": "FROST", "symbol": "❄", "tagline": "Ice mode - cold conditions",
        "bg": "#06111b", "panel": "#091723", "card": "#0d1f2f", "card_hi": "#132a3f",
        "border": "#1d3a55", "text": "#ecf8ff", "muted": "#9fc6df", "faint": "#4f7591",
        "accent": "#5ccfff", "accent2": "#c3efff", "accent_text": "#03111c",
        "banner_top": "#123d5e", "banner_bottom": "#06111b", "grid": "#15304a",
        "line": "#6fd6ff", "band": "#5ccfff", "particles": ["#ffffff", "#d6f3ff", "#9fdcff", "#e8f9ff"],
        "seq": ["#071624", "#0d3150", "#1a5c8a", "#3fa3d8", "#8fd8ff", "#e6f8ff"],
    },
    "gale": {
        "label": "GALE", "symbol": "≋", "tagline": "Wind mode - air in motion",
        "bg": "#081312", "panel": "#0b1a19", "card": "#0f2321", "card_hi": "#152f2c",
        "border": "#21433f", "text": "#eafff9", "muted": "#a2d2c6", "faint": "#56817a",
        "accent": "#3fe0b0", "accent2": "#b5f7e3", "accent_text": "#03140f",
        "banner_top": "#11423c", "banner_bottom": "#081312", "grid": "#183531",
        "line": "#4fe6bb", "band": "#3fe0b0", "particles": ["#c8fff0", "#7debd0", "#ffffff", "#9ff5dc"],
        "seq": ["#08201d", "#0f4039", "#19705f", "#2fae8c", "#7debd0", "#e2fff6"],
    },
    "monsoon": {
        "label": "MONSOON", "symbol": "☂", "tagline": "Rain mode - monsoon watch",
        "bg": "#090c19", "panel": "#0c1023", "card": "#11162e", "card_hi": "#192040",
        "border": "#262f58", "text": "#eef1ff", "muted": "#a9b4e2", "faint": "#5b6597",
        "accent": "#6f8cff", "accent2": "#a8e0ff", "accent_text": "#060917",
        "banner_top": "#1f2d6b", "banner_bottom": "#090c19", "grid": "#1d2547",
        "line": "#7f9bff", "band": "#6f8cff", "particles": ["#9fc4ff", "#c9dcff", "#6f8cff", "#dfe9ff"],
        "seq": ["#0b1030", "#1a2563", "#2f45a6", "#5b7cf0", "#9fc4ff", "#e8f0ff"],
    },
}

THEME_ORDER = ("solar", "blaze", "frost", "gale", "monsoon")

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def blend(c1, c2, t):
    """Mix two hex colours: t=0 -> c1, t=1 -> c2."""
    a, b = _rgb(c1), _rgb(c2)
    return "#%02x%02x%02x" % tuple(int(round(x + (y - x) * t)) for x, y in zip(a, b))


def shade(color, t, target="#000000"):
    return blend(color, target, t)


class ThemeManager:
    STEPS = 9

    def __init__(self, root):
        self.root = root
        self.name = "solar"
        self.p = dict(PALETTES["solar"])
        self.reason = "Default warm theme"
        self.auto = True
        self._items = []
        self._listeners = []
        self._watchers = []
        self._anim = None
        self.style = ttk.Style(root)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self._style_ttk(self.p)

    # --------------------------------------------------------- registry --
    def bind(self, widget, **roles):
        """bind(label, bg='card', fg='text') -> recolours automatically."""
        self._items.append((widget, roles))
        self._configure(widget, roles, self.p)
        return widget

    def listen(self, callback):
        self._listeners.append(callback)

    def watch(self, widget, redraw):
        """Call redraw() after every theme change while the widget exists
        (used by canvas-drawn widgets that paint their own colours)."""
        self._watchers.append((widget, redraw))

    def _notify_watchers(self):
        alive = []
        for widget, fn in self._watchers:
            try:
                if widget.winfo_exists():
                    fn()
                    alive.append((widget, fn))
            except tk.TclError:
                pass
        self._watchers = alive

    def _configure(self, widget, roles, pal):
        try:
            widget.configure(**{opt: pal[key] for opt, key in roles.items()})
            return True
        except tk.TclError:
            return False

    def _apply(self, pal):
        alive = []
        for widget, roles in self._items:
            if self._configure(widget, roles, pal):
                alive.append((widget, roles))
        self._items = alive

    # ------------------------------------------------------------ switch --
    def set(self, name, reason="", force=False):
        if name not in PALETTES:
            return
        self.reason = reason or PALETTES[name]["tagline"]
        if name == self.name and not force:
            for cb in list(self._listeners):
                cb(self.p, False)
            return
        old, new = dict(self.p), PALETTES[name]
        self.name = name
        if self._anim:
            self.root.after_cancel(self._anim)
        self._animate(old, new, 1)

    def _animate(self, old, new, step):
        t = step / self.STEPS
        pal = {k: (blend(old[k], v, t) if isinstance(v, str) and HEX.match(v) and isinstance(old.get(k), str)
                   and HEX.match(old[k]) else v) for k, v in new.items()}
        self._apply(pal)
        if step < self.STEPS:
            self._anim = self.root.after(28, self._animate, old, new, step + 1)
        else:
            self._anim = None
            self.p = dict(new)
            self._style_ttk(self.p)
            self._notify_watchers()
            for cb in list(self._listeners):
                cb(self.p, True)

    # --------------------------------------------------------------- ttk --
    def _style_ttk(self, p):
        s = self.style
        s.configure("Treeview", background=p["card"], fieldbackground=p["card"], foreground=p["text"],
                    bordercolor=p["border"], borderwidth=0,
                    rowheight=int(26 * getattr(self.root, "S", 1.0)))
        s.map("Treeview", background=[("selected", p["accent"])], foreground=[("selected", p["accent_text"])])
        s.configure("Treeview.Heading", background=p["card_hi"], foreground=p["muted"], relief="flat",
                    bordercolor=p["border"], font=self.root.fonts["small_bold"] if hasattr(self.root, "fonts") else None)
        s.map("Treeview.Heading", background=[("active", p["border"])])
        for orient in ("Vertical", "Horizontal"):
            s.configure(f"{orient}.TScrollbar", background=p["card_hi"], troughcolor=p["card"],
                        bordercolor=p["card"], arrowcolor=p["muted"], lightcolor=p["card_hi"], darkcolor=p["card_hi"])
            s.map(f"{orient}.TScrollbar", background=[("active", p["border"])])
        s.configure("TCombobox", fieldbackground=p["card_hi"], background=p["card_hi"], foreground=p["text"],
                    arrowcolor=p["accent"], bordercolor=p["border"], lightcolor=p["card_hi"], darkcolor=p["card_hi"],
                    selectbackground=p["card_hi"], selectforeground=p["text"], padding=4)
        s.map("TCombobox", fieldbackground=[("readonly", p["card_hi"])], foreground=[("readonly", p["text"])],
              selectbackground=[("readonly", p["card_hi"])], selectforeground=[("readonly", p["text"])])
        s.configure("TSpinbox", fieldbackground=p["card_hi"], background=p["card_hi"], foreground=p["text"],
                    arrowcolor=p["accent"], bordercolor=p["border"], lightcolor=p["card_hi"], darkcolor=p["card_hi"])
        s.configure("Accent.Horizontal.TProgressbar", troughcolor=p["card_hi"], background=p["accent"],
                    bordercolor=p["card_hi"], lightcolor=p["accent"], darkcolor=p["accent"])
        self.root.option_add("*TCombobox*Listbox.background", p["card_hi"])
        self.root.option_add("*TCombobox*Listbox.foreground", p["text"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", p["accent"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", p["accent_text"])


from ..theme_rules import ThemeDetector  # noqa: E402,F401  (re-exported)
