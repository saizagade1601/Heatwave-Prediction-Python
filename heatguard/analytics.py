"""
analytics.py  -  Phase II analytics with Collections & Functional programming
==============================================================================
Experiment 6:
    list, tuple, set, dict          -> storing readings & results
    lambda, map(), filter(), reduce() -> processing them
The dashboard's "Insights" panel is built entirely from these functions.
"""
from collections import Counter, defaultdict
from functools import reduce

import numpy as np
import pandas as pd

from .config import SEASON_ORDER, THRESHOLDS


def functional_summary(daily, days=30):
    """Statistics of the last `days` days computed the functional way."""
    temps = list(daily["temp"].tail(days).round(1))                      # list
    humid = list(daily["humidity"].tail(days).round(0))
    rain_flags = list(daily["rain"].tail(days))

    to_f = lambda c: round(c * 9 / 5 + 32, 1)                            # lambda
    fahrenheit = list(map(to_f, temps))                                  # map()
    hot_days = list(filter(lambda t: t >= THRESHOLDS["heat_c"], temps))  # filter()
    cold_days = list(filter(lambda t: t <= THRESHOLDS["cold_c"], temps))
    total = reduce(lambda a, b: a + b, temps, 0.0)                       # reduce()
    hottest = reduce(lambda a, b: a if a >= b else b, temps)
    coldest = reduce(lambda a, b: a if a <= b else b, temps)
    rainy = reduce(lambda a, b: a + b, rain_flags, 0)

    span = (float(min(temps)), float(max(temps)))                        # tuple (immutable)
    stats = {                                                             # dict
        "days": len(temps),
        "mean_c": total / len(temps),
        "mean_f": sum(fahrenheit) / len(fahrenheit),
        "hottest_c": hottest,
        "coldest_c": coldest,
        "range": span,
        "heatwave_days": len(hot_days),
        "cold_days": len(cold_days),
        "rainy_days": int(rainy),
        "avg_humidity": sum(humid) / len(humid),
    }
    levels = set(map(lambda t: "Heatwave" if t >= 40 else "Hot" if t >= 35 else
                     "Cold" if t <= 10 else "Normal", temps))             # set (unique)
    stats["levels_seen"] = sorted(levels)
    return stats


def condition_counts(rows, top=8):
    """Counter (a dict subclass) of the most common weather conditions."""
    return Counter(rows["condition"]).most_common(top)


def seasonal_table(rows):
    """dict: season -> list of temperatures (defaultdict of lists)."""
    groups = defaultdict(list)
    for season, temp in zip(rows["season"], rows["temperature"]):
        groups[season].append(float(temp))
    return {s: groups.get(s, []) for s in SEASON_ORDER}


def monthly_matrix(daily):
    """Year x month table of average temperature (for the heat calendar)."""
    m = daily["temp"].groupby([daily.index.year, daily.index.month]).mean().unstack()
    return m.reindex(columns=range(1, 13))


def hotspots(df, days=60, top=15):
    """Hotspot identification: countries with most readings >= heat threshold."""
    cutoff = df["ts"].max() - pd.Timedelta(days=days)
    recent = df[df["ts"] >= cutoff]
    g = recent.groupby("country").agg(
        avg_temp=("temperature", "mean"), max_temp=("temperature", "max"),
        heat_days=("temperature", lambda s: int((s >= THRESHOLDS["heat_c"]).sum())))
    return g.sort_values(["heat_days", "max_temp"], ascending=False).head(top)


def coldspots(df, days=60, top=10):
    cutoff = df["ts"].max() - pd.Timedelta(days=days)
    recent = df[df["ts"] >= cutoff]
    g = recent.groupby("country").agg(avg_temp=("temperature", "mean"), min_temp=("temperature", "min"))
    return g.sort_values("avg_temp").head(top)


def correlation(rows):
    cols = {"Temp": "temperature", "Humidity": "humidity", "Wind": "wind_kph",
            "Rain": "precip_mm", "Visibility": "visibility_km", "Ozone": "ozone"}
    data = rows[list(cols.values())].astype(float)
    data.columns = list(cols)
    return data.corr().fillna(0.0)


def wind_rose_bins(rows, sectors=16):
    deg = rows["wind_degree"].astype(float).values % 360
    speed = rows["wind_kph"].astype(float).values
    width = 360 / sectors
    idx = ((deg + width / 2) // width).astype(int) % sectors
    speed_bins = [(0, 10), (10, 20), (20, 35), (35, 1000)]
    table = np.zeros((len(speed_bins), sectors))
    for k, (lo, hi) in enumerate(speed_bins):
        sel = (speed >= lo) & (speed < hi)
        table[k] = np.bincount(idx[sel], minlength=sectors)
    total = max(len(deg), 1)
    return table / total * 100, speed_bins


def heatwave_streaks(daily, threshold=None):
    """Longest run of consecutive days >= threshold (spell analysis)."""
    threshold = threshold or THRESHOLDS["heat_c"]
    hot = (daily["temp_max"] >= threshold).astype(int).values
    best = cur = 0
    for v in hot:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best
