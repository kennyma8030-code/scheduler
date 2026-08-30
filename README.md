# Rutgers Course Schedule Generator

Pick your courses, lock the sections you already know, describe what matters
in plain English — get ranked, conflict-free schedules with WebReg indexes
ready to register.

Course data comes from the Rutgers Schedule of Classes API (surveyed in
[`backend/class_scheduler/API_NOTES.md`](backend/class_scheduler/API_NOTES.md)),
synced per term into a local database. The full design is in
[`backend/class_scheduler/SPEC.md`](backend/class_scheduler/SPEC.md).

## How it works

1. Each requirement is a **lock level**: an exact section (index), a course
   (generator picks the section), or a flexible group ("any course satisfying
   core HST" — generator picks the course *and* section).
2. Free-text preferences are parsed by Gemini into weighted constraints
   (no 8ams, keep Fridays free, compact days, lunch break, instructor and
   campus preferences, credit range, ...).
3. A pruned selection search walks the section combinations: time conflicts
   and the hard **35-minute cross-campus rule** (Busch–Livingston exempt —
   short hop, treated as adjacent) are precomputed into a conflict bitmask, branch-and-bound cuts dominated branches, and runs above
   ~1M raw combinations automatically spread across worker processes.
4. Results come back grouped as course combinations, each with section
   variants, scored `(1 − Σ weight·violation / Σ weight) × 100`.

Mostly-locked runs finish in milliseconds. Fully-flexible from-scratch runs
are allowed to take seconds to minutes — slow-but-thorough is the contract.

## Setup

### Backend

```bash
cd backend
python -m venv venv
venv/Scripts/pip install -r requirements.txt        # . venv/bin/activate on mac
```

Optional `backend/.env`:

```
GEMINI_API_KEY=...        # enables natural-language preferences
DATABASE_URL=postgresql://user@localhost/rutgers_soc   # else sqlite:///app.db
```

Sync a term (run from the repo root; repeat after add/drop):

```bash
backend/venv/Scripts/python -m backend.class_scheduler.sync 2026 fall NB
```

Run the API:

```bash
backend/venv/Scripts/python -m uvicorn backend.main:app --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

### Open/closed polling

`openSections.json` is a snapshot, not a change feed, so the poller diffs the
fetched set of open registration indexes against the last known state and
records only the transitions.

```bash
backend/venv/Scripts/python -m backend.class_scheduler.poll            # all synced terms
backend/venv/Scripts/python -m backend.class_scheduler.poll 2026-9-NB  # one term
backend/venv/Scripts/python -m backend.class_scheduler.poll --report   # recent activity
```

The first run for a term seeds state silently; later runs log every flip to
`section_status_changes`. Every tick also writes a `poll_runs` row whether or
not anything moved, so a quiet stretch can be told apart from a poller
outage. If a run reports open indexes "not in the catalog", the term's sync is
stale — re-run `sync` for it.

**Deploying the poller** (Railway cron, or any scheduler): deploy this repo as
a second service whose start command is
`python -m backend.class_scheduler.poll`, with a cron schedule of
`*/15 * * * *`. Schedules are UTC and the platform minimum interval is 5
minutes. The process must exit when finished — Railway skips subsequent runs
while a previous one is alive — which it does, disposing the engine on the way
out. Note that each run gets a fresh container, so `SOCClient`'s disk cache
starts cold and every tick performs a real fetch.

Sub-5-minute polling (for an instant-notification sniper, where the interval
*is* the product) is not possible with cron and needs an always-on worker
looping with a sleep instead.

## Development

```bash
# all tests (no network, no DB)
backend/venv/Scripts/python -m backend.class_scheduler.tests

# live end-to-end harness against the synced DB
backend/venv/Scripts/python -m backend.class_scheduler.harness 2026-9-NB

# live SOC API smoke test
backend/venv/Scripts/python -m backend.class_scheduler.explore 2026 fall NB
```

Key modules: `backend/class_scheduler/generator.py` (the search),
`constraints.py` (the vocabulary + LLM-output factory), `catalog.py`
(requirements + DB queries), `api.py` (HTTP surface), `preference_parser.py`
(Gemini prompt), `travel.py` (campus transfer rules), `poll.py` (open/closed
history), `soc.py`/`models.py`/`schema.py`/`sync.py` (the SOC data layer).

