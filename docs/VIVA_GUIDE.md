# HeatGuard AI: Viva Guide

## 1. The problem (30-second pitch)
Heatwaves are becoming more frequent and more dangerous. The use case **KJS-CES-01** asks for a system that
**monitors** temperature, **predicts** heatwaves, and **warns** people early. HeatGuard AI does this in Python.
It stores 155k real weather readings from 211 countries in **SQLite**, analyses them, forecasts the next 7-30 days
with **machine learning**, and shows everything on a **web dashboard at http://localhost:5000** with pop-up early
warnings and a theme that changes with the data.

## 2. Architecture (front end + back end)
```
 BROWSER (front end)                         PYTHON (back end)
 web/index.html  +  app.js  +  charts.js      server.py  (Flask web server)
   pages, themes, pop-ups, D3 charts  <──JSON──  /api/overview  /api/forecast  /api/sql ...
                                                 │
                                                 ▼
                       heatguard package: data_manager → SQLite climate.db → pandas
                                          analyzers (ABC) · analytics · forecaster (ML)
                                          monitor.py: 3 sensor threads → queue
```
* **Back end** = `server.py` (Flask REST API) + the `heatguard/` package (data, database, models, AI, threads).
* **Front end** = `web/` (HTML + CSS + JavaScript). D3 draws the charts. It is bundled, so it works offline.
* The browser asks the server for data with `fetch("/api/...")`, and the server answers in **JSON**.
* The server always reads from the **database**. That is why an `INSERT` in the SQL Lab changes every page.
* `START_DASHBOARD.bat` starts the server with **pythonw** (Python without a console window) and opens the browser.

## 3. Use-case phases → code
| Phase | In the project |
|---|---|
| I Data acquisition | `data_manager.py` cleans the CSV: fixes country spellings (e.g. "Inde"→India), drops impossible values and duplicates, adds season, heat index and rain flag, then stores it in SQLite. |
| II Analytics & prediction | `analytics.py` (seasonal, hotspots, correlation) and `forecaster.py` (temperature, humidity, wind and rain-chance models). |
| III IoT AWS | `monitor.py` runs simulated Automated Weather Stations, with one **thread** per sensor. |
| IV Validation | `ForecastEngine.backtest()` hides the last 30 days, predicts them and reports MAE / RMSE / accuracy. |
| V Advisory & warning | `advisories.py` gives advice to 4 stakeholder groups. Toasts and modal pop-ups show the warnings, and the `alerts` table logs them. |

## 4. How the forecast works (simple words)
1. **Seasonal-Trend AR model:** learns the yearly temperature cycle (sine/cosine waves) plus a slow trend, using
   Ridge regression. Today's "extra" heat (the anomaly) fades a little each day; this is the AR(1) part.
2. **Random Forest model:** looks at the last 1, 2, 3, 7 and 14 days and the time of year, and predicts tomorrow.
   It then feeds that prediction back in to predict the next day, and so on (recursive forecasting).
3. **AI Ensemble:** the average of both. Averaging usually reduces error.
4. **Rain chance:** **Logistic regression** uses the season, humidity, temperature and how rainy the last week was,
   and gives a probability from 0 to 100 %.
5. **Confidence band:** an 80 % range that widens further into the future, because uncertainty grows.
6. **Heatwave label (IMD-inspired):** a day counts as a heatwave if T ≥ 40 °C and it is ≥ 4.5 °C above the seasonal
   normal, or if T ≥ 45 °C. It is severe if the departure is ≥ 6.5 °C or T ≥ 47 °C. A cold wave is T ≤ 10 °C and 4.5 °C below normal.
7. **Heat index:** the "feels like" temperature from temperature + humidity (NOAA Rothfusz formula).

## 5. Experiments used
| Exp | Concept | Where to point in the code |
|---|---|---|
| 1 | Class, object, private members, getter/setter, static & class methods, getattr/hasattr | `models.py → WeatherRecord` |
| 2 | Constructors, lists of objects | `models.py → WeatherStation.records`, `hottest()`, `average()` |
| 3 | String handling, multilevel inheritance, `super()` | `text_tools.py`, `Location → WeatherStation → AutomatedWeatherStation` |
| 4 | Abstract class + polymorphism | `analyzers.py → ClimateAnalyzer(ABC)`, `forecaster.py → BaseForecaster(ABC)` |
| 5 | Exceptions, modules, multithreading | `exceptions.py`, `monitor.py` sensor threads, `app.run_bg()` background jobs |
| 6 | list/tuple/set/dict, lambda/map/filter/reduce | `analytics.functional_summary()`, `config.py` |
| 7 | GUI + Canvas drawing | web GUI: canvas particle banner, SVG dial and icons (`web/static`); a full Tkinter Canvas version is in `desktop_version.py` + `heatguard/ui/` |
| 8 | SQLite database | `database.py`, SQL Lab page |

## 6. Likely viva questions
**Q: Why SQLite and not just pandas?**
A: SQLite gives permanent storage, real SQL (Exp 8), and lets the user change the data. pandas is used for fast
analysis after loading *from* the database.

**Q: How does the theme change according to the query?**
A: `ThemeDetector.from_query()` (in `heatguard/theme_rules.py`) reads the SQL text first: `MIN(temperature)` gives ice,
`MAX(temperature)` gives fire, wind gives wind, rain/humidity gives monsoon. If the text is neutral, it looks at the
average temperature in the result. The server sends the theme name back in the JSON. The browser then sets
`<body data-theme="blaze">`, every colour (CSS variable) fades to the new palette, and the banner particles change.

**Q: Where is polymorphism?**
A: `run_all()` calls `analyze()` on 5 different analyzer objects, and each one behaves differently. The Forecast Lab
calls `fit()` and `predict()` on whichever model you pick.

**Q: Why use threads?**
A: The sensors work at the same time (Exp 5): temperature, humidity and wind each have their own thread. They put
readings in a thread-safe `queue.Queue`. When the browser polls `/api/monitor/poll` every second, the server empties the
queue, runs the analyzers and returns new readings and alerts. Flask itself is also multi-threaded
(`threaded=True`), so a forecast can train while the live monitor keeps running.

**Q: What happens when a sensor sends a bad value?**
A: `SensorThread.validate()` raises `InvalidSensorValueError`. The thread catches it in `try/except`, reports a
FAULT in the event feed, and carries on. The program never crashes.

**Q: How accurate is the forecast?**
A: Open the Model accuracy card. The MAE is about 2-4 °C for most countries over a 30-day horizon. The readings are single
snapshots at different times of day, so some noise cannot be predicted.

**Q: What is the difference between the abstract class and the normal parent class?**
A: `ClimateAnalyzer` cannot be instantiated because it has an `@abstractmethod`, so every child *must* implement
`analyze()`. `Location` is a normal parent, so you can create its objects directly.

**Q: What does `@property` do in WeatherRecord?**
A: It turns getter/setter methods into attribute access. `rec.temperature = 99` calls the setter, which validates the
value and raises an error because 99 is outside -60…60.

**Q: How do the pop-ups work?**
A: The server returns an `alerts` list in its JSON. `toast()` in app.js slides a small card in at the bottom-right.
Severe alerts call `modal()`, a full-screen pop-up with a flashing red border and stakeholder actions. Every alert is
also inserted into the `alerts` table.

**Q: Why a web app on localhost instead of a normal window?**
A: Anyone can open it in a browser, and the Python back end is cleanly separated from the HTML/JS front end
(client-server architecture). The same back end could later be put on a real server for the whole city.

**Q: What would you add next?**
A: Live data from IMD or a weather API, the seven IMD regions on a map, an LLM that writes the advisories, and SMS
alerts.
