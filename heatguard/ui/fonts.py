"""fonts.py - picks the nicest font that exists on this computer."""
import tkinter.font as tkfont

UI_CANDIDATES = ("Segoe UI", "SF Pro Text", "Helvetica Neue", "Inter", "Ubuntu", "Cantarell",
                 "DejaVu Sans", "Arial", "Helvetica")
DISPLAY_CANDIDATES = ("Bahnschrift", "Segoe UI Semibold", "SF Pro Display", "Poppins", "Montserrat",
                      "Inter Display", "Helvetica Neue", "DejaVu Sans", "Arial")
MONO_CANDIDATES = ("Cascadia Code", "Consolas", "JetBrains Mono", "SF Mono", "Menlo", "DejaVu Sans Mono",
                   "Courier New")
SYMBOL_CANDIDATES = ("Segoe UI Symbol", "Apple Symbols", "DejaVu Sans", "Noto Sans Symbols2", "Arial Unicode MS")


def _pick(candidates, available):
    lower = {name.lower(): name for name in available}
    for name in candidates:
        if name.lower() in lower:
            return lower[name.lower()]
    return "TkDefaultFont"


def build_fonts(root):
    available = set(tkfont.families(root))
    ui = _pick(UI_CANDIDATES, available)
    disp = _pick(DISPLAY_CANDIDATES, available)
    mono = _pick(MONO_CANDIDATES, available)
    sym = _pick(SYMBOL_CANDIDATES, available)

    def f(family, size, weight="normal"):
        return tkfont.Font(root=root, family=family, size=size, weight=weight)

    fonts = {
        "family": ui, "display_family": disp, "mono_family": mono, "symbol_family": sym,
        "tiny": f(ui, 8), "small": f(ui, 9), "small_bold": f(ui, 9, "bold"),
        "body": f(ui, 10), "body_bold": f(ui, 10, "bold"),
        "h3": f(disp, 11, "bold"), "h2": f(disp, 14, "bold"), "h1": f(disp, 20, "bold"),
        "hero": f(disp, 30, "bold"), "kpi": f(disp, 20, "bold"), "giant": f(disp, 40, "bold"),
        "mono": f(mono, 11), "mono_small": f(mono, 9),
        "symbol": f(sym, 13), "symbol_big": f(sym, 20),
    }
    root.fonts = fonts
    return fonts
