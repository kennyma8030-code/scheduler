# class_scheduler

Rutgers course data for the schedule generator. See `API_NOTES.md` for the
upstream API survey.

## Split of responsibilities

The SOC exposes two endpoints, and they are treated very differently:

| | `courses.json` | `openSections.json` |
|---|---|---|
| contents | catalog: courses, sections, meeting times | list of open registration indexes |
| changes | once a semester | every 30 seconds |
| size | 21 MB (0.9 MB gzip) | 27 KB gzip |
| where it lives | **Postgres**, synced per semester | **never stored** — fetched live |

Storing open/closed would mean rewriting 12k rows every 30 seconds to persist a
boolean that costs 27 KB to refetch. Instead `sync.py` writes only static data,
and readers overlay live state at query time:

```python
live = SOCClient().open_section_indexes(2026, "9", "NB")
open_now = [s for s in candidate_sections if s.index in live]
```

## Local setup

```bash
brew install postgresql@17
brew services start postgresql@17
createdb rutgers_soc
```

`backend/.env` holds the connection string:

```
DATABASE_URL=postgresql://kenny@localhost/rutgers_soc
```

Unset, everything falls back to `sqlite:///app.db` — the schema uses no
Postgres-only column types, so development works without a server.

## Syncing

```bash
python -m backend.class_scheduler.sync 2026 fall NB        # one campus
python -m backend.class_scheduler.sync 2026 fall NB NK CM  # all three
python -m backend.class_scheduler.sync --list              # what's loaded
python -m backend.class_scheduler.sync 2026 fall NB --force
```

Run it once when a semester's catalog is published, and again after add/drop
settles. A term is replaced wholesale rather than diffed — at ~4.4k courses a
full rewrite in one transaction is faster and more obviously correct than
reconciling, and takes ~6 s.

Re-running is safe and cheap: the sync fingerprints the static content and
skips the write when nothing changed.

> **Do not store `courses.id` or `sections.id` anywhere.** A re-sync assigns new
> primary keys. Reference a section by `(term_key, index)` — the registration
> index is the stable identifier, and it's what WebReg uses too.

## Schema

```
terms              one row per synced campus-term ("2026-9-NB"), plus sync bookkeeping
courses            natural key (term_key, course_string, supplement_code)
course_core_codes  one row per core requirement a course satisfies
sections           registration index, instructors, exam, restrictions
meetings           day 0-6 + start/end as minutes since midnight; NULL = asynchronous
```

Meetings store minutes-since-midnight rather than the API's three overlapping
time formats, so "nothing before 10am" and "no Friday classes" are indexed
integer comparisons.

## Two data quirks the schema encodes

**`courseString` is not unique within a term.** `01:750:193` is a 4-credit
lecture *and* a separate 0-credit lab, distinguished only by `supplementCode`
(`''` vs `'LB'`). They are registered for independently, so both are kept and
the supplement code is part of the natural key.

**Some courses arrive split across two records.** 9 of 4438 in Fall 2026 NB —
`16:400:603` comes back as indexes `['19376','19377']` and `['19378']`. Taking
either record alone silently hides half the sections, so `parse_courses` unions
them (`merge_split_courses`). This is why the sync reports 4429 courses from a
4438-record payload while preserving all 11984 sections.

## Why not the HTTP ETag for change detection

`courses.json` embeds each section's `openStatus`, so its body — and its ETag —
changes every 15-minute cache window as seats flip, even when the catalog is
untouched. The ETag is stable *within* a window (verified across HEAD and
repeated GETs) but useless across them. `sync.content_fingerprint` hashes the
normalized data with `open` excluded instead.

## Current contents

```
terms 4 | courses 11273 | core codes 3893 | sections 28148 | meetings 40381
```

Fall 2026 NB/NK/CM and Spring 2026 NB. The product query — open undergrad
sections satisfying a core code, nothing before 10:00, nothing on Friday —
runs in ~13 ms.
