"""
monitor.py  -  Phase III: IoT Automated Weather Station (AWS) simulator
=======================================================================
Experiment 5 : MULTITHREADING + exception handling + modules
    * One thread per sensor type (temperature, humidity, wind) - exactly
      like Exp 5 - running at the same time.
    * Sensors sometimes send garbage (-999, None) on purpose; this raises
      InvalidSensorValueError which is caught and reported as a FAULT.
    * Threads never touch the GUI directly. They put messages in a
      thread-safe queue.Queue and the GUI reads it every 200 ms.
Experiment 3 : the three sensor classes INHERIT from SensorThread.
"""
import queue
import random
import threading
import time
from datetime import datetime

from .config import VALID_RANGES
from .exceptions import InvalidSensorValueError
from .models import AutomatedWeatherStation


class SensorThread(threading.Thread):
    """Base sensor thread (parent class)."""
    sensor = "generic"
    unit = ""
    range_key = "temperature"

    def __init__(self, network, interval=1.2):
        super().__init__(daemon=True, name=f"{self.sensor}-sensor")
        self.network = network
        self.interval = interval

    def read(self, state):                      # overridden by children
        raise NotImplementedError

    def validate(self, value):
        low, high = VALID_RANGES[self.range_key]
        if value is None or not (low <= value <= high):
            raise InvalidSensorValueError(self.sensor, value, (low, high))
        return value

    def run(self):
        while not self.network.stop_event.is_set():
            for country, state in list(self.network.states.items()):
                try:
                    if random.random() < self.network.fault_rate:
                        raw = random.choice([None, -999.0, 999.0])      # simulated hardware fault
                    else:
                        raw = self.read(state)
                    value = self.validate(raw)
                except InvalidSensorValueError as exc:
                    self.network.post("fault", country, self.sensor, None, str(exc))
                else:
                    self.network.post("reading", country, self.sensor, round(value, 1), self.unit)
                finally:
                    self.network.counts[self.sensor] = self.network.counts.get(self.sensor, 0) + 1
            time.sleep(self.interval)


class TemperatureSensor(SensorThread):
    sensor, unit, range_key = "temperature", "\N{DEGREE SIGN}C", "temperature"

    def read(self, s):
        s["temp_drift"] = 0.85 * s["temp_drift"] + random.gauss(0, 0.45)
        spike = s.pop("spike_temp", 0.0)
        s["temp_now"] = s["temp"] + s["temp_drift"] + spike
        return s["temp_now"]


class HumiditySensor(SensorThread):
    sensor, unit, range_key = "humidity", "%", "humidity"

    def read(self, s):
        s["hum_drift"] = 0.85 * s["hum_drift"] + random.gauss(0, 1.2)
        return max(1.0, min(100.0, s["humidity"] + s["hum_drift"]))


class WindSensor(SensorThread):
    sensor, unit, range_key = "wind", "km/h", "wind_kph"

    def read(self, s):
        s["wind_drift"] = 0.8 * s["wind_drift"] + random.gauss(0, 1.5)
        gust = s.pop("spike_wind", 0.0)
        return max(0.0, s["wind"] + s["wind_drift"] + gust)


class AWSNetwork:
    """Owns the stations, the threads and the message queue."""

    def __init__(self):
        self.queue = queue.Queue()
        self.stop_event = threading.Event()
        self.threads = []
        self.states = {}
        self.stations = {}
        self.counts = {}
        self.fault_rate = 0.03

    @property
    def running(self):
        return any(t.is_alive() for t in self.threads)

    def post(self, kind, country, sensor, value, extra):
        self.queue.put({"kind": kind, "country": country, "sensor": sensor, "value": value,
                        "extra": extra, "time": datetime.now().strftime("%H:%M:%S")})

    def start(self, baselines):
        """baselines: {country: {temperature, humidity, wind_kph, longitude, timezone}}"""
        self.stop()
        self.stop_event = threading.Event()
        self.states = {}
        for country, b in baselines.items():
            self.stations[country] = AutomatedWeatherStation(country, b.get("longitude", 0.0), b.get("timezone", "UTC"))
            self.states[country] = {"temp": float(b["temperature"]), "humidity": float(b["humidity"]),
                                    "wind": float(b["wind_kph"]), "temp_drift": 0.0, "hum_drift": 0.0,
                                    "wind_drift": 0.0, "temp_now": float(b["temperature"])}
        self.threads = [TemperatureSensor(self, 1.0), HumiditySensor(self, 1.3), WindSensor(self, 1.6)]
        for t in self.threads:
            t.start()

    def stop(self):
        self.stop_event.set()
        self.threads = []

    def inject(self, country, kind):
        """Demo button: force a heat spike / gust on the next reading."""
        s = self.states.get(country)
        if not s:
            return
        if kind == "heat":
            s["spike_temp"] = max(0.0, 46.5 - s["temp"]) + random.uniform(0.5, 2.0)
            s["hum_drift"] = min(s["hum_drift"], 22.0 - s["humidity"])     # heatwaves are dry
        elif kind == "cold":
            s["spike_temp"] = min(0.0, -1.0 - s["temp"]) - random.uniform(0.5, 2.0)
        elif kind == "wind":
            s["spike_wind"] = 55 + random.uniform(0, 15)
