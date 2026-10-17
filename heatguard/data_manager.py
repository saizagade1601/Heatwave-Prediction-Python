"""
data_manager.py  -  Phase I: Data acquisition, cleaning and storage
====================================================================
Experiment 5 : exception handling (try / except / else / finally, raise)
               and modules (this file is a reusable module)

Flow:   CSV  --clean()-->  SQLite (climate.db)  --load-->  pandas DataFrame
The dashboard always reads from the DATABASE, so any INSERT / UPDATE /
DELETE you run in the SQL Lab shows up on every page.
"""
import threading

import numpy as np
import pandas as pd

from . import text_tools as tt
from .config import (CSV_PATH, DB_PATH, DB_DIR, REQUIRED_COLUMNS, VALID_RANGES,
                     MONTH_TO_SEASON, MIN_RECORDS_PER_COUNTRY)
from .database import ClimateDatabase
from .exceptions import DataUnavailableError, InsufficientDataError
from .models import heat_index_c


def parse_times(values):
    """Accepts '2026-07-25 11:15' and '2026-07-26 11:15:00' (rows typed in the SQL Lab)."""
    try:
        return pd.to_datetime(values, format="ISO8601", errors="coerce")
    except (TypeError, ValueError):             # very old pandas
        return pd.to_datetime(values, errors="coerce")


class DataManager:
    def __init__(self, csv_path=CSV_PATH, db_path=DB_PATH):
        self.csv_path = csv_path
        DB_DIR.mkdir(parents=True, exist_ok=True)
        self.db = ClimateDatabase(db_path)
        self.df = pd.DataFrame()
        self.clean_report = {}
        self._daily_cache = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------ loading --
    def prepare(self, progress=None, force_rebuild=False):
        """Make sure the database exists, then load it into memory."""
        say = progress or (lambda frac, msg: None)
        if force_rebuild or not self.db.is_ready():
            say(0.05, "Reading climate dataset (CSV)...")
            raw = self.read_csv()
            say(0.25, "Cleaning data: names, dates, invalid sensor values...")
            clean, self.clean_report = self.clean(raw)
            say(0.35, "Building SQLite database climate.db ...")
            self.db.build_from_frame(clean, progress=lambda f: say(0.35 + 0.45 * f, "Writing rows to SQLite..."))
        say(0.85, "Loading data from database...")
        self.reload()
        say(1.0, "Ready")

    def read_csv(self):
        try:
            raw = pd.read_csv(self.csv_path)
        except FileNotFoundError:
            raise DataUnavailableError(
                f"Dataset not found at {self.csv_path}. Put V_S_DATA_SET_CLIMATE.csv in the data folder.") from None
        except (pd.errors.ParserError, UnicodeDecodeError) as exc:
            raise DataUnavailableError(f"Dataset could not be read: {exc}") from exc
        missing = [c for c in REQUIRED_COLUMNS if c not in raw.columns]
        if missing:
            raise DataUnavailableError(f"Dataset is missing columns: {', '.join(missing)}")
        return raw

    @staticmethod
    def clean(raw):
        """Return (clean DataFrame, report dict)."""
        report = {"raw_rows": len(raw)}
        df = pd.DataFrame({
            "country": raw["country"].map(tt.clean_country),
            "longitude": pd.to_numeric(raw["longitude"], errors="coerce"),
            "timezone": raw["timezone"].astype(str).str.strip(),
            "ts": pd.to_datetime(raw["last_updated"], format="%d-%m-%Y %H:%M", errors="coerce"),
            "temperature": pd.to_numeric(raw["temperature_celsius"], errors="coerce"),
            "condition": raw["condition_text"].map(tt.clean_condition),
            "wind_kph": pd.to_numeric(raw["wind_kph"], errors="coerce"),
            "wind_degree": pd.to_numeric(raw["wind_degree"], errors="coerce"),
            "wind_direction": raw["wind_direction"].astype(str).str.strip().str.upper(),
            "precip_mm": pd.to_numeric(raw["precip_mm"], errors="coerce"),
            "humidity": pd.to_numeric(raw["humidity"], errors="coerce"),
            "visibility_km": pd.to_numeric(raw["visibility_km"], errors="coerce"),
            "gust_mph": pd.to_numeric(raw["gust_mph"], errors="coerce"),
            "ozone": pd.to_numeric(raw["air_quality_Ozone"], errors="coerce"),
            "aqi_index": pd.to_numeric(raw["air_quality_us-epa-index"], errors="coerce"),
        })
        before = len(df)
        df = df.dropna(subset=["ts", "temperature", "humidity", "country"])
        report["bad_dates_or_values"] = before - len(df)

        # remove physically impossible sensor values
        before = len(df)
        for col, (low, high) in VALID_RANGES.items():
            df = df[df[col].between(low, high)]
        report["out_of_range"] = before - len(df)

        # drop countries with too few rows (mostly mis-spelt duplicates)
        counts = df["country"].value_counts()
        keep = counts[counts >= MIN_RECORDS_PER_COUNTRY].index
        report["rare_country_rows"] = int((~df["country"].isin(keep)).sum())
        df = df[df["country"].isin(keep)]

        before = len(df)
        df = df.drop_duplicates(subset=["country", "ts"]).sort_values(["country", "ts"])
        report["duplicates"] = before - len(df)

        df["recorded_at"] = df["ts"].dt.strftime("%Y-%m-%d %H:%M")
        df["date"] = df["ts"].dt.strftime("%Y-%m-%d")
        df["month"] = df["ts"].dt.month.astype(int)
        df["year"] = df["ts"].dt.year.astype(int)
        df["season"] = df["month"].map(MONTH_TO_SEASON)
        df["heat_index"] = [heat_index_c(t, h) for t, h in zip(df["temperature"], df["humidity"])]
        df["is_rain"] = ((df["precip_mm"] > 0.1) | df["condition"].map(tt.is_rainy)).astype(int)
        df["wind_degree"] = df["wind_degree"].fillna(0).astype(int)
        df["aqi_index"] = df["aqi_index"].fillna(1).astype(int)
        report["clean_rows"] = len(df)
        report["countries"] = int(df["country"].nunique())
        return df.drop(columns=["ts"]).reset_index(drop=True), report

    def reload(self):
        """(Re)load the weather table from SQLite into pandas."""
        try:
            cols, rows = self.db.fetch("SELECT * FROM weather_data")
        except Exception as exc:          # table dropped / db locked etc.
            raise DataUnavailableError(
                f"Could not read weather_data from the database ({exc}). Use 'Reset database' in the SQL Lab.") from exc
        df = pd.DataFrame(rows, columns=cols)
        if df.empty:
            raise DataUnavailableError("weather_data is empty. Use 'Reset database' in the SQL Lab.")
        df["ts"] = parse_times(df["recorded_at"])
        df = df.dropna(subset=["ts", "temperature"])
        for col in ("temperature", "humidity", "wind_kph", "precip_mm", "gust_mph",
                    "visibility_km", "ozone", "heat_index", "longitude"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["humidity"] = df["humidity"].fillna(df["humidity"].median())
        df["wind_kph"] = df["wind_kph"].fillna(0.0)
        df["precip_mm"] = df["precip_mm"].fillna(0.0)
        df["is_rain"] = pd.to_numeric(df["is_rain"], errors="coerce").fillna(0).astype(int)
        df["wind_degree"] = pd.to_numeric(df["wind_degree"], errors="coerce").fillna(0)
        missing_hi = df["heat_index"].isna()
        if missing_hi.any():   # rows inserted from the SQL Lab may not have it
            df.loc[missing_hi, "heat_index"] = [heat_index_c(t, h) for t, h in
                                                zip(df.loc[missing_hi, "temperature"], df.loc[missing_hi, "humidity"])]
        with self._lock:
            self.df = df.sort_values(["country", "ts"]).reset_index(drop=True)
            self._daily_cache.clear()

    # ------------------------------------------------------------ queries --
    def countries(self):
        return sorted(self.df["country"].dropna().unique().tolist())

    def country_rows(self, country):
        rows = self.df[self.df["country"] == country]
        if rows.empty:
            raise DataUnavailableError(f"No data for '{country}'.")
        return rows

    def daily(self, country):
        """One row per calendar day (gaps filled) - used by charts & models."""
        if country in self._daily_cache:
            return self._daily_cache[country]
        rows = self.country_rows(country)
        g = rows.set_index("ts").sort_index()
        day = pd.DataFrame({
            "temp": g["temperature"].resample("D").mean(),
            "temp_max": g["temperature"].resample("D").max(),
            "temp_min": g["temperature"].resample("D").min(),
            "humidity": g["humidity"].resample("D").mean(),
            "wind": g["wind_kph"].resample("D").mean(),
            "precip": g["precip_mm"].resample("D").sum(min_count=1),
            "rain": g["is_rain"].resample("D").max(),
            "wind_degree": g["wind_degree"].resample("D").mean(),
        })
        observed = day["temp"].notna()
        num = ["temp", "temp_max", "temp_min", "humidity", "wind", "wind_degree"]
        day[num] = day[num].interpolate(limit=10).ffill().bfill()
        day["precip"] = day["precip"].fillna(0.0)
        day["rain"] = day["rain"].fillna(0).astype(int)
        day["observed"] = observed
        if len(day) < 60:
            raise InsufficientDataError(f"{country} has only {len(day)} days of data.")
        self._daily_cache[country] = day
        return day

    @staticmethod
    def seasonal_normal(daily, when, window=15):
        """Average temperature for the same time of year (+- window days)."""
        doy = daily.index.dayofyear.values
        target = pd.Timestamp(when).dayofyear
        diff = np.abs(doy - target)
        diff = np.minimum(diff, 366 - diff)
        mask = (diff <= window) & (daily.index < pd.Timestamp(when) - pd.Timedelta(days=window))
        if mask.sum() < 10:
            mask = diff <= window
        return float(daily["temp"].values[mask].mean())

    def latest(self, country):
        """Latest observation for a country as a plain dict (+ normal temp)."""
        rows = self.country_rows(country)
        last = rows.iloc[-1]
        try:
            normal = self.seasonal_normal(self.daily(country), last["ts"])
        except InsufficientDataError:
            normal = None
        rec = {k: last[k] for k in ("country", "recorded_at", "temperature", "humidity", "wind_kph",
                                    "precip_mm", "condition", "visibility_km", "gust_mph", "ozone",
                                    "aqi_index", "heat_index", "wind_direction", "longitude", "season")}
        rec["ts"] = last["ts"]
        rec["normal"] = normal
        prev = rows.iloc[-2] if len(rows) > 1 else last
        rec["temp_change"] = float(last["temperature"] - prev["temperature"])
        return rec

    def latest_snapshot(self):
        """The newest reading of every country (for global views)."""
        idx = self.df.groupby("country")["ts"].idxmax()
        return self.df.loc[idx].reset_index(drop=True)

    def recent(self, days=30):
        cutoff = self.df["ts"].max() - pd.Timedelta(days=days)
        return self.df[self.df["ts"] >= cutoff]
