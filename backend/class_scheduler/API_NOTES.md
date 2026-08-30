# Rutgers Schedule of Classes (SOC) API — findings

Probed live on 2026-08-13 against Fall 2026 New Brunswick.

## Base URL

```
https://classes.rutgers.edu/soc/api/
```

`https://sis.rutgers.edu/soc/api/...` still works but returns a `302` to
`classes.rutgers.edu`, costing an extra round trip. Use `classes` directly.

No auth, no API key, no rate limiting observed. CORS is not enabled, so the
frontend must go through our backend.

## Endpoints — there are only two

I probed 24 candidate paths (`init.json`, `subjects.json`, `coreCodes.json`,
`schools.json`, `terms.json`, `search.json`, `courseDetail.json`, …). Every one
except the two below returns a Tomcat 404 page. I confirmed this against the
source: the official SOC frontend's own JavaScript (`soc_app.CourseDownloadService.js`
and friends, downloaded from `/soc/js/`) contains exactly two URL literals —
`/soc/api/courses.json` and `/soc/api/openSections.json`. Everything else the
official UI shows (subject list, school list, core-code dropdown, semester
picker) is **derived client-side from the courses dump** or computed in JS.

| Endpoint | Returns | Server cache | Wire size (NB Fall '26) |
|---|---|---|---|
| `courses.json?year=&term=&campus=` | `list[Course]`, sections nested | `max-age=900` | 0.9 MB gzip / 21 MB raw |
| `openSections.json?year=&term=&campus=` | `list[str]` of open registration indexes | `max-age=30` | 27 KB gzip |

`courses.gzip` and `openSections.gzip` are aliases returning identical JSON —
no reason to use them, the `.json` endpoints already gzip via content negotiation.

### Parameters

| Param | Values | Notes |
|---|---|---|
| `year` | `2024`–`2026` confirmed | `2027` returns `[]`; future terms appear as they're published |
| `term` | `0` winter, `1` spring, `7` summer, `9` fall | |
| `campus` | `NB`, `NK`, `CM` | one per request; `ONLINE` returns `[]` |

**`subject` and `level` are silently ignored.** I tested
`&subject=198` and `&level=U` — both return the full 4438-course dump
unchanged. There is no server-side filtering of any kind. This is the single
most important constraint on the design: **fetch the whole campus dump once,
cache it, filter locally.** That's what `soc.py` does.

**`openSections.json` ignores `campus` too** (found 2026-08-29). Requesting
`campus=NB`, `campus=NK` and `campus=CM` returns three byte-identical sets —
11041 indexes each on the day I checked, against an NB catalog of 11975
sections. So the response is university-wide, and roughly 3.1k of those
indexes belong to Newark and Camden.

Consequences: intersect the returned set with the term's own section indexes
before counting anything, or every NB open-count is inflated by ~40%. And
surplus indexes are **not** a sign of a stale sync — `poll.py` originally read
them that way and reported a stale catalog that wasn't stale. Note this is
unlike `courses.json`, where `campus` *is* honored; only the filter on this
second endpoint is dead.

### Term / campus sizes (2026)

| | NB | NK | CM |
|---|---|---|---|
| Winter (`0`) | 127 | | |
| Spring (`1`) | 4572 | | |
| Summer (`7`) | 1046 | | |
| Fall (`9`) | 4438 | 1322 | 961 |

## Fall 2026 NB shape

```
courses     4438   (2625 undergrad / 1813 graduate, 243 subjects, 26 schools)
sections   11984   (8154 open, 5654 fully asynchronous)
meetings   17393   (11033 with an actual time, 6360 async/TBA)
```

Meetings per day: Mon 2556, Tue 2555, Wed 2246, Thu 2499, **Fri 1153**, Sat 22, Sun 2.
Friday is already less than half of any other weekday, so "no Friday classes"
is a much cheaper preference to satisfy than it sounds.

## Field reference

### Course

Useful for preference matching:

| Field | Example | Use |
|---|---|---|
| `courseString` | `"01:198:112"` | canonical id, `unit:subject:number` |
| `title` / `expandedTitle` | `"DATA STRUCTURES"` | display; `expandedTitle` set on 2713/4438 |
| `subject` / `subjectDescription` | `"198"` / `"Computer Science"` | major-based filtering |
| `offeringUnitCode`, `school` | `"01"` / `School of Arts and Sciences` | school filtering |
| `level` | `"U"` / `"G"` | exclude grad courses |
| `credits` | `4` | credit-load targeting; **`null` on 486 courses** (variable credit) |
| `coreCodes` | `[{code:"HST", coreCodeDescription:"Historical Analysis", ...}]` | core requirement fulfillment |
| `preReqNotes` | `"(01:198:111 INTRO COMPUTER SCI )"` | prereq text, **contains `<em>OR</em>` HTML** |
| `campusLocations` | `[{code:"2", description:"Busch"}]` | campus preference |
| `openSections` | `18` | count of open sections |
| `synopsisUrl` | dept URL | `courseDescription` is **always empty** — this is the only description pointer |

### Section

| Field | Example | Use |
|---|---|---|
| `index` | `"11425"` | 5-digit registration index (WebReg code) — the primary key |
| `number` | `"01"` | section number within the course |
| `openStatus` / `openStatusText` | `false` / `"CLOSED"` | **stale by up to 15 min** — see below |
| `meetingTimes` | see below | the scheduling payload |
| `instructors` | `[{name:"CENTENO"}]` | instructor preference |
| `examCode` / `examCodeText` | `"M"` / `"Computer Science"` | `O`=no final, `C`=during class, `A`=by arrangement, rest are common-hour exam groups |
| `finalExam` | `"12/16/2026 - 0400 - 0700 PM"` | final exam conflict detection |
| `crossListedSections` | `[{registrationIndex:"10053", ...}]` | same class under another subject — must not be treated as a conflict |
| `openToText` / `majors` | `"MAJ: 080 (Art - Liberal Art), ..."` | major restriction; empty means unrestricted |
| `honorPrograms` | `[{code:"A"}]` | honors sections |
| `sectionEligibility` | `"1ST YEAR ONLY"` | eligibility restriction |
| `comments` / `commentsText` | | notes shown in the UI |
| `sessionDates` | `null` in fall | populated for summer sessions |

### meetingTimes entry

```json
{
  "meetingDay": "H",
  "startTimeMilitary": "1550", "endTimeMilitary": "1710",
  "startTime": "0350", "endTime": "0510", "pmCode": "P",
  "meetingModeCode": "02", "meetingModeDesc": "LEC",
  "buildingCode": "TIL", "roomNumber": "254",
  "campusLocation": "3", "campusAbbrev": "LIV", "campusName": "LIVINGSTON"
}
```

- **Day codes are `M T W H F S U`** — `H` is Thursday, `U` is Sunday, so every day
  is one letter. Empty string means asynchronous.
- **Use `startTimeMilitary`/`endTimeMilitary`.** The `startTime`/`endTime` pair is
  12-hour and only disambiguated by the separate `pmCode` field (`A`/`P`/empty) —
  strictly worse. `models.py` converts military time to minutes-since-midnight.
- Async/TBA meetings have **every** time field empty (6360 of 17393 records).
  They occupy no slot and can never conflict.
- 27 meeting modes. The ones that matter: `02 LEC` (8140), `90 ONLINE
  INSTRUCTION(INTERNET)` (1816), `03 RECIT` (1068), `05 LAB` (789), `04 SEM` (457),
  `07 STUDIO` (325). The rest are research/independent-study modes with no fixed time.
- Campus location codes: `1` College Ave, `2` Busch, `3` Livingston, `4`
  Douglass/Cook, `5` Downtown NB, `O` Online, `Z` Off Campus, `S` Study Abroad.
  A section's meetings can span campuses — that's what makes travel time a real
  constraint (a CAC→Busch hop needs ~40 min of bus).

### Core codes available (Fall 2026 NB)

19 distinct codes. `coreCodes` is empty for most courses; only courses that
actually satisfy a requirement carry them.

```
SOEHS 642  SOE: Approved Humanities/Social Science
CE    147  Non-Core: Community Engagement
WCd    93  Writing and Communication in a Discipline
HST    81  Historical Analysis
AHp    77  Arts and Literatures
CCD    64  Diversities and Social Inequalities
CCO    64  Our Common Future
WCr    62  Writing and Communication, Revision
NS     60  Natural Sciences
SCL    58  Social Analysis
AHo    53  Philosophical and Theoretical Issues
QQ     35  Quantitative Information
ITR    34  Information Technology and Research
QR     33  Mathematical or Formal Reasoning
AHq    22  Nature of Languages
AHr    13  Critical Creative Expression
GVT     7  SEBS Core: Government/Regulatory Analysis
ECN     4  SEBS Core: Economic Analysis
WC      3  Writing and Communication 01:355:101
```

This is the vocabulary for "fulfill 2 core requirements" — the user picks codes
from this list and the generator counts distinct satisfied codes.

## Gotchas

1. **`openStatus` in `courses.json` is stale.** Comparing the two endpoints
   fetched minutes apart, 29 of 11984 sections disagreed. `courses.json` is
   cached 15 min, `openSections.json` 30 s. Always overlay the live index set —
   `parse_courses(raw, open_indexes)` does this.
2. **Cross-listed sections are not conflicts.** The same class appears under
   multiple subject codes with different indexes. `Section.conflicts_with`
   checks `crossListedSections` before comparing times.
3. **`credits` is `null` for 486 courses.** Any credit-total constraint has to
   decide what to do with variable-credit courses.
4. **`preReqNotes` contains HTML** (`<em>OR</em>`) and is free text, not a
   parseable grammar. Parsing it properly is its own project; treat it as an
   advisory string for now.
5. **`courseDescription` is always empty.** Only `synopsisUrl` (a department web
   page) is available. If real descriptions are needed they have to come from
   elsewhere.
6. **A section can span campuses**, and `campusLocations` on the course is the
   union over sections — filter at the meeting level, not the course level.
7. **21 MB of JSON per campus-term.** Parse once into the normalized models and
   keep them in memory or in SQLite; do not re-parse per request.

## What this gives the scheduler

Directly supported preferences:

- **no classes on day X** — `Meeting.day`
- **nothing before/after time T** — `Meeting.start` / `Meeting.end`
- **open sections only** — `openSections.json` overlay
- **N core requirements** — `Course.core_codes`
- **N major courses** — `Course.subject`
- **campus preference / minimize bus trips** — `Meeting.campus_code`
- **credit load** — `Course.credits`
- **instructor preference** — `Section.instructors`
- **avoid 8 AMs, compact days, long gaps** — derivable from meeting times, and
  this is exactly what the existing `templates.py` constraint scoring already does
- **no final exam conflicts** — `Section.finalExam` (not yet parsed in `models.py`)

Not available from this API: professor ratings (RateMyProfessor), seat counts
(only open/closed boolean), waitlists, degree-audit / major requirement lists
(would need Degree Navigator or a hand-maintained mapping).

## Note on the existing scheduler

`backend/algorithm.py` works in whole-hour slots (`range(24)`). Class times are
not hour-aligned — `15:50–17:10` is typical. The class scheduler uses
minutes-since-midnight throughout, so the constraint-scoring logic in
`templates.py` needs a time-unit adaptation before it can be reused here.

## Reproducing

```bash
python -m backend.class_scheduler.explore 2026 fall NB
```

Hits the live API, parses, and prints the summary above plus worked examples.
