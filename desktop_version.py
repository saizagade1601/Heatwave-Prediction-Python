"""
HeatGuard AI - Heatwave Intelligence Dashboard
==============================================
Python mini project  |  Use case KJS-CES-01
Climate Intelligence for Heatwave Monitoring, Prediction, and Early Warning

Sai Sanjay Zagade  |  Roll No. 16014225105  |  SY B.Tech AI & DS (Batch B3)

OPTIONAL DESKTOP VERSION (Experiment 7 - Tkinter Canvas)
The main project is the WEB dashboard: double-click START_DASHBOARD.bat
(or run  python server.py) and it opens on http://localhost:5000.
This file opens the same project as a Tkinter desktop window instead:
    python desktop_version.py
"""
import sys


def enable_high_dpi():
    """Sharp text on Windows laptops with 125% / 150% display scaling."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:          # noqa: BLE001 - older Windows versions
            pass


def check_requirements():
    missing = []
    for module in ("pandas", "numpy", "matplotlib", "sklearn"):
        try:
            __import__(module)
        except ImportError:
            missing.append("scikit-learn" if module == "sklearn" else module)
    if missing:
        print("\n  Missing libraries: " + ", ".join(missing))
        print("  Install them with:\n\n      pip install -r requirements.txt\n")
        sys.exit(1)
    try:
        import tkinter  # noqa: F401
    except ImportError:
        print("\n  Tkinter is not available in this Python installation.")
        print("  Re-install Python from python.org and tick 'tcl/tk and IDLE'.\n")
        sys.exit(1)


if __name__ == "__main__":
    check_requirements()
    enable_high_dpi()
    from heatguard.ui.app import HeatGuardApp

    app = HeatGuardApp()
    app.mainloop()
