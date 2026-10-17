"""
config.py  -  Central settings for the Heatwave Intelligence Dashboard
=======================================================================
Use case : KJS-CES-01  Climate Intelligence for Heatwave Monitoring,
           Prediction, and Early Warning

Exp 6 (Python Collections) is used heavily here:
    tuple  -> fixed, read-only facts (paths, column order, season months)
    dict   -> key/value settings (thresholds, season lookup)
    set    -> unique keyword groups (rain words, snow words)
    list   -> ordered things (preset countries)
"""
from pathlib import Path

# ----------------------------------------------------------------- paths --
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DB_DIR = ROOT_DIR / "database"
CSV_PATH = DATA_DIR / "V_S_DATA_SET_CLIMATE.csv"
DB_PATH = DB_DIR / "climate.db"

APP_TITLE = "HeatGuard AI  |  Heatwave Intelligence Command Center"
APP_SHORT = "HEATGUARD AI"
USE_CASE_ID = "KJS-CES-01"
USE_CASE_TITLE = "Climate Intelligence for Heatwave Monitoring, Prediction, and Early Warning"

# Student details (shown on the Project page)
STUDENT = {
    "name": "Sai Sanjay Zagade",
    "roll": "16014225105",
    "batch": "B3",
    "class": "SY B.Tech AI & DS",
    "course": "OOPL - Python (Sem III, 2026-27)",
    "college": "K. J. Somaiya School of Engineering",
}

DEFAULT_COUNTRY = "India"
MIN_RECORDS_PER_COUNTRY = 300          # countries with fewer rows are noise

# Columns that MUST exist in the CSV (tuple = fixed, read-only)
REQUIRED_COLUMNS = (
    "country", "longitude", "timezone", "last_updated", "temperature_celsius",
    "condition_text", "wind_kph", "wind_degree", "wind_direction", "precip_mm",
    "humidity", "visibility_km", "gust_mph", "air_quality_Ozone",
    "air_quality_us-epa-index",
)

# Physically valid ranges -> anything outside is a faulty sensor value
VALID_RANGES = {
    "temperature": (-60.0, 60.0),
    "humidity": (0.0, 100.0),
    "wind_kph": (0.0, 250.0),
    "precip_mm": (0.0, 500.0),
}

# --------------------------------------------------------- IMD seasons --
# India Meteorological Department uses four climatic seasons
SEASON_MONTHS = {
    "Winter": (1, 2),
    "Pre-Monsoon": (3, 4, 5),
    "Monsoon": (6, 7, 8, 9),
    "Post-Monsoon": (10, 11, 12),
}
MONTH_TO_SEASON = {m: s for s, months in SEASON_MONTHS.items() for m in months}
SEASON_ORDER = ("Winter", "Pre-Monsoon", "Monsoon", "Post-Monsoon")

# ---------------------------------------------- alert thresholds (dict) --
# These are editable live from the Alerts page.
THRESHOLDS = {
    "heat_c": 40.0,        # IMD: heatwave considered when temp >= 40 C (plains)
    "severe_heat_c": 45.0,  # IMD: heatwave regardless of normal when >= 45 C
    "cold_c": 10.0,        # IMD: cold wave considered when temp <= 10 C
    "freeze_c": 0.0,
    "wind_kph": 40.0,
    "humidity_pct": 85.0,
    "rain_mm": 7.5,        # moderate rain
    "heat_index_c": 41.0,  # 'danger' band of the heat index
}

# Keyword groups (set = unique words, fast "in" checks)
RAIN_WORDS = {"rain", "drizzle", "shower", "thunder", "storm", "sleet"}
SNOW_WORDS = {"snow", "blizzard", "ice", "freezing", "sleet"}
FOG_WORDS = {"fog", "mist", "haze"}

# Severity levels (tuple of tuples -> ordered + read-only)
SEVERITY_LEVELS = (
    (0, "Normal"),
    (1, "Watch"),
    (2, "Warning"),
    (3, "Severe"),
)

FORECAST_HORIZONS = (7, 14, 30)
