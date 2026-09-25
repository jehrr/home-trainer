"""Инструменты тренера. Каждый возвращает компактный JSON, чтобы не раздувать контекст."""
from __future__ import annotations

import datetime as dt
import math
import traceback
from collections import OrderedDict
from datetime import date, timedelta

import intervals
import storage
import weather
from i18n import tr
from intervals import pick

FEEL_LABELS = {1: "тяжело", 2: "так себе", 3: "нормально", 4: "хорошо", 5: "отлично"}

_PLAN_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "date": {"type": "string", "description": "ГГГГ-ММ-ДД"},
        "title": {"type": "string", "description": "Короткое название, например «Sweet spot 3×15»"},
        "kind": {"type": "string", "enum": list(storage.PLAN_KINDS)},
        "description": {"type": "string", "description": "Структура: разминка, интервалы в % FTP и отдых, заминка, каденс"},
        "duration_min": {"type": "integer"},
        "target_tss": {"type": "integer"},
        "start_time": {"type": "string", "description": "ЧЧ:ММ, если известно"},
        "place": {"type": "string", "description": "Имя сохранённого места, если известно"},
        "indoor": {"type": "boolean", "description": "Станок"},
        "notes": {"type": "string"},
    },
    "required": ["date", "title", "kind"],
}

# ── Определения для Claude ───────────────────────────────

TOOLS = [
    {
        "name": "get_morning_snapshot",
        "description": "Всё для утреннего решения одним вызовом: восстановление за ночь и неделю с флагами риска, "
                       "план на сегодня и ближайшие дни, нагрузка последних дней, была ли интенсивная тренировка "
                       "за 48 часов, погода на время и место сегодняшней тренировки. Используй для утреннего "
                       "брифинга и вопросов «что делать сегодня».",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_recent_activities",
        "description": "Список тренировок атлета из Intervals.icu: дата, тип, длительность, мощность, NP, нагрузка "
                       "(TSS), пульс, каденс, а также оценка ощущений атлетом (RPE, самочувствие). Используй для "
                       "оценки нагрузки и чтобы найти id тренировки для подробного разбора.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "За сколько дней назад, по умолчанию 14", "minimum": 1, "maximum": 180},
                "limit": {"type": "integer", "description": "Максимум тренировок, по умолчанию 20", "minimum": 1, "maximum": 50},
            },
        },
    },
    {
        "name": "get_activity_details",
        "description": "Подробный разбор одной тренировки: интервалы, лучшие усилия (5 с – 20 мин), время в зонах "
                       "мощности от текущего FTP, каденс, аэробный дрейф. Нужен id из get_recent_activities.",
        "input_schema": {
            "type": "object",
            "properties": {"activity_id": {"type": "string"}},
            "required": ["activity_id"],
        },
    },
    {
        "name": "get_wellness",
        "description": "Восстановление по дням (данные WHOOP через Intervals.icu): HRV, пульс покоя, сон, "
                       "готовность, а также фитнес (CTL), усталость (ATL) и форма.",
        "input_schema": {
            "type": "object",
            "properties": {"days": {"type": "integer", "description": "За сколько дней, по умолчанию 7", "minimum": 1, "maximum": 60}},
        },
    },
    {
        "name": "get_training_analysis",
        "description": "Аналитика за несколько недель: объём и нагрузка по неделям, распределение интенсивности "
                       "(низкая / средняя / высокая), аэробный дрейф на длинных спокойных заездах, лучшие усилия и "
                       "оценка FTP по ним, тренд фитнеса и формы, средняя оценка ощущений. Используй для разбора "
                       "недели и оценки прогресса.",
        "input_schema": {
            "type": "object",
            "properties": {"weeks": {"type": "integer", "description": "Сколько недель, по умолчанию 4", "minimum": 1, "maximum": 12}},
        },
    },
    {
        "name": "get_plan",
        "description": "Тренировочный план атлета (хранится локально): тренировки по датам со структурой, "
                       "длительностью, целевой нагрузкой, местом и статусом.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "description": "ГГГГ-ММ-ДД, по умолчанию неделю назад"},
                "date_to": {"type": "string", "description": "ГГГГ-ММ-ДД, по умолчанию через 14 дней"},
            },
        },
    },
    {
        "name": "add_planned_workouts",
        "description": "Добавить в план одну или несколько тренировок. Когда атлет просит составить план — "
                       "добавляй сразу, без дополнительного подтверждения.",
        "input_schema": {
            "type": "object",
            "properties": {"workouts": {"type": "array", "items": _PLAN_ITEM_SCHEMA, "minItems": 1, "maxItems": 60}},
            "required": ["workouts"],
        },
    },
    {
        "name": "update_planned_workout",
        "description": "Изменить тренировку в плане: перенести на другую дату, поменять содержание, место, "
                       "станок или улица, отметить статус (done, partial, missed, skipped, moved).",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                **{k: v for k, v in _PLAN_ITEM_SCHEMA["properties"].items()},
                "status": {"type": "string", "enum": list(storage.PLAN_STATUSES)},
            },
            "required": ["id"],
        },
    },
    {
        "name": "delete_planned_workouts",
        "description": "Удалить тренировки из плана по id. Перед удалением нескольких спроси согласие.",
        "input_schema": {
            "type": "object",
            "properties": {"ids": {"type": "array", "items": {"type": "integer"}, "minItems": 1}},
            "required": ["ids"],
        },
    },
    {
        "name": "compare_plan_vs_actual",
        "description": "Сверка плана с фактом: какие запланированные тренировки выполнены, выполнены частично или "
                       "пропущены, что сделано сверх плана, процент выполнения по времени и нагрузке. Статусы в "
                       "плане обновляются автоматически.",
        "input_schema": {
            "type": "object",
            "properties": {"days_back": {"type": "integer", "description": "За сколько дней, по умолчанию 7", "minimum": 1, "maximum": 42}},
        },
    },
    {
        "name": "save_ride_feedback",
        "description": "Сохранить ощущения атлета о тренировке: RPE 1–10, самочувствие 1–5 (1 тяжело … 5 отлично), "
                       "комментарий. Для тренировок без данных (из Strava) можно указать длительность и средний пульс "
                       "со слов атлета. Если id не указан, берётся последняя тренировка за указанную дату или вообще.",
        "input_schema": {
            "type": "object",
            "properties": {
                "activity_id": {"type": "string"},
                "date": {"type": "string", "description": "ГГГГ-ММ-ДД"},
                "rpe": {"type": "integer", "minimum": 1, "maximum": 10},
                "feel": {"type": "integer", "minimum": 1, "maximum": 5},
                "note": {"type": "string"},
                "duration_min": {"type": "integer"},
                "avg_hr": {"type": "integer"},
            },
        },
    },
    {
        "name": "get_weather",
        "description": "Почасовой прогноз погоды на время тренировки: температура и ощущаемая, осадки, ветер и "
                       "порывы с направлением, влажность, УФ, восход и закат. Место — имя сохранённого места, "
                       "название населённого пункта или координаты.",
        "input_schema": {
            "type": "object",
            "properties": {
                "place": {"type": "string", "description": "Название сохранённого места или населённого пункта"},
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
                "date": {"type": "string", "description": "ГГГГ-ММ-ДД, по умолчанию сегодня"},
                "start_time": {"type": "string", "description": "Время старта ЧЧ:ММ, по умолчанию 08:00"},
                "hours": {"type": "integer", "description": "Длительность тренировки в часах, по умолчанию 3", "minimum": 1, "maximum": 12},
            },
        },
    },
    {
        "name": "save_place",
        "description": "Сохранить место тренировки под коротким именем (например «Побережье»). Если координаты "
                       "не известны, укажи query — название для поиска.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "query": {"type": "string"},
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
                "note": {"type": "string", "description": "Тип дорог, рельеф, особенности"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "update_profile",
        "description": "Обновить устойчивый параметр профиля атлета: ftp_w, weight_kg, max_hr, lthr, "
                       "plan_start_date, target_event, weekly_hours, default_place, default_start_time и др.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "enum": sorted(storage.PROFILE_KEYS.keys())},
                "value": {"type": "string"},
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "add_note",
        "description": "Запомнить долгосрочный факт об атлете: травмы, предпочтения, ограничения, реакция на "
                       "нагрузку, договорённости. Не для разовых мелочей.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
]

TOOL_LABELS = tr("tool_labels")

POWER_ZONES = [
    ("Z1 восстановление", 0.00, 0.60),
    ("Z2 база", 0.60, 0.80),
    ("Z3 темп", 0.80, 0.90),
    ("Z4 порог", 0.90, 1.05),
    ("Z5 VO2max", 1.05, 1.20),
    ("Z6 анаэробная/спринт", 1.20, 99.0),
]


# ── Вспомогательное ──────────────────────────────────────

def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v not in (None, "", [], {})}


def _r(v, nd=0):
    if v is None:
        return None
    try:
        return round(float(v), nd) if nd else int(round(float(v)))
    except (TypeError, ValueError):
        return v


def _current_ftp() -> int:
    try:
        return int(float(storage.get_profile().get("ftp_w") or 242))
    except ValueError:
        return 242


def _date_arg(value, default: date) -> date:
    if not value:
        return default
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError as e:
        raise ValueError(f"Неверная дата {value!r}, нужен формат ГГГГ-ММ-ДД") from e


def _act_date(a: dict) -> str:
    return (a.get("start_date_local") or "")[:10]


def _feedback_view(fb: dict | None) -> dict | None:
    if not fb:
        return None
    return _clean({
        "rpe": fb.get("rpe"),
        "feel": FEEL_LABELS.get(fb.get("feel")) if fb.get("feel") else None,
        "note": fb.get("note"),
    }) or None


def _activity_summary(a: dict, fb: dict | None = None) -> dict:
    if intervals.is_strava_stub(a):
        out = {
            "id": str(a.get("id")),
            "date": (a.get("start_date_local") or "")[:16].replace("T", " "),
            "source": "STRAVA",
            "data_available": False,
            "note": "Пришла из Strava: Intervals.icu не отдаёт её данные через API",
        }
        if fb:
            out["athlete_reported"] = _clean({
                "duration_min": fb.get("manual_duration_min"), "avg_hr": fb.get("manual_avg_hr"),
                **(_feedback_view(fb) or {}),
            })
        return out
    moving = pick(a, "moving_time", "elapsed_time")
    dist = a.get("distance")
    return _clean({
        "id": str(a.get("id")),
        "date": (a.get("start_date_local") or "")[:16].replace("T", " "),
        "name": a.get("name"),
        "type": a.get("type"),
        "source": a.get("source"),
        "duration_min": _r(moving / 60) if moving else None,
        "distance_km": _r(dist / 1000, 1) if dist else None,
        "elevation_m": _r(pick(a, "total_elevation_gain")),
        "avg_power_w": _r(pick(a, "icu_average_watts", "average_watts")),
        "np_w": _r(pick(a, "icu_weighted_avg_watts", "weighted_average_watts", "normalized_power")),
        "intensity_pct": _r(pick(a, "icu_intensity")),
        "load_tss": _r(pick(a, "icu_training_load", "tss")),
        "avg_hr": _r(pick(a, "average_heartrate")),
        "max_hr": _r(pick(a, "max_heartrate")),
        "avg_cadence": _r(pick(a, "average_cadence")),
        "ftp_used": _r(pick(a, "icu_ftp")),
        "feedback": _feedback_view(fb),
    })


def _duration_min(a: dict, fb: dict | None = None) -> int:
    moving = pick(a, "moving_time", "elapsed_time")
    if moving:
        return int(round(moving / 60))
    if fb and fb.get("manual_duration_min"):
        return int(fb["manual_duration_min"])
    return 0


def _intensity(a: dict) -> float | None:
    """Интенсивность тренировки как доля FTP (IF)."""
    v = pick(a, "icu_intensity")
    if v is not None:
        v = float(v)
        return v / 100 if v > 3 else v
    np_w = pick(a, "icu_weighted_avg_watts", "weighted_average_watts", "normalized_power")
    return float(np_w) / _current_ftp() if np_w else None


def _best_avg(values: list, window: int):
    if len(values) < window:
        return None
    s = sum(values[:window])
    best = s
    for i in range(window, len(values)):
        s += values[i] - values[i - window]
        best = max(best, s)
    return int(round(best / window))


_stream_cache: OrderedDict = OrderedDict()


def _streams(activity_id: str) -> dict:
    """Потоки данных тренировки с кэшем: завершённые тренировки не меняются."""
    key = str(activity_id)
    if key in _stream_cache:
        _stream_cache.move_to_end(key)
        return _stream_cache[key]
    try:
        data = intervals.get_streams(key)
    except intervals.IntervalsError:
        data = {}
    _stream_cache[key] = data
    if len(_stream_cache) > 80:
        _stream_cache.popitem(last=False)
    return data


def _zone_seconds(watts: list, ftp: int) -> list[int]:
    sec = [0] * len(POWER_ZONES)
    for w in watts:
        if not w or w <= 0:
            continue
        ratio = w / ftp
        for i, (_, lo, hi) in enumerate(POWER_ZONES):
            if lo <= ratio < hi:
                sec[i] += 1
                break
    return sec


def _decoupling(watts: list, hr: list) -> float | None:
    """Аэробный дрейф Pw:HR, %: насколько упала мощность на удар пульса во второй половине.
    Первые 10 минут (разминка) не учитываются. Меньше 5 % — хорошая аэробная база."""
    n = min(len(watts), len(hr))
    if n < 3600:
        return None
    w, h = watts[600:n], hr[600:n]
    half = len(w) // 2

    def ef(ws, hs):
        pairs = [(x or 0, y) for x, y in zip(ws, hs) if y and y > 0]
        if len(pairs) < 600:
            return None
        return (sum(p[0] for p in pairs) / len(pairs)) / (sum(p[1] for p in pairs) / len(pairs))

    ef1, ef2 = ef(w[:half], h[:half]), ef(w[half:], h[half:])
    if not ef1 or not ef2:
        return None
    return round((ef1 - ef2) / ef1 * 100, 1)


def _activities_with_feedback(oldest: date, newest: date) -> tuple[list[dict], dict]:
    acts = intervals.list_activities(oldest.isoformat(), (newest + timedelta(days=1)).isoformat())
    acts = [a for a in acts if oldest.isoformat() <= _act_date(a) <= newest.isoformat()]
    acts.sort(key=lambda a: a.get("start_date_local") or "")
    return acts, storage.feedback_map([a.get("id") for a in acts])


# ── Тренировки и восстановление ──────────────────────────

def get_recent_activities(days: int = 14, limit: int = 20) -> dict:
    acts, fbs = _activities_with_feedback(date.today() - timedelta(days=int(days)), date.today())
    acts.reverse()
    items = [_activity_summary(a, fbs.get(str(a.get("id")))) for a in acts[: int(limit)]]
    blocked = sum(1 for i in items if i.get("data_available") is False and not i.get("athlete_reported"))
    result = {"period_days": days, "count": len(items), "activities": items}
    if blocked:
        result["warning"] = (f"Тренировок из Strava без данных: {blocked}. Если нужна такая тренировка — "
                             "попроси атлета описать её и сохрани через save_ride_feedback.")
    return result


def get_activity_details(activity_id: str) -> dict:
    a = intervals.get_activity(str(activity_id))
    fb = storage.feedback_map([activity_id]).get(str(activity_id))
    if intervals.is_strava_stub(a):
        return _activity_summary(a, fb)
    out = _activity_summary(a, fb)

    laps = []
    for iv in (a.get("icu_intervals") or [])[:30]:
        dur = pick(iv, "moving_time", "elapsed_time")
        laps.append(_clean({
            "type": iv.get("type"),
            "label": iv.get("label"),
            "duration_min": _r(dur / 60, 1) if dur else None,
            "avg_power_w": _r(pick(iv, "average_watts")),
            "np_w": _r(pick(iv, "weighted_average_watts")),
            "avg_hr": _r(pick(iv, "average_heartrate")),
            "avg_cadence": _r(pick(iv, "average_cadence")),
        }))
    if laps:
        out["intervals"] = laps

    streams = _streams(str(activity_id))
    watts = [w or 0 for w in streams.get("watts") or []]
    if watts:
        ftp = _current_ftp()
        out["best_efforts_w"] = _clean({
            f"{s}s" if s < 60 else f"{s // 60}min": _best_avg(watts, s) for s in (5, 30, 60, 300, 1200)
        })
        zone_sec = _zone_seconds(watts, ftp)
        out["time_in_zones_min"] = {
            name: round(sec / 60) for (name, _, _), sec in zip(POWER_ZONES, zone_sec) if sec >= 30
        }
        out["zones_based_on_ftp_w"] = ftp
        out["coasting_pct"] = round(100 * sum(1 for w in watts if w <= 0) / len(watts))
        dec = _decoupling(watts, streams.get("heartrate") or [])
        if dec is not None:
            out["aerobic_decoupling_pct"] = dec

    cad = [c for c in streams.get("cadence") or [] if c and c > 0]
    if cad:
        out["cadence"] = {
            "avg_pedaling": round(sum(cad) / len(cad)),
            "pct_below_80": round(100 * sum(1 for c in cad if c < 80) / len(cad)),
            "pct_85_95": round(100 * sum(1 for c in cad if 85 <= c <= 95) / len(cad)),
        }
    return out


# ── Восстановление ───────────────────────────────────────

WELLNESS_FIELDS = {
    "hrv": ("hrv",), "hrv_sdnn": ("hrvSDNN",),
    "resting_hr": ("restingHR", "resting_hr"),
    "readiness": ("readiness",),
    "sleep_score": ("sleepScore", "sleep_score"),
    "sleep_quality": ("sleepQuality",),
    "avg_sleeping_hr": ("avgSleepingHR",),
    "spo2": ("spO2",), "respiration": ("respiration",),
    "weight_kg": ("weight",),
    "fitness_ctl": ("ctl",), "fatigue_atl": ("atl",), "ramp_rate": ("rampRate",),
    "soreness": ("soreness",), "fatigue_subjective": ("fatigue",), "stress": ("stress",),
    "mood": ("mood",), "motivation": ("motivation",),
}


def get_wellness(days: int = 7) -> dict:
    newest = date.today()
    oldest = newest - timedelta(days=int(days) - 1)
    rows = intervals.list_wellness(oldest.isoformat(), newest.isoformat())
    rows.sort(key=lambda r: r.get("id") or "")
    out_days = []
    for r in rows:
        d = {"date": r.get("id")}
        for out_key, keys in WELLNESS_FIELDS.items():
            v = pick(r, *keys)
            if v is not None:
                d[out_key] = _r(v, 1)
        sleep = pick(r, "sleepSecs", "sleep_secs")
        if sleep:
            d["sleep_h"] = round(sleep / 3600, 1)
        if d.get("fitness_ctl") is not None and d.get("fatigue_atl") is not None:
            d["form_tsb"] = round(d["fitness_ctl"] - d["fatigue_atl"], 1)
        if len(d) > 1:
            out_days.append(d)

    result = {"days": out_days}
    hrvs = [d["hrv"] for d in out_days if d.get("hrv")]
    if len(hrvs) >= 3:
        result["hrv_avg"] = round(sum(hrvs) / len(hrvs), 1)
        result["hrv_latest_vs_avg_pct"] = round(100 * (hrvs[-1] / result["hrv_avg"] - 1))
    return result


# ── Аналитика за несколько недель ───────────────────────

def get_training_analysis(weeks: int = 4) -> dict:
    weeks = max(1, min(int(weeks or 4), 12))
    today = date.today()
    start = today - timedelta(days=today.weekday()) - timedelta(weeks=weeks - 1)  # с понедельника
    acts, fbs = _activities_with_feedback(start, today)
    ftp = _current_ftp()

    week_rows: dict[str, dict] = {}
    zone_total = [0] * len(POWER_ZONES)
    long_rides, best = [], {5: 0, 60: 0, 300: 0, 1200: 0}
    rpes, blocked, streams_used = [], 0, 0

    for a in acts:
        d = date.fromisoformat(_act_date(a))
        monday = (d - timedelta(days=d.weekday())).isoformat()
        wk = week_rows.setdefault(monday, {"week_from": monday, "sessions": 0, "hours": 0.0,
                                           "distance_km": 0.0, "tss": 0, "no_data_sessions": 0})
        fb = fbs.get(str(a.get("id")))
        wk["sessions"] += 1
        wk["hours"] += _duration_min(a, fb) / 60
        if fb and fb.get("rpe"):
            rpes.append(fb["rpe"])
        if intervals.is_strava_stub(a):
            wk["no_data_sessions"] += 1
            blocked += 1
            continue
        wk["distance_km"] += (a.get("distance") or 0) / 1000
        wk["tss"] += int(pick(a, "icu_training_load", "tss") or 0)

        # Потоки нужны для зон, лучших усилий и дрейфа; берём для велотренировок, не больше 25 штук
        if "ride" not in (a.get("type") or "").lower() or streams_used >= 25:
            continue
        streams_used += 1
        st = _streams(str(a.get("id")))
        watts = [w or 0 for w in st.get("watts") or []]
        if not watts:
            continue
        for i, sec in enumerate(_zone_seconds(watts, ftp)):
            zone_total[i] += sec
        for s in best:
            v = _best_avg(watts, s)
            if v and v > best[s]:
                best[s] = v
        intensity = _intensity(a)
        if len(watts) >= 3600 and (intensity is None or intensity < 0.85):
            dec = _decoupling(watts, st.get("heartrate") or [])
            if dec is not None:
                long_rides.append({"date": _act_date(a), "duration_min": _duration_min(a),
                                   "if": round(intensity, 2) if intensity else None, "decoupling_pct": dec})

    for wk in week_rows.values():
        wk["hours"] = round(wk["hours"], 1)
        wk["distance_km"] = round(wk["distance_km"])
        if not wk["no_data_sessions"]:
            del wk["no_data_sessions"]

    result: dict = {"period": f"{start.isoformat()} — {today.isoformat()}", "ftp_used_w": ftp,
                    "weeks": [week_rows[k] for k in sorted(week_rows)]}

    total = sum(zone_total)
    if total:
        low = (zone_total[0] + zone_total[1]) / total
        mid = (zone_total[2] + zone_total[3]) / total
        high = (zone_total[4] + zone_total[5]) / total
        if low >= 0.75 and high >= mid:
            model = "поляризованное"
        elif low > mid > high:
            model = "пирамидальное"
        else:
            model = "пороговое (много времени в Z3–Z4)"
        result["intensity_distribution"] = {
            "low_z1_z2_pct": round(low * 100), "mid_z3_z4_pct": round(mid * 100),
            "high_z5_z6_pct": round(high * 100), "model": model,
            "time_in_zones_h": {POWER_ZONES[i][0]: round(sec / 3600, 1) for i, sec in enumerate(zone_total) if sec},
        }
    if long_rides:
        result["aerobic_decoupling"] = {
            "rides": long_rides[-6:],
            "hint": "Меньше 5 % — хорошая аэробная база для такой длительности, больше 8 % — база отстаёт или сказалась усталость и жара.",
        }
    best_view = _clean({"5s": best[5], "1min": best[60], "5min": best[300], "20min": best[1200]})
    if best_view:
        result["best_efforts_w"] = best_view
        if best[1200]:
            result["ftp_estimate_w"] = {
                "from_best_20min": round(best[1200] * 0.95),
                "note": "Оценка верна, только если 20 минут ехали на пределе. По спокойным тренировкам она занижена.",
            }
    eftps = [pick(a, "icu_eftp") for a in acts if pick(a, "icu_eftp")]
    if eftps:
        result["intervals_eftp_w"] = _r(eftps[-1])

    try:
        wl = get_wellness(days=min(weeks * 7, 60))["days"]
        with_ctl = [d for d in wl if d.get("fitness_ctl") is not None]
        if with_ctl:
            first, last = with_ctl[0], with_ctl[-1]
            result["fitness_trend"] = _clean({
                "ctl_start": first.get("fitness_ctl"), "ctl_now": last.get("fitness_ctl"),
                "atl_now": last.get("fatigue_atl"), "form_now": last.get("form_tsb"),
            })
    except Exception:
        pass
    if rpes:
        result["avg_rpe"] = round(sum(rpes) / len(rpes), 1)
    if blocked:
        result["warning"] = f"Тренировок из Strava без данных: {blocked}. В нагрузке и зонах они не учтены."
    return result


# ── Локальный план ───────────────────────────────────────

def _plan_view(p: dict) -> dict:
    return _clean({
        "id": p["id"], "date": p["date"], "start_time": p["start_time"], "place": p["place"],
        "title": p["title"], "kind": p["kind"], "description": p["description"],
        "duration_min": p["duration_min"], "target_tss": p["target_tss"],
        "indoor": True if p["indoor"] else None, "status": p["status"],
        "activity_id": p["activity_id"], "notes": p["notes"],
    })


def get_plan(date_from=None, date_to=None) -> dict:
    d1 = _date_arg(date_from, date.today() - timedelta(days=7))
    d2 = _date_arg(date_to, date.today() + timedelta(days=14))
    items = [_plan_view(p) for p in storage.list_plan(d1.isoformat(), d2.isoformat())]
    return {"from": d1.isoformat(), "to": d2.isoformat(), "count": len(items), "workouts": items,
            **({"note": "План на этот период пуст."} if not items else {})}


def _normalize_plan_item(w: dict) -> dict:
    item = dict(w)
    if "date" in item and item["date"] is not None:
        item["date"] = _date_arg(item["date"], date.today()).isoformat()
    if item.get("kind") and item["kind"] not in storage.PLAN_KINDS:
        item["kind"] = "other"
    if item.get("status") and item["status"] not in storage.PLAN_STATUSES:
        raise ValueError(f"Неизвестный статус {item['status']}")
    if "indoor" in item and item["indoor"] is not None:
        item["indoor"] = 1 if item["indoor"] else 0
    return item


def add_planned_workouts(workouts: list) -> dict:
    ids = [storage.add_planned(_normalize_plan_item(w)) for w in workouts]
    return {"added": len(ids), "ids": ids}


def update_planned_workout(id: int, **fields) -> dict:
    if not storage.get_planned(int(id)):
        raise ValueError(f"Тренировки с id {id} нет в плане")
    storage.update_planned(int(id), _normalize_plan_item(fields))
    return {"updated": _plan_view(storage.get_planned(int(id)))}


def delete_planned_workouts(ids: list) -> dict:
    for i in ids:
        storage.delete_planned(int(i))
    return {"deleted": len(ids)}


def compare_plan_vs_actual(days_back: int = 7) -> dict:
    today = date.today()
    start = today - timedelta(days=int(days_back))
    plan = [p for p in storage.list_plan(start.isoformat(), today.isoformat()) if p["kind"] != "rest"]
    acts, fbs = _activities_with_feedback(start, today)

    by_date: dict[str, list] = {}
    for a in acts:
        by_date.setdefault(_act_date(a), []).append(a)
    used: set = set()
    rows = []
    planned_min = actual_min = planned_tss = actual_tss = 0
    counts = {"done": 0, "partial": 0, "missed": 0, "pending": 0}

    for p in plan:
        candidates = [a for a in by_date.get(p["date"], []) if a.get("id") not in used]
        act = max(candidates, key=lambda a: _duration_min(a, fbs.get(str(a.get("id"))))) if candidates else None
        row = {"plan_id": p["id"], "date": p["date"], "planned": p["title"],
               "planned_min": p["duration_min"], "planned_tss": p["target_tss"]}
        planned_min += p["duration_min"] or 0
        planned_tss += p["target_tss"] or 0

        if act is None:
            if p["status"] in ("skipped", "moved"):
                row["result"] = p["status"]
            elif p["date"] < today.isoformat():
                row["result"] = "missed"
                counts["missed"] += 1
                if p["status"] == "planned":
                    storage.update_planned(p["id"], {"status": "missed"})
            else:
                row["result"] = "pending"
                counts["pending"] += 1
            rows.append(_clean(row))
            continue

        used.add(act.get("id"))
        fb = fbs.get(str(act.get("id")))
        dur = _duration_min(act, fb)
        tss = int(pick(act, "icu_training_load", "tss") or 0)
        actual_min += dur
        actual_tss += tss
        ratio = dur / p["duration_min"] if p["duration_min"] and dur else None
        result = "done" if ratio is None or ratio >= 0.8 else "partial"
        counts[result] += 1
        row.update({"result": result, "activity_id": str(act.get("id")), "actual_min": dur or None,
                    "actual_tss": tss or None, "actual_if": round(_intensity(act), 2) if _intensity(act) else None,
                    "feedback": _feedback_view(fb),
                    "no_data": True if intervals.is_strava_stub(act) and not fb else None})
        if p["status"] in ("planned", "missed"):
            storage.update_planned(p["id"], {"status": result, "activity_id": str(act.get("id"))})
        rows.append(_clean(row))

    extra = [_clean({"date": _act_date(a), "id": str(a.get("id")), "name": a.get("name"),
                     "duration_min": _duration_min(a, fbs.get(str(a.get("id")))) or None,
                     "tss": _r(pick(a, "icu_training_load", "tss"))})
             for a in acts if a.get("id") not in used]
    result = {
        "period": f"{start.isoformat()} — {today.isoformat()}",
        "summary": {**counts, "planned_sessions": len(plan),
                    "time_compliance_pct": round(100 * actual_min / planned_min) if planned_min else None,
                    "planned_tss": planned_tss or None, "actual_tss_on_plan": actual_tss or None},
        "sessions": rows,
    }
    if extra:
        result["extra_activities"] = extra
    if not plan:
        result["note"] = "За этот период в плане ничего нет — сравнивать не с чем."
    return result


# ── Ощущения после заезда ────────────────────────────────

def save_ride_feedback(activity_id=None, date=None, rpe=None, feel=None, note="", duration_min=None, avg_hr=None) -> dict:
    if not activity_id:
        day = _date_arg(date, dt.date.today())
        acts = intervals.list_activities((day - timedelta(days=14 if not date else 0)).isoformat(),
                                         (day + timedelta(days=1)).isoformat())
        acts = [a for a in acts if not date or _act_date(a) == day.isoformat()]
        if not acts:
            raise ValueError("Не нашёл тренировку для оценки — уточни дату")
        act = max(acts, key=lambda a: a.get("start_date_local") or "")
        activity_id, day_str = str(act.get("id")), _act_date(act)
    else:
        day_str = _date_arg(date, dt.date.today()).isoformat() if date else ""
        if not day_str:
            try:
                day_str = _act_date(intervals.get_activity(str(activity_id))) or dt.date.today().isoformat()
            except intervals.IntervalsError:
                day_str = dt.date.today().isoformat()
    if rpe is not None and not 1 <= int(rpe) <= 10:
        raise ValueError("RPE должно быть от 1 до 10")
    if feel is not None and not 1 <= int(feel) <= 5:
        raise ValueError("Самочувствие должно быть от 1 до 5")
    storage.save_feedback(str(activity_id), day_str, rpe, feel, note or "", duration_min, avg_hr)
    return {"saved_for_activity": str(activity_id), "date": day_str}


# ── Утренняя сводка ──────────────────────────────────────

def get_morning_snapshot() -> dict:
    today = date.today()
    profile = storage.get_profile()
    out: dict = {"today": today.isoformat(),
                 "weekday": ["пн", "вт", "ср", "чт", "пт", "сб", "вс"][today.weekday()]}
    flags = []

    try:
        w = get_wellness(days=7)
        days = w.get("days") or []
        latest = days[-1] if days else {}
        out["recovery"] = _clean({"latest": latest, "hrv_week_avg": w.get("hrv_avg"),
                                  "hrv_vs_avg_pct": w.get("hrv_latest_vs_avg_pct")})
        if latest.get("date") and latest["date"] != today.isoformat():
            flags.append(f"данных восстановления за сегодня нет, последние за {latest['date']}")
        if (w.get("hrv_latest_vs_avg_pct") or 0) <= -10:
            flags.append(f"HRV на {abs(w['hrv_latest_vs_avg_pct'])} % ниже среднего за неделю")
        if latest.get("sleep_h") and latest["sleep_h"] < 6:
            flags.append(f"сон всего {latest['sleep_h']} ч")
        if latest.get("form_tsb") is not None and latest["form_tsb"] < -25:
            flags.append(f"форма {latest['form_tsb']}: высокая накопленная усталость")
    except Exception as e:
        out["recovery"] = {"error": str(e)}

    plan_today = storage.list_plan(today.isoformat(), today.isoformat())
    out["plan_today"] = [_plan_view(p) for p in plan_today] or "в плане на сегодня ничего нет"
    out["plan_next_days"] = [_plan_view(p) for p in storage.list_plan(
        (today + timedelta(days=1)).isoformat(), (today + timedelta(days=3)).isoformat())]

    try:
        acts, fbs = _activities_with_feedback(today - timedelta(days=3), today)
        out["last_3_days"] = [_activity_summary(a, fbs.get(str(a.get("id")))) for a in reversed(acts)]
        hard = [a for a in acts if (_intensity(a) or 0) >= 0.85 and _duration_min(a) >= 30
                and _act_date(a) >= (today - timedelta(days=2)).isoformat()]
        if hard:
            flags.append(f"интенсивная тренировка {_act_date(hard[-1])} — меньше 48 часов назад или на границе")
        missed = [p for p in storage.list_plan((today - timedelta(days=1)).isoformat(),
                                               (today - timedelta(days=1)).isoformat())
                  if p["kind"] != "rest" and not any(_act_date(a) == p["date"] for a in acts)]
        if missed:
            flags.append("вчерашняя тренировка по плану не выполнена: " + ", ".join(p["title"] for p in missed))
    except Exception as e:
        out["last_3_days"] = {"error": str(e)}

    main = next((p for p in plan_today if p["kind"] != "rest"), None)
    place = (main or {}).get("place") or profile.get("default_place") or ""
    start = (main or {}).get("start_time") or profile.get("default_start_time") or "08:00"
    hours = math.ceil((main["duration_min"] or 120) / 60) if main else 2
    if main and main["indoor"]:
        out["weather"] = "тренировка на станке, погода не важна"
    elif place:
        try:
            out["weather"] = get_weather(place=place, date=today.isoformat(), start_time=start, hours=hours)
        except Exception as e:
            out["weather"] = {"error": str(e)}
    else:
        out["weather"] = ("место не задано: ни в плане, ни в профиле (default_place). "
                          "Спроси, где будет тренировка, или предложи сохранить обычное место.")
    out["flags"] = flags or ["явных красных флагов нет"]
    return out


# ── Погода, места, профиль ───────────────────────────────

def _resolve_location(place=None, latitude=None, longitude=None) -> dict:
    if latitude is not None and longitude is not None:
        return {"name": place or f"{latitude}, {longitude}", "latitude": float(latitude), "longitude": float(longitude)}
    if not place:
        places = storage.list_places()
        if len(places) == 1:
            p = places[0]
            return {"name": p["name"], "latitude": p["latitude"], "longitude": p["longitude"], "saved": True}
        raise ValueError(tr("err_place_missing"))
    saved = storage.find_place(place)
    if saved:
        return {"name": saved["name"], "latitude": saved["latitude"], "longitude": saved["longitude"],
                "note": saved.get("note"), "saved": True}
    found = weather.geocode(place, count=3)
    if not found:
        raise ValueError(tr("err_place_not_found", place=place))
    g = found[0]
    loc = {"name": g["name"], "region": g["region"], "latitude": g["latitude"], "longitude": g["longitude"]}
    if len(found) > 1:
        loc["other_matches"] = [f'{x["name"]} ({x["region"]})' for x in found[1:]]
    return loc


def get_weather(place=None, latitude=None, longitude=None, date=None, start_time="08:00", hours=3) -> dict:
    loc = _resolve_location(place, latitude, longitude)
    day = date or dt.date.today().isoformat()
    fc = weather.forecast(loc["latitude"], loc["longitude"], day, start_time or "08:00", hours or 3)
    return {"location": _clean(loc), **fc}


def save_place(name, query=None, latitude=None, longitude=None, note="") -> dict:
    if latitude is None or longitude is None:
        found = weather.geocode(query or name, count=1)
        if not found:
            raise ValueError(f"Не нашёл координаты для «{query or name}»")
        latitude, longitude = found[0]["latitude"], found[0]["longitude"]
        region = found[0]["region"]
    else:
        region = None
    storage.save_place(name, float(latitude), float(longitude), note or "")
    return _clean({"saved": name, "latitude": latitude, "longitude": longitude, "region": region})


def update_profile(key: str, value: str) -> dict:
    if key not in storage.PROFILE_KEYS:
        raise ValueError(f"Неизвестный параметр {key}")
    old = storage.get_profile().get(key)
    storage.set_profile(key, str(value))
    if key == "ftp_w" and old and old != str(value):
        storage.add_note(f"FTP изменён: {old} → {value} Вт ({date.today().isoformat()})")
    return {"updated": key, "old": old, "new": str(value)}


def add_note(text: str) -> dict:
    note_id = storage.add_note(text.strip())
    return {"saved_note_id": note_id}


IMPLEMENTATIONS = {
    "get_morning_snapshot": get_morning_snapshot,
    "get_recent_activities": get_recent_activities,
    "get_activity_details": get_activity_details,
    "get_wellness": get_wellness,
    "get_training_analysis": get_training_analysis,
    "get_plan": get_plan,
    "add_planned_workouts": add_planned_workouts,
    "update_planned_workout": update_planned_workout,
    "delete_planned_workouts": delete_planned_workouts,
    "compare_plan_vs_actual": compare_plan_vs_actual,
    "save_ride_feedback": save_ride_feedback,
    "get_weather": get_weather,
    "save_place": save_place,
    "update_profile": update_profile,
    "add_note": add_note,
}


def execute(name: str, args: dict) -> tuple[dict, bool]:
    """Выполнить инструмент. Возвращает (результат, была_ли_ошибка)."""
    fn = IMPLEMENTATIONS.get(name)
    if not fn:
        return {"error": f"Неизвестный инструмент {name}"}, True
    try:
        return fn(**(args or {})), False
    except (intervals.IntervalsError, weather.WeatherError, ValueError, TypeError) as e:
        return {"error": str(e)}, True
    except Exception as e:  # неожиданные ошибки не должны ронять диалог
        traceback.print_exc()
        return {"error": f"Внутренняя ошибка инструмента: {e}"}, True
