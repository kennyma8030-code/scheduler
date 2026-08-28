# SPEC — Rutgers Course Schedule Generator

The project's rescope from a roommate schedule optimizer to a course schedule
generator. This document specifies the full system: generation algorithm,
constraint vocabulary, NL preference pipeline, API surface, persistence,
frontend, and milestones. Companion docs: `API_NOTES.md` (the SOC API survey
this design is built on) and `README.md` (storage design and sync ops).

## 1. Overview & strategy

Generate ranked weekly course schedules for a Rutgers term from:

- **(a)** the synced SOC catalog (this package's `soc.py` / `models.py` /
  `schema.py` / `sync.py`, used as-is),
- **(b)** a list of requirements — specific sections, specific courses, and
  flexible groups ("one of these three electives", "any course satisfying
  core HST"),
- **(c)** free-text preferences parsed into weighted constraints by Gemini.

**Kept from the existing system:** minutes-since-midnight wire format and
5-minute slot math (`backend/timegrid.py` — built explicitly because hour
blocks could not represent a 15:50–17:10 class); the constraint contract
(score ∈ [0,1] per constraint, weights, hard-reject,
`final_score = (1 − Σw·s/Σw)·100`); the NL→JSON→factory-with-repair pipeline
shape from `PreferenceParser.py`/`algorithm.py`; the "precompute per side,
aggregate per combination" two-phase performance idea (reborn as per-section
precompute → per-combination aggregate); the Analytics funnel stats shape.

**Replaced:** the roommate optimizer is a *placement* search (where do
flexible events go on a continuous grid). Course scheduling is a *selection*
search (which section of each course) — times are fixed by the catalog, so
the search is a product over section candidate sets with conflict pruning,
and constraints score over sorted meeting blocks rather than 288-slot loops
(a 5-course week is ~15 blocks; looping 7×288 slots per combination wastes
100× the work). Slot bitmasks are kept only for O(1) conflict tests.

**Retired (final milestone):** the roommate flow — `/analyze/*`, `/import/*`,
`templates.py`, `algorithm.py`, `PreferenceParser.py`, `EventClassifier.py`,
both calendar importers, roommate `models.py`, `db.py`, and the roommate
frontend components. `timegrid.py` survives. All new backend code lives in
`backend/class_scheduler/` so the deletion is a clean cut.

## 2. Generation algorithm — `generator.py`

### Data shapes

```python
@dataclass(frozen=True)
class Block:
    day: int          # 0..6 (M=0 … U=6)
    start: int        # minutes since midnight
    end: int
    campus_code: str  # "1".."5", "O", "Z", "S"
    mode: str         # LEC / RECIT / LAB / ...

@dataclass(frozen=True)
class Candidate:      # one (course, section) choice, precomputed once
    course: Course; section: Section
    group_idx: int; cand_id: int          # global index
    credits: float | None
    blocks: tuple[Block, ...]             # timed meetings, sorted (day, start)
    day_masks: tuple[int, ...]            # 7 × 288-bit ints (timegrid.minutes_to_slot)
    is_fully_async: bool
    section_penalty: float                # Σ w·s over soft section-kind constraints
    conflict_mask: int                    # bit j ⇒ conflicts with cand_id j

@dataclass
class Group:
    label: str                            # "01:198:112" or "core HST"
    candidates: list[Candidate]
    min_section_penalty: float            # branch-and-bound lower bound

class CourseScheduleGenerator:
    def __init__(self, groups, constraints, *, max_course_combos=5,
                 max_sections_per_combo=5, time_budget_s=None): ...
    def run(self) -> GenerateResult       # {course_combos, results, stats, warnings, infeasible}
```

### Lock levels — the user shapes the search space before generation

Each requirement carries one of three lock levels; the Builder UI makes this
the primary pre-generation customization (the user tightens locks to make
the run faster):

- **`section`** — exact section known (WebReg index). A group of exactly one
  candidate. Together these form the **skeleton**.
- **`course`** — the course is fixed; the generator chooses the section.
  Group = that course's sections.
- **flexible** (`one_of` / `core`) — the generator chooses the course *and*
  the section. Group = union of sections across eligible courses.

The typical run has most requirements locked at `section` or `course` and
only 1–2 flexible groups — the search space is the product of the *unlocked*
group sizes only. A fully-flexible from-scratch run is explicitly allowed to
be slow (larger time budget, honest `truncated` flag), never wrong.

### The cross-campus rule (checked first, always)

**Two same-day consecutive meetings on different campuses with a gap of less
than 35 minutes ⇒ the combination is immediately invalid.** This is a
built-in hard rule (`MIN_CAMPUS_TRANSFER_MIN = 35` in `travel.py`), not an
LLM-emitted constraint, and it is evaluated at the earliest possible moment
at every stage: skeleton validation, candidate pre-filtering against the
skeleton, and (via the conflict bitmask) on every DFS extension.

**Exemption: Busch ↔ Livingston** (`EXEMPT_FROM_MINIMUM` in `travel.py`).
Those two campuses are a short, frequent hop that students make between
back-to-back classes routinely, and Rutgers schedules them as effectively
adjacent, so the pair never triggers the hard minimum. It still carries its
15-minute `BUS_MINUTES` cost in soft scoring, so a real gap is still
preferred where one exists — it just can't invalidate a schedule.

The `BUS_MINUTES` matrix otherwise survives only for *soft* comfort scoring
(prefer more slack / fewer campus hops).

### Pipeline

0. **Skeleton validation.** Section-locked picks are checked among
   themselves first: pairwise `Section.conflicts_with` + the 35-minute rule.
   Any violation returns immediately as `infeasible` naming the exact pair
   and reason ("10901 and 12374: Busch→CAC with a 20-minute gap on Monday")
   — before any search or LLM call.
1. **Candidate build + hard section filters.** Load each group's sections
   from the DB (`catalog.py`), overlay live open status
   (`SOCClient.open_section_indexes`). Hard section-kind constraints
   (open-only, hard "nothing before 11", hard "no Fridays", hard
   avoid-instructor) apply here as *filters*, shrinking branching before
   search. If a group empties → structured `infeasible` naming the group and
   the killing constraint ("CS112 has no open sections after your 'nothing
   before 11' rule").
2. **Pre-filter against the skeleton.** Every remaining candidate is checked
   once against the locked skeleton: time conflict or 35-minute violation ⇒
   discarded before search. With most courses locked this is where the bulk
   of the branching dies — the DFS then only explores survivors.
3. **Per-candidate soft precompute** → `section_penalty`; per-group
   `min_section_penalty`.
4. **Pairwise conflict matrix** across different groups via
   `Section.conflicts_with` (honors cross-listing), **with the 35-minute
   rule folded into the same bit**: a cross-campus pair with an insufficient
   gap sets the conflict bit exactly like a time overlap, so the DFS prunes
   both with one mask test. Cross-listed twins in *different* groups are
   marked conflicting anyway (can't take the same course twice) + warning;
   likewise two flexible-group candidates resolving to the same course.
   ~180 candidates → ~16k integer-comparison checks; sub-millisecond.
5. **DFS, fail-first ordering.** Groups sorted ascending by candidate count
   (skeleton groups of size 1 first, effectively pre-placed); candidates
   within a group ascending by `section_penalty` (best-first improves bound
   quality). Prunes, in order of cheapness:
   - *Conflict + travel*: one mask test, `chosen_conflicts >> cand_id & 1`
     (includes the 35-minute rule via step 4).
   - *Bound*: `penalty_so_far + Σ min_section_penalty(remaining groups) ≥
     worst_kept` once the result set is full. Only the section-decomposable
     part participates, keeping the bound admissible.
   - *Credit*: hard `max_credits` already exceeded → prune (monotone).
6. **Leaf scoring.** Merge chosen blocks into 7 sorted per-day lists
   (~15 blocks). Run schedule- and selection-kind constraints; any hard
   score > 0 rejects. `final_score = (1 − total_penalty/total_weight)·100`.
7. **Result shaping — course combinations, then section combinations.**
   Results are grouped by the *set of courses* chosen (flexible groups mean
   different branches choose different courses). The generator keeps the top
   `max_course_combos` (default 5) course combinations ranked by their best
   section-combination score, and within each up to `max_sections_per_combo`
   (default 5) section variants. When everything is course-locked there is
   exactly one combination and this degenerates to a flat top-N list.
8. **Time budget.** `time_budget_s` defaults by search-space size (≈5 s when
   mostly locked; 60 s+ for from-scratch runs — slow-but-thorough is the
   contract there). Checked every N leaves; on exhaustion return what's
   found with `stats.truncated = true`.

### Execution model — hybrid

Never per-branch threads: a branch step is a microsecond bitmask test
(thread overhead would dwarf the work, the GIL serializes CPU-bound Python
threads, and branch-and-bound depends on branches seeing a fresh shared
bound).

- **Sequential DFS by default.** After skeleton pre-filtering, compute
  `estimated_raw = Π len(group.candidates)`. Below the threshold (default
  **1,000,000**) run the single-process DFS: mostly-locked runs finish in
  milliseconds, mid-size in tens of milliseconds.
- **Worker pool above the threshold.** Partition the largest group's
  candidates across `min(cpu_count, 8)` `multiprocessing` workers; each runs
  the same sequential DFS on its slice with its own heap; the parent merges
  top-Ns and unions stats. Workers bound only against their local heap
  (slightly stale bounds ⇒ somewhat less pruning; correctness unaffected).
  Candidate groups are plain dataclasses and pickle cheaply, once per
  worker. `stats.workers` reports the mode used.

### Combinatorics & caps

Mostly-locked runs (the common case): product of 1–2 unlocked groups → tens
to a few thousand leaves after skeleton pre-filtering; milliseconds.
From-scratch worst case (6 flexible × 30+ sections) is unacceptable raw, so:
**per-group candidate cap 60** (keep lowest `section_penalty` after hard
filters); **core-filler groups cap 40** (open first, best penalty first).
Caps are always reported in `stats`/`warnings`.

**Async sections** (5,654 of 11,984 in Fall 2026 NB — not an edge case):
empty `blocks`, zero masks, conflict with nothing; contribute credits, core
codes, and section-kind scores (notably `PreferAsync`); invisible to
day-shape constraints. Note they also defeat conflict pruning — an
async-heavy flexible search is the worst case the caps, bound, and time
budget exist for.

## 3. Constraint vocabulary — `constraints.py`

Three kinds sharing the existing hard/weight/[0,1] contract. Times in params
are **minutes since midnight** (the factory converts the LLM's "HH:MM");
days are ints 0–6.

```python
class SectionConstraint:   kind = "section"    # decomposable; precomputed per candidate; hard ⇒ filter
    def score_section(self, cand: Candidate) -> float: ...
class ScheduleConstraint:  kind = "schedule"   # needs the merged week of blocks
    def score_schedule(self, week: WeekOccupancy) -> float: ...
class SelectionConstraint: kind = "selection"  # about the chosen set, ignores times
    def score_selection(self, selection: list[Candidate]) -> float: ...
```

### Section-kind (hard ⇒ pre-filter; soft ⇒ contributes to the DFS bound)

| Class | Params | Score |
|---|---|---|
| `NoClassesBefore` | `time`, `days?` | fraction of timed meetings starting before `time` (on `days` if given) |
| `NoClassesAfter` | `time`, `days?` | fraction of timed meetings ending after `time` |
| `NoClassesOnDays` | `days` | fraction of timed meetings on banned days |
| `AvoidEarlyMornings` | `cutoff=9:00` | alias of `NoClassesBefore` — its own LLM label |
| `PreferInstructor` | `course_string`, `names` | 0 if the selected section of that course matches, else 1 |
| `AvoidInstructor` | `course_string?`, `names` | 1 if a matching instructor is selected, else 0 |
| `OpenSectionsOnly` | — | binary; **hard, injected by default** (opt-out via `options.open_only=false`) |
| `PreferAsync` | `maximize` | 0 if `is_fully_async == maximize`, else mismatch fraction |
| `PreferCampus` / `AvoidCampus` | `campus_codes` | fraction of timed meetings off/on the listed campuses |
| `PreferHonors` / `AvoidHonors` | — | binary on `section.honors` |

### Schedule-kind (leaf-time, over sorted blocks)

| Class | Params | Score | Ports from |
|---|---|---|---|
| `MaxDaysWithClasses` | `max_days` | `max(0, days_used − max)/(7 − max)` | new ("3-day week") |
| `FreeDayOn` | `days` | fraction of listed days that have classes | new |
| `MaxGapPerDay` | `max_gap`, `ignore_below=30min` | excess gap-minutes between consecutive blocks, normalized; gaps < 30 min are passing periods (`BREAK_MIN_MINUTES` semantics) | `MaxGapsInDay` |
| `CompactDays` | `tight` | mean over class days of `(span − class_min)/span` (or complement) | `KeepScheduleTight` |
| `LunchBreak` | `window=(11:00,14:00)`, `min_free=30` | fraction of class days lacking a free interval ≥ `min_free` inside the window | `GuaranteedFreeBlock` |
| `GetOutBy` | `time`, `days?` | per applicable day `min(1, overrun/120)`, mean | new |
| `MaxClassesPerDay` | `max_count` | excess on worst day / `max_count` | `MaxTimesPerDay` |
| `TravelComfort` | `matrix=BUS_MINUTES`, `slack=10` | soft only — per consecutive cross-campus same-day pair: `max(0, travel+slack − gap)/(travel+slack)`, mean. The **hard** 35-minute rule is built into the generator (§2), not a constraint | new |

### Selection-kind

| Class | Params | Score |
|---|---|---|
| `CreditRange` | `min`, `max` | shortfall/overrun normalized by 3 credits per unit, capped at 1; null-credit courses count as `assumed_credits` (default 3.0) and flag the result |
| `CoreCoverage` | `codes`, `count` | `(count − distinct satisfied)/count`, floor 0; satisfied = union of selected courses' `core_codes` |
| `NoFinalExamConflicts` | — | conflicting parseable exam pairs / C(n,2); unparseable skipped + warning; **soft-only in v1** |

Registry: `CONSTRAINT_TYPES: dict[str, type]` in `constraints.py` (replaces
`constants.constraint_dict`). No code imports from `templates.py` — the
formulas are rewritten block-based.

### `travel.py`

`MIN_CAMPUS_TRANSFER_MIN = 35` — the hard rule: any two same-day consecutive
meetings on different campuses need ≥ 35 minutes between them, else the
combination is invalid. `EXEMPT_FROM_MINIMUM` — pairs that skip that
minimum, currently Busch ↔ Livingston only (short frequent hop, treated as
adjacent; still soft-scored at its 15-minute cost). Plus
`BUS_MINUTES: dict[frozenset[str], int]` for
soft comfort scoring only — CAC↔Busch 40, CAC↔Livingston 35,
CAC↔Cook/Douglass 25, Busch↔Livingston 15, Busch↔Cook 45, Livingston↔Cook
40, Downtown ≈ CAC+10; same campus 0; `O`/`Z`/`S` → 0. Hand-tuned
estimates; module constants with a comment inviting correction.

## 4. NL preference pipeline — `preference_parser.py`

`CoursePreferenceParser`: same mechanics as the existing `PreferenceParser`
(Gemini `gemini-3.1-pro-preview`, system prompt *is* the vocabulary spec,
JSON-array-only output, markdown-fence stripping). New ~150-line prompt:

- **Context injection:** selected courses as
  `01:198:112 "Intro to CS" (instructors: CENTENO; …)`; the term's core
  codes with descriptions (so "a history core" → `HST`).
- **LLM vocabulary:** times as `"HH:MM"` 24-hour strings (hour ints are too
  coarse for 15:50 classes); days as full names; courses as `course_string`;
  instructors and campuses as raw names.
- **Sections with one worked example each:** TIME OF DAY, DAYS, DAY SHAPE,
  SECTIONS & INSTRUCTORS, REQUIREMENTS.
- **Weight ladder copied verbatim** from the existing prompt (0.3–0.4
  nice-to-have … 0.9–1.0 can't-stand; `hard=true` only for
  never/non-negotiable). It's battle-tested.

**Factory** — `build_constraints(ai_output, ctx) -> (constraints, warnings)`
in `constraints.py`, mirroring `constraint_factory`'s repair philosophy but
*recording* drops instead of silently swallowing them:

1. Unknown `type` → drop + warning.
2. `"HH:MM"` → minutes; day names → ints; campus names → codes (via
   reversed `CAMPUS_LOCATIONS`).
3. Course resolution: exact `course_string` match, else
   `difflib.get_close_matches` on titles (cutoff 0.6), else drop + warning.
4. Instructor resolution against the union of the selected courses'
   instructor lists (SOC format `"SURNAME, INITIAL"`): normalized surname
   match; ambiguity keeps all matches + warning.
5. Weight clamp to [0,1]; dedupe on (type, params).
6. Append injected defaults: `OpenSectionsOnly(hard)` and soft
   `TravelComfort` (the hard 35-minute rule lives in the generator).

Warnings flow through the API to the UI ("we couldn't apply: …") — the one
deliberate improvement over the old silent-drop behavior.

## 5. Input model — requirement groups

```python
class Requirement(BaseModel):            # discriminated on `kind` — kinds ARE the lock levels
    kind: Literal["section", "course", "one_of", "core"]
    course_string: str | None; supplement: str = ""       # kind="section"|"course"
    index: str | None = None                               # kind="section": exact WebReg index
    options: list[CourseRef] | None                        # kind="one_of"
    core_code: str | None; subjects: list[str] | None; level: str = "U"  # kind="core"
    label: str = ""

class GenerateRequest(BaseModel):
    term_key: str
    requirements: list[Requirement]      # 1..8
    preferences_text: str = ""
    options: GenerateOptions             # open_only=True, assumed_credits_for_variable=3.0,
                                         # max_course_combos=5, max_sections_per_combo=5,
                                         # time_budget_s=None (auto-scaled by search-space size)
```

Each `Requirement` = one search `Group`, and its kind is its lock level
(§2): `section` → one candidate (skeleton); `course` → that course's
sections (a lecture and its `LB` supplement are distinct requirements; the
UI auto-suggests adding the lab); `one_of` → union across options; `core` →
all U-level sections carrying that `CourseCoreCode` (the indexed ~13 ms
query), subject-narrowed if given, capped at 40. LEC+RECIT bundles need no
special handling — one WebReg index registers all of a section's meetings.
"Fill to N credits" = `one_of`/`core` groups + a `credit_range` constraint;
variable course *count* is out of scope for v1.

The Builder UI presents lock level as a per-requirement toggle (exact
section ⇄ any section of this course ⇄ let the generator pick the course) so
the user can tighten the search before running — the intended workflow is
"most classes known, generator fills the last 1–2 slots."

## 6. API surface — `api.py` (`APIRouter(prefix="/api")`, mounted in `main.py`)

Catalog reads hit the synced DB, never SOC directly; only the open-status
overlay calls `SOCClient` (30 s TTL disk cache makes this free; serves stale
on outage). This is also the CORS answer — the frontend never talks to SOC.

```
GET  /api/terms                                 → [{key, label, course_count, section_count, synced_at}]
GET  /api/subjects?term_key=                    → [{code, description, course_count}]
GET  /api/core-codes?term_key=                  → [{code, description, course_count}]
GET  /api/courses/search?term_key=&q=&subject=&core=&level=U&limit=20
       typeahead: normalized course_string prefix ("cs 112" → 198:112) + title ILIKE;
       rows include open_section_count (live overlay), campuses, has_async_sections
GET  /api/courses/{term_key}/{course_string}?supplement=   → full course + sections + meetings
GET  /api/open-status?term_key=                 → {open_indexes, fetched_at}   # UI polls 30s
POST /api/schedule/generate                     body GenerateRequest → GenerateResponse
POST /api/schedule/save                         {term_key, name, indexes, requirements,
                                                 preferences_text, constraints_json, score}
GET  /api/schedule/saved                        → list
GET  /api/schedule/saved/{id}                   → re-hydrated from (term_key, index) refs,
                                                 open overlay reapplied, + stale_indexes[]
```

**GenerateResponse** (stats mirror the existing funnel so Analytics ports):

```jsonc
{
  "course_combos": [{                     // grouped: course combination → its section variants
    "courses": ["01:198:112", "01:640:152", "01:750:203", "01:013:120"],
    "results": [ /* up to max_sections_per_combo entries of the shape below */ ]
  }],
  "results": [{                           // flat top-N across combos (simple view)
    "score": 87.4,
    "indexes": ["10901", "12374", ...],            // WebReg-ready
    "credits_total": 15.5, "credits_assumed": false,
    "selections": [{ "requirement_label", "course_string", "title", "credits",
                     "section": { "index", "number", "open", "instructors", "honors",
                                  "exam_code", "final_exam", "meetings": [...] } }],
    "week": [[{"start":950,"end":1030,"index":"10901","course_string":"01:198:112",
               "campus_code":"2"}], ...],           // 7 day-arrays, minutes
    "penalties": [{"type":"max_gap_per_day","weight":0.6,"score":0.21}]  // explainability
  }],
  "stats": { "candidates_per_group", "raw_product", "leaves_scored",
             "pruned_conflict", "pruned_bound", "pruned_hard",
             "truncated", "workers", "elapsed_ms" },
  "constraints": [...],                             // parsed JSON, echoed
  "warnings": ["couldn't match instructor 'smith'", "core HST capped at 40 sections"],
  "infeasible": null                                // or {group, reason} / {pair, reason}
}
```

## 7. Persistence

Unify on this package's `schema.py` `Base`/engine (`DATABASE_URL` or sqlite
fallback). Add:

```python
class SavedSchedule(Base):
    __tablename__ = "saved_schedules"
    id; term_key (FK terms.key, indexed); name
    indexes: JSON            # ["10901", ...] — (term_key, index) refs ONLY, never row ids
    requirements: JSON       # replayable: "regenerate" after a re-sync is one POST
    preferences_text: Text; constraints_json: JSON; score: Float?; created_at
```

`backend/db.py` (legacy separate `declarative_base`, same `app.db`) is
frozen — no new imports — and deleted in M6.

## 8. Frontend

Split the 1208-line `App.jsx`:

```
src/
  api.js                    # fetch wrapper, centralized API_BASE
  App.jsx                   # view router: landing | builder | results | saved
  theme.js                  # extracted ThemeToggle + palette (kept)
  components/
    WeekGrid.jsx            # NEW centerpiece: day columns (Mon–Fri, +weekend when used),
                            # 7:00–22:00 rows, absolutely-positioned blocks (borrow Timeline's
                            # top/height math), colored by campus (CAC red, Busch blue,
                            # Livingston yellow, Cook/Douglass green), async courses in a
                            # footer strip, click → section popover
    CourseSearch.jsx        # debounced typeahead on /api/courses/search
    RequirementList.jsx     # course chips with the lock-level toggle (exact section ⇄ any
                            # section ⇄ generator picks course); "add alternate" → one_of;
                            # "+ core requirement"; running credit total
    SectionCard.jsx         # index (click-to-copy for WebReg), instructors, meetings,
                            # open badge, final exam, honors tag
    Carousel.jsx            # ported ScheduleCarousel (keyboard nav); outer level = course
                            # combos, inner level = section variants
    Analytics.jsx           # ported funnel (PipeStep/PipeArrow/ScoreBar), renamed stages
    PenaltyPanel.jsx        # NEW: per-result constraint breakdown + warnings
  views/
    Landing.jsx             # term picker (GET /api/terms), rewritten copy
    Builder.jsx             # RequirementList + CourseSearch | preferences textarea with
                            # example chips ("no 8ams", "keep Fridays free"); Generate
    Results.jsx             # Carousel of WeekGrids + SectionCards + Analytics + PenaltyPanel;
                            # polls /api/open-status every 30s, flips open badges live
    Saved.jsx               # ported HistoryView vs /api/schedule/saved, with Regenerate
```

Reused: theme system, carousel interaction, funnel components,
`fmtTime`/`minToHHMM`. Deleted immediately: dead `RoommateScheduler.jsx`.
Deleted in M6: `RoommateForm`, `WeeklyRoommateForm`, `ICSImportModal`,
`DayPicker`, roommate Results views.

## 9. Milestones (each independently testable)

- **M1 — Engine** (no LLM/HTTP): `constraints.py`, `generator.py`,
  `travel.py`, `catalog.py` (DB query layer + open overlay), `tests/`
  against the already-synced terms; `__main__` harness modeled on
  `explore.py`. *Exit:* mostly-locked request (4 locked + 1 flexible) in
  well under 1 s; skeleton violations reported instantly with the offending
  pair; from-scratch 6×30 stress crosses the 1M threshold, engages the
  worker pool, and completes or truncates honestly within its budget.
- **M2 — Catalog API**: read endpoints in `api.py`, mounted in `main.py`.
  Testable with curl.
- **M3 — NL pipeline**: `preference_parser.py` + `build_constraints` +
  warnings. Golden-file tests (recorded LLM outputs → deterministic factory
  tests).
- **M4 — Generate + persistence**: `POST /api/schedule/generate` wiring;
  `SavedSchedule` + save/load endpoints.
- **M5 — Frontend**: split App.jsx; WeekGrid first, then the Builder flow,
  then polish (open-status polling, penalty panel, saved view).
- **M6 — Retirement**: delete the roommate endpoints, modules, and
  components listed in §1; update the top-level README.

## 10. Risks & open decisions

1. **Travel times**: the hard rule is a flat 35 minutes for any cross-campus
   consecutive pair, checked first at every stage; `BUS_MINUTES` estimates
   feed only soft comfort scoring, and the constants invite correction.
2. **Final-exam parsing** (`"12/16/2026 - 0400 - 0700 PM"`): regex +
   meridiem inference (start > end numerically ⇒ opposite meridiem);
   unparseable → skip + warn; soft-only in v1.
3. **486 null-credit courses**: `assumed_credits_for_variable=3.0`, result
   flags `credits_assumed`, UI shows "≈".
4. **Core-filler cap (40)** can hide a better answer; the warning tells the
   user to narrow by subject.
5. **Cross-listed pairs across groups**: treated as conflicts + warning;
   test with 01:198:206 / 14:332:226-style pairs.
6. **All-soft-schedule-constraint or async-heavy requests** weaken conflict
   and bound pruning → the caps, threshold-triggered worker pool, and time
   budget are the backstop; stats make degradation visible, never mysterious.
7. **Open-status races**: sections can close between generation and
   registration; 30 s polling and prominent WebReg indexes are the practical
   mitigation; no guarantees.
