# Privacy Policy

_Last updated: October 8, 2026_

Home Trainer is an open-source application that each user runs on their own computer. There is no hosted service: the author of this project does not operate any server that receives, stores or processes your data.

## What data the app accesses

With your permission, the app reads:

- **From WHOOP** (via the WHOOP Developer API, scopes you approve during sign-in): workouts (sport, time, duration, strain, heart rate, heart-rate zones, calories, distance), and, if granted, recovery, sleep, cycle, profile and body measurement data.
- **From Intervals.icu**, with the API key you provide: activities, wellness data and athlete settings.
- **From Open-Meteo**: weather forecasts and place search for locations you choose. Only coordinates or place names are sent.

## Where your data is stored

Everything stays on your computer, in the app folder:

- `.env` — your API keys and WHOOP client credentials;
- `data/coach.db` — conversations with the coach, your training plan, profile, notes, saved places and post-ride feedback;
- `data/whoop_tokens.json` — WHOOP access and refresh tokens.

These files are excluded from version control and are never uploaded anywhere by the app.

## Who receives your data

To generate the coach's replies, the app sends the relevant part of your data — your messages, conversation history, profile, notes and the training, recovery, plan and weather data the coach requests — to the **Anthropic API** using your own API key. This processing is governed by [Anthropic's policies](https://www.anthropic.com/legal). No other third parties receive your data. The app does not sell, share, or use your data for advertising, and contains no analytics or tracking.

## Your control

- **Revoke WHOOP access:** press "Disconnect" in the app (this deletes the stored tokens), and/or remove the app's access in your WHOOP account settings.
- **Delete your data:** delete the `data/` folder and the `.env` file. Conversations, notes and places can also be deleted individually in the app.
- **Stop all access:** stop the app and revoke the API keys in Intervals.icu, WHOOP and Anthropic.

## Changes

Changes to this policy are published in this file in the project repository.

## Contact

Questions: open an issue at https://github.com/jehrr/home-trainer/issues
