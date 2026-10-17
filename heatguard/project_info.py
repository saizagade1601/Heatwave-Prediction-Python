"""project_info.py - use-case phases and experiment mapping (shown on the Project page)."""

PHASES = [
    ("I", "Data acquisition", "CSV → cleaning → SQLite climate.db", "data_manager.py, database.py"),
    ("II", "AI analytics & prediction", "seasonal analysis, hotspots, temperature / rain / humidity forecasts",
     "analytics.py, forecaster.py"),
    ("III", "IoT weather stations", "simulated AWS sensor threads stream live readings", "monitor.py"),
    ("IV", "Validation", "30-day backtest compares AI forecasts with real observations", "forecaster.py (backtest)"),
    ("V", "Advisory & early warning", "pop-up alerts + advice for citizens, farmers, health, authorities",
     "advisories.py, Alerts page"),
]

EXPERIMENTS = [
    ("1", "Classes & objects", "WeatherRecord: constructor, private __temperature, getter/setter, "
                               "@staticmethod validate(), @classmethod from_dict(), getattr/hasattr", "models.py"),
    ("2", "Constructors & lists", "WeatherStation keeps a LIST of WeatherRecord objects: append, sort, "
                                  "hottest(), average()", "models.py"),
    ("3", "Strings & inheritance", "Location → WeatherStation → AutomatedWeatherStation (multilevel); "
                                   "country / condition cleaning with strip, title, split, join, f-strings",
     "models.py, text_tools.py"),
    ("4", "Abstract classes & polymorphism", "ClimateAnalyzer(ABC) with 5 analyzers; BaseForecaster(ABC) with "
                                             "Seasonal-Trend, Random Forest and Ensemble models", "analyzers.py, forecaster.py"),
    ("5", "Exceptions, modules, threads", "custom exceptions; heatguard package of modules; 3 sensor threads + "
                                          "a multi-threaded Flask server; faulty sensor values are caught", "exceptions.py, monitor.py, server.py"),
    ("6", "Collections & functional", "list / tuple / set / dict / Counter / defaultdict; lambda, map, filter, "
                                      "reduce for the 30-day statistics", "analytics.py, config.py"),
    ("7", "GUI & Canvas drawing", "web GUI: icons, dial and the animated particle banner are drawn on a canvas; "
                                  "a full Tkinter Canvas desktop version is included too", "web/static, desktop_version.py"),
    ("8", "SQLite database", "climate.db with weather_data, alerts, forecasts + a view; the SQL Lab runs any "
                             "query and the theme reacts", "database.py, server.py (/api/sql)"),
]

DEMO = [
    "Command Center: switch region (India → Kuwait → Iceland) - the theme turns warm, fiery or icy.",
    "AI Forecast Lab: choose 14 days + AI Ensemble, read the early-warning banner, compare model accuracy.",
    "SQL Lab: run 'MAX temperature per country' (fire) then 'MIN temperature per country' (ice).",
    "SQL Lab: run 'INSERT a 47 C heatwave reading' - the dashboard reloads and a SEVERE pop-up appears.",
    "Alerts & AWS: start the monitor, press 'Heat spike' - watch threads, faults and alerts live.",
    "SQL Lab: 'Alert log' preset shows every alert that was saved to SQLite.",
]
