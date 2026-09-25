"use strict";
// Переводы интерфейса. Язык берётся из <html lang>, его выставляет сервер по LANGUAGE в .env.

const I18N = {
  ru: {
    title: "Тренер",
    close: "Закрыть", open_panel: "Открыть панель", close_panel: "Закрыть панель",
    loading: "Загружаю…", refresh: "Обновить", save: "Сохранить", cancel: "Отмена", delete: "Удалить",
    edit: "Изменить", find: "Найти", add: "Добавить", send: "Отправить",
    today_state: "Состояние сегодня", g_hrv: "HRV", g_sleep: "сон, ч", g_rhr: "пульс покоя", g_form: "форма",
    today_data: "Данные за {date}", today_data_avg: "Данные за {date}, средний HRV за неделю {avg}",
    no_recovery: "Нет данных восстановления", recovery_failed: "Не удалось загрузить данные восстановления",
    last_ride: "Последний заезд", brief: "Утренний брифинг", plan: "План", review: "Разбор недели",
    weather_places: "Погода и места", about_me: "Обо мне", dialogs: "Диалоги", new_chat: "Новый диалог",
    message_placeholder: "Сообщение тренеру", message_label: "Сообщение тренеру",
    delete_chat_label: "Удалить диалог «{title}»", delete_chat_confirm: "Удалить диалог «{title}»?",
    empty_title: "О чём поговорим?",
    empty_text: "Тренер сам посмотрит тренировки, восстановление, план и погоду, когда это нужно для ответа.",
    suggestions: [
      "Что у меня сегодня по плану и готов ли я к нему?",
      "Разбери последнюю тренировку",
      "Как я восстановился за неделю?",
      "Завтра еду утром — посмотри погоду и скажи, что надеть",
    ],
    thinking: "Думаю…", still_preparing: "Тренер ещё готовит ответ…",
    no_answer: "Ответ на этот вопрос не пришёл.", retry: "Повторить", answer_failed: "Ответ не получен: {msg}",
    // Память
    memory_title: "Что тренер обо мне знает", profile: "Профиль", notes: "Заметки",
    notes_empty: "Пока пусто. Тренер добавляет сюда важные факты сам, можно дописать и вручную.",
    places_count: "Сохранено мест: {n}. ", places_hint: "Места настраиваются в меню «Погода и места».",
    note_placeholder: "Например: болит левое колено после длинных подъёмов",
    saved: "Сохранено", save_failed: "Не сохранилось: {msg}",
    unsaved_confirm: "Изменения в профиле не сохранены. Закрыть без сохранения?",
    // Погода и места
    forecast_title: "Прогноз на тренировку", place: "Место", date: "Дата", start: "Старт", hours: "Часов",
    show_forecast: "Показать прогноз", my_places: "Мои места", add_place: "Добавить место",
    add_place_hint: "Найди по названию или вставь координаты, например из Google Maps:",
    geo_placeholder: "Название: Адлер, Лазаревское, Красная Поляна",
    place_name: "Имя места", place_name_ph: "Побережье", latitude: "Широта", longitude: "Долгота",
    place_note: "Описание для тренера", place_note_ph: "Ровная дорога вдоль моря, ветрено", save_place: "Сохранить место",
    no_places: "Пока нет сохранённых мест. Добавь первое ниже.", add_place_first: "Сначала добавь место ниже",
    delete_place_confirm: "Удалить место «{name}»?",
    flag_storm: "гроза", flag_rain: "дождь до {p}%", flag_rain_maybe: "возможен дождь {p}%",
    flag_wind: "сильный ветер {g} км/ч", flag_gusts: "опасные порывы {g} км/ч", flag_cold: "холодно", flag_heat: "жара",
    feels_from: "{a}…{b}°, ощущается от {f}°", sunset_at: "закат в {t}",
    th_hour: "Час", th_temp: "Темп.", th_precip: "Осадки", th_wind: "Ветер/порывы", th_cond: "Условия",
    discuss: "Обсудить с тренером", today_word: "Сегодня", tomorrow_word: "Завтра",
    discuss_msg: "{day} в {time} тренируюсь: место «{place}», около {hours} ч. Что надеть и какую тренировку делать с учётом погоды и восстановления?",
    loading_forecast: "Загружаю прогноз…", forecast_failed: "Прогноз не загрузился: {msg}",
    searching: "Ищу…", nothing_found: "Ничего не нашлось. Попробуй другое написание или введи координаты.",
    search_failed: "Поиск не удался: {msg}",
    bad_coords: "Проверь координаты: широта от −90 до 90, долгота от −180 до 180", place_saved: "«{name}» сохранено",
    kmh: "км/ч",
    // Последний заезд
    feel: ["тяжело", "так себе", "нормально", "хорошо", "отлично"],
    strava_ride: "Тренировка из Strava", ride: "Тренировка", min: "мин",
    no_data_manual: "Данных нет, можно вписать вручную", edit_rating: "Изменить оценку", how_was_it: "Как прошло?",
    rpe_label: "Насколько тяжело, 1–10", feel_label: "Самочувствие", minutes_ph: "минут", avg_hr_ph: "ср. пульс",
    ride_note_ph: "Комментарий: ноги, дыхание, что мешало",
    // План
    plan_ask: "Составить план на неделю с тренером",
    plan_hint: "Тренер добавляет и переносит тренировки сам по просьбе в чате. Статусы обновляются при сверке плана с фактом. Если панель была открыта во время ответа, закрой и открой её снова.",
    plan_empty: "План пуст. Нажми кнопку выше или напиши тренеру, например: «составь план на две недели, 6 часов в неделю, длинная в субботу».",
    plan_ask_msg: "Составь мне план на следующую неделю с учётом текущей формы, восстановления и моих мест и добавь его в план.",
    today_prefix: "Сегодня, ", indoor: "станок", status: "Статус", delete_workout_confirm: "Удалить тренировку из плана?",
    statuses: { planned: "запланировано", done: "выполнено", partial: "частично", missed: "пропущено", skipped: "отменено", moved: "перенесено" },
    weekdays: ["Воскресенье", "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"],
    months_gen: ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"],
    day_label: "{weekday}, {day} {month}",
    // Статус
    intervals_keys: "ключи Intervals.icu", missing_env: "Не заданы в .env: {list}", server_down: "Сервер недоступен",
  },

  en: {
    title: "Trainer",
    close: "Close", open_panel: "Open panel", close_panel: "Close panel",
    loading: "Loading…", refresh: "Refresh", save: "Save", cancel: "Cancel", delete: "Delete",
    edit: "Edit", find: "Search", add: "Add", send: "Send",
    today_state: "Today's status", g_hrv: "HRV", g_sleep: "sleep, h", g_rhr: "resting HR", g_form: "form",
    today_data: "Data for {date}", today_data_avg: "Data for {date}, 7-day HRV average {avg}",
    no_recovery: "No recovery data", recovery_failed: "Couldn't load recovery data",
    last_ride: "Last ride", brief: "Morning briefing", plan: "Plan", review: "Weekly review",
    weather_places: "Weather & places", about_me: "About me", dialogs: "Conversations", new_chat: "New conversation",
    message_placeholder: "Message your coach", message_label: "Message your coach",
    delete_chat_label: "Delete conversation “{title}”", delete_chat_confirm: "Delete conversation “{title}”?",
    empty_title: "What shall we talk about?",
    empty_text: "The coach checks your workouts, recovery, plan and weather on its own whenever an answer needs them.",
    suggestions: [
      "What's on my plan today, and am I ready for it?",
      "Review my last workout",
      "How well did I recover this week?",
      "Riding tomorrow morning — check the weather and tell me what to wear",
    ],
    thinking: "Thinking…", still_preparing: "The coach is still preparing an answer…",
    no_answer: "No answer came back for this question.", retry: "Retry", answer_failed: "No answer received: {msg}",
    memory_title: "What the coach knows about me", profile: "Profile", notes: "Notes",
    notes_empty: "Nothing here yet. The coach adds important facts on its own; you can add your own too.",
    places_count: "Saved places: {n}. ", places_hint: "Places are managed in the “Weather & places” menu.",
    note_placeholder: "e.g. left knee hurts after long climbs",
    saved: "Saved", save_failed: "Not saved: {msg}",
    unsaved_confirm: "Profile changes aren't saved. Close without saving?",
    forecast_title: "Workout forecast", place: "Place", date: "Date", start: "Start", hours: "Hours",
    show_forecast: "Show forecast", my_places: "My places", add_place: "Add a place",
    add_place_hint: "Search by name or paste coordinates, e.g. from Google Maps:",
    geo_placeholder: "Name: Boulder, Girona, Mallorca",
    place_name: "Place name", place_name_ph: "Coast", latitude: "Latitude", longitude: "Longitude",
    place_note: "Notes for the coach", place_note_ph: "Flat coastal road, often windy", save_place: "Save place",
    no_places: "No saved places yet. Add your first one below.", add_place_first: "Add a place below first",
    delete_place_confirm: "Delete place “{name}”?",
    flag_storm: "thunderstorm", flag_rain: "rain up to {p}%", flag_rain_maybe: "possible rain {p}%",
    flag_wind: "strong wind {g} km/h", flag_gusts: "dangerous gusts {g} km/h", flag_cold: "cold", flag_heat: "heat",
    feels_from: "{a}…{b}°, feels like {f}° at the lowest", sunset_at: "sunset at {t}",
    th_hour: "Hour", th_temp: "Temp", th_precip: "Precip", th_wind: "Wind/gusts", th_cond: "Conditions",
    discuss: "Discuss with the coach", today_word: "Today", tomorrow_word: "Tomorrow",
    discuss_msg: "{day} at {time} I'm riding at “{place}” for about {hours} h. What should I wear and what workout should I do, given the weather and my recovery?",
    loading_forecast: "Loading forecast…", forecast_failed: "Forecast failed to load: {msg}",
    searching: "Searching…", nothing_found: "Nothing found. Try a different spelling or enter coordinates.",
    search_failed: "Search failed: {msg}",
    bad_coords: "Check the coordinates: latitude −90 to 90, longitude −180 to 180", place_saved: "“{name}” saved",
    kmh: "km/h",
    feel: ["awful", "meh", "okay", "good", "great"],
    strava_ride: "Strava activity", ride: "Workout", min: "min",
    no_data_manual: "No data — you can enter it manually", edit_rating: "Edit rating", how_was_it: "How did it go?",
    rpe_label: "How hard, 1–10", feel_label: "How you felt", minutes_ph: "minutes", avg_hr_ph: "avg HR",
    ride_note_ph: "Comment: legs, breathing, anything that got in the way",
    plan_ask: "Build this week's plan with the coach",
    plan_hint: "The coach adds and moves workouts when you ask in the chat. Statuses update when the plan is compared with what you actually did. If this panel was open during a reply, close and reopen it.",
    plan_empty: "The plan is empty. Press the button above or ask the coach, e.g. “build a two-week plan, 6 hours a week, long ride on Saturday”.",
    plan_ask_msg: "Build me a plan for next week based on my current form, recovery and saved places, and add it to the plan.",
    today_prefix: "Today, ", indoor: "indoor", status: "Status", delete_workout_confirm: "Delete this workout from the plan?",
    statuses: { planned: "planned", done: "done", partial: "partial", missed: "missed", skipped: "cancelled", moved: "moved" },
    weekdays: ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
    months_gen: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
    day_label: "{weekday}, {month} {day}",
    intervals_keys: "Intervals.icu keys", missing_env: "Missing in .env: {list}", server_down: "Server unavailable",
  },
};

const LANG = I18N[document.documentElement.lang] ? document.documentElement.lang : "ru";

function t(key, vars) {
  let v = I18N[LANG][key];
  if (v === undefined) v = I18N.ru[key];
  if (v === undefined) return key;
  if (typeof v !== "string" || !vars) return v;
  return v.replace(/\{(\w+)\}/g, (_, k) => (vars[k] !== undefined ? vars[k] : ""));
}

// Статичная разметка: data-i18n — текст, data-i18n-ph — placeholder, data-i18n-aria — aria-label
function applyI18n(root = document) {
  document.title = t("title");
  root.querySelectorAll("[data-i18n]").forEach((el) => (el.textContent = t(el.dataset.i18n)));
  root.querySelectorAll("[data-i18n-ph]").forEach((el) => el.setAttribute("placeholder", t(el.dataset.i18nPh)));
  root.querySelectorAll("[data-i18n-aria]").forEach((el) => el.setAttribute("aria-label", t(el.dataset.i18nAria)));
}
