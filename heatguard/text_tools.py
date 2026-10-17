"""
text_tools.py  -  String handling  (Experiment 3: String Handling)
==================================================================
Cleaning and formatting text with Python string methods:
strip(), lower(), upper(), title(), replace(), split(), join(),
startswith(), f-strings, format(), slicing, repetition (*).
"""
from .config import RAIN_WORDS, SNOW_WORDS, FOG_WORDS

# Some rows of the dataset have the country written in another language.
# A dict maps those spellings to the standard English name.
COUNTRY_ALIASES = {
    "usa united states of america": "United States of America",
    "inde": "India",
    "malásia": "Malaysia",
    "mexique": "Mexico",
    "polônia": "Poland",
    "польша": "Poland",
    "marrocos": "Morocco",
    "турция": "Turkey",
    "火鸡": "Turkey",
    "südkorea": "South Korea",
    "bélgica": "Belgium",
    "turkménistan": "Turkmenistan",
    "jemen": "Yemen",
    "saudi arabien": "Saudi Arabia",
    "letonia": "Latvia",
    "estonie": "Estonia",
    "komoren": "Comoros",
    "كولومبيا": "Colombia",
    "гватемала": "Guatemala",
}


def clean_country(name):
    """'  inde ' -> 'India'.  Removes extra spaces and fixes foreign spellings."""
    if not isinstance(name, str):
        return ""
    cleaned = " ".join(name.strip().split())          # collapse double spaces
    return COUNTRY_ALIASES.get(cleaned.lower(), cleaned)


def clean_condition(text):
    """' patchy RAIN nearby ' -> 'Patchy Rain Nearby'."""
    if not isinstance(text, str):
        return "Unknown"
    return " ".join(text.strip().split()).title()


def _words(text):
    return set(str(text).lower().replace("-", " ").split())


def is_rainy(condition):
    """True when the condition text talks about rain (string search)."""
    return bool(_words(condition) & RAIN_WORDS)


def is_snowy(condition):
    return bool(_words(condition) & SNOW_WORDS)


def is_foggy(condition):
    return bool(_words(condition) & FOG_WORDS)


def condition_kind(condition, temperature=None, wind=None):
    """Map a free-text condition to one icon family used by the UI."""
    text = str(condition).lower()
    if "thunder" in text or "storm" in text:
        return "storm"
    if is_snowy(text):
        return "snow"
    if is_rainy(text):
        return "rain"
    if is_foggy(text):
        return "fog"
    if wind is not None and wind >= 35:
        return "wind"
    if "overcast" in text or text.startswith("cloudy"):
        return "cloud"
    if "partly" in text:
        return "partly"
    return "sun"


def banner(title, width=60, char="="):
    """Repetition + centering: '==== TITLE ===='."""
    return f" {title.upper()} ".center(width, char)


def format_temp(value, unit="C"):
    return "--" if value is None else f"{value:.1f}\N{DEGREE SIGN}{unit}"


def short_date(ts):
    """Timestamp -> 'Thu 16 Jul'."""
    return ts.strftime("%a %d %b")


def slugify(text):
    """'Heat Wave Alert!' -> 'heat_wave_alert'  (used for file names)."""
    keep = [ch.lower() if ch.isalnum() else "_" for ch in text.strip()]
    return "_".join(part for part in "".join(keep).split("_") if part)


def sql_keyword_list():
    """Words highlighted in the SQL editor."""
    words = """select from where and or not in between like is null order by asc desc
    group having limit offset distinct count avg min max sum as insert into values
    update set delete create table drop alter add column view index join left inner
    on case when then else end round strftime date cast real integer text primary key
    autoincrement if exists union all"""
    return set(words.split())
