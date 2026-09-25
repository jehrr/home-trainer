"""Погода через Open-Meteo: прогноз по часам и поиск мест по названию. Ключи не нужны."""
from __future__ import annotations

from datetime import date as date_cls, datetime, timedelta

import httpx

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
MAX_FORECAST_DAYS = 16

WMO_RU = {
    0: "ясно", 1: "преимущественно ясно", 2: "переменная облачность", 3: "пасмурно",
    45: "туман", 48: "туман с изморозью",
    51: "слабая морось", 53: "морось", 55: "сильная морось",
    56: "ледяная морось", 57: "сильная ледяная морось",
    61: "слабый дождь", 63: "дождь", 65: "сильный дождь",
    66: "ледяной дождь", 67: "сильный ледяной дождь",
    71: "слабый снег", 73: "снег", 75: "сильный снег", 77: "снежная крупа",
    80: "слабый ливень", 81: "ливень", 82: "сильный ливень",
    85: "снегопад", 86: "сильный снегопад",
    95: "гроза", 96: "гроза с градом", 99: "гроза с сильным градом",
}

_client = httpx.Client(timeout=20.0, transport=httpx.HTTPTransport(retries=2))


class WeatherError(Exception):
    pass


def compass(deg) -> str:
    if deg is None:
        return ""
    return ["С", "СВ", "В", "ЮВ", "Ю", "ЮЗ", "З", "СЗ"][round(deg / 45) % 8]


def geocode(name: str, count: int = 5) -> list[dict]:
    try:
        r = _client.get(GEOCODE_URL, params={"name": name, "count": count, "language": "ru", "format": "json"})
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise WeatherError(f"Поиск места не удался: {e}") from e
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
        raise WeatherError(f"Неверная дата {day!r}, нужен формат ГГГГ-ММ-ДД") from e
    today = date_cls.today()
    if target_day < today - timedelta(days=1):
        raise WeatherError("Прогноз доступен только на сегодня и вперёд")
    if target_day > today + timedelta(days=MAX_FORECAST_DAYS - 1):
        raise WeatherError(f"Прогноз доступен максимум на {MAX_FORECAST_DAYS} дней вперёд")

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
        raise WeatherError(f"Прогноз не загрузился: {e}") from e
    data = r.json()
    h = data.get("hourly") or {}
    times = h.get("time") or []

    start_key = f"{day}T{start_hour:02d}:00"
    if start_key not in times:
        raise WeatherError("Нет данных на указанный час")
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
            "conditions": WMO_RU.get(code, f"код {code}"),
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
        "weekday": ["пн", "вт", "ср", "чт", "пт", "сб", "вс"][target_day.weekday()],
        "hourly": rows,
        "summary": summary,
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
