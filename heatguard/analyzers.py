"""
analyzers.py  -  Abstract classes & polymorphism  (Experiment 4)
================================================================
ClimateAnalyzer is an ABSTRACT base class. Each child class gives its
own version of analyze(). The dashboard just loops over a list of
analyzers and calls analyze() on each one -> POLYMORPHISM.

Severity rules are inspired by IMD heatwave / cold-wave criteria:
  * Heatwave    : temp >= 40 C and departure from normal >= 4.5 C,
                  or temp >= 45 C
  * Severe heat : temp >= 40 C and departure >= 6.5 C, or temp >= 47 C
  * Cold wave   : temp <= 10 C and departure <= -4.5 C
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .config import THRESHOLDS
from .models import heat_index_c


@dataclass
class AnalysisResult:
    analyzer: str
    level: int          # 0 Normal, 1 Watch, 2 Warning, 3 Severe
    label: str
    message: str
    icon: str = "sun"

    @property
    def is_alert(self):
        return self.level >= 2


class ClimateAnalyzer(ABC):
    """Abstract base: every analyzer MUST implement analyze()."""

    name = "Analyzer"
    icon = "sun"

    def __init__(self, thresholds=None):
        self.thresholds = thresholds if thresholds is not None else THRESHOLDS

    @abstractmethod
    def analyze(self, reading):
        """reading is a dict with temperature, humidity, wind_kph, precip_mm,
        normal (seasonal normal temperature, optional)."""

    def result(self, level, label, message):
        return AnalysisResult(self.name, level, label, message, self.icon)


class HeatwaveAnalyzer(ClimateAnalyzer):
    name = "Heatwave"
    icon = "heat"

    def analyze(self, reading):
        t = reading.get("temperature")
        normal = reading.get("normal")
        dep = None if normal is None else t - normal
        heat = self.thresholds["heat_c"]
        severe = self.thresholds["severe_heat_c"]
        dep_txt = "" if dep is None else f" ({dep:+.1f}\N{DEGREE SIGN}C vs normal)"
        if t >= severe + 2 or (t >= heat and dep is not None and dep >= 6.5):
            return self.result(3, "SEVERE HEATWAVE", f"{t:.1f}\N{DEGREE SIGN}C{dep_txt}. Extreme heat - stay indoors 12-4 PM.")
        if t >= severe or (t >= heat and dep is not None and dep >= 4.5):
            return self.result(2, "HEATWAVE", f"{t:.1f}\N{DEGREE SIGN}C{dep_txt}. Heatwave conditions.")
        if t >= heat - 3:
            return self.result(1, "HOT DAY", f"{t:.1f}\N{DEGREE SIGN}C{dep_txt}. Close to heatwave level.")
        return self.result(0, "NORMAL", f"{t:.1f}\N{DEGREE SIGN}C{dep_txt}.")


class ColdwaveAnalyzer(ClimateAnalyzer):
    name = "Cold Wave"
    icon = "snow"

    def analyze(self, reading):
        t = reading.get("temperature")
        normal = reading.get("normal")
        dep = None if normal is None else t - normal
        cold = self.thresholds["cold_c"]
        if t <= self.thresholds["freeze_c"] - 5:
            return self.result(3, "SEVERE COLD", f"{t:.1f}\N{DEGREE SIGN}C - deep freeze, frostbite risk.")
        if t <= self.thresholds["freeze_c"] or (t <= cold and dep is not None and dep <= -4.5):
            return self.result(2, "COLD WAVE", f"{t:.1f}\N{DEGREE SIGN}C - cold wave conditions.")
        if t <= cold:
            return self.result(1, "CHILLY", f"{t:.1f}\N{DEGREE SIGN}C - cold, dress warmly.")
        return self.result(0, "NORMAL", f"{t:.1f}\N{DEGREE SIGN}C - no cold stress.")


class HeatStressAnalyzer(ClimateAnalyzer):
    """Combines temperature + humidity into the heat index (feels-like)."""
    name = "Heat Stress"
    icon = "drop"

    def analyze(self, reading):
        hi = heat_index_c(reading.get("temperature"), reading.get("humidity"))
        limit = self.thresholds["heat_index_c"]
        if hi >= limit + 13:
            return self.result(3, "EXTREME DANGER", f"Feels like {hi:.0f}\N{DEGREE SIGN}C - heat stroke likely.")
        if hi >= limit:
            return self.result(2, "DANGER", f"Feels like {hi:.0f}\N{DEGREE SIGN}C - heat cramps / exhaustion likely.")
        if hi >= 32:
            return self.result(1, "CAUTION", f"Feels like {hi:.0f}\N{DEGREE SIGN}C - fatigue with long exposure.")
        return self.result(0, "COMFORT", f"Feels like {hi:.0f}\N{DEGREE SIGN}C.")


class WindAnalyzer(ClimateAnalyzer):
    name = "Wind"
    icon = "wind"

    def analyze(self, reading):
        w = reading.get("wind_kph", 0.0) or 0.0
        limit = self.thresholds["wind_kph"]
        if w >= limit * 1.5:
            return self.result(3, "STORM WINDS", f"{w:.0f} km/h - damaging gusts possible.")
        if w >= limit:
            return self.result(2, "HIGH WIND", f"{w:.0f} km/h - secure loose objects.")
        if w >= limit * 0.6:
            return self.result(1, "BREEZY", f"{w:.0f} km/h - breezy.")
        return self.result(0, "CALM", f"{w:.0f} km/h.")


class RainAnalyzer(ClimateAnalyzer):
    name = "Rain"
    icon = "rain"

    def analyze(self, reading):
        p = reading.get("precip_mm", 0.0) or 0.0
        prob = reading.get("rain_prob")
        limit = self.thresholds["rain_mm"]
        if p >= limit * 4:
            return self.result(3, "HEAVY RAIN", f"{p:.1f} mm - flooding risk.")
        if p >= limit or (prob is not None and prob >= 0.8):
            extra = f"{p:.1f} mm" if prob is None else f"{prob:.0%} chance"
            return self.result(2, "RAIN WARNING", f"{extra} - carry rain protection.")
        if p > 0.2 or (prob is not None and prob >= 0.5):
            extra = f"{p:.1f} mm" if prob is None else f"{prob:.0%} chance"
            return self.result(1, "SHOWERS", f"{extra} - light showers.")
        extra = f"{p:.1f} mm" if prob is None else f"{prob:.0%} chance"
        return self.result(0, "DRY", f"{extra}.")


def default_analyzers(thresholds=None):
    """A LIST of different objects that share one interface."""
    return [HeatwaveAnalyzer(thresholds), HeatStressAnalyzer(thresholds),
            ColdwaveAnalyzer(thresholds), WindAnalyzer(thresholds), RainAnalyzer(thresholds)]


def run_all(reading, analyzers=None):
    """Polymorphism: same call, different behaviour for each object."""
    analyzers = analyzers or default_analyzers()
    return [a.analyze(reading) for a in analyzers]
