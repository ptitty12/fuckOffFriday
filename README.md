# fuck off friday

Init (in a british accent).

Is it just you, or is nobody working today? The meter watches US Google search
interest for Salesforce, Oracle and Workday, software nobody googles for fun,
and compares today with a normal day of the same weekday. Below normal means
people are not working.

## Running it

```sh
cp .env.example .env        # add your DataForSEO credentials
docker compose up -d        # web on :5000 + an updater that grabs every 3h
```

Without Docker:

```sh
pip install -r requirements.txt
python update_db.py         # one grab, archived in full
python app.py               # http://localhost:5000
```

`update_db.py` is safe to run as often as you like (cron, a loop, by hand);
`scheduler.py` just calls it on a fixed cadence. `python update_db.py --rebuild`
recomputes the derived tables from the archive if the scoring ever changes.

## How the score works

Every grab asks for the last 90 days of daily interest per company. Google
normalises each pull to its own 0 to 100 scale, so nothing is ever compared
across grabs; all maths happens inside one grab and only ratios leave it.

- **Baseline.** For a date, the median of the same weekday over the complete
  days of that grab (the date itself excluded). A Friday is only ever judged
  against other Fridays.
- **Score.** `value / baseline - 1`, averaged across companies, as a percent.
- **Settled score.** A day's score from the most recent grab in which it was a
  complete day. This is what the history chart and weekday profile use.

### The partial-day problem, and why old grabs are kept

Google reports the current day with only the hours it has seen so far. A grab
at 9am contains about a third of the day, so today's raw score always looks
like a disaster. That was the "artificially low" number.

Every pull is now archived verbatim (`grabs` + `grab_values`). Each grab's last
day is stored as a *partial reading*. Once that day settles (a later grab sees
it complete), the pair tells us what fraction of the day's relative level was
visible at that hour. Today's reading is divided by the median of those
completion factors from grabs taken within ±90 minutes of the same local hour,
preferring the same weekday when there are at least three, otherwise any day of
the same type (weekday / weekend). Until three comparable samples exist, the
headline falls back to the last settled day and today's number is shown as a
raw, uncalibrated reading.

Grabbing more often (the updater defaults to every 3 hours) fills the
calibration table faster and lets the meter move during the day. The "How it
works" section on the site shows how many samples exist per hour band.

## Layout

| file | what |
|---|---|
| `scoring.py` | pure maths: baselines, ratios, calibration, weekday profile, moods |
| `database.py` | SQLite schema, grab archive, derived tables, legacy import |
| `trends.py` | DataForSEO Google Trends client |
| `meter.py` | turns the database into the JSON the page shows |
| `update_db.py` / `scheduler.py` | take a grab once / on a cadence |
| `app.py` | Flask routes: `/`, `/api/dashboard`, `/api/today`, `/api/history`, `/api/profile`, `/api/status` |
| `static/`, `templates/` | the site, plain HTML/CSS/JS |
| `tests/` | `pytest` |

The v1 tables (`t_series`, `productivity`) and `allHistoricals.csv` are
imported once as legacy grabs so the history reaches back to January 2024; they
never take part in calibration.

## Credentials

The DataForSEO token used to be hard-coded. It now comes from the environment
(`DATAFORSEO_LOGIN` + `DATAFORSEO_PASSWORD`, or `DATAFORSEO_AUTH`). The old
token is still in git history, so rotate it.
