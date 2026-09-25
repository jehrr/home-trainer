"""Тексты, которые сервер показывает пользователю или передаёт тренеру. Язык — LANGUAGE в .env."""
from __future__ import annotations

import config

STRINGS = {
    "ru": {
        # подписи действий тренера в чате
        "tool_labels": {
            "get_morning_snapshot": "Собираю утреннюю сводку",
            "get_recent_activities": "Смотрю последние тренировки",
            "get_activity_details": "Разбираю тренировку",
            "get_wellness": "Проверяю восстановление",
            "get_training_analysis": "Считаю аналитику за несколько недель",
            "get_plan": "Открываю план",
            "add_planned_workouts": "Добавляю в план",
            "update_planned_workout": "Меняю план",
            "delete_planned_workouts": "Удаляю из плана",
            "compare_plan_vs_actual": "Сверяю план с фактом",
            "save_ride_feedback": "Записываю ощущения",
            "get_weather": "Смотрю прогноз погоды",
            "save_place": "Сохраняю место",
            "update_profile": "Обновляю профиль",
            "add_note": "Записываю в заметки",
        },
        "brief": "Утренний брифинг",
        "review": "Разбор недели",
        "months_gen": ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
                       "сентября", "октября", "ноября", "декабря"],
        "special_title": "{label}, {day} {month}",
        "new_chat": "Новый диалог",
        # положение в плане
        "phases": ["фаза 1 — аэробная база", "фаза 2 — порог", "фаза 3 — VO2max", "фаза 4 — скорость и пик"],
        "plan_no_start": "Дата начала плана не задана — если это важно для ответа, спроси атлета и сохрани её.",
        "plan_no_start_ui": "Дата начала плана не указана. Её можно задать в разделе «Обо мне» или сказать тренеру.",
        "plan_bad_start": "Дата начала плана записана некорректно: {start}",
        "plan_future": "План начнётся {start}.",
        "plan_done": "16-недельный план завершён: с начала прошло {weeks} нед.",
        "plan_week": "Сейчас неделя {week} из 16, {phase}.",
        "plan_rest_week": " Разгрузочная неделя с FTP-тестом.",
        # системный промт
        "weekdays": ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"],
        "h_now": "## Сейчас", "h_profile": "## Профиль атлета", "h_notes": "## Заметки об атлете",
        "h_places": "## Сохранённые места тренировок", "none_yet": "- пока нет",
        "h_summary": "## Резюме более ранней части этого разговора",
        "summary_prompt": (
            "Ты ведёшь конспект разговора тренера по велоспорту с атлетом. Обнови резюме: объедини прежнее резюме "
            "и новый фрагмент. Сохрани факты о состоянии атлета, ключевые цифры (мощность, HRV, нагрузка), принятые "
            "решения и договорённости, открытые вопросы. Не больше 250 слов, по-русски, без вступлений.\n\n"
            "Прежнее резюме:\n{old}\n\nНовый фрагмент:\n{text}"
        ),
        "summary_none": "(нет)", "athlete": "Атлет", "coach": "Тренер",
        # ошибки
        "err_conv_not_found": "Диалог не найден",
        "err_empty_message": "Пустое сообщение",
        "err_busy": "Тренер ещё отвечает на предыдущее сообщение в этом диалоге",
        "err_nothing_to_retry": "Нечего повторять",
        "err_no_claude": "Нет связи с Claude API. Проверь интернет и попробуй ещё раз.",
        "err_no_anthropic_key": "Не задан ANTHROPIC_API_KEY в .env",
        "err_unknown_type": "Неизвестный тип",
        "err_place_name": "Нужно имя места",
        "err_coords": "Широта от −90 до 90, долгота от −180 до 180",
        "err_empty_note": "Пустая заметка",
        "err_unknown_param": "Неизвестный параметр",
        "err_place_missing": "Не указано место. Спроси атлета, где он будет тренироваться.",
        "err_place_not_found": "Место «{place}» не найдено. Уточни название или координаты.",
        # погода
        "compass": ["С", "СВ", "В", "ЮВ", "Ю", "ЮЗ", "З", "СЗ"],
        "weekdays_short": ["пн", "вт", "ср", "чт", "пт", "сб", "вс"],
        "wmo_code": "код {code}",
        "err_geocode": "Поиск места не удался: {e}",
        "err_bad_date": "Неверная дата {day!r}, нужен формат ГГГГ-ММ-ДД",
        "err_past": "Прогноз доступен только на сегодня и вперёд",
        "err_too_far": "Прогноз доступен максимум на {days} дней вперёд",
        "err_forecast": "Прогноз не загрузился: {e}",
        "err_no_hour": "Нет данных на указанный час",
        "wmo": {
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
        },
        # профиль
        "profile_labels": {
            "name": "имя", "age": "возраст, лет", "weight_kg": "вес, кг", "height_cm": "рост, см",
            "discipline": "дисциплина", "ftp_w": "текущий FTP, Вт", "ftp_goal_w": "целевой FTP, Вт",
            "max_hr": "максимальный пульс", "lthr": "пульс на пороге (LTHR)",
            "plan_start_date": "дата начала 16-недельного плана (ГГГГ-ММ-ДД)",
            "target_event": "целевой старт и дата", "weekly_hours": "доступно часов в неделю",
            "default_place": "обычное место тренировок (имя сохранённого места)",
            "default_start_time": "обычное время старта (ЧЧ:ММ)",
        },
    },

    "en": {
        "tool_labels": {
            "get_morning_snapshot": "Gathering the morning snapshot",
            "get_recent_activities": "Checking recent workouts",
            "get_activity_details": "Analysing the workout",
            "get_wellness": "Checking recovery",
            "get_training_analysis": "Crunching multi-week analytics",
            "get_plan": "Opening the plan",
            "add_planned_workouts": "Adding to the plan",
            "update_planned_workout": "Updating the plan",
            "delete_planned_workouts": "Removing from the plan",
            "compare_plan_vs_actual": "Comparing plan vs actual",
            "save_ride_feedback": "Saving your feedback",
            "get_weather": "Checking the forecast",
            "save_place": "Saving the place",
            "update_profile": "Updating your profile",
            "add_note": "Adding a note",
        },
        "brief": "Morning briefing",
        "review": "Weekly review",
        "months_gen": ["January", "February", "March", "April", "May", "June", "July", "August",
                       "September", "October", "November", "December"],
        "special_title": "{label}, {month} {day}",
        "new_chat": "New conversation",
        "phases": ["phase 1 — aerobic base", "phase 2 — threshold", "phase 3 — VO2max", "phase 4 — speed and peak"],
        "plan_no_start": "The plan start date is not set — if it matters for the answer, ask the athlete and save it.",
        "plan_no_start_ui": "Plan start date isn't set. You can set it under “About me” or tell the coach.",
        "plan_bad_start": "The plan start date is invalid: {start}",
        "plan_future": "The plan starts on {start}.",
        "plan_done": "The 16-week plan is complete: {weeks} weeks since the start.",
        "plan_week": "Week {week} of 16, {phase}.",
        "plan_rest_week": " Recovery week with an FTP test.",
        "weekdays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "h_now": "## Now", "h_profile": "## Athlete profile", "h_notes": "## Notes about the athlete",
        "h_places": "## Saved training locations", "none_yet": "- none yet",
        "h_summary": "## Summary of the earlier part of this conversation",
        "summary_prompt": (
            "You keep notes on a conversation between a cycling coach and an athlete. Update the summary by merging "
            "the previous summary with the new excerpt. Keep facts about the athlete's condition, key numbers (power, "
            "HRV, load), decisions and agreements, and open questions. At most 250 words, in English, no preamble.\n\n"
            "Previous summary:\n{old}\n\nNew excerpt:\n{text}"
        ),
        "summary_none": "(none)", "athlete": "Athlete", "coach": "Coach",
        "err_conv_not_found": "Conversation not found",
        "err_empty_message": "Empty message",
        "err_busy": "The coach is still answering the previous message in this conversation",
        "err_nothing_to_retry": "Nothing to retry",
        "err_no_claude": "Can't reach the Claude API. Check your connection and try again.",
        "err_no_anthropic_key": "ANTHROPIC_API_KEY is not set in .env",
        "err_unknown_type": "Unknown type",
        "err_place_name": "A place name is required",
        "err_coords": "Latitude must be −90 to 90, longitude −180 to 180",
        "err_empty_note": "Empty note",
        "err_unknown_param": "Unknown parameter",
        "err_place_missing": "No place given. Ask the athlete where they'll be training.",
        "err_place_not_found": "Place “{place}” not found. Try another name or coordinates.",
        "compass": ["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
        "weekdays_short": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "wmo_code": "code {code}",
        "err_geocode": "Place search failed: {e}",
        "err_bad_date": "Invalid date {day!r}, expected YYYY-MM-DD",
        "err_past": "Forecasts are only available for today and later",
        "err_too_far": "Forecasts are available at most {days} days ahead",
        "err_forecast": "Forecast failed to load: {e}",
        "err_no_hour": "No data for the requested hour",
        "wmo": {
            0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
            45: "fog", 48: "freezing fog",
            51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
            56: "freezing drizzle", 57: "heavy freezing drizzle",
            61: "light rain", 63: "rain", 65: "heavy rain",
            66: "freezing rain", 67: "heavy freezing rain",
            71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
            80: "light showers", 81: "showers", 82: "heavy showers",
            85: "snow showers", 86: "heavy snow showers",
            95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with heavy hail",
        },
        "profile_labels": {
            "name": "name", "age": "age, years", "weight_kg": "weight, kg", "height_cm": "height, cm",
            "discipline": "discipline", "ftp_w": "current FTP, W", "ftp_goal_w": "goal FTP, W",
            "max_hr": "max heart rate", "lthr": "threshold heart rate (LTHR)",
            "plan_start_date": "16-week plan start date (YYYY-MM-DD)",
            "target_event": "target event and date", "weekly_hours": "hours available per week",
            "default_place": "usual training location (saved place name)",
            "default_start_time": "usual start time (HH:MM)",
        },
    },
}


def tr(key: str, **kwargs):
    value = STRINGS[config.LANGUAGE].get(key, STRINGS["ru"].get(key, key))
    if isinstance(value, str) and kwargs:
        return value.format(**kwargs)
    return value
