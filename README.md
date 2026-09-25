# Home Trainer

A local AI coaching agent for road cycling, built on Claude. It pulls data from Intervals.icu on its own (workouts, WHOOP recovery data) and weather forecasts from Open-Meteo, keeps a training plan, and remembers your conversations and key facts about you as an athlete.

The interface and the coach are available in English and Russian; you choose the language during setup.

## Setup

```bash
git clone https://github.com/jehrr/home-trainer.git
cd home-trainer
python3 -m pip install -r requirements.txt
python3 configure.py
```

`configure.py` asks for the interface language (English or Russian) and your keys, and writes them to `.env`:

- **Intervals.icu API key** — Intervals.icu → Settings → Developer Settings → API Key
- **Athlete id** — from your Intervals.icu profile URL, e.g. `i123456`
- **Anthropic API key** — console.anthropic.com → API Keys

You can also copy `.env.example` to `.env` and fill it in by hand. To change the language later, set `LANGUAGE=en` or `LANGUAGE=ru` in `.env` and restart.

Python 3.9 or newer is required.

## Run

```bash
python3 app.py
```

Then open http://localhost:8765.

## Features

- **Morning briefing** — one button in the sidebar. The coach checks last night's recovery, today's planned workout, recent training load, and the weather at your training location, and opens with a verdict: as planned, go easier, move indoors, reschedule, or rest. One briefing per day; pressing the button again opens the existing one.
- **Training plan** — stored locally. The coach builds and reschedules workouts through the chat; the Plan panel shows the schedule and statuses.
- **Plan vs. actual** — completed, partial, missed, and unplanned sessions. Statuses update automatically.
- **Weekly review** — weekly volume and load, intensity distribution, aerobic decoupling on long rides, best efforts and an FTP estimate, fitness and form trends, and recommendations for the next week.
- **Post-ride feedback** — the "Last ride" block in the sidebar lets you log RPE and how you felt. For activities with no data (imported from Strava), you can also enter duration and average heart rate. You can simply tell the coach in the chat as well.
- **Weather and places** — hourly forecast for your workout window and management of saved training locations, by name or by coordinates.

To have the morning briefing check the weather automatically, set your usual training location and start time in the profile panel, or specify them for individual workouts in the plan.

## Getting started

1. Save your training locations in "Weather and places" and set your usual location and start time in the profile panel.
2. Ask the coach to build a plan, either with the button in the Plan panel or in your own words, e.g. "build a two-week plan, 6 hours a week, long ride on Saturday".
3. Press "Morning briefing" in the morning, rate your ride in the "Last ride" block afterwards, and run the "Weekly review" at the end of the week.

Everything the coach knows about you can be viewed and edited in the profile panel.

## How it works

| File | Purpose |
|---|---|
| `app.py` | Web server: streaming chat, conversations, plan, memory, weather endpoints |
| `agent.py` | Claude tool-use loop, context assembly, history compaction |
| `tools.py` | Coach tools: workouts, recovery, plan, analytics, feedback, weather, memory |
| `intervals.py` | Intervals.icu API client |
| `weather.py` | Open-Meteo forecast and geocoding |
| `storage.py` | SQLite storage in `data/coach.db` |
| `prompts/<lang>/coach.md` | Coach persona and rules, per language — edit without touching the code |
| `prompts/<lang>/plan.md` | Training methodology and plan reference |
| `i18n.py`, `static/i18n.js` | Server and interface translations |
| `configure.py` | Setup wizard that creates `.env` |

Instead of stuffing all data into the prompt, the coach calls tools only when a question requires them.

Memory works in three layers: full conversations are stored in the database; when a conversation grows long, its older part is condensed into a summary; persistent facts (FTP, weight, places, injuries) are saved to the athlete profile and notes and are available in every conversation.

Replies are generated in a background thread, so a long answer is still completed and saved if you reload or close the page.

## Access from your phone

Set `HOST=0.0.0.0` in `.env`, restart, and open `http://<your-computer-IP>:8765` on your phone. There is no authentication, so use this only on a trusted home network.

## Models

| `MODEL` value | Notes |
|---|---|
| `claude-sonnet-5` | Default. Good balance of quality, speed, and cost |
| `claude-opus-5-5` | Deeper analysis and season planning; slower and more expensive |
| `claude-haiku-4-5-20251001` | Fastest and cheapest; weaker at complex analysis |

`SUMMARY_MODEL` (default `claude-haiku-4-5-20251001`) is used only to condense long conversations. If a model isn't available for your key, the coach will return a "model not found" error; switch `MODEL` back and restart.

## Limitations

Intervals.icu does not return activities imported from Strava through its API. The coach detects such activities and asks you to describe them instead.

## Security

`.gitignore` uses an allow-list: everything is ignored except the project files, so `.env`, the database, and any other files in the folder never end up in git. If you add a new project file, add a matching `!/filename` line to `.gitignore`.
