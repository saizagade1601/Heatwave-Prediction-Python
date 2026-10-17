"""
models.py  -  Core classes of the system
=========================================
Experiment 1 : class, object, constructor, private members (__x),
               getter / setter (property), @staticmethod, @classmethod,
               getattr / setattr / hasattr
Experiment 2 : parameterized constructors + LISTS of objects
Experiment 3 : INHERITANCE  (multilevel:  Location -> WeatherStation ->
               AutomatedWeatherStation)  and super()
"""
from datetime import datetime

from .config import VALID_RANGES
from .exceptions import InvalidSensorValueError


# ===================================================================== Exp 1
class WeatherRecord:
    """One weather observation (one row of the dataset)."""

    record_count = 0                      # class variable shared by all objects

    def __init__(self, country, timestamp, temperature, humidity,
                 wind_kph=0.0, precip_mm=0.0, condition="Unknown"):
        self.country = country            # public member
        self.timestamp = timestamp
        self.condition = condition
        self.__temperature = None         # private members (name mangling)
        self.__humidity = None
        self.wind_kph = wind_kph
        self.precip_mm = precip_mm
        # go through the setters so values are validated
        self.temperature = temperature
        self.humidity = humidity
        WeatherRecord.record_count += 1

    # ---- getter / setter for a private member ----------------------------
    @property
    def temperature(self):
        return self.__temperature

    @temperature.setter
    def temperature(self, value):
        self.__temperature = self.validate("temperature", value)

    @property
    def humidity(self):
        return self.__humidity

    @humidity.setter
    def humidity(self, value):
        self.__humidity = self.validate("humidity", value)

    # ---- static method: needs no object / class data ----------------------
    @staticmethod
    def validate(sensor, value):
        low, high = VALID_RANGES[sensor]
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise InvalidSensorValueError(sensor, value, (low, high)) from None
        if not low <= value <= high:
            raise InvalidSensorValueError(sensor, value, (low, high))
        return value

    @staticmethod
    def c_to_f(celsius):
        return celsius * 9 / 5 + 32

    # ---- class method: alternative constructor ------------------------------
    @classmethod
    def from_dict(cls, row):
        return cls(
            country=row.get("country", "Unknown"),
            timestamp=row.get("recorded_at", datetime.now()),
            temperature=row.get("temperature"),
            humidity=row.get("humidity"),
            wind_kph=row.get("wind_kph", 0.0),
            precip_mm=row.get("precip_mm", 0.0),
            condition=row.get("condition", "Unknown"),
        )

    # ---- derived values --------------------------------------------------------
    @property
    def heat_index(self):
        return heat_index_c(self.temperature, self.humidity)

    def as_dict(self):
        """Uses getattr() to build a dict of all public fields (Exp 1)."""
        fields = ("country", "timestamp", "temperature", "humidity",
                  "wind_kph", "precip_mm", "condition", "heat_index")
        return {name: getattr(self, name) for name in fields if hasattr(self, name)}

    def __repr__(self):
        return (f"WeatherRecord({self.country!r}, {self.temperature:.1f}C, "
                f"{self.humidity:.0f}%)")


def heat_index_c(temp_c, humidity):
    """'Feels-like' temperature (NOAA Rothfusz regression), in Celsius."""
    if temp_c is None or humidity is None:
        return None
    if temp_c < 27:
        return float(temp_c)
    t = temp_c * 9 / 5 + 32
    rh = humidity
    hi = (-42.379 + 2.04901523 * t + 10.14333127 * rh - 0.22475541 * t * rh
          - 0.00683783 * t * t - 0.05481717 * rh * rh + 0.00122874 * t * t * rh
          + 0.00085282 * t * rh * rh - 0.00000199 * t * t * rh * rh)
    hi_c = (hi - 32) * 5 / 9
    # the regression is only valid up to ~ 60 C 'feels like'; cap absurd extrapolations
    return round(min(hi_c, temp_c + 25, 75.0), 1)


# ===================================================================== Exp 3
class Location:
    """Level 1 (parent): a place on Earth."""

    def __init__(self, country, longitude=0.0, timezone="UTC"):
        self.country = country
        self.longitude = longitude
        self.timezone = timezone

    def describe(self):
        return f"{self.country} (lon {self.longitude:.2f}, {self.timezone})"


class WeatherStation(Location):
    """Level 2 (child): a station that stores a LIST of records  (Exp 2)."""

    def __init__(self, country, longitude=0.0, timezone="UTC", station_id=None):
        super().__init__(country, longitude, timezone)        # call parent constructor
        self.station_id = station_id or f"WS-{country[:3].upper()}"
        self.records = []                                     # list of WeatherRecord objects

    # --- list operations (Exp 2) ---
    def add_record(self, record):
        self.records.append(record)

    def latest(self):
        return self.records[-1] if self.records else None

    def hottest(self, n=5):
        return sorted(self.records, key=lambda r: r.temperature, reverse=True)[:n]

    def average(self, field="temperature"):
        values = [getattr(r, field) for r in self.records]
        return sum(values) / len(values) if values else None

    def describe(self):                                       # method overriding
        return f"Station {self.station_id} - {super().describe()} - {len(self.records)} records"


class AutomatedWeatherStation(WeatherStation):
    """Level 3 (grand-child): IoT-enabled AWS (Phase III of the use case)."""

    def __init__(self, country, longitude=0.0, timezone="UTC", sensors=("temperature", "humidity", "wind")):
        super().__init__(country, longitude, timezone, station_id=f"AWS-{country[:3].upper()}")
        self.sensors = list(sensors)
        self.online = True
        self.faults = 0

    def describe(self):
        state = "ONLINE" if self.online else "OFFLINE"
        return f"{super().describe()} | IoT sensors: {', '.join(self.sensors)} | {state}"
