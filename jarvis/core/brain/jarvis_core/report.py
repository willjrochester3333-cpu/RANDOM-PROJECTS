"""The house report: everything J.A.R.V.I.S. knows about right now, as plain sentences.

Small language models follow a short plain-text report far better than JSON, so this is
what goes in front of every question.
"""
import asyncio
import logging
import os
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

log = logging.getLogger("jarvis.report")


LAT = os.environ.get("LOCATION_LAT", "").strip()
LON = os.environ.get("LOCATION_LON", "").strip()
PLACE = os.environ.get("LOCATION_NAME", "").strip()
FORECAST_URL = os.environ.get("FORECAST_URL", "https://api.open-meteo.com/v1/forecast")
FORECAST_TTL = 1800     # seconds between forecast downloads

try:
    ZONE = ZoneInfo(os.environ.get("TZ", "").strip() or "UTC")
except (ZoneInfoNotFoundError, ValueError):
    log.warning("unknown time zone %r, using UTC", os.environ.get("TZ"))
    ZONE = ZoneInfo("UTC")


def now() -> datetime:
    return datetime.now(ZONE)


def clock_text() -> str:
    return now().strftime("%A %d %B %Y, %H:%M")


# Only the parts of the report that matter for the question are sent: on a Pi, every word the
# model has to read before answering costs time.
TOPICS = {
    "weather": r"weather|rain|sun|cloud|cold|hot|warm|chilly|temp|degree|outside|forecast|umbrella|coat|"
               r"jacket|wind|snow|frost|ice|icy|storm|humid|pressure|tomorrow|tonight|today|week|dark|"
               r"light|dawn|dusk|sunrise|sunset|wear|walk|garden|wash|dry",
    "dinner": r"dinner|food|eat|tea|kitchen|ready|hungry|meal|lunch|supper",
    "devices": r"device|online|offline|camera|station|sensor|status|working|broken|system|house|home|"
               r"pi|server|beacon|console|kitchen|outpost|everything",
}

WEATHER_CODES = {
    0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "freezing fog",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 56: "freezing drizzle", 57: "freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains", 80: "showers", 81: "showers",
    82: "heavy showers", 85: "snow showers", 86: "snow showers", 95: "thunderstorms",
    96: "thunderstorms with hail", 99: "thunderstorms with hail",
}


class Forecast:
    """Fetches a 3-day forecast from Open-Meteo (free, no key) and keeps it for half an hour."""

    def __init__(self):
        self.enabled = bool(LAT and LON)
        self.text = ""
        self.days: list[dict] = []       # today, tomorrow, the day after: for instant answers
        self.sunrise = self.sunset = ""
        self.fetched = 0.0
        self.http = httpx.AsyncClient(timeout=15)
        self._lock = asyncio.Lock()

    async def run(self) -> None:
        """Keep the forecast fresh in the background, so no question ever waits for it."""
        while self.enabled:
            await self.refresh()
            await asyncio.sleep(60)

    async def refresh(self) -> None:
        if not self.enabled or time.time() - self.fetched < FORECAST_TTL:
            return
        async with self._lock:
            if time.time() - self.fetched < FORECAST_TTL:
                return
            try:
                r = await self.http.get(FORECAST_URL, params={
                    "latitude": LAT, "longitude": LON, "timezone": "auto", "forecast_days": 3,
                    "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
                    "hourly": "temperature_2m,precipitation_probability,weather_code",
                })
                r.raise_for_status()
                data = r.json()
                self.text = self._render(data)
                daily = data["daily"]
                self.days = [{"desc": WEATHER_CODES.get(daily["weather_code"][i], "mixed"),
                              "high": daily["temperature_2m_max"][i], "low": daily["temperature_2m_min"][i],
                              "rain": daily["precipitation_probability_max"][i]} for i in range(len(daily["time"]))]
                self.sunrise, self.sunset = daily["sunrise"][0][11:16], daily["sunset"][0][11:16]
                self.fetched = time.time()
                log.info("forecast updated")
            except (httpx.HTTPError, KeyError, ValueError, IndexError) as e:
                log.warning("forecast unavailable: %s", e)
                self.fetched = time.time() - FORECAST_TTL + 300     # try again in 5 minutes

    @staticmethod
    def _render(d: dict) -> str:
        daily, hourly = d["daily"], d["hourly"]
        names = ["Today", "Tomorrow", "The day after"]
        out = []
        for i, name in enumerate(names[:len(daily["time"])]):
            out.append(f"{name}: {WEATHER_CODES.get(daily['weather_code'][i], 'mixed')}, high {daily['temperature_2m_max'][i]:.0f}, "
                       f"low {daily['temperature_2m_min'][i]:.0f} degrees, {daily['precipitation_probability_max'][i]:.0f} percent chance of rain.")
        out.append(f"Sunrise {daily['sunrise'][0][11:16]}, sunset {daily['sunset'][0][11:16]}.")
        # the next 12 hours, every 3 hours, from the current hour
        hour = now().strftime("%Y-%m-%dT%H:00")
        start = hourly["time"].index(hour) if hour in hourly["time"] else 0
        hours = []
        for j in range(start, min(start + 13, len(hourly["time"])), 3):
            hours.append(f"{hourly['time'][j][11:16]} {hourly['temperature_2m'][j]:.0f} degrees "
                         f"{WEATHER_CODES.get(hourly['weather_code'][j], '')} {hourly['precipitation_probability'][j]:.0f}% rain")
        out.append("Next hours: " + "; ".join(hours) + ".")
        return " ".join(out)


def topics(question: str) -> set[str]:
    """Which parts of the report a question needs. An empty question gets everything."""
    q = question.lower()
    if not q.strip():
        return set(TOPICS)
    return {name for name, pattern in TOPICS.items() if re.search(rf"\b({pattern})", q)}


def base(snapshot: dict, clock: str) -> str:
    """The part of the report every question gets: when and where it is, the temperature
    outside, and dinner if it has been called. It doesn't depend on the question, so the model
    can read it while the question is still being asked."""
    parts = ["Now: " + clock + (f" in {PLACE}" if PLACE else "") + "."]
    w = snapshot.get("weather")
    if w and not w["stale"]:
        parts.append(f"Outside: {w['temp_c']:.0f} degrees.")
    d = snapshot.get("dinner", {})
    if d.get("state") in ("calling", "acknowledged"):
        parts.append(_DINNER[d["state"]])
    return " ".join(parts)


_DINNER = {"idle": "Dinner has not been called.",
           "calling": "Dinner is ready and nobody has answered yet.",
           "acknowledged": "Dinner is ready and someone has said they are on their way."}


def details(snapshot: dict, history: list[dict], forecast: Forecast, question: str = "") -> str:
    """The parts of the report a question needs on top of the base: the full weather for a
    weather question, dinner for a dinner question, devices for a question about devices."""
    want = topics(question)
    parts = []
    w = snapshot.get("weather")
    if "weather" in want:
        if w:
            mins = w["age_s"] // 60
            when = "just now" if mins < 1 else f"{mins} minutes ago"
            stale = " This reading is old; the station may be down." if w["stale"] else ""
            parts.append(f"Our weather station: {w['temp_c']:.1f} degrees C, {w['humidity']:.0f} percent "
                         f"humidity, pressure {w['pressure_hpa']:.0f} hectopascals, measured {when}.{stale}")
        else:
            parts.append("Our own weather station has not reported yet.")
        if len(history) >= 2:
            temps = [h["temp_c"] for h in history]
            parts.append(f"Last 24 hours: low {min(temps):.1f}, high {max(temps):.1f} degrees.")
            now_ts = history[-1]["ts"]
            earlier = [h for h in history if now_ts - h["ts"] >= 3 * 3600]
            if earlier:
                change = history[-1]["pressure_hpa"] - earlier[-1]["pressure_hpa"]
                if change <= -1.5:
                    parts.append(f"Pressure falling ({change:+.1f} hPa in 3 hours): rain or wind more likely.")
                elif change >= 1.5:
                    parts.append(f"Pressure rising ({change:+.1f} hPa in 3 hours): settling weather.")
                else:
                    parts.append("Pressure steady.")
        if forecast.enabled:
            parts.append("Forecast: " + (forecast.text or "not available right now."))
        else:
            parts.append("No forecast is set up (LOCATION_LAT and LOCATION_LON are empty).")
    state = snapshot.get("dinner", {}).get("state")
    if "dinner" in want and state not in ("calling", "acknowledged"):      # those are in the base
        parts.append(_DINNER.get(state, "Dinner: unknown."))
    if "devices" in want:
        nodes = snapshot.get("nodes", {})
        on = sorted(n for n, s in nodes.items() if s.get("online"))
        off = sorted(n for n, s in nodes.items() if not s.get("online"))
        if on:
            parts.append("Devices online: " + ", ".join(on) + ".")
        if off:
            parts.append("Devices offline: " + ", ".join(off) + ".")
        if snapshot.get("cameras"):
            parts.append("A live camera is showing on the dashboard.")
    return " ".join(parts)


def describe(snapshot: dict, history: list[dict], forecast: Forecast, question: str = "") -> str:
    """The whole report for a question (an empty question gets everything)."""
    extra = details(snapshot, history, forecast, question)
    return base(snapshot, clock_text()) + (f" {extra}" if extra else "")
