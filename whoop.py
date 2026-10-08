"""WHOOP Developer API v2: OAuth и тренировки, записанные браслетом.

Токены хранятся в data/whoop_tokens.json (папка data/ не попадает в git).
Refresh-токен WHOOP одноразовый: после каждого обновления сохраняем новый.
"""
from __future__ import annotations

import json
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx

import config
from i18n import tr

AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
API_URL = "https://api.prod.whoop.com/developer/v2"
SCOPES = "read:workout read:recovery read:sleep read:profile offline"
TOKENS_PATH = config.DB_PATH.parent / "whoop_tokens.json"

_client = httpx.Client(timeout=httpx.Timeout(25.0, connect=10.0), transport=httpx.HTTPTransport(retries=2))
_lock = threading.Lock()
_pending_states: dict[str, float] = {}


class WhoopError(Exception):
    pass


# ── Состояние подключения ────────────────────────────────

def configured() -> bool:
    return bool(config.WHOOP_CLIENT_ID and config.WHOOP_CLIENT_SECRET)


def _load_tokens() -> dict | None:
    try:
        return json.loads(TOKENS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _save_tokens(data: dict) -> None:
    TOKENS_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKENS_PATH.write_text(json.dumps(data), encoding="utf-8")
    try:
        TOKENS_PATH.chmod(0o600)
    except OSError:
        pass


def connected() -> bool:
    return configured() and bool((_load_tokens() or {}).get("refresh_token") or (_load_tokens() or {}).get("access_token"))


def disconnect() -> None:
    try:
        TOKENS_PATH.unlink()
    except OSError:
        pass


def status() -> dict:
    return {"configured": configured(), "connected": connected(), "redirect_uri": config.WHOOP_REDIRECT_URI}


# ── OAuth ────────────────────────────────────────────────

def authorize_url() -> str:
    if not configured():
        raise WhoopError(tr("whoop_not_configured"))
    state = secrets.token_urlsafe(16)
    now = time.time()
    for s, t in list(_pending_states.items()):  # убираем устаревшие
        if now - t > 900:
            _pending_states.pop(s, None)
    _pending_states[state] = now
    return AUTH_URL + "?" + urlencode({
        "client_id": config.WHOOP_CLIENT_ID,
        "redirect_uri": config.WHOOP_REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
    })


def _token_request(data: dict) -> dict:
    try:
        r = _client.post(TOKEN_URL, data={**data, "client_id": config.WHOOP_CLIENT_ID,
                                          "client_secret": config.WHOOP_CLIENT_SECRET})
    except httpx.HTTPError as e:
        raise WhoopError(tr("whoop_no_connection", e=e)) from e
    if r.status_code >= 400:
        raise WhoopError(tr("whoop_token_failed", code=r.status_code, text=r.text[:200]))
    tok = r.json()
    return {
        "access_token": tok.get("access_token"),
        "refresh_token": tok.get("refresh_token"),
        "expires_at": time.time() + int(tok.get("expires_in") or 3600) - 60,
    }


def finish_authorization(code: str, state: str) -> None:
    if not state or _pending_states.pop(state, None) is None:
        raise WhoopError(tr("whoop_bad_state"))
    _save_tokens(_token_request({"grant_type": "authorization_code", "code": code,
                                 "redirect_uri": config.WHOOP_REDIRECT_URI}))


def _access_token() -> str:
    with _lock:
        tok = _load_tokens()
        if not tok:
            raise WhoopError(tr("whoop_not_connected"))
        if tok.get("access_token") and time.time() < tok.get("expires_at", 0):
            return tok["access_token"]
        if not tok.get("refresh_token"):
            raise WhoopError(tr("whoop_reconnect"))
        try:
            new = _token_request({"grant_type": "refresh_token", "refresh_token": tok["refresh_token"],
                                  "scope": "offline"})
        except WhoopError:
            raise WhoopError(tr("whoop_reconnect"))
        if not new.get("refresh_token"):
            new["refresh_token"] = tok["refresh_token"]
        _save_tokens(new)
        return new["access_token"]


def _get(path: str, params: dict | None = None) -> dict:
    token = _access_token()
    try:
        r = _client.get(API_URL + path, params=params, headers={"Authorization": f"Bearer {token}"})
    except httpx.HTTPError as e:
        raise WhoopError(tr("whoop_no_connection", e=e)) from e
    if r.status_code == 401:
        raise WhoopError(tr("whoop_reconnect"))
    if r.status_code >= 400:
        raise WhoopError(tr("whoop_api_error", code=r.status_code, text=r.text[:200]))
    return r.json()


# ── Тренировки ───────────────────────────────────────────

def _parse_utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _local(dt_utc: datetime, offset: str | None) -> datetime:
    """Местное время тренировки по смещению из WHOOP, например «+03:00»."""
    try:
        sign = -1 if offset and offset.startswith("-") else 1
        h, m = (offset or "+00:00").lstrip("+-").split(":")
        delta = timedelta(hours=int(h), minutes=int(m)) * sign
    except (ValueError, AttributeError):
        delta = timedelta(0)
    return (dt_utc + delta).replace(tzinfo=None)


def normalize(w: dict) -> dict:
    """Тренировка WHOOP в том же виде, что и активность Intervals.icu, плюс поля WHOOP."""
    start = _parse_utc(w["start"])
    end = _parse_utc(w["end"]) if w.get("end") else start
    seconds = max(0, int((end - start).total_seconds()))
    score = w.get("score") or {}
    zones = score.get("zone_durations") or {}
    zone_min = {
        f"z{i}": round((zones.get(k) or 0) / 60000)
        for i, k in enumerate(["zone_zero_milli", "zone_one_milli", "zone_two_milli",
                               "zone_three_milli", "zone_four_milli", "zone_five_milli"])
    }
    sport = (w.get("sport_name") or "activity").replace("_", " ")
    return {
        "id": f"whoop:{w['id']}",
        "source": "WHOOP",
        "type": f"{sport.capitalize()} (WHOOP)",
        "name": sport.capitalize(),
        "start_date_local": _local(start, w.get("timezone_offset")).strftime("%Y-%m-%dT%H:%M:%S"),
        "moving_time": seconds,
        "elapsed_time": seconds,
        "distance": score.get("distance_meter"),
        "total_elevation_gain": score.get("altitude_gain_meter"),
        "average_heartrate": score.get("average_heart_rate"),
        "max_heartrate": score.get("max_heart_rate"),
        "whoop_strain": score.get("strain"),
        "kilojoules": score.get("kilojoule"),
        "hr_zones_min": {k: v for k, v in zone_min.items() if v},
        "score_state": w.get("score_state"),
    }


def list_workouts(oldest: str, newest: str) -> list[dict]:
    """Тренировки с браслета за период [oldest, newest) в днях ГГГГ-ММ-ДД."""
    start = datetime.fromisoformat(oldest).replace(tzinfo=timezone.utc) - timedelta(days=1)
    end = datetime.fromisoformat(newest).replace(tzinfo=timezone.utc) + timedelta(days=1)
    params = {"start": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
              "end": end.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "limit": 25}
    out, pages = [], 0
    while pages < 20:
        data = _get("/activity/workout", params)
        out += [normalize(w) for w in data.get("records") or [] if w.get("start")]
        nxt = data.get("next_token") or data.get("nextToken")
        if not nxt:
            break
        params["nextToken"] = nxt
        pages += 1
    return [w for w in out if oldest <= w["start_date_local"][:10] < newest]


def get_workout(workout_id: str) -> dict:
    return normalize(_get(f"/activity/workout/{workout_id.removeprefix('whoop:')}"))
