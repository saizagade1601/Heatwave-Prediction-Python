"""
forecaster.py  -  Phase II: AI-driven forecasting
==================================================
Predicts the next 7 / 14 / 30 days of
    * temperature  (with an 80 % confidence band)
    * humidity
    * wind speed
    * chance of rain (probability 0-100 %)
and classifies each day's heatwave risk.

Experiment 4 (abstraction + polymorphism):
    BaseForecaster (ABC)
        |- SeasonalTrendForecaster   statistics: seasonal harmonics + trend + AR(1)
        |- RandomForestForecaster    machine learning: lag features + random forest
        |- EnsembleForecaster        averages any list of forecasters
All three expose the SAME methods fit() / predict() so the Forecast Lab can
switch models with one dropdown.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LogisticRegression, Ridge

from .analyzers import HeatwaveAnalyzer, ColdwaveAnalyzer, HeatStressAnalyzer
from .exceptions import InsufficientDataError
from .models import heat_index_c
from .text_tools import short_date

Z80 = 1.2816          # z-score for an 80 % interval
YEAR = 365.25


def seasonal_features(dates, origin):
    """Columns: trend (years), sin/cos of the yearly cycle (2 harmonics)."""
    dates = pd.DatetimeIndex(dates)
    t = (dates - origin).days.values / YEAR
    w = 2 * np.pi * dates.dayofyear.values / YEAR
    return np.column_stack([t, np.sin(w), np.cos(w), np.sin(2 * w), np.cos(2 * w)])


@dataclass
class Prediction:
    dates: pd.DatetimeIndex
    mean: np.ndarray
    low: np.ndarray
    high: np.ndarray


# ====================================================================== ABC
class BaseForecaster(ABC):
    name = "Base"
    short = "base"

    def __init__(self):
        self.fitted = False

    @abstractmethod
    def fit(self, series):
        """series: pd.Series indexed by daily dates."""

    @abstractmethod
    def predict(self, horizon):
        """Return a Prediction for the next `horizon` days."""

    def _check(self, series, minimum=90):
        if series is None or series.dropna().shape[0] < minimum:
            raise InsufficientDataError(f"{self.name} needs at least {minimum} days of history.")


class SeasonalTrendForecaster(BaseForecaster):
    """y = trend + yearly seasonality  (Ridge regression)
       + AR(1) memory of today's anomaly that fades day by day."""
    name = "Seasonal-Trend AR"
    short = "seasonal"

    def fit(self, series):
        self._check(series)
        s = series.astype(float)
        self.origin = s.index[0]
        self.last_date = s.index[-1]
        X = seasonal_features(s.index, self.origin)
        self.model = Ridge(alpha=1.0).fit(X, s.values)
        resid = s.values - self.model.predict(X)
        r0, r1 = resid[:-1], resid[1:]
        phi = float(np.corrcoef(r0, r1)[0, 1]) if np.std(r0) > 0 else 0.0
        self.phi = float(np.clip(phi, 0.0, 0.97))
        self.sigma = float(np.std(r1 - self.phi * r0)) or 0.5
        self.last_resid = float(np.mean(resid[-2:]))
        self.fitted = True
        return self

    def baseline(self, dates):
        return self.model.predict(seasonal_features(dates, self.origin))

    def predict(self, horizon):
        dates = pd.date_range(self.last_date + pd.Timedelta(days=1), periods=horizon, freq="D")
        k = np.arange(1, horizon + 1)
        mean = self.baseline(dates) + self.last_resid * self.phi ** k
        var = self.sigma ** 2 * np.cumsum(self.phi ** (2 * (k - 1)))
        sd = np.sqrt(var)
        return Prediction(dates, mean, mean - Z80 * sd, mean + Z80 * sd)


class RandomForestForecaster(BaseForecaster):
    """Machine-learning model: learns from the last days (lags) + season.
    Predicts one day ahead, then feeds its own prediction back in
    (recursive multi-step forecasting)."""
    name = "Random Forest (ML)"
    short = "forest"
    LAGS = (1, 2, 3, 7, 14)

    def __init__(self, n_estimators=150):
        super().__init__()
        self.n_estimators = n_estimators

    def _row(self, history, date):
        h = np.asarray(history)
        lags = [h[-lag] for lag in self.LAGS]
        roll7, roll30 = h[-7:].mean(), h[-30:].mean()
        season = seasonal_features([date], self.origin)[0, 1:]
        return np.concatenate([lags, [roll7, roll30], season])

    def fit(self, series):
        self._check(series, minimum=120)
        s = series.astype(float)
        self.origin = s.index[0]
        self.last_date = s.index[-1]
        values = s.values
        start = 30
        X = np.array([self._row(values[:i], s.index[i]) for i in range(start, len(values))])
        y = values[start:]
        self.model = RandomForestRegressor(n_estimators=self.n_estimators, max_depth=12,
                                           min_samples_leaf=3, oob_score=True,
                                           random_state=42, n_jobs=-1).fit(X, y)
        self.oob_sd = float(np.std(y - self.model.oob_prediction_))
        self.history = list(values)
        self.fitted = True
        return self

    def predict(self, horizon):
        hist = list(self.history)
        dates = pd.date_range(self.last_date + pd.Timedelta(days=1), periods=horizon, freq="D")
        means, sds = [], []
        for i, d in enumerate(dates):
            row = self._row(hist, d).reshape(1, -1)
            tree_preds = np.array([t.predict(row)[0] for t in self.model.estimators_])
            m = float(tree_preds.mean())
            sd = float(np.sqrt(tree_preds.std() ** 2 + self.oob_sd ** 2 * (1 + 0.12 * i)))
            means.append(m)
            sds.append(sd)
            hist.append(m)
        mean, sd = np.array(means), np.array(sds)
        return Prediction(dates, mean, mean - Z80 * sd, mean + Z80 * sd)


class EnsembleForecaster(BaseForecaster):
    """Composition: holds a LIST of forecasters and averages them."""
    name = "AI Ensemble"
    short = "ensemble"

    def __init__(self, members=None):
        super().__init__()
        self.members = members or [SeasonalTrendForecaster(), RandomForestForecaster()]

    def fit(self, series):
        for m in self.members:
            m.fit(series)               # polymorphism: each fits in its own way
        self.fitted = True
        return self

    def predict(self, horizon):
        preds = [m.predict(horizon) for m in self.members]
        mean = np.mean([p.mean for p in preds], axis=0)
        sd = np.sqrt(np.mean([((p.high - p.low) / (2 * Z80)) ** 2 for p in preds], axis=0))
        return Prediction(preds[0].dates, mean, mean - Z80 * sd, mean + Z80 * sd)


MODEL_CHOICES = {
    "AI Ensemble": EnsembleForecaster,
    "Random Forest (ML)": RandomForestForecaster,
    "Seasonal-Trend AR": SeasonalTrendForecaster,
}


# ========================================================== rain chance model
class RainChanceModel:
    """Logistic regression: P(rain) from season + humidity + temperature +
    how rainy the previous week was. Falls back to climatology for dry places."""

    def fit(self, daily):
        self.origin = daily.index[0]
        y = daily["rain"].values.astype(int)
        self.climate = self._climatology(daily)
        self.use_model = y.sum() >= 8 and (len(y) - y.sum()) >= 8
        if self.use_model:
            X = self._features(daily.index, daily["humidity"].values, daily["temp"].values,
                               pd.Series(y, index=daily.index).shift(1).rolling(7, min_periods=1).mean().fillna(y.mean()).values)
            self.mu, self.sd = X.mean(axis=0), X.std(axis=0) + 1e-9
            self.model = LogisticRegression(C=0.8, max_iter=600).fit((X - self.mu) / self.sd, y)
        self.recent = list(y[-7:])
        return self

    def _climatology(self, daily):
        doy = daily.index.dayofyear.values
        rain = daily["rain"].values
        table = np.zeros(367)
        for d in range(1, 367):
            diff = np.abs(doy - d)
            mask = np.minimum(diff, 366 - diff) <= 15
            table[d] = (rain[mask].sum() + 1) / (mask.sum() + 2)
        return table

    def _features(self, dates, humidity, temp, recent_frac):
        season = seasonal_features(dates, self.origin)[:, 1:]
        return np.column_stack([season, humidity, temp, recent_frac])

    def predict(self, dates, humidity, temp):
        clim = self.climate[pd.DatetimeIndex(dates).dayofyear.values]
        if not self.use_model:
            return np.clip(clim, 0.01, 0.99)
        probs, window = [], list(self.recent)
        for i, d in enumerate(dates):
            frac = np.mean(window[-7:])
            x = self._features(pd.DatetimeIndex([d]), [humidity[i]], [temp[i]], [frac])
            p = float(self.model.predict_proba((x - self.mu) / self.sd)[0, 1])
            p = 0.75 * p + 0.25 * clim[i]
            probs.append(p)
            window.append(p)
        return np.clip(np.array(probs), 0.01, 0.99)


# ================================================================= result
@dataclass
class ForecastResult:
    country: str
    model_name: str
    horizon: int
    history: pd.DataFrame
    dates: pd.DatetimeIndex
    temp: np.ndarray
    temp_low: np.ndarray
    temp_high: np.ndarray
    normal: np.ndarray
    humidity: np.ndarray
    wind: np.ndarray
    rain_prob: np.ndarray
    heat_index: list
    risk_level: list
    risk_label: list
    kind: list
    messages: list
    metrics: dict = field(default_factory=dict)
    summary: str = ""

    def table_rows(self):
        for i, d in enumerate(self.dates):
            yield (d.strftime("%Y-%m-%d"), round(float(self.temp[i]), 1), round(float(self.temp_low[i]), 1),
                   round(float(self.temp_high[i]), 1), round(float(self.humidity[i]), 0),
                   round(float(self.rain_prob[i]) * 100, 0), self.risk_label[i])


def day_kind(temp, rain_prob, humidity, wind):
    if temp <= 0 and rain_prob >= 0.4:
        return "snow"
    if rain_prob >= 0.65 and temp >= 26:
        return "storm"
    if rain_prob >= 0.5:
        return "rain"
    if wind >= 35:
        return "wind"
    if temp >= 38:
        return "heat"
    if rain_prob >= 0.3 or humidity >= 80:
        return "cloud" if humidity >= 85 else "partly"
    return "sun"


def day_message(date, t, lo, hi, rp, hum, hi_c, label):
    """One friendly sentence per forecast day (string formatting, Exp 3)."""
    parts = [f"{short_date(date)}: {t:.1f}\N{DEGREE SIGN}C (range {lo:.0f}-{hi:.0f}\N{DEGREE SIGN}C)",
             f"rain {rp:.0%}", f"humidity {hum:.0f}%"]
    if label in ("SEVERE HEATWAVE", "HEATWAVE"):
        tip = "Heatwave - avoid outdoor work 12-4 PM, drink water every 20 min"
    elif label == "HOT DAY":
        tip = "Hot day - stay hydrated, wear light cotton"
    elif label in ("COLD WAVE", "SEVERE COLD"):
        tip = "Cold wave - protect elderly and children, layer up"
    elif label == "CHILLY":
        tip = "Chilly - carry a jacket"
    elif rp >= 0.6:
        tip = "Rain likely - carry an umbrella, watch for waterlogging"
    elif hi_c is not None and hi_c >= 41:
        tip = f"Muggy - feels like {hi_c:.0f}\N{DEGREE SIGN}C"
    else:
        tip = "Comfortable conditions"
    return f"{', '.join(parts)}  ->  {tip}."


class ForecastEngine:
    """Facade used by the UI: one call builds everything for a country."""

    def __init__(self, data_manager):
        self.dm = data_manager
        self._cache = {}

    def run(self, country, horizon=14, model_name="AI Ensemble", backtest=True):
        key = (country, horizon, model_name, self.dm.db.version)
        if key in self._cache:
            return self._cache[key]
        daily = self.dm.daily(country)
        model = MODEL_CHOICES[model_name]().fit(daily["temp"])
        pred = model.predict(horizon)

        season_model = SeasonalTrendForecaster().fit(daily["temp"])
        normal = season_model.baseline(pred.dates)
        hum = np.clip(SeasonalTrendForecaster().fit(daily["humidity"]).predict(horizon).mean, 3, 100)
        wind = np.clip(SeasonalTrendForecaster().fit(daily["wind"]).predict(horizon).mean, 0, None)
        rain = RainChanceModel().fit(daily).predict(pred.dates, hum, pred.mean)

        heat_an, cold_an, stress_an = HeatwaveAnalyzer(), ColdwaveAnalyzer(), HeatStressAnalyzer()
        levels, labels, kinds, msgs, his = [], [], [], [], []
        for i, d in enumerate(pred.dates):
            reading = {"temperature": float(pred.mean[i]), "normal": float(normal[i]),
                       "humidity": float(hum[i]), "wind_kph": float(wind[i])}
            results = [heat_an.analyze(reading), cold_an.analyze(reading), stress_an.analyze(reading)]
            top = max(results[:2], key=lambda r: r.level)
            hi_c = heat_index_c(float(pred.mean[i]), float(hum[i]))
            levels.append(top.level)
            labels.append(top.label)
            kinds.append(day_kind(pred.mean[i], rain[i], hum[i], wind[i]))
            his.append(hi_c)
            msgs.append(day_message(d, pred.mean[i], pred.low[i], pred.high[i], rain[i], hum[i], hi_c, top.label))

        metrics = self.backtest(daily, model_name) if backtest else {}
        result = ForecastResult(country, model_name, horizon, daily.tail(120), pred.dates, pred.mean,
                                pred.low, pred.high, normal, hum, wind, rain, his, levels, labels, kinds, msgs,
                                metrics)
        result.summary = self.summarise(result)
        self._cache[key] = result
        return result

    @staticmethod
    def backtest(daily, model_name, holdout=30):
        """Hide the last 30 days, forecast them, and compare with reality."""
        out = {}
        try:
            train, test = daily["temp"].iloc[:-holdout], daily["temp"].iloc[-holdout:]
            for name in (model_name,) if model_name != "AI Ensemble" else tuple(MODEL_CHOICES):
                pred = MODEL_CHOICES[name]().fit(train).predict(holdout).mean
                err = pred - test.values
                out[name] = {
                    "MAE": float(np.mean(np.abs(err))),
                    "RMSE": float(np.sqrt(np.mean(err ** 2))),
                    "within3": float(np.mean(np.abs(err) <= 3.0) * 100),
                    "MAE_7d": float(np.mean(np.abs(err[:7]))),
                    "pred": pred,
                }
            out["_test"] = (test.index, test.values)
        except InsufficientDataError:
            pass
        return out

    @staticmethod
    def summarise(r):
        hot = sum(1 for lvl, lab in zip(r.risk_level, r.risk_label) if lab in ("HEATWAVE", "SEVERE HEATWAVE"))
        cold = sum(1 for lab in r.risk_label if lab in ("COLD WAVE", "SEVERE COLD"))
        peak_i = int(np.argmax(r.temp))
        low_i = int(np.argmin(r.temp))
        wet = int(np.sum(r.rain_prob >= 0.5))
        text = (f"Next {r.horizon} days in {r.country}: peak {r.temp[peak_i]:.1f}\N{DEGREE SIGN}C on "
                f"{short_date(r.dates[peak_i])}, lowest {r.temp[low_i]:.1f}\N{DEGREE SIGN}C on "
                f"{short_date(r.dates[low_i])}. ")
        if hot:
            text += f"{hot} heatwave day(s) expected - early warning issued. "
        elif cold:
            text += f"{cold} cold-wave day(s) expected. "
        else:
            text += "No heatwave expected. "
        text += f"Rain likely on {wet} day(s); average humidity {np.mean(r.humidity):.0f}%."
        return text
