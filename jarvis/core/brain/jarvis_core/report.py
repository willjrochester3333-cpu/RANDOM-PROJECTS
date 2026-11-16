"""The house report: everything J.A.R.V.I.S. knows about right now, as plain sentences.

Small language models follow a short plain-text report far better than JSON, so this is
what goes in front of every question.
"""
import asyncio
import logging
import os
import time

import httpx

log = logging.getLogger("jarvis.report")

LAT = os.environ.get("LOCATION_LAT", "").strip()
LON = os.environ.get("LOCATION_LON", "").strip()
PLACE = os.environ.get("LOCATION_NAME", "").strip()
FORECAST_URL = os.environ.get("FORECAST_URL", "https://api.open-meteo.com/v1/forecast")
FORECAST_TTL = 1800     # seconds between forecast downloads

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
        self.fetched = 0.0
        self.http = httpx.AsyncClient(timeout=15)
        self._lock = asyncio.Lock()

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
                self.text = self._render(r.json())
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
        now = time.strftime("%Y-%m-%dT%H:00")
        start = hourly["time"].index(now) if now in hourly["time"] else 0
        hours = []
        for j in range(start, min(start + 13, len(hourly["time"])), 3):
            hours.append(f"{hourly['time'][j][11:16]} {hourly['temperature_2m'][j]:.0f} degrees "
                         f"{WEATHER_CODES.get(hourly['weather_code'][j], '')} {hourly['precipitation_probability'][j]:.0f}% rain")
        out.append("Next hours: " + "; ".join(hours) + ".")
        return " ".join(out)


def describe(snapshot: dict, history: list[dict], forecast: Forecast) -> str:
    parts = []
    parts.append("Now: " + time.strftime("%A %d %B %Y, %H:%M") + (f" in {PLACE}" if PLACE else "") + ".")

    w = snapshot.get("weather")
    if w:
        mins = w["age_s"] // 60
        when = "just now" if mins < 1 else f"{mins} minutes ago"
        stale = " This reading is old; the station may be down." if w["stale"] else ""
        parts.append(f"Outside right now, from our own weather station: {w['temp_c']:.1f} degrees C, "
                     f"{w['humidity']:.0f} percent humidity, pressure {w['pressure_hpa']:.0f} hectopascals, measured {when}.{stale}")
    else:
        parts.append("Our own weather station has not reported yet.")
    if len(history) >= 2:
        temps = [h["temp_c"] for h in history]
        lo, hi = min(temps), max(temps)
        parts.append(f"Last 24 hours: low {lo:.1f}, high {hi:.1f} degrees.")
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

    d = snapshot.get("dinner", {})
    parts.append({"idle": "Dinner has not been called.",
                  "calling": "Dinner is ready and nobody has answered yet.",
                  "acknowledged": "Dinner is ready and someone has said they are on their way."}
                 .get(d.get("state"), "Dinner: unknown."))
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
