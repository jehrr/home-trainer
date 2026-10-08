# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-10-08

First public release.

### Added

- Local AI cycling coach built on Claude with tool use: the coach fetches only the data a question needs.
- Intervals.icu integration: activities, intervals, power streams, wellness and fitness/fatigue/form.
- WHOOP integration via the WHOOP Developer API v2: workouts recorded without a bike computer, merged with Intervals.icu without double-counting; Strava placeholders replaced with WHOOP data.
- Weather forecasts from Open-Meteo for the workout window, saved training places by name or coordinates.
- Local training plan that the coach builds and reschedules in the chat, with a plan panel and statuses.
- Plan vs. actual comparison with automatic statuses.
- Morning briefing with a verdict: as planned, go easier, indoors, reschedule or rest.
- Weekly review: volume and load, intensity distribution, aerobic decoupling, best efforts and FTP estimate, fitness trends.
- Post-ride feedback (RPE, how you felt), including manual duration and heart rate for activities without data.
- Persistent memory: conversations in SQLite, automatic summaries of long conversations, athlete profile and notes.
- English and Russian interface and coach; setup wizard `configure.py`.
- Logo, favicon and social preview image.
- Background answer generation: replies are completed and saved even if the page is reloaded; retry for interrupted answers.

[0.1.0]: https://github.com/jehrr/home-trainer/releases/tag/v0.1.0
