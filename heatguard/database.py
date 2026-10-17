"""
database.py  -  SQLite backend  (Experiment 8: Database-driven system)
======================================================================
Tables
    weather_data : every cleaned observation from the CSV
    alerts       : alerts raised by the dashboard / AWS monitor
    forecasts    : AI forecasts saved from the Forecast Lab
View
    country_summary : one row per country (records, avg / max / min temp)

The SQL Lab page sends any query typed by the user to run_query().
"""
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime

from .exceptions import QueryError

WEATHER_COLUMNS = (
    "country", "longitude", "timezone", "recorded_at", "date", "month", "year",
    "season", "temperature", "condition", "wind_kph", "wind_degree",
    "wind_direction", "precip_mm", "humidity", "visibility_km", "gust_mph",
    "ozone", "aqi_index", "heat_index", "is_rain",
)

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS weather_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        country TEXT NOT NULL,
        longitude REAL,
        timezone TEXT,
        recorded_at TEXT,
        date TEXT,
        month INTEGER,
        year INTEGER,
        season TEXT,
        temperature REAL,
        condition TEXT,
        wind_kph REAL,
        wind_degree INTEGER,
        wind_direction TEXT,
        precip_mm REAL,
        humidity REAL,
        visibility_km REAL,
        gust_mph REAL,
        ozone REAL,
        aqi_index INTEGER,
        heat_index REAL,
        is_rain INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS alerts (
        alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT,
        country TEXT,
        alert_type TEXT,
        severity TEXT,
        temperature REAL,
        message TEXT,
        source TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS forecasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT,
        country TEXT,
        forecast_date TEXT,
        model TEXT,
        temp_pred REAL,
        temp_low REAL,
        temp_high REAL,
        humidity_pred REAL,
        rain_chance REAL,
        risk TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_weather_country ON weather_data(country)",
    "CREATE INDEX IF NOT EXISTS idx_weather_date ON weather_data(date)",
    """CREATE VIEW IF NOT EXISTS country_summary AS
        SELECT country,
               COUNT(*)                    AS records,
               ROUND(AVG(temperature), 1)  AS avg_temp,
               MAX(temperature)            AS max_temp,
               MIN(temperature)            AS min_temp,
               ROUND(AVG(humidity), 1)     AS avg_humidity,
               ROUND(SUM(precip_mm), 1)    AS total_rain_mm
        FROM weather_data GROUP BY country""",
)

DESTRUCTIVE = ("delete", "drop", "update", "alter", "insert", "replace", "create")


@dataclass
class QueryResult:
    sql: str
    columns: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    rowcount: int = 0
    kind: str = "select"          # select / modify / other
    elapsed_ms: float = 0.0
    message: str = ""
    truncated: bool = False
    data_changed: bool = False


def split_statements(script):
    """Split 'a; b; c' into statements, respecting quotes (uses sqlite3.complete_statement)."""
    statements, buf = [], ""
    for ch in script:
        buf += ch
        if ch == ";" and sqlite3.complete_statement(buf):
            if buf.strip(" ;\n\t"):
                statements.append(buf.strip())
            buf = ""
    if buf.strip(" ;\n\t"):
        statements.append(buf.strip())
    return statements


def first_word(sql):
    lines = [ln for ln in sql.strip().splitlines() if not ln.strip().startswith("--")]
    words = " ".join(lines).strip().split()
    return words[0].lower() if words else ""


class ClimateDatabase:
    MAX_ROWS = 5000

    def __init__(self, path):
        self.path = str(path)
        self.version = 0                  # increases whenever data changes

    @contextmanager
    def connect(self):
        """Open a connection, hand it out, and ALWAYS close it (finally)."""
        conn = sqlite3.connect(self.path, timeout=10)
        try:
            yield conn
        finally:
            conn.close()

    # ------------------------------------------------------------ setup --
    def create_schema(self, conn):
        cur = conn.cursor()
        for stmt in SCHEMA:
            cur.execute(stmt)
        conn.commit()

    def is_ready(self):
        try:
            with self.connect() as conn:
                n = conn.execute("SELECT COUNT(*) FROM weather_data").fetchone()[0]
                self.create_schema(conn)      # make sure alerts / forecasts exist
                return n > 0
        except sqlite3.Error:
            return False

    def build_from_frame(self, df, progress=None):
        """Create tables and insert all cleaned rows (executemany in chunks)."""
        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute("DROP VIEW IF EXISTS country_summary")
            cur.execute("DROP TABLE IF EXISTS weather_data")
            self.create_schema(conn)
            cols = ", ".join(WEATHER_COLUMNS)
            marks = ", ".join("?" for _ in WEATHER_COLUMNS)
            sql = f"INSERT INTO weather_data ({cols}) VALUES ({marks})"
            data = df[list(WEATHER_COLUMNS)].astype(object).where(df[list(WEATHER_COLUMNS)].notna(), None)
            rows = data.values.tolist()
            chunk = 10000
            for start in range(0, len(rows), chunk):
                cur.executemany(sql, rows[start:start + chunk])
                if progress:
                    progress(min(1.0, (start + chunk) / len(rows)))
            conn.commit()
        self.version += 1

    # ----------------------------------------------------------- queries --
    def run_query(self, script):
        """Run one or more SQL statements typed by the user.
        Returns the result of the LAST statement that produced rows."""
        statements = split_statements(script)
        if not statements:
            raise QueryError("The query is empty. Type some SQL first.")
        start = time.perf_counter()
        result = QueryResult(sql=script)
        changed = False
        try:
            with self.connect() as conn:
                cur = conn.cursor()
                for stmt in statements:
                    cur.execute(stmt)
                    if cur.description:                       # SELECT-like
                        rows = cur.fetchmany(self.MAX_ROWS + 1)
                        result.columns = [d[0] for d in cur.description]
                        result.truncated = len(rows) > self.MAX_ROWS
                        result.rows = rows[: self.MAX_ROWS]
                        result.rowcount = len(result.rows)
                        result.kind = "select"
                    else:
                        word = first_word(stmt)
                        if word in DESTRUCTIVE:
                            changed = True
                        result.kind = "modify"
                        result.rowcount = cur.rowcount if cur.rowcount is not None else 0
                conn.commit()
        except sqlite3.Error as exc:
            raise QueryError(str(exc)) from exc
        finally:
            result.elapsed_ms = (time.perf_counter() - start) * 1000
        if changed:
            self.version += 1
            result.data_changed = True
        if result.kind == "select":
            more = " (showing first 5000)" if result.truncated else ""
            result.message = f"{result.rowcount} row(s) returned in {result.elapsed_ms:.0f} ms{more}"
        else:
            n = max(result.rowcount, 0)
            result.message = (f"Statement executed - {n} row(s) affected in {result.elapsed_ms:.0f} ms. "
                              "Dashboard data refreshed.")
        return result

    def fetch(self, sql, params=()):
        with self.connect() as conn:
            cur = conn.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return cols, cur.fetchall()

    def schema_overview(self):
        """{table_or_view: [columns]} for the schema browser."""
        out = {}
        with self.connect() as conn:
            names = conn.execute(
                "SELECT name, type FROM sqlite_master WHERE type IN ('table','view') "
                "AND name NOT LIKE 'sqlite_%' ORDER BY type, name").fetchall()
            for name, kind in names:
                cols = [r[1] for r in conn.execute(f"PRAGMA table_info('{name}')")]
                label = f"{name}  (view)" if kind == "view" else name
                out[label] = cols
        return out

    # ------------------------------------------------- app write helpers --
    def insert_alert(self, country, alert_type, severity, temperature, message, source="dashboard"):
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO alerts (created_at, country, alert_type, severity, temperature, message, source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), country, alert_type, severity,
                 None if temperature is None else round(float(temperature), 1), message, source))
            conn.commit()

    def insert_forecasts(self, rows):
        with self.connect() as conn:
            conn.executemany(
                "INSERT INTO forecasts (created_at, country, forecast_date, model, temp_pred, temp_low, "
                "temp_high, humidity_pred, rain_chance, risk) VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
            conn.commit()

    def recent_alerts(self, limit=200):
        return self.fetch("SELECT alert_id, created_at, country, alert_type, severity, temperature, message, source "
                          "FROM alerts ORDER BY alert_id DESC LIMIT ?", (limit,))
