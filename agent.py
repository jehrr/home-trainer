"""Агент-тренер: цикл вызова Claude с инструментами, сборка контекста, сжатие истории."""
from __future__ import annotations

import copy
import json
import traceback
from datetime import date, datetime
from typing import Iterator

import anthropic

import config
import storage
import tools
from i18n import tr

_client: anthropic.Anthropic | None = None

PHASE_WEEKS = [(1, 4), (5, 8), (9, 12), (13, 16)]


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        if not config.ANTHROPIC_API_KEY:
            raise RuntimeError(tr("err_no_anthropic_key"))
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


# ── Системный промт ──────────────────────────────────────

_prompt_warned = False


def _static_prompt() -> str:
    """Правила тренера и план. Ищем в папке своего языка, затем в старом месте, затем в другом языке."""
    global _prompt_warned
    other = "en" if config.LANGUAGE == "ru" else "ru"
    for folder in (config.PROMPTS_DIR / config.LANGUAGE, config.PROMPTS_DIR, config.PROMPTS_DIR / other):
        parts = [(folder / name).read_text(encoding="utf-8").strip()
                 for name in ("coach.md", "plan.md") if (folder / name).exists()]
        parts = [p for p in parts if p]
        if parts:
            if folder != config.PROMPTS_DIR / config.LANGUAGE and not _prompt_warned:
                print(f"  ⚠ prompts/{config.LANGUAGE}/ not found, using {folder}", flush=True)
                _prompt_warned = True
            return "\n\n".join(parts)
    if not _prompt_warned:
        print(f"  ⚠ No coach prompts found in {config.PROMPTS_DIR} — the coach will work without its rules", flush=True)
        _prompt_warned = True
    return ""


def plan_position(profile: dict, for_ui: bool = False) -> str:
    start = profile.get("plan_start_date") or ""
    if not start:
        return tr("plan_no_start_ui" if for_ui else "plan_no_start")
    try:
        days = (date.today() - date.fromisoformat(start)).days
    except ValueError:
        return tr("plan_bad_start", start=start)
    if days < 0:
        return tr("plan_future", start=start)
    week = days // 7 + 1
    if week > 16:
        return tr("plan_done", weeks=week - 1)
    phase = tr("phases")[next(i for i, (lo, hi) in enumerate(PHASE_WEEKS) if lo <= week <= hi)]
    rest = tr("plan_rest_week") if week % 4 == 0 else ""
    return tr("plan_week", week=week, phase=phase) + rest


def _dynamic_prompt(conversation: dict) -> str:
    profile = storage.get_profile()
    now = datetime.now()
    lines = [
        f"{tr('h_now')}\n{now.strftime('%Y-%m-%d %H:%M')}, {tr('weekdays')[now.weekday()]}.",
        plan_position(profile),
        "\n" + tr("h_profile"),
    ]
    for key, label in storage.PROFILE_KEYS.items():
        if profile.get(key):
            lines.append(f"- {label}: {profile[key]}")

    notes = storage.list_notes()
    if notes:
        lines.append("\n" + tr("h_notes"))
        lines += [f"- {n['text']}" for n in notes]

    places = storage.list_places()
    lines.append("\n" + tr("h_places"))
    if places:
        for p in places:
            note = f" — {p['note']}" if p.get("note") else ""
            lines.append(f"- {p['name']} ({p['latitude']}, {p['longitude']}){note}")
    else:
        lines.append(tr("none_yet"))

    if conversation.get("summary"):
        lines.append("\n" + tr("h_summary") + "\n" + conversation["summary"])
    return "\n".join(lines)


def build_system(conversation: dict) -> list[dict]:
    blocks = []
    static = _static_prompt()
    if static:  # API не принимает пустой блок, тем более с кэшем
        blocks.append({"type": "text", "text": static, "cache_control": {"type": "ephemeral"}})
    blocks.append({"type": "text", "text": _dynamic_prompt(conversation)})
    return blocks


def _tools_with_cache() -> list[dict]:
    t = copy.deepcopy(tools.TOOLS)
    t[-1]["cache_control"] = {"type": "ephemeral"}
    return t


# ── История сообщений ────────────────────────────────────

def _as_blocks(content) -> list[dict]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return list(content)


def sanitize(messages: list[dict]) -> list[dict]:
    """Приводит историю к виду, который примет API.

    - склеивает подряд идущие сообщения одной роли (например, после сбоя посреди ответа);
    - убирает вызовы инструментов без результатов и результаты без вызовов;
    - гарантирует, что история начинается с сообщения пользователя.
    """
    merged: list[dict] = []
    for m in messages:
        blocks = _as_blocks(m["content"])
        if merged and merged[-1]["role"] == m["role"]:
            merged[-1]["content"] += blocks
        else:
            merged.append({"role": m["role"], "content": blocks})

    for i, m in enumerate(merged):
        if m["role"] != "assistant":
            continue
        call_ids = {b["id"] for b in m["content"] if b.get("type") == "tool_use"}
        if not call_ids:
            continue
        nxt = merged[i + 1] if i + 1 < len(merged) else None
        answered = {b.get("tool_use_id") for b in (nxt["content"] if nxt and nxt["role"] == "user" else [])
                    if b.get("type") == "tool_result"}
        missing = call_ids - answered
        if missing:
            m["content"] = [b for b in m["content"] if not (b.get("type") == "tool_use" and b["id"] in missing)]

    valid_ids = {b["id"] for m in merged if m["role"] == "assistant" for b in m["content"] if b.get("type") == "tool_use"}
    for m in merged:
        if m["role"] == "user":
            m["content"] = [b for b in m["content"]
                            if b.get("type") != "tool_result" or b.get("tool_use_id") in valid_ids]

    merged = [m for m in merged if m["content"]]
    while merged and merged[0]["role"] != "user":
        merged.pop(0)
    # повторная склейка после чисток
    result: list[dict] = []
    for m in merged:
        if result and result[-1]["role"] == m["role"]:
            result[-1]["content"] += m["content"]
        else:
            result.append(m)
    return result


def _with_cache_marker(messages: list[dict]) -> list[dict]:
    msgs = copy.deepcopy(messages)
    if msgs and msgs[-1]["content"]:
        last = msgs[-1]["content"][-1]
        if last.get("type") in ("text", "tool_result"):
            last["cache_control"] = {"type": "ephemeral"}
    return msgs


def build_messages(conversation: dict) -> list[dict]:
    rows = storage.get_messages(conversation["id"], after_turn=conversation.get("summarized_turns", 0))
    return sanitize(rows)


# ── Сжатие истории ───────────────────────────────────────

def _render_for_summary(rows: list[dict]) -> str:
    out = []
    for r in rows:
        for b in _as_blocks(r["content"]):
            t = b.get("type")
            if t == "text" and b.get("text", "").strip():
                who = tr("athlete") if r["role"] == "user" else tr("coach")
                out.append(f"{who}: {b['text'].strip()}")
            elif t == "tool_use":
                out.append(f"[тренер вызвал {b['name']} {json.dumps(b.get('input', {}), ensure_ascii=False)}]")
            elif t == "tool_result":
                text = b.get("content") if isinstance(b.get("content"), str) else json.dumps(b.get("content"), ensure_ascii=False)
                out.append(f"[результат: {text[:400]}]")
    return "\n".join(out)


def maybe_compact(conv_id: int) -> None:
    conv = storage.get_conversation(conv_id)
    if not conv:
        return
    rows = storage.get_messages(conv_id, after_turn=conv["summarized_turns"])
    turns = sorted({r["turn"] for r in rows})
    if len(turns) <= config.HISTORY_COMPACT_AT:
        return
    cutoff = turns[-config.HISTORY_KEEP_TURNS - 1]
    old_rows = [r for r in rows if r["turn"] <= cutoff]
    transcript = _render_for_summary(old_rows)
    prompt = tr("summary_prompt", old=conv["summary"] or tr("summary_none"), text=transcript)
    try:
        resp = client().messages.create(model=config.SUMMARY_MODEL, max_tokens=700,
                                        messages=[{"role": "user", "content": prompt}])
        summary = "".join(b.text for b in resp.content if b.type == "text").strip()
    except Exception as e:  # сжатие необязательно: при ошибке просто попробуем в следующий раз
        print(f"  сжатие истории не удалось: {e}")
        return
    if summary:
        storage.update_summary(conv_id, summary, cutoff)


# ── Основной цикл ────────────────────────────────────────

def _block_to_dict(b) -> dict | None:
    if b.type == "text":
        return {"type": "text", "text": b.text} if b.text else None
    if b.type == "tool_use":
        return {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
    return None


def run_turn(conv_id: int, user_text: str | None) -> Iterator[dict]:
    """Один ответ тренера. Отдаёт события для интерфейса: text, tool, tool_done, error, done.

    user_text=None — повторить ответ на последний вопрос, если прошлая попытка сорвалась.
    """
    conv = storage.get_conversation(conv_id)
    if not conv:
        yield {"type": "error", "message": tr("err_conv_not_found")}
        return

    if user_text is None:
        turn = storage.next_turn(conv_id) - 1
        if turn < 1:
            yield {"type": "error", "message": tr("err_nothing_to_retry")}
            return
    else:
        turn = storage.next_turn(conv_id)
        storage.add_message(conv_id, turn, "user", user_text)
    if user_text and turn == 1 and conv.get("kind", "chat") == "chat":
        title = user_text.strip().replace("\n", " ")
        storage.rename_conversation(conv_id, title[:60] + ("…" if len(title) > 60 else ""))

    try:
        api = client()
        for round_no in range(config.MAX_TOOL_ROUNDS + 1):
            conv = storage.get_conversation(conv_id)
            params = dict(
                model=config.MODEL,
                max_tokens=config.MAX_TOKENS,
                system=build_system(conv),
                tools=_tools_with_cache(),
                messages=_with_cache_marker(build_messages(conv)),
            )
            if round_no == config.MAX_TOOL_ROUNDS:
                params["tool_choice"] = {"type": "none"}

            with api.messages.stream(**params) as stream:
                for event in stream:
                    if event.type == "text":
                        yield {"type": "text", "delta": event.text}
                final = stream.get_final_message()

            blocks = [d for d in (_block_to_dict(b) for b in final.content) if d]
            calls = [b for b in blocks if b["type"] == "tool_use"]
            if final.stop_reason != "tool_use":
                blocks = [b for b in blocks if b["type"] != "tool_use"]
                calls = []
            if blocks:
                storage.add_message(conv_id, turn, "assistant", blocks)
            if not calls:
                break

            results = []
            for call in calls:
                yield {"type": "tool", "name": call["name"],
                       "label": tools.TOOL_LABELS.get(call["name"], call["name"]), "input": call["input"]}
                output, is_error = tools.execute(call["name"], call["input"])
                results.append({
                    "type": "tool_result",
                    "tool_use_id": call["id"],
                    "content": json.dumps(output, ensure_ascii=False),
                    **({"is_error": True} if is_error else {}),
                })
                yield {"type": "tool_done", "name": call["name"], "ok": not is_error,
                       **({"error": output.get("error")} if is_error else {})}
            storage.add_message(conv_id, turn, "user", results)
    except anthropic.APIStatusError as e:
        print(f"  ✗ Claude API {e.status_code}: {getattr(e, 'message', e)}", flush=True)
        yield {"type": "error", "message": f"Claude API {e.status_code}: {getattr(e, 'message', e)}"}
    except anthropic.APIConnectionError as e:
        print(f"  ✗ Нет связи с Claude API: {e}", flush=True)
        yield {"type": "error", "message": tr("err_no_claude")}
    except Exception as e:
        traceback.print_exc()
        yield {"type": "error", "message": f"{type(e).__name__}: {e}"}

    yield {"type": "done"}
    maybe_compact(conv_id)


def transcript_for_ui(conv_id: int) -> list[dict]:
    """История диалога в виде, удобном интерфейсу: реплики атлета и тренера с пометками об инструментах."""
    rows = storage.get_messages(conv_id)
    out: list[dict] = []
    for r in rows:
        blocks = _as_blocks(r["content"])
        if r["role"] == "user":
            text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
            if text:
                out.append({"role": "user", "text": text, "tools": []})
            continue
        if not out or out[-1]["role"] != "assistant":
            out.append({"role": "assistant", "text": "", "tools": []})
        for b in blocks:
            if b.get("type") == "text":
                out[-1]["text"] += (("\n\n" if out[-1]["text"] else "") + b["text"])
            elif b.get("type") == "tool_use":
                out[-1]["tools"].append(tools.TOOL_LABELS.get(b["name"], b["name"]))
    return out


def needs_answer(conv_id: int) -> bool:
    """True, если на последний вопрос атлета так и не пришёл текстовый ответ."""
    rows = storage.get_messages(conv_id)
    if not rows:
        return False
    last_turn = rows[-1]["turn"]
    for r in rows:
        if r["turn"] == last_turn and r["role"] == "assistant":
            if any(b.get("type") == "text" and b.get("text", "").strip() for b in _as_blocks(r["content"])):
                return False
    return True
