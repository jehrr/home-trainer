"""Веб-сервер тренера. Запуск: python3 app.py"""
import datetime
import json
import queue
import threading
import time
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import agent
import config
import storage
import tools
from i18n import tr
import weather

storage.init_db()
app = FastAPI(title="Home Trainer")
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")


@app.middleware("http")
async def no_cache_for_ui(request, call_next):
    # Чтобы после обновления файлов браузер не показывал старый интерфейс из кэша
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


class ChatIn(BaseModel):
    message: str


class TitleIn(BaseModel):
    title: str


class NoteIn(BaseModel):
    text: str


class PlaceIn(BaseModel):
    name: str
    latitude: float
    longitude: float
    note: str = ""


class PlanPatch(BaseModel):
    status: Optional[str] = None
    date: Optional[str] = None


class FeedbackIn(BaseModel):
    activity_id: str
    rpe: Optional[int] = None
    feel: Optional[int] = None
    note: str = ""
    duration_min: Optional[int] = None
    avg_hr: Optional[int] = None


class ProfileIn(BaseModel):
    key: str
    value: str


@app.get("/")
def index():
    html = (config.STATIC_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html.replace('<html lang="ru">', f'<html lang="{config.LANGUAGE}">', 1))


@app.get("/api/status")
def status():
    return {
        "model": config.MODEL,
        "language": config.LANGUAGE,
        "anthropic_key": bool(config.ANTHROPIC_API_KEY),
        "intervals_key": bool(config.INTERVALS_API_KEY and config.INTERVALS_ATHLETE_ID),
    }


# ── Диалоги ──────────────────────────────────────────────

@app.get("/api/conversations")
def conversations():
    return storage.list_conversations()


@app.post("/api/conversations")
def new_conversation():
    return {"id": storage.create_conversation()}


@app.get("/api/conversations/{conv_id}")
def conversation(conv_id: int):
    conv = storage.get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, tr("err_conv_not_found"))
    return {"id": conv_id, "title": conv["title"], "has_summary": bool(conv["summary"]),
            "kind": conv.get("kind", "chat"), "running": conv_id in _running,
            "needs_answer": conv_id not in _running and agent.needs_answer(conv_id),
            "messages": agent.transcript_for_ui(conv_id)}


@app.patch("/api/conversations/{conv_id}")
def rename(conv_id: int, body: TitleIn):
    storage.rename_conversation(conv_id, body.title.strip()[:80] or tr("new_chat"))
    return {"ok": True}


@app.delete("/api/conversations/{conv_id}")
def delete(conv_id: int):
    storage.delete_conversation(conv_id)
    return {"ok": True}


# Ответ готовится в фоновом потоке: если страницу закрыли или обновили,
# тренер всё равно доводит ответ до конца и сохраняет его.
_running: set = set()
_running_lock = threading.Lock()


def _stream_turn(conv_id: int, text):
    with _running_lock:
        if conv_id in _running:
            raise HTTPException(409, tr("err_busy"))
        _running.add(conv_id)
    events: queue.Queue = queue.Queue()

    def worker():
        try:
            for event in agent.run_turn(conv_id, text):
                events.put(event)
        except Exception as e:  # страховка: поток не должен умирать молча
            events.put({"type": "error", "message": str(e)})
        finally:
            with _running_lock:
                _running.discard(conv_id)
            events.put(None)

    threading.Thread(target=worker, daemon=True).start()

    def stream():
        while True:
            event = events.get()
            if event is None:
                break
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/conversations/{conv_id}/chat")
def chat(conv_id: int, body: ChatIn):
    if not body.message.strip():
        raise HTTPException(400, tr("err_empty_message"))
    if not storage.get_conversation(conv_id):
        raise HTTPException(404, tr("err_conv_not_found"))
    return _stream_turn(conv_id, body.message.strip())


@app.post("/api/conversations/{conv_id}/retry")
def retry(conv_id: int):
    if not storage.get_conversation(conv_id):
        raise HTTPException(404, tr("err_conv_not_found"))
    return _stream_turn(conv_id, None)


# ── Память атлета ────────────────────────────────────────

@app.get("/api/memory")
def memory():
    return {
        "profile": storage.get_profile(),
        "profile_labels": storage.PROFILE_KEYS,
        "notes": storage.list_notes(),
        "places": storage.list_places(),
        "plan": agent.plan_position(storage.get_profile(), for_ui=True),
    }


@app.put("/api/profile")
def set_profile(body: ProfileIn):
    if body.key not in storage.PROFILE_KEYS:
        raise HTTPException(400, tr("err_unknown_param"))
    storage.set_profile(body.key, body.value.strip())
    return {"ok": True}


@app.post("/api/notes")
def add_note(body: NoteIn):
    if not body.text.strip():
        raise HTTPException(400, tr("err_empty_note"))
    return {"id": storage.add_note(body.text.strip())}


@app.delete("/api/notes/{note_id}")
def delete_note(note_id: int):
    storage.delete_note(note_id)
    return {"ok": True}


@app.get("/api/places")
def places():
    return storage.list_places()


@app.post("/api/places")
def save_place(body: PlaceIn):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, tr("err_place_name"))
    if not (-90 <= body.latitude <= 90 and -180 <= body.longitude <= 180):
        raise HTTPException(400, tr("err_coords"))
    storage.save_place(name, round(body.latitude, 4), round(body.longitude, 4), body.note.strip())
    return {"ok": True}


@app.get("/api/geocode")
def geocode(q: str):
    if not q.strip():
        return []
    try:
        return weather.geocode(q.strip(), count=6)
    except weather.WeatherError as e:
        raise HTTPException(502, str(e))


@app.get("/api/weather")
def forecast(place: str = "", latitude: Optional[float] = None, longitude: Optional[float] = None,
             date: str = "", start_time: str = "08:00", hours: int = 2):
    data, is_error = tools.execute("get_weather", {
        "place": place or None, "latitude": latitude, "longitude": longitude,
        "date": date or None, "start_time": start_time, "hours": hours,
    })
    if is_error:
        raise HTTPException(400, data.get("error"))
    return data


@app.delete("/api/places/{name}")
def delete_place(name: str):
    storage.delete_place(name)
    return {"ok": True}


# ── Брифинг и разбор недели ─────────────────────────────




@app.post("/api/special/{kind}")
def special_conversation(kind: str):
    """Открыть сегодняшний брифинг или разбор недели; если его ещё нет — создать."""
    if kind not in ("brief", "review"):
        raise HTTPException(404, tr("err_unknown_type"))
    today = datetime.date.today()
    day = today.isoformat()
    existing = storage.find_conversation(kind, day)
    if existing:
        return {"id": existing["id"], "created": False}
    label = tr("brief") if kind == "brief" else tr("review")
    conv_id = storage.create_conversation(tr("special_title", label=label, day=today.day, month=tr("months_gen")[today.month - 1]), kind, day)
    return {"id": conv_id, "created": True, "message": label}


# ── План ─────────────────────────────────────────────────

@app.get("/api/plan")
def plan(date_from: str = "", date_to: str = ""):
    data, is_error = tools.execute("get_plan", {"date_from": date_from or None, "date_to": date_to or None})
    if is_error:
        raise HTTPException(400, data.get("error"))
    return data


@app.patch("/api/plan/{workout_id}")
def patch_plan(workout_id: int, body: PlanPatch):
    data, is_error = tools.execute("update_planned_workout", {"id": workout_id, **body.model_dump(exclude_none=True)})
    if is_error:
        raise HTTPException(400, data.get("error"))
    return data


@app.delete("/api/plan/{workout_id}")
def delete_plan(workout_id: int):
    storage.delete_planned(workout_id)
    return {"ok": True}


# ── Ощущения после заезда ────────────────────────────────

@app.get("/api/latest-activity")
def latest_activity():
    data, is_error = tools.execute("get_recent_activities", {"days": 21, "limit": 1})
    if is_error:
        return {"error": data.get("error")}
    acts = data.get("activities") or []
    if not acts:
        return {"activity": None}
    a = acts[0]
    fb = storage.feedback_map([a["id"]]).get(a["id"])
    return {"activity": a, "feedback": fb}


@app.post("/api/feedback")
def feedback(body: FeedbackIn):
    data, is_error = tools.execute("save_ride_feedback", body.model_dump(exclude_none=True))
    if is_error:
        raise HTTPException(400, data.get("error"))
    return data


# ── Сводка на сегодня ────────────────────────────────────

_today_cache: dict = {"at": 0.0, "data": None}


@app.get("/api/today")
def today(refresh: bool = False):
    if not refresh and _today_cache["data"] and time.time() - _today_cache["at"] < 600:
        return _today_cache["data"]
    data, is_error = tools.execute("get_wellness", {"days": 7})
    profile = storage.get_profile()
    plan = agent.plan_position(profile, for_ui=True)
    result = {"plan": plan}
    if is_error:
        result["error"] = data.get("error")
    else:
        days = data.get("days") or []
        result["latest"] = days[-1] if days else None
        result["hrv_avg"] = data.get("hrv_avg")
        result["hrv_trend"] = [d.get("hrv") for d in days]
    _today_cache.update(at=time.time(), data=result)
    return result


if __name__ == "__main__":
    print(f"\n  Home Trainer: http://{'localhost' if config.HOST == '127.0.0.1' else config.HOST}:{config.PORT}")
    print(f"  Model: {config.MODEL} | Language: {config.LANGUAGE}")
    if not config.ANTHROPIC_API_KEY:
        print("  ⚠ ANTHROPIC_API_KEY is not set in .env — the chat will not work")
    if not (config.INTERVALS_API_KEY and config.INTERVALS_ATHLETE_ID):
        print("  ⚠ Intervals.icu keys are not set in .env — workout data is unavailable")
    print("  Ctrl+C to stop\n")
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="warning")
