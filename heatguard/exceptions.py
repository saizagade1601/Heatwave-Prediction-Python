"""
exceptions.py  -  Custom exceptions  (Experiment 5: Exception Handling)
=====================================================================
Every error the app can expect has its own class, so the code can react
precisely (try / except / else / finally) instead of crashing.
"""


class HeatGuardError(Exception):
    """Base class for every error raised by this project."""


class DataUnavailableError(HeatGuardError):
    """Raised when the dataset / weather data cannot be found or read."""


class InvalidSensorValueError(HeatGuardError):
    """Raised when a reading is outside its physically possible range."""

    def __init__(self, sensor, value, valid_range):
        self.sensor = sensor
        self.value = value
        self.valid_range = valid_range
        low, high = valid_range
        super().__init__(f"{sensor} reading {value!r} is outside the valid range {low} .. {high}")


class InsufficientDataError(HeatGuardError):
    """Raised when there is not enough history to train a forecast model."""


class QueryError(HeatGuardError):
    """Raised when an SQL query in the SQL Lab fails."""
