"""
theme_rules.py  -  decides which visual theme fits a query / reading
=====================================================================
Used by both the web dashboard and the desktop (Tkinter) version.
    blaze = fire, frost = ice, gale = wind, monsoon = rain, solar = default
"""
import re


class ThemeDetector:
    """Reads an SQL query + its result and decides which theme fits."""

    TEMP_COLS = ("temp", "temperature", "max_temp", "min_temp", "avg_temp", "heat_index", "temp_pred")

    @classmethod
    def from_query(cls, sql, columns, rows):
        q = " ".join(sql.lower().split())
        cols = [c.lower() for c in columns]
        value = cls._temperature_value(cols, rows)
        mentions_temp = "temp" in q or "heat" in q

        # 0. data-changing statements: judge by the temperature values written
        if q.startswith(("insert", "update", "delete")):
            nums = [float(n) for n in re.findall(r"(?<![\w.])-?\d+\.\d+|(?<![\w.])-?\d+(?![\w.])", q)]
            temps = [n for n in nums if -60 <= n <= 60]
            verb = q.split()[0].upper()
            if q.startswith("insert") and temps and max(temps) >= 40:
                return "blaze", f"{verb} wrote a {max(temps):.1f}\N{DEGREE SIGN}C heatwave reading - fire mode"
            if q.startswith("insert") and temps and min(temps) <= 0:
                return "frost", f"{verb} wrote a {min(temps):.1f}\N{DEGREE SIGN}C reading - ice mode"
            if "temperature + " in q or "temperature+" in q:
                return "blaze", f"{verb} warmed the data - fire mode"
            return "solar", f"{verb} changed the database - dashboard refreshed"

        # 1. what the query ASKS for
        if mentions_temp and re.search(r"\bmin\s*\(", q):
            return "frost", f"Query asks for MIN temperature{cls._fmt(value)} - ice mode"
        if mentions_temp and re.search(r"\bmax\s*\(", q):
            return "blaze", f"Query asks for MAX temperature{cls._fmt(value)} - fire mode"
        tail = q.split(" from ", 1)[1] if " from " in q else q          # WHERE / GROUP / ORDER part
        if (re.search(r"order\s+by\s+\w*(temp|heat)\w*\s+asc", q) or re.search(r"temp\w*\s*(<|<=)\s*-?\d", q)
                or "snow" in q or "freez" in q):
            return "frost", f"Filtering the coldest readings{cls._fmt(value)} - ice mode"
        if (re.search(r"order\s+by\s+\w*(temp|heat)\w*\s+desc", q) or re.search(r"temp\w*\s*(>|>=)\s*\d", q)
                or "heatwave" in q):
            return "blaze", f"Filtering the hottest readings{cls._fmt(value)} - fire mode"
        agg = r"(sum|avg|max|min|count)\s*\(\s*\w*"
        if re.search(agg + r"(wind|gust)", q) or re.search(r"wind|gust", tail):
            return "gale", "Query is about wind / gusts - wind mode"
        if (re.search(agg + r"(precip|rain|humid)", q)
                or re.search(r"precip|rain|thunder|drizzle|monsoon|humid", tail)):
            return "monsoon", "Query is about rain / humidity - monsoon mode"

        # 2. what the RESULT shows
        if value is not None:
            if value >= 33:
                return "blaze", f"Result temperature is high{cls._fmt(value)} - fire mode"
            if value <= 12:
                return "frost", f"Result temperature is low{cls._fmt(value)} - ice mode"
            return "solar", f"Result temperature is moderate{cls._fmt(value)}"
        return "solar", "Neutral query - warm baseline theme"

    @classmethod
    def _temperature_value(cls, cols, rows):
        for i, c in enumerate(cols):
            if any(c == t or c.startswith(t) or t in c for t in cls.TEMP_COLS):
                vals = [r[i] for r in rows[:500] if isinstance(r[i], (int, float))]
                if vals:
                    return sum(vals) / len(vals)
        return None

    @staticmethod
    def _fmt(v):
        return "" if v is None else f" (avg {v:.1f}\N{DEGREE SIGN}C)"

    @staticmethod
    def from_temperature(temp, condition="", wind=0.0, precip=0.0):
        cond = str(condition).lower()
        if temp >= 35:
            return "blaze", f"{temp:.1f}\N{DEGREE SIGN}C - extreme heat, fire mode"
        if temp <= 8 or "snow" in cond:
            return "frost", f"{temp:.1f}\N{DEGREE SIGN}C - cold conditions, ice mode"
        if wind >= 30:
            return "gale", f"Wind {wind:.0f} km/h - wind mode"
        if precip >= 1.0 or "rain" in cond or "thunder" in cond:
            return "monsoon", f"{condition} - monsoon mode"
        return "solar", f"{temp:.1f}\N{DEGREE SIGN}C - warm baseline"
