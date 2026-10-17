"""sql_presets.py - ready-made SQLite queries for the SQL Lab (Experiment 8)."""

PRESETS = [
    ("BASICS", [
        ("All columns, first 100 rows", "SELECT * FROM weather_data LIMIT 100;"),
        ("India - latest 30 readings", "SELECT date, temperature, humidity, precip_mm, condition\nFROM weather_data\n"
                                       "WHERE country = 'India'\nORDER BY recorded_at DESC\nLIMIT 30;"),
        ("Count all readings", "SELECT COUNT(*) AS total_readings FROM weather_data;"),
        ("Distinct weather conditions", "SELECT DISTINCT condition FROM weather_data ORDER BY condition;"),
        ("Country summary (view)", "SELECT * FROM country_summary\nORDER BY avg_temp DESC\nLIMIT 20;"),
    ]),
    ("♨ HEAT  (fire theme)", [
        ("MAX temperature per country", "SELECT country, MAX(temperature) AS max_temp\nFROM weather_data\n"
                                        "GROUP BY country\nORDER BY max_temp DESC\nLIMIT 15;"),
        ("Heatwave days >= 40 C (HAVING)", "SELECT country, COUNT(*) AS heatwave_days\nFROM weather_data\n"
                                            "WHERE temperature >= 40\nGROUP BY country\nHAVING COUNT(*) > 5\n"
                                            "ORDER BY heatwave_days DESC;"),
        ("India pre-monsoon heat (BETWEEN)", "SELECT date, temperature, humidity, heat_index\nFROM weather_data\n"
                                             "WHERE country = 'India' AND season = 'Pre-Monsoon'\n"
                                             "  AND temperature BETWEEN 38 AND 50\nORDER BY temperature DESC;"),
        ("Highest feels-like (heat index)", "SELECT country, date, temperature, humidity, heat_index\n"
                                            "FROM weather_data\nORDER BY heat_index DESC\nLIMIT 20;"),
    ]),
    ("❄ COLD  (ice theme)", [
        ("MIN temperature per country", "SELECT country, MIN(temperature) AS min_temp\nFROM weather_data\n"
                                        "GROUP BY country\nORDER BY min_temp ASC\nLIMIT 15;"),
        ("Below freezing readings", "SELECT country, date, temperature, condition\nFROM weather_data\n"
                                    "WHERE temperature < 0\nORDER BY temperature ASC\nLIMIT 50;"),
        ("Snow conditions (LIKE)", "SELECT country, date, temperature, condition\nFROM weather_data\n"
                                   "WHERE condition LIKE '%snow%'\nORDER BY date DESC\nLIMIT 50;"),
    ]),
    ("≋ WIND  (wind theme)", [
        ("Windiest countries (AVG)", "SELECT country, ROUND(AVG(wind_kph), 1) AS avg_wind_kph,\n"
                                     "       MAX(gust_mph) AS max_gust_mph\nFROM weather_data\nGROUP BY country\n"
                                     "ORDER BY avg_wind_kph DESC\nLIMIT 15;"),
        ("Storm-force wind readings", "SELECT country, date, wind_kph, wind_direction\nFROM weather_data\n"
                                      "WHERE wind_kph > 60\nORDER BY wind_kph DESC;"),
    ]),
    ("☂ RAIN  (monsoon theme)", [
        ("Rainiest countries (SUM)", "SELECT country, ROUND(SUM(precip_mm), 1) AS total_rain_mm\n"
                                     "FROM weather_data\nGROUP BY country\nORDER BY total_rain_mm DESC\nLIMIT 15;"),
        ("Thunderstorms (LIKE)", "SELECT country, date, condition, precip_mm\nFROM weather_data\n"
                                 "WHERE condition LIKE '%thunder%'\nORDER BY precip_mm DESC\nLIMIT 50;"),
        ("India monthly rain", "SELECT substr(date, 1, 7) AS year_month, ROUND(SUM(precip_mm), 1) AS rain_mm\n"
                               "FROM weather_data\nWHERE country = 'India'\nGROUP BY year_month\nORDER BY year_month;"),
    ]),
    ("TRENDS", [
        ("India monthly temperature", "SELECT substr(date, 1, 7) AS year_month, ROUND(AVG(temperature), 1) AS avg_temp\n"
                                      "FROM weather_data\nWHERE country = 'India'\nGROUP BY year_month\nORDER BY year_month;"),
        ("India by IMD season (GROUP BY)", "SELECT season, ROUND(AVG(temperature), 1) AS avg_temp,\n"
                                           "       MAX(temperature) AS max_temp, COUNT(*) AS readings\n"
                                           "FROM weather_data\nWHERE country = 'India'\nGROUP BY season;"),
        ("Countries IN a list", "SELECT country, ROUND(AVG(temperature), 1) AS avg_temp\nFROM weather_data\n"
                                "WHERE country IN ('India', 'Pakistan', 'Bangladesh', 'Nepal', 'Sri Lanka')\n"
                                "GROUP BY country\nORDER BY avg_temp DESC;"),
    ]),
    ("ALERTS & FORECASTS", [
        ("Alert log", "SELECT * FROM alerts ORDER BY alert_id DESC LIMIT 100;"),
        ("Alerts per severity", "SELECT severity, COUNT(*) AS alerts FROM alerts GROUP BY severity;"),
        ("Saved AI forecasts", "SELECT * FROM forecasts ORDER BY id DESC LIMIT 60;"),
    ]),
    ("MODIFY DATA  (changes dashboard)", [
        ("INSERT a 47 C heatwave reading (demo)",
         "INSERT INTO weather_data (country, longitude, timezone, recorded_at, date, month, year,\n"
         "    season, temperature, condition, wind_kph, wind_degree, wind_direction,\n"
         "    precip_mm, humidity, visibility_km, gust_mph, ozone, aqi_index, is_rain)\n"
         "SELECT 'India', 77.2, 'Asia/Kolkata',\n"
         "       strftime('%Y-%m-%d %H:%M', MAX(recorded_at), '+1 day'),\n"
         "       date(MAX(recorded_at), '+1 day'),\n"
         "       CAST(strftime('%m', MAX(recorded_at), '+1 day') AS INTEGER),\n"
         "       CAST(strftime('%Y', MAX(recorded_at), '+1 day') AS INTEGER),\n"
         "       'Monsoon', 47.0, 'Sunny', 14.0, 300, 'WNW', 0.0, 18, 10, 12.0, 120, 3, 0\n"
         "FROM weather_data WHERE country = 'India';"),
        ("UPDATE: +2 C warming for India July 2026",
         "UPDATE weather_data\nSET temperature = temperature + 2\nWHERE country = 'India' AND date >= '2026-07-01';"),
        ("DELETE the demo rows again", "DELETE FROM weather_data\nWHERE country = 'India' AND temperature = 47.0;"),
        ("ALTER: add a column to alerts", "ALTER TABLE alerts ADD COLUMN acknowledged INTEGER DEFAULT 0;"),
    ]),
]
