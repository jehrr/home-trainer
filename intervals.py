"""Клиент Intervals.icu API.

Учтённые особенности:
- Cloudflare режет запросы без браузерного User-Agent (ошибка 1010).
- Активности, пришедшие из Strava, API не отдаёт: вместо данных приходит заглушка с полем _note.
- Названия полей в ответах бывают в разных вариантах, поэтому значения берутся через pick().
"""
from __future__ import annotations

import base64

import httpx

import config

BASE_URL = "https://intervals.icu/api/v1"


class IntervalsError(Exception):
    pass


def _headers() -> dict:
    token = base64.b64encode(f"API_KEY:{config.INTERVALS_API_KEY}".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://intervals.icu/",
    }


_client = httpx.Client(
    timeout=httpx.Timeout(25.0, connect=10.0),
    transport=httpx.HTTPTransport(retries=2),
)


def _get(path: str, params: dict | None = None):
    if not config.INTERVALS_API_KEY or not config.INTERVALS_ATHLETE_ID:
        raise IntervalsError("Не заданы INTERVALS_API_KEY или INTERVALS_ATHLETE_ID в .env")
    try:
        resp = _client.get(BASE_URL + path, params=params, headers=_headers())
    except httpx.HTTPError as e:
        raise IntervalsError(f"Нет связи с Intervals.icu: {e}") from e
    if resp.status_code >= 400:
        raise IntervalsError(f"Intervals.icu вернул {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def pick(d: dict, *keys):
    """Первое непустое значение из списка возможных имён поля."""
    for k in keys:
        v = d.get(k)
        if v not in (None, "", []):
            return v
    return None


def is_strava_stub(activity: dict) -> bool:
    return activity.get("source") == "STRAVA" and not activity.get("type")


def list_activities(oldest: str, newest: str) -> list[dict]:
    data = _get(f"/athlete/{config.INTERVALS_ATHLETE_ID}/activities",
                {"oldest": oldest, "newest": newest})
    return data if isinstance(data, list) else []


def get_activity(activity_id: str) -> dict:
    return _get(f"/activity/{activity_id}", {"intervals": "true"})


def get_streams(activity_id: str, types: str = "watts,heartrate,cadence") -> dict[str, list]:
    data = _get(f"/activity/{activity_id}/streams", {"types": types})
    result = {}
    if isinstance(data, list):
        for s in data:
            if isinstance(s, dict) and s.get("type"):
                result[s["type"]] = s.get("data") or []
    return result


def list_wellness(oldest: str, newest: str) -> list[dict]:
    data = _get(f"/athlete/{config.INTERVALS_ATHLETE_ID}/wellness",
                {"oldest": oldest, "newest": newest})
    return data if isinstance(data, list) else []


def list_events(oldest: str, newest: str) -> list[dict]:
    data = _get(f"/athlete/{config.INTERVALS_ATHLETE_ID}/events",
                {"oldest": oldest, "newest": newest})
    return data if isinstance(data, list) else []
