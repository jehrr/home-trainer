"""Погода через Open-Meteo: прогноз по часам и поиск мест по названию. Ключи не нужны."""
from __future__ import annotations

from datetime import date as date_cls, datetime, timedelta

import httpx

import config
from i18n import tr

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
MAX_FORECAST_DAYS = 16


_client = httpx.Client(timeout=20.0, transport=httpx.HTTPTransport(retries=2))


class WeatherError(Exception):
    pass


def compass(deg) -> str:
    if deg is None:
        return ""
    return tr("compass")[round(deg / 45) % 8]


def geocode(name: str, count: int = 5) -> list[dict]:
    try:
        r = _client.get(GEOCODE_URL, params={"name": name, "count": count, "language": config.LANGUAGE, "format": "json"})
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise WeatherError(tr("err_geocode", e=e)) from e
    out = []
    for g in r.json().get("results") or []:
        out.append({
            "name": g.get("name"),
            "region": ", ".join(x for x in (g.get("admin1"), g.get("country")) if x),
            "latitude": round(g["latitude"], 4),
            "longitude": round(g["longitude"], 4),
        })
    return out


def forecast(latitude: float, longitude: float, day: str, start_time: str = "08:00", hours: int = 3) -> dict:
    try:
        target_day = date_cls.fromisoformat(day)
    except ValueError as e:
        raise WeatherError(tr("err_bad_date", day=day)) from e
    today = date_cls.today()
    if target_day < today - timedelta(days=1):
        raise WeatherError(tr("err_past"))
    if target_day > today + timedelta(days=MAX_FORECAST_DAYS - 1):
        raise WeatherError(tr("err_too_far", days=MAX_FORECAST_DAYS))

    try:
        start_hour = int(start_time.split(":")[0])
    except (ValueError, AttributeError):
        start_hour = 8
    hours = max(1, min(int(hours or 3), 12))

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join([
            "temperature_2m", "apparent_temperature", "precipitation_probability", "precipitation",
            "weather_code", "wind_speed_10m", "wind_gusts_10m", "wind_direction_10m",
            "relative_humidity_2m", "uv_index",
        ]),
        "daily": "sunrise,sunset",
        "timezone": "auto",
        "start_date": day,
        "end_date": (target_day + timedelta(days=1)).isoformat(),
    }
    try:
        r = _client.get(FORECAST_URL, params=params)
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise WeatherError(tr("err_forecast", e=e)) from e
    data = r.json()
    h = data.get("hourly") or {}
    times = h.get("time") or []

    start_key = f"{day}T{start_hour:02d}:00"
    if start_key not in times:
        raise WeatherError(tr("err_no_hour"))
    i0 = times.index(start_key)

    rows = []
    for i in range(i0, min(i0 + hours, len(times))):
        code = h["weather_code"][i]
        rows.append({
            "time": times[i][11:16],
            "temp_c": h["temperature_2m"][i],
            "feels_like_c": h["apparent_temperature"][i],
            "precip_prob_pct": h["precipitation_probability"][i],
            "precip_mm": h["precipitation"][i],
            "wind_kmh": h["wind_speed_10m"][i],
            "gusts_kmh": h["wind_gusts_10m"][i],
            "wind_from": compass(h["wind_direction_10m"][i]),
            "humidity_pct": h["relative_humidity_2m"][i],
            "uv_index": h["uv_index"][i],
            "conditions": tr("wmo").get(code, tr("wmo_code", code=code)),
            "wmo_code": code,
        })

    def _vals(key):
        return [row[key] for row in rows if row[key] is not None]

    daily = data.get("daily") or {}
    summary = {
        "temp_range_c": [min(_vals("temp_c"), default=None), max(_vals("temp_c"), default=None)],
        "feels_like_min_c": min(_vals("feels_like_c"), default=None),
        "max_precip_prob_pct": max(_vals("precip_prob_pct"), default=None),
        "total_precip_mm": round(sum(_vals("precip_mm")), 1),
        "max_gusts_kmh": max(_vals("gusts_kmh"), default=None),
        "thunderstorm": any(row["wmo_code"] in (95, 96, 99) for row in rows),
    }
    if daily.get("sunrise"):
        summary["sunrise"] = daily["sunrise"][0][11:16]
        summary["sunset"] = daily["sunset"][0][11:16]

    return {
        "date": day,
        "weekday": tr("weekdays_short")[target_day.weekday()],
        "hourly": rows,
        "summary": summary,
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
