"""
HeatGuard AI - Web dashboard server (runs on http://localhost:5000)
===================================================================
Python mini project  |  Use case KJS-CES-01
Sai Sanjay Zagade  |  Roll No. 16014225105  |  SY B.Tech AI & DS (B3)

BACK END  : this file (Flask) + the 'heatguard' package (data, SQLite,
            OOP models, analyzers, AI forecaster, IoT threads, alerts)
FRONT END : web/index.html + web/static (HTML, CSS, JavaScript, D3 charts)

Start it by double-clicking START_DASHBOARD.bat  (no terminal needed),
or from VS Code:  python server.py
Your browser opens http://localhost:5000 automatically.
"""
import logging
import math
import os
import sys
import threading
import time
import webbrowser
from collections import deque
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# When started with pythonw.exe there is no console: write output to a log file
if sys.stdout is None or sys.stderr is None or os.environ.get("HEATGUARD_LOG"):
    log_file = open(ROOT / "server.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = log_file

try:
    from flask import Flask, jsonify, request, send_from_directory
except ImportError:
    print("Flask is missing. Run:  pip install -r requirements.txt")
    raise

import numpy as np                                                # noqa: E402
import pandas as pd                                               # noqa: E402

from heatguard import analytics as an                             # noqa: E402
from heatguard.advisories import build_advisory, STAKEHOLDERS, _ADVICE   # noqa: E402
from heatguard.analyzers import run_all                           # noqa: E402
from heatguard.config import (THRESHOLDS, DEFAULT_COUNTRY, STUDENT, USE_CASE_ID,   # noqa: E402
                              USE_CASE_TITLE)
from heatguard.data_manager import DataManager                    # noqa: E402
from heatguard.exceptions import HeatGuardError, QueryError        # noqa: E402
from heatguard.forecaster import ForecastEngine, SeasonalTrendForecaster, MODEL_CHOICES  # noqa: E402
from heatguard.monitor import AWSNetwork                          # noqa: E402
from heatguard.project_info import PHASES, EXPERIMENTS, DEMO      # noqa: E402
from heatguard.sql_presets import PRESETS                         # noqa: E402
from heatguard.theme_rules import ThemeDetector                   # noqa: E402

PORT = int(os.environ.get("HEATGUARD_PORT", "5000"))
URL = f"http://localhost:{PORT}"

app = Flask(__name__, static_folder=str(ROOT / "web" / "static"), static_url_path="/static")
logging.getLogger("werkzeug").setLevel(logging.WARNING)
app.json.sort_keys = False          # keep seasons / models in their natural order

dm = DataManager()
engine = ForecastEngine(dm)
LOCK = threading.RLock()
STATE = {"ready": False, "progress": 0.0, "message": "Starting...", "error": None}
ALERTED = set()


# ------------------------------------------------------------- helpers --
def clean(v):
    """Make numpy / pandas values JSON friendly."""
    if isinstance(v, (np.floating, float)):
        v = float(v)
        return None if math.isnan(v) or math.isinf(v) else round(v, 3)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.strftime("%Y-%m-%d %H:%M")
    if isinstance(v, np.ndarray):
        return [clean(x) for x in v.tolist()]
    if isinstance(v, (list, tuple)):
        return [clean(x) for x in v]
    if isinstance(v, dict):
        return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace")
    return v


def ok(data=None, **kw):
    payload = dict(data or {}, **kw)
    return jsonify(clean(payload))


def fail(message, code=400):
    return jsonify({"error": str(message)}), code


def dates(index):
    return [d.strftime("%Y-%m-%d") for d in pd.DatetimeIndex(index)]


def analyse_reading(rec):
    reading = {"temperature": float(rec["temperature"]), "normal": rec.get("normal"),
               "humidity": float(rec["humidity"]), "wind_kph": float(rec["wind_kph"] or 0),
               "precip_mm": float(rec["precip_mm"] or 0)}
    return run_all(reading)


def result_dict(r):
    return {"analyzer": r.analyzer, "level": r.level, "label": r.label, "message": r.message, "icon": r.icon}


def collect_alerts(country, results, temperature, source):
    """Store new level>=2 results in SQLite and return them for pop-ups."""
    out = []
    for r in results:
        if r.level < 2:
            continue
        key = (country, r.analyzer, r.label, source, round(float(temperature or 0)))
        if key in ALERTED:
            continue
        ALERTED.add(key)
        try:
            dm.db.insert_alert(country, r.analyzer, r.label, temperature, r.message, source)
        except Exception:                                       # noqa: BLE001
            pass
        item = result_dict(r)
        item.update(country=country, temperature=temperature, source=source)
        if r.level >= 3:
            adv = _ADVICE.get(r.label, _ADVICE["SEVERE HEATWAVE"])
            item["actions"] = [f"{k}: {v}" for k, v in list(adv.items())[:3]]
        out.append(item)
    return out


def boot():
    def progress(frac, msg):
        STATE.update(progress=frac, message=msg)
    try:
        dm.prepare(progress=progress)
        STATE.update(ready=True, progress=1.0, message="Ready")
        print(f"[{datetime.now():%H:%M:%S}] data ready: {len(dm.df):,} rows")
    except Exception as exc:                                    # noqa: BLE001
        STATE.update(error=str(exc), message=str(exc))
        print("BOOT ERROR:", exc)


# --------------------------------------------------------------- pages --
@app.route("/")
def index():
    return send_from_directory(ROOT / "web", "index.html")


@app.route("/api/status")
def status():
    return ok(STATE)


@app.route("/api/meta")
def meta():
    df = dm.df
    return ok(countries=dm.countries(), default_country=DEFAULT_COUNTRY, rows=len(df),
              n_countries=int(df["country"].nunique()), first=df["ts"].min(), latest=df["ts"].max(),
              thresholds=THRESHOLDS, student=STUDENT, use_case={"id": USE_CASE_ID, "title": USE_CASE_TITLE},
              clean_report=dm.clean_report, presets=[{"group": g, "items": [{"name": n, "sql": s} for n, s in items]}
                                                     for g, items in PRESETS],
              phases=PHASES, experiments=EXPERIMENTS, demo=DEMO, models=list(MODEL_CHOICES),
              stakeholders=list(STAKEHOLDERS))


@app.route("/api/startup")
def startup():
    snap = dm.latest_snapshot()
    hot = snap[snap["temperature"] >= THRESHOLDS["heat_c"]].sort_values("temperature", ascending=False)
    cold = snap[snap["temperature"] <= THRESHOLDS["freeze_c"]]
    for c, t in zip(hot["country"], hot["temperature"]):
        key = (c, "startup", round(float(t)))
        if key not in ALERTED:
            ALERTED.add(key)
            dm.db.insert_alert(c, "Heatwave", "HEATWAVE", t, "Latest reading above heatwave threshold", "startup scan")
    return ok(hot=[{"country": c, "temperature": t} for c, t in zip(hot["country"], hot["temperature"])],
              cold=[{"country": c, "temperature": t} for c, t in zip(cold["country"], cold["temperature"])],
              rows=len(dm.df), countries=int(dm.df["country"].nunique()))


@app.route("/api/overview")
def overview():
    country = request.args.get("country", DEFAULT_COUNTRY)
    try:
        with LOCK:
            rec = dm.latest(country)
            daily = dm.daily(country)
    except HeatGuardError as exc:
        return fail(exc, 404)
    results = analyse_reading(rec)
    tail = daily.tail(180)
    try:
        normal = SeasonalTrendForecaster().fit(daily["temp"]).baseline(tail.index)
    except HeatGuardError:
        normal = np.full(len(tail), np.nan)
    theme, reason = ThemeDetector.from_temperature(float(rec["temperature"]), rec["condition"],
                                                   float(rec["wind_kph"] or 0), float(rec["precip_mm"] or 0))
    alerts = collect_alerts(country, results, float(rec["temperature"]), "latest reading")
    reading = {k: rec[k] for k in ("country", "temperature", "humidity", "wind_kph", "precip_mm", "condition",
                                   "visibility_km", "gust_mph", "ozone", "aqi_index", "heat_index",
                                   "wind_direction", "longitude", "season", "normal", "temp_change")}
    reading["time"] = rec["ts"].strftime("%a %d %b %Y, %H:%M")
    return ok(reading=reading, results=[result_dict(r) for r in results],
              trend={"dates": dates(tail.index), "temp": tail["temp"].values,
                     "avg7": tail["temp"].rolling(7, min_periods=1).mean().values, "normal": normal},
              theme={"name": theme, "reason": f"{country}: {reason}"}, alerts=alerts)


def forecast_json(r):
    headline, level, advice = build_advisory(r)
    m = {k: v for k, v in r.metrics.items() if not k.startswith("_")}
    test = r.metrics.get("_test")
    hist = r.history.tail(60)
    if max(r.risk_level) >= 2 and any("HEAT" in lab for lab in r.risk_label) or np.max(r.temp) >= 35:
        theme, why = "blaze", f"forecast peak {np.max(r.temp):.1f}\N{DEGREE SIGN}C"
    elif np.min(r.temp) <= 8:
        theme, why = "frost", f"forecast low {np.min(r.temp):.1f}\N{DEGREE SIGN}C"
    elif np.mean(r.rain_prob) >= 0.5:
        theme, why = "monsoon", f"rain likely ({np.mean(r.rain_prob):.0%} average chance)"
    elif np.mean(r.wind) >= 25:
        theme, why = "gale", f"windy ({np.mean(r.wind):.0f} km/h average)"
    else:
        theme, why = "solar", "moderate forecast"
    return {
        "country": r.country, "model": r.model_name, "horizon": r.horizon,
        "dates": dates(r.dates), "temp": r.temp, "low": r.temp_low, "high": r.temp_high, "normal": r.normal,
        "humidity": r.humidity, "wind": r.wind, "rain": r.rain_prob, "heat_index": r.heat_index,
        "risk_level": r.risk_level, "risk_label": r.risk_label, "kind": r.kind, "messages": r.messages,
        "summary": r.summary, "advisory": {"headline": headline, "level": level, "advice": advice},
        "history": {"dates": dates(hist.index), "temp": hist["temp"].values},
        "metrics": {k: {"MAE": v["MAE"], "RMSE": v["RMSE"], "within3": v["within3"], "MAE_7d": v["MAE_7d"],
                        "pred": v["pred"]} for k, v in m.items()},
        "test": {"dates": dates(test[0]), "actual": test[1]} if test else None,
        "theme": {"name": theme, "reason": f"{r.country} forecast: {why}"},
    }


@app.route("/api/forecast")
def forecast():
    country = request.args.get("country", DEFAULT_COUNTRY)
    horizon = int(request.args.get("horizon", 14))
    model = request.args.get("model", "AI Ensemble")
    backtest = request.args.get("backtest", "1") == "1"
    if model not in MODEL_CHOICES or horizon not in (7, 14, 30):
        return fail("Unknown model or horizon")
    try:
        r = engine.run(country, horizon, model, backtest=backtest)
    except HeatGuardError as exc:
        return fail(exc, 404)
    data = forecast_json(r)
    alerts = []
    worst = max(r.risk_level)
    if worst >= 2:
        days = [f"{d:%a %d %b}" for d, lv in zip(r.dates, r.risk_level) if lv >= 2]
        label = r.risk_label[r.risk_level.index(worst)]
        key = (country, "forecast", tuple(days))
        if key not in ALERTED:
            ALERTED.add(key)
            dm.db.insert_alert(country, "Forecast", label, float(np.max(r.temp)),
                               f"{label} forecast for {', '.join(days)}", "AI forecast")
            alerts.append({"level": worst, "label": label, "country": country, "analyzer": "Forecast",
                           "message": f"{label.title()} expected on {', '.join(days[:4])}."})
    data["alerts"] = alerts
    return ok(data)


@app.route("/api/forecast/save", methods=["POST"])
def forecast_save():
    body = request.get_json(force=True)
    try:
        r = engine.run(body["country"], int(body["horizon"]), body["model"], backtest=False)
    except (KeyError, HeatGuardError) as exc:
        return fail(exc)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = [(now, r.country, d.strftime("%Y-%m-%d"), r.model_name, round(float(r.temp[i]), 2),
             round(float(r.temp_low[i]), 2), round(float(r.temp_high[i]), 2), round(float(r.humidity[i]), 1),
             round(float(r.rain_prob[i]) * 100, 1), r.risk_label[i]) for i, d in enumerate(r.dates)]
    dm.db.insert_forecasts(rows)
    return ok(saved=len(rows))


# ----------------------------------------------------------------- SQL --
@app.route("/api/sql", methods=["POST"])
def sql():
    body = request.get_json(force=True)
    text = (body.get("sql") or "").strip()
    country = body.get("country", DEFAULT_COUNTRY)
    try:
        with LOCK:
            res = dm.db.run_query(text)
            alerts = []
            if res.data_changed:
                dm.reload()
                try:
                    rec = dm.latest(country)
                    alerts = collect_alerts(country, analyse_reading(rec), float(rec["temperature"]),
                                            "after SQL change")
                except HeatGuardError:
                    pass
    except QueryError as exc:
        return fail(f"SQL error: {exc}")
    except HeatGuardError as exc:
        return fail(f"{exc}")
    theme, reason = ThemeDetector.from_query(res.sql, res.columns, res.rows if res.kind == "select" else [])
    return ok(columns=res.columns, rows=[list(r) for r in res.rows], kind=res.kind, rowcount=res.rowcount,
              message=res.message, truncated=res.truncated, data_changed=res.data_changed,
              theme={"name": theme, "reason": reason}, alerts=alerts, rows_total=len(dm.df),
              countries=dm.countries() if res.data_changed else None)


@app.route("/api/schema")
def schema():
    return ok(schema=dm.db.schema_overview())


@app.route("/api/reset", methods=["POST"])
def reset():
    with LOCK:
        dm.prepare(force_rebuild=True)
    return ok(rows=len(dm.df), report=dm.clean_report)


# ----------------------------------------------------------- analytics --
@app.route("/api/analytics/country")
def analytics_country():
    country = request.args.get("country", DEFAULT_COUNTRY)
    try:
        rows = dm.country_rows(country)
        daily = dm.daily(country)
    except HeatGuardError as exc:
        return fail(exc, 404)
    stats = an.functional_summary(daily, 30)
    matrix = an.monthly_matrix(daily)
    seasons = {}
    for name, vals in an.seasonal_table(rows).items():
        if vals:
            a = np.array(vals)
            q1, med, q3 = np.percentile(a, [25, 50, 75])
            sample = a if len(a) <= 400 else np.random.default_rng(1).choice(a, 400, replace=False)
            seasons[name] = {"min": a.min(), "q1": q1, "median": med, "q3": q3, "max": a.max(), "mean": a.mean(),
                             "n": len(a), "values": sample}
    rose, bins = an.wind_rose_bins(rows)
    corr = an.correlation(rows)
    rec = dm.latest(country)
    theme, reason = ThemeDetector.from_temperature(float(rec["temperature"]), rec["condition"],
                                                   float(rec["wind_kph"] or 0), float(rec["precip_mm"] or 0))
    return ok(stats=stats, streak=an.heatwave_streaks(daily), records=len(rows),
              span=f"{daily.index[0]:%b %Y} - {daily.index[-1]:%b %Y}",
              matrix={"years": [int(y) for y in matrix.index], "values": matrix.values},
              seasons=seasons, rose={"table": rose, "bins": ["< 10 km/h", "10-20", "20-35", "35+ km/h"]},
              corr={"labels": list(corr.columns), "values": corr.values},
              theme={"name": theme, "reason": f"{country}: {reason}"})


@app.route("/api/analytics/global")
def analytics_global():
    df = dm.df
    hot = an.hotspots(df)
    cold = an.coldspots(df)
    snap = dm.latest_snapshot()
    weekly = df.set_index("ts")["temperature"].resample("W").mean().dropna()
    above = int((snap["temperature"] >= THRESHOLDS["heat_c"]).sum())
    top = snap.loc[snap["temperature"].idxmax()]
    low = snap.loc[snap["temperature"].idxmin()]
    theme = ("blaze", f"Global view: {above} countries ≥ {THRESHOLDS['heat_c']:.0f}\N{DEGREE SIGN}C right now") \
        if above else ("solar", f"Global view: hottest now {top['country']} {top['temperature']:.1f}\N{DEGREE SIGN}C")
    return ok(hot=[{"country": c, "heat_days": r["heat_days"], "max_temp": r["max_temp"]} for c, r in hot.iterrows()],
              cold=[{"country": c, "avg_temp": r["avg_temp"], "min_temp": r["min_temp"]} for c, r in cold.iterrows()],
              snapshot=[{"country": c, "lon": x, "temp": t} for c, x, t in
                        zip(snap["country"], snap["longitude"], snap["temperature"])],
              weekly={"dates": dates(weekly.index), "temp": weekly.values},
              chips={"tracked": len(snap), "above": above,
                     "below": int((snap["temperature"] <= 0).sum()),
                     "hottest": f"{top['country']} {top['temperature']:.1f}\N{DEGREE SIGN}",
                     "coldest": f"{low['country']} {low['temperature']:.1f}\N{DEGREE SIGN}",
                     "hottest_t": top["temperature"], "coldest_t": low["temperature"],
                     "top_hotspot": hot.index[0] if len(hot) else "-"},
              rows=len(df), countries=int(df["country"].nunique()),
              theme={"name": theme[0], "reason": theme[1]})


# ---------------------------------------------------- IoT AWS monitor --
class MonitorHub:
    """Owns the AWS sensor threads (Exp 5) and turns their messages into
    live state, an event feed and alerts for the browser."""

    def __init__(self):
        self.net = AWSNetwork()
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.live, self.streams = {}, {}
        self.events = deque(maxlen=400)
        self.seq = 0
        self.faults = self.readings = 0
        self.last_alert = {}
        self.pending_alerts = []

    def event(self, text, kind="ok"):
        self.seq += 1
        self.events.append({"id": self.seq, "text": text, "kind": kind})

    def start(self, countries):
        base = {}
        for c in countries[:6]:
            try:
                base[c] = dm.latest(c)
            except HeatGuardError:
                continue
        if not base:
            raise HeatGuardError("Pick at least one valid country")
        with self.lock:
            self.reset()
            self.live = {c: {} for c in base}
            self.streams = {c: [] for c in base}
            self.net.start(base)
            self.event(f"[system] started {len(self.net.threads)} sensor threads for: {', '.join(base)}", "info")
            for st in self.net.stations.values():
                self.event(f"[station] {st.describe()}", "info")

    def stop(self):
        with self.lock:
            self.net.stop()
            self.event("[system] monitor stopped - threads asked to exit", "info")

    def process(self):
        with self.lock:
            for _ in range(500):
                try:
                    m = self.net.queue.get_nowait()
                except Exception:                                 # queue.Empty
                    break
                self._handle(m)

    def _handle(self, m):
        c = m["country"]
        if m["kind"] == "fault":
            self.faults += 1
            self.event(f"{m['time']}  FAULT  {c:<14} {m['extra']}  -> InvalidSensorValueError caught", "fault")
            self.live.setdefault(c, {})["fault"] = m["time"]
            return
        self.readings += 1
        key = {"temperature": "temperature", "humidity": "humidity", "wind": "wind_kph"}[m["sensor"]]
        state = self.live.setdefault(c, {})
        state[key] = m["value"]
        if m["sensor"] == "temperature":
            self.streams.setdefault(c, []).append(m["value"])
            self.streams[c] = self.streams[c][-80:]
            self.event(f"{m['time']}  read   {c:<14} temperature {m['value']:>6.1f} \N{DEGREE SIGN}C")
        if {"temperature", "humidity", "wind_kph"} <= state.keys():
            results = run_all({"temperature": state["temperature"], "humidity": state["humidity"],
                               "wind_kph": state["wind_kph"], "precip_mm": 0.0})
            state["level"] = max(r.level for r in results)
            state["status"] = max(results, key=lambda r: r.level).label
            for r in results:
                if r.level < 2:
                    continue
                k = (c, r.label)
                if k in self.last_alert and time.monotonic() - self.last_alert[k] < 45:
                    continue
                self.last_alert[k] = time.monotonic()
                self.event(f"{m['time']}  ALERT  {c:<14} {r.label}: {r.message}", "alert")
                dm.db.insert_alert(c, r.analyzer, r.label, state["temperature"], r.message, "AWS sensor")
                item = result_dict(r)
                item.update(country=c, temperature=state["temperature"], source="AWS sensor")
                if r.level >= 3:
                    adv = _ADVICE.get(r.label, _ADVICE["SEVERE HEATWAVE"])
                    item["actions"] = [f"{k2}: {v}" for k2, v in list(adv.items())[:3]]
                self.pending_alerts.append(item)

    def snapshot(self, since):
        self.process()
        with self.lock:
            alerts, self.pending_alerts = self.pending_alerts, []
            return {"running": self.net.running, "events": [e for e in self.events if e["id"] > since],
                    "live": self.live, "streams": self.streams, "alerts": alerts,
                    "stats": {"threads": sum(t.is_alive() for t in self.net.threads),
                              "readings": self.readings, "faults": self.faults}}


HUB = MonitorHub()


@app.route("/api/monitor/start", methods=["POST"])
def monitor_start():
    try:
        HUB.start(request.get_json(force=True).get("countries", []))
    except HeatGuardError as exc:
        return fail(exc)
    return ok(started=True)


@app.route("/api/monitor/stop", methods=["POST"])
def monitor_stop():
    HUB.stop()
    return ok(stopped=True)


@app.route("/api/monitor/inject", methods=["POST"])
def monitor_inject():
    body = request.get_json(force=True)
    states = HUB.net.states
    if not states:
        return fail("Start the monitor first")
    target = body.get("country") if body.get("country") in states else next(iter(states))
    HUB.net.inject(target, body.get("kind", "heat"))
    HUB.event(f"[demo] injected {body.get('kind')} event into {target}", "info")
    return ok(target=target)


@app.route("/api/monitor/poll")
def monitor_poll():
    return ok(HUB.snapshot(int(request.args.get("since", 0))))


@app.route("/api/alerts")
def alerts():
    cols, rows = dm.db.recent_alerts(200)
    return ok(columns=cols, rows=[list(r) for r in rows])


@app.route("/api/scan", methods=["POST"])
def scan():
    snap = dm.latest_snapshot()
    found = []
    for _, rec in snap.iterrows():
        results = run_all({"temperature": float(rec["temperature"]), "humidity": float(rec["humidity"]),
                           "wind_kph": float(rec["wind_kph"]), "precip_mm": float(rec["precip_mm"])})
        for r in results:
            if r.level >= 2:
                dm.db.insert_alert(rec["country"], r.analyzer, r.label, float(rec["temperature"]), r.message,
                                   "data scan")
                found.append(f"{rec['country']}: {r.label} - {r.message}")
    for line in found[:60]:
        HUB.event(f"[scan]  {line}", "alert")
    return ok(count=len(found), countries=len(snap))


@app.route("/api/thresholds", methods=["POST"])
def thresholds():
    body = request.get_json(force=True)
    for k, v in body.items():
        if k in THRESHOLDS:
            try:
                THRESHOLDS[k] = float(v)
            except (TypeError, ValueError):
                pass
    return ok(thresholds=THRESHOLDS)


@app.route("/api/shutdown", methods=["POST"])
def shutdown():
    HUB.net.stop()
    threading.Timer(0.6, lambda: os._exit(0)).start()
    return ok(bye=True)


# ------------------------------------------------------------- startup --
def port_in_use(port):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


if __name__ == "__main__":
    open_browser = "--no-browser" not in sys.argv
    if port_in_use(PORT):
        # already running (e.g. double-clicked twice): just open the page
        if open_browser:
            webbrowser.open(URL)
        sys.exit(0)
    threading.Thread(target=boot, daemon=True).start()
    if open_browser:
        threading.Timer(1.2, lambda: webbrowser.open(URL)).start()
    print(f"HeatGuard AI running at {URL}  (close it with the 'Stop server' button in the dashboard)")
    app.run(host="127.0.0.1", port=PORT, debug=False, threaded=True, use_reloader=False)
