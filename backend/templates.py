# SCORING SYSTEM NOTES:
#   Each constraint produces a score in [0.0, 1.0] where 0 = no violation, 1 = maximum violation.
#   final_score = (1 - sum(weight * score for all constraints)) * 100
#   Hard constraints: any score > 0 causes the schedule pair to be rejected entirely.
#   Soft constraints: accumulate weighted penalties.
#
# SINGLE CONSTRAINTS (is_cross = False):
#   Concern one person's schedule. Use self.person ("a" or "b") to pick event stream.
#   Interface: reset() → process(hour, a_event, b_event) × 24 → finalize()
#   Free time (None) is treated as "home" throughout.
#
# CROSS-RELATIONAL CONSTRAINTS (is_cross = True):
#   Compare both roommates' schedules. Processed in two phases:
#     Phase 1 (per schedule): reset_side(person) → accumulate(person, hour, event) × 24
#                             → get_state(person) to snapshot per-person state
#     Phase 2 (per pair):     load_state("a", state_a) + load_state("b", state_b) → compare()
#   This avoids re-looping 24 hours for every pair — the inner loop runs once per schedule,
#   not once per (schedule_a × schedule_b) combination.


# ── WHEN AN EVENT HAPPENS ─────────────────────────────────────────────────────

# Single: prefer that a specific event happens during specified hours.
# Score = fraction of event hours that fall outside the preferred window.
class EventDuring:
    is_cross = False

    def __init__(self, event, person, hours, hard, weight):
        self.event = event
        self.person = person        # "a" or "b"
        self.hours_set = set(hours)
        self.hard = hard
        self.weight = weight
        self.violations = 0
        self.score = 0

    def reset(self):
        self.violations = 0
        self.score = 0

    def process(self, hour, a_event, b_event):
        event = a_event if self.person == "a" else b_event
        if event is self.event and hour not in self.hours_set:
            self.violations += 1

    def finalize(self):
        self.score = self.violations / self.event.duration if self.event.duration else 0


# Single: prefer that a specific event does NOT happen during specified hours.
# Mirror of EventDuring — score = fraction of event hours inside the forbidden window.
class EventNotDuring:
    is_cross = False

    def __init__(self, event, person, hours, hard, weight):
        self.event = event
        self.person = person
        self.hours_set = set(hours)
        self.hard = hard
        self.weight = weight
        self.violations = 0
        self.score = 0

    def reset(self):
        self.violations = 0
        self.score = 0

    def process(self, hour, a_event, b_event):
        event = a_event if self.person == "a" else b_event
        if event is self.event and hour in self.hours_set:
            self.violations += 1

    def finalize(self):
        self.score = self.violations / self.event.duration if self.event.duration else 0


# Single: prefer that a specific "noisy" event does not happen during quiet hours.
# Semantically distinct from EventNotDuring — intended for events that disturb others
# (gaming, parties, loud phone calls). Same logic, different AI label.
# Score = fraction of the noisy event's hours that land in the quiet window.
class LoudNotDuring:
    is_cross = False

    def __init__(self, event, person, hours, hard, weight):
        self.event = event
        self.person = person
        self.hours_set = set(hours)
        self.hard = hard
        self.weight = weight
        self.violations = 0
        self.score = 0

    def reset(self):
        self.violations = 0
        self.score = 0

    def process(self, hour, a_event, b_event):
        event = a_event if self.person == "a" else b_event
        if event is self.event and hour in self.hours_set:
            self.violations += 1

    def finalize(self):
        self.score = self.violations / self.event.duration if self.event.duration else 0


# Single: prefer that a person is home (in_dorm or free) during specified hours.
# Score = fraction of required hours where the person is actually away.
class HomeDuring:
    is_cross = False

    def __init__(self, person, hours, hard, weight):
        self.person = person
        self.hours_set = set(hours)
        self.hard = hard
        self.weight = weight
        self.violations = 0
        self.score = 0

    def reset(self):
        self.violations = 0
        self.score = 0

    def process(self, hour, a_event, b_event):
        if hour not in self.hours_set:
            return
        event = a_event if self.person == "a" else b_event
        # away if event is explicitly out-of-dorm; free time counts as home
        if event is not None and not event.in_dorm:
            self.violations += 1

    def finalize(self):
        self.score = self.violations / len(self.hours_set) if self.hours_set else 0


# Single: prefer that a person is away (not in_dorm) during specified hours.
# Inverse of HomeDuring — score = fraction of required hours where person is home.
class AwayDuring:
    is_cross = False

    def __init__(self, person, hours, hard, weight):
        self.person = person
        self.hours_set = set(hours)
        self.hard = hard
        self.weight = weight
        self.violations = 0
        self.score = 0

    def reset(self):
        self.violations = 0
        self.score = 0

    def process(self, hour, a_event, b_event):
        if hour not in self.hours_set:
            return
        event = a_event if self.person == "a" else b_event
        # home if free (None) or in_dorm event
        if event is None or event.in_dorm:
            self.violations += 1

    def finalize(self):
        self.score = self.violations / len(self.hours_set) if self.hours_set else 0


# ── EVENT ORDER FOR ONE PERSON ────────────────────────────────────────────────

# Single: prefer that first_event starts before second_event.
# Flip first_event/second_event in AI output to express "after".
# Binary score: 0 if correctly ordered, 1 if violated.
class EventBeforeEvent:
    is_cross = False

    def __init__(self, first_event, second_event, person, hard, weight):
        self.first_event = first_event
        self.second_event = second_event
        self.person = person
        self.hard = hard
        self.weight = weight
        self.first_start = None
        self.second_start = None
        self.score = 0

    def reset(self):
        self.first_start = None
        self.second_start = None
        self.score = 0

    def process(self, hour, a_event, b_event):
        event = a_event if self.person == "a" else b_event
        if event is self.first_event and self.first_start is None:
            self.first_start = hour
        if event is self.second_event and self.second_start is None:
            self.second_start = hour

    def finalize(self):
        if self.first_start is None or self.second_start is None:
            self.score = 0
            return
        self.score = 1.0 if self.first_start >= self.second_start else 0.0


# Single: prefer two events to be scheduled back-to-back (no gap between them).
# Set want_adjacent=False to penalize adjacency instead.
# Binary score: 1 if the want_adjacent preference is not met.
class EventsBackToBack:
    is_cross = False

    def __init__(self, first_event, second_event, person, want_adjacent, hard, weight):
        self.first_event = first_event
        self.second_event = second_event
        self.person = person
        self.want_adjacent = want_adjacent
        self.hard = hard
        self.weight = weight
        self.first_end = None
        self.second_start = None
        self.prev_event = None
        self.score = 0

    def reset(self):
        self.first_end = None
        self.second_start = None
        self.prev_event = None
        self.score = 0

    def process(self, hour, a_event, b_event):
        event = a_event if self.person == "a" else b_event
        if self.prev_event is self.first_event and event is not self.first_event:
            self.first_end = hour
        if event is self.second_event and self.second_start is None:
            self.second_start = hour
        self.prev_event = event

    def finalize(self):
        if self.first_end is None or self.second_start is None:
            self.score = 0
            return
        adjacent = (self.second_start - self.first_end == 0)
        self.score = 0.0 if (adjacent == self.want_adjacent) else 1.0


# Single: prefer a min and/or max gap between two of one person's events.
# Score = how far outside [min_gap, max_gap] the actual gap is, normalized.
class TimeBetweenEvents:
    is_cross = False

    def __init__(self, first_event, second_event, person, hard, weight,
                 min_gap=None, max_gap=None):
        self.first_event = first_event
        self.second_event = second_event
        self.person = person
        self.min_gap = min_gap
        self.max_gap = max_gap
        self.hard = hard
        self.weight = weight
        self.first_end = None
        self.second_start = None
        self.prev_event = None
        self.score = 0

    def reset(self):
        self.first_end = None
        self.second_start = None
        self.prev_event = None
        self.score = 0

    def process(self, hour, a_event, b_event):
        event = a_event if self.person == "a" else b_event
        if self.prev_event is self.first_event and event is not self.first_event:
            self.first_end = hour
        if event is self.second_event and self.second_start is None:
            self.second_start = hour
        self.prev_event = event

    def finalize(self):
        if self.first_end is None or self.second_start is None:
            self.score = 0
            return
        gap = max(0, self.second_start - self.first_end)
        if self.min_gap is not None and gap < self.min_gap:
            self.score = (self.min_gap - gap) / self.min_gap
        elif self.max_gap is not None and gap > self.max_gap:
            self.score = min((gap - self.max_gap) / 24, 1.0)
        else:
            self.score = 0.0


# Single: require a minimum amount of free time immediately before and/or after an event.
# Score = fraction of required buffer hours that are occupied.
class FreeTimeAroundEvent:
    is_cross = False

    def __init__(self, event, person, hard, weight, before=0, after=0):
        self.event = event
        self.person = person
        self.before = before
        self.after = after
        self.hard = hard
        self.weight = weight
        self.event_start = None
        self.event_end = None
        self.schedule = {}
        self.score = 0

    def reset(self):
        self.event_start = None
        self.event_end = None
        self.schedule = {}
        self.score = 0

    def process(self, hour, a_event, b_event):
        event = a_event if self.person == "a" else b_event
        self.schedule[hour] = event
        if event is self.event:
            if self.event_start is None:
                self.event_start = hour
            self.event_end = hour + 1

    def finalize(self):
        if self.event_start is None or self.event_end is None:
            self.score = 0
            return
        required = self.before + self.after
        if required == 0:
            self.score = 0
            return
        missing = 0
        for h in range(self.event_start - self.before, self.event_start):
            if h < 0 or self.schedule.get(h) is not None:
                missing += 1
        for h in range(self.event_end, self.event_end + self.after):
            if h >= 24 or self.schedule.get(h) is not None:
                missing += 1
        self.score = missing / required


# ── DAILY SCHEDULE SHAPE FOR ONE PERSON ──────────────────────────────────────

# Single: prefer a person's events to be clustered together (minimize idle gaps).
# Set tight=False to prefer spread out. Score = gap ratio within active span.
class KeepScheduleTight:
    is_cross = False

    def __init__(self, person, tight, hard, weight):
        self.person = person
        self.tight = tight
        self.hard = hard
        self.weight = weight
        self.schedule = {}
        self.score = 0

    def reset(self):
        self.schedule = {}
        self.score = 0

    def process(self, hour, a_event, b_event):
        event = a_event if self.person == "a" else b_event
        self.schedule[hour] = event

    def finalize(self):
        active = [h for h, e in self.schedule.items() if e is not None]
        if not active:
            self.score = 0
            return
        span_start, span_end = min(active), max(active) + 1
        span = span_end - span_start
        gap_hours = sum(1 for h in range(span_start, span_end) if self.schedule.get(h) is None)
        gap_ratio = gap_hours / span if span > 0 else 0
        self.score = gap_ratio if self.tight else (1 - gap_ratio)


# Single: limit how many distinct break segments exist between a person's events.
# Score = normalized excess beyond max_gaps.
class MaxGapsInDay:
    is_cross = False

    def __init__(self, person, max_gaps, hard, weight):
        self.person = person
        self.max_gaps = max_gaps
        self.hard = hard
        self.weight = weight
        self.gap_count = 0
        self.in_gap = False
        self.started = False
        self.score = 0

    def reset(self):
        self.gap_count = 0
        self.in_gap = False
        self.started = False
        self.score = 0

    def process(self, hour, a_event, b_event):
        event = a_event if self.person == "a" else b_event
        if event is not None:
            if self.started and self.in_gap:
                self.gap_count += 1
            self.started = True
            self.in_gap = False
        else:
            if self.started:
                self.in_gap = True

    def finalize(self):
        excess = max(0, self.gap_count - self.max_gaps)
        self.score = min(excess / max(self.max_gaps + 1, 1), 1.0)


# Single: ensure there is at least one contiguous free block of at least min_duration hours.
# Score = how short the longest free block falls, normalized.
class GuaranteedFreeBlock:
    is_cross = False

    def __init__(self, person, min_duration, hard, weight):
        self.person = person
        self.min_duration = min_duration
        self.hard = hard
        self.weight = weight
        self.max_free_block = 0
        self.current_run = 0
        self.score = 0

    def reset(self):
        self.max_free_block = 0
        self.current_run = 0
        self.score = 0

    def process(self, hour, a_event, b_event):
        event = a_event if self.person == "a" else b_event
        if event is None:
            self.current_run += 1
            self.max_free_block = max(self.max_free_block, self.current_run)
        else:
            self.current_run = 0

    def finalize(self):
        if self.max_free_block >= self.min_duration:
            self.score = 0.0
        else:
            self.score = (self.min_duration - self.max_free_block) / self.min_duration


# Single: prefer a min and/or max number of hours spent at home per day.
# "Home" includes free time and any in_dorm events.
class TotalHomeHours:
    is_cross = False

    def __init__(self, person, hard, weight, min_hours=None, max_hours=None):
        self.person = person
        self.min_hours = min_hours
        self.max_hours = max_hours
        self.hard = hard
        self.weight = weight
        self.home_hours = 0
        self.score = 0

    def reset(self):
        self.home_hours = 0
        self.score = 0

    def process(self, hour, a_event, b_event):
        event = a_event if self.person == "a" else b_event
        if event is None or event.in_dorm:
            self.home_hours += 1

    def finalize(self):
        if self.min_hours is not None and self.home_hours < self.min_hours:
            self.score = (self.min_hours - self.home_hours) / 24
        elif self.max_hours is not None and self.home_hours > self.max_hours:
            self.score = (self.home_hours - self.max_hours) / 24
        else:
            self.score = 0.0


# Single: prefer that a specific event does not exceed max_hours total.
# Score = normalized excess hours above the limit.
class MaxTimesPerDay:
    is_cross = False

    def __init__(self, event, person, max_hours, hard, weight):
        self.event = event
        self.person = person
        self.max_hours = max_hours
        self.hard = hard
        self.weight = weight
        self.event_hours = 0
        self.score = 0

    def reset(self):
        self.event_hours = 0
        self.score = 0

    def process(self, hour, a_event, b_event):
        event = a_event if self.person == "a" else b_event
        if event is self.event:
            self.event_hours += 1

    def finalize(self):
        excess = max(0, self.event_hours - self.max_hours)
        self.score = min(excess / 24, 1.0)


# ── EVENT ORDER BETWEEN ROOMMATES ─────────────────────────────────────────────

# Cross-relational: first_event (from first_person's schedule) must start before
# second_event (from second_person's schedule). Used by constraint_factory when
# event_before_event spans two different people's schedules.
# Binary score: 0 if correctly ordered, 1 if violated.
class CrossEventBeforeEvent:
    is_cross = True

    def __init__(self, first_event, first_person, second_event, second_person, hard, weight):
        self.first_event = first_event
        self.first_person = first_person
        self.second_event = second_event
        self.second_person = second_person
        self.hard = hard
        self.weight = weight
        self.first_start = None
        self.second_start = None
        self.score = 0

    def reset(self):
        self.first_start = None
        self.second_start = None
        self.score = 0

    def reset_side(self, person):
        if person == self.first_person:
            self.first_start = None
        if person == self.second_person:
            self.second_start = None

    def accumulate(self, person, hour, event):
        if person == self.first_person and event is self.first_event and self.first_start is None:
            self.first_start = hour
        if person == self.second_person and event is self.second_event and self.second_start is None:
            self.second_start = hour

    def get_state(self, person):
        if person == self.first_person:
            return {"first_start": self.first_start}
        return {"second_start": self.second_start}

    def load_state(self, person, state):
        for k, v in state.items():
            setattr(self, k, v)

    def compare(self):
        if self.first_start is None or self.second_start is None:
            self.score = 0
            return
        self.score = 1.0 if self.first_start >= self.second_start else 0.0


# Cross-relational: prefer that A's event starts before B's event.
# Binary score: 0 if correctly ordered, 1 if violated.
class MyEventBeforeTheirEvent:
    is_cross = True

    def __init__(self, a_event, b_event, hard, weight):
        self.a_event = a_event
        self.b_event = b_event
        self.hard = hard
        self.weight = weight
        self.a_start = None
        self.b_start = None
        self.score = 0

    def reset(self):
        self.a_start = None
        self.b_start = None
        self.score = 0

    def reset_side(self, person):
        if person == "a":
            self.a_start = None
        else:
            self.b_start = None

    def accumulate(self, person, hour, event):
        if person == "a":
            if event is self.a_event and self.a_start is None:
                self.a_start = hour
        else:
            if event is self.b_event and self.b_start is None:
                self.b_start = hour

    def get_state(self, person):
        return {"a_start": self.a_start} if person == "a" else {"b_start": self.b_start}

    def load_state(self, person, state):
        for k, v in state.items():
            setattr(self, k, v)

    def compare(self):
        if self.a_start is None or self.b_start is None:
            self.score = 0
            return
        self.score = 1.0 if self.a_start >= self.b_start else 0.0


# Cross-relational: prefer a min and/or max gap between when A's event ends and B's begins.
# Score = how far outside [min_gap, max_gap] the actual gap is, normalized.
class TimeBetweenOurEvents:
    is_cross = True

    def __init__(self, a_event, b_event, hard, weight, min_gap=None, max_gap=None):
        self.a_event = a_event
        self.b_event = b_event
        self.min_gap = min_gap
        self.max_gap = max_gap
        self.hard = hard
        self.weight = weight
        self.a_end = None
        self.b_start = None
        self._prev_a = None
        self.score = 0

    def reset(self):
        self.a_end = None
        self.b_start = None
        self._prev_a = None
        self.score = 0

    def reset_side(self, person):
        if person == "a":
            self.a_end = None
            self._prev_a = None
        else:
            self.b_start = None

    def accumulate(self, person, hour, event):
        if person == "a":
            if self._prev_a is self.a_event and event is not self.a_event:
                self.a_end = hour
            self._prev_a = event
        else:
            if event is self.b_event and self.b_start is None:
                self.b_start = hour

    def get_state(self, person):
        return {"a_end": self.a_end} if person == "a" else {"b_start": self.b_start}

    def load_state(self, person, state):
        for k, v in state.items():
            setattr(self, k, v)

    def compare(self):
        if self.a_end is None or self.b_start is None:
            self.score = 0
            return
        gap = max(0, self.b_start - self.a_end)
        if self.min_gap is not None and gap < self.min_gap:
            self.score = (self.min_gap - gap) / self.min_gap
        elif self.max_gap is not None and gap > self.max_gap:
            self.score = min((gap - self.max_gap) / 24, 1.0)
        else:
            self.score = 0.0


# Cross-relational: prefer two events (one per roommate) to start at the same hour.
# Score = difference in start hours, normalized by 24.
class StartAtSameTime:
    is_cross = True

    def __init__(self, a_event, b_event, hard, weight):
        self.a_event = a_event
        self.b_event = b_event
        self.hard = hard
        self.weight = weight
        self.a_start = None
        self.b_start = None
        self.score = 0

    def reset(self):
        self.a_start = None
        self.b_start = None
        self.score = 0

    def reset_side(self, person):
        if person == "a":
            self.a_start = None
        else:
            self.b_start = None

    def accumulate(self, person, hour, event):
        if person == "a":
            if event is self.a_event and self.a_start is None:
                self.a_start = hour
        else:
            if event is self.b_event and self.b_start is None:
                self.b_start = hour

    def get_state(self, person):
        return {"a_start": self.a_start} if person == "a" else {"b_start": self.b_start}

    def load_state(self, person, state):
        for k, v in state.items():
            setattr(self, k, v)

    def compare(self):
        if self.a_start is None or self.b_start is None:
            self.score = 0
            return
        self.score = abs(self.a_start - self.b_start) / 24


# ── ROOMMATE OVERLAP ──────────────────────────────────────────────────────────

# Cross-relational: prevent two specific events from happening at the same time.
# Score = fraction of the shorter event's hours that overlap with the other.
class NotAtSameTime:
    is_cross = True

    def __init__(self, a_event, b_event, hard, weight):
        self.a_event = a_event
        self.b_event = b_event
        self.hard = hard
        self.weight = weight
        self.a_hours = set()
        self.b_hours = set()
        self.score = 0

    def reset(self):
        self.a_hours = set()
        self.b_hours = set()
        self.score = 0

    def reset_side(self, person):
        if person == "a":
            self.a_hours = set()
        else:
            self.b_hours = set()

    def accumulate(self, person, hour, event):
        if person == "a" and event is self.a_event:
            self.a_hours.add(hour)
        elif person == "b" and event is self.b_event:
            self.b_hours.add(hour)

    def get_state(self, person):
        return {"a_hours": frozenset(self.a_hours)} if person == "a" else {"b_hours": frozenset(self.b_hours)}

    def load_state(self, person, state):
        for k, v in state.items():
            setattr(self, k, v)

    def compare(self):
        overlap = len(self.a_hours & self.b_hours)
        denom = min(self.a_event.duration, self.b_event.duration)
        self.score = overlap / denom if denom else 0


# Cross-relational: maximize or minimize overlap between two specific events.
# maximize=True: penalize low overlap; maximize=False: penalize high overlap.
class OverlapTheirEvents:
    is_cross = True

    def __init__(self, a_event, b_event, maximize, hard, weight):
        self.a_event = a_event
        self.b_event = b_event
        self.maximize = maximize
        self.hard = hard
        self.weight = weight
        self.a_hours = set()
        self.b_hours = set()
        self.score = 0

    def reset(self):
        self.a_hours = set()
        self.b_hours = set()
        self.score = 0

    def reset_side(self, person):
        if person == "a":
            self.a_hours = set()
        else:
            self.b_hours = set()

    def accumulate(self, person, hour, event):
        if person == "a" and event is self.a_event:
            self.a_hours.add(hour)
        elif person == "b" and event is self.b_event:
            self.b_hours.add(hour)

    def get_state(self, person):
        return {"a_hours": frozenset(self.a_hours)} if person == "a" else {"b_hours": frozenset(self.b_hours)}

    def load_state(self, person, state):
        for k, v in state.items():
            setattr(self, k, v)

    def compare(self):
        max_possible = min(self.a_event.duration, self.b_event.duration)
        if max_possible == 0:
            self.score = 0
            return
        overlap = len(self.a_hours & self.b_hours)
        ratio = overlap / max_possible
        self.score = (1 - ratio) if self.maximize else ratio


# Cross-relational: maximize or minimize total hours both roommates are home simultaneously.
# "Home" = in_dorm=True or free time (None). minimize=True: penalize high overlap.
class BothHome:
    is_cross = True

    def __init__(self, minimize, hard, weight):
        self.minimize = minimize
        self.hard = hard
        self.weight = weight
        self.a_home_hours = set()
        self.b_home_hours = set()
        self.score = 0

    def reset(self):
        self.a_home_hours = set()
        self.b_home_hours = set()
        self.score = 0

    def reset_side(self, person):
        if person == "a":
            self.a_home_hours = set()
        else:
            self.b_home_hours = set()

    def accumulate(self, person, hour, event):
        is_home = event is None or event.in_dorm
        if person == "a" and is_home:
            self.a_home_hours.add(hour)
        elif person == "b" and is_home:
            self.b_home_hours.add(hour)

    def get_state(self, person):
        return {"a_home_hours": frozenset(self.a_home_hours)} if person == "a" else {"b_home_hours": frozenset(self.b_home_hours)}

    def load_state(self, person, state):
        for k, v in state.items():
            setattr(self, k, v)

    def compare(self):
        overlap = len(self.a_home_hours & self.b_home_hours)
        self.score = overlap / 24 if self.minimize else (1 - overlap / 24)


# Cross-relational: enforce min and/or max hours where both roommates are home simultaneously.
class BothHomeLimits:
    is_cross = True

    def __init__(self, hard, weight, min_hours=None, max_hours=None):
        self.min_hours = min_hours
        self.max_hours = max_hours
        self.hard = hard
        self.weight = weight
        self.a_home_hours = set()
        self.b_home_hours = set()
        self.score = 0

    def reset(self):
        self.a_home_hours = set()
        self.b_home_hours = set()
        self.score = 0

    def reset_side(self, person):
        if person == "a":
            self.a_home_hours = set()
        else:
            self.b_home_hours = set()

    def accumulate(self, person, hour, event):
        is_home = event is None or event.in_dorm
        if person == "a" and is_home:
            self.a_home_hours.add(hour)
        elif person == "b" and is_home:
            self.b_home_hours.add(hour)

    def get_state(self, person):
        return {"a_home_hours": frozenset(self.a_home_hours)} if person == "a" else {"b_home_hours": frozenset(self.b_home_hours)}

    def load_state(self, person, state):
        for k, v in state.items():
            setattr(self, k, v)

    def compare(self):
        overlap = len(self.a_home_hours & self.b_home_hours)
        if self.min_hours is not None and overlap < self.min_hours:
            self.score = (self.min_hours - overlap) / 24
        elif self.max_hours is not None and overlap > self.max_hours:
            self.score = (overlap - self.max_hours) / 24
        else:
            self.score = 0.0


# ── SHARED SPACES ─────────────────────────────────────────────────────────────

# Cross-relational: only one roommate should use a shared resource at a time.
# Score = fraction of the shorter usage period where both are using simultaneously.
class OneAtATime:
    is_cross = True

    def __init__(self, a_event, b_event, hard, weight):
        self.a_event = a_event
        self.b_event = b_event
        self.hard = hard
        self.weight = weight
        self.a_hours = set()
        self.b_hours = set()
        self.score = 0

    def reset(self):
        self.a_hours = set()
        self.b_hours = set()
        self.score = 0

    def reset_side(self, person):
        if person == "a":
            self.a_hours = set()
        else:
            self.b_hours = set()

    def accumulate(self, person, hour, event):
        if person == "a" and event is self.a_event:
            self.a_hours.add(hour)
        elif person == "b" and event is self.b_event:
            self.b_hours.add(hour)

    def get_state(self, person):
        return {"a_hours": frozenset(self.a_hours)} if person == "a" else {"b_hours": frozenset(self.b_hours)}

    def load_state(self, person, state):
        for k, v in state.items():
            setattr(self, k, v)

    def compare(self):
        conflict = len(self.a_hours & self.b_hours)
        denom = min(self.a_event.duration, self.b_event.duration)
        self.score = conflict / denom if denom else 0


# Cross-relational: prefer a minimum cooldown between one person finishing a shared
# resource and the other starting it. Checks both directions (A then B, B then A).
# Score = how short the actual minimum gap falls below min_gap, normalized.
class GapBetweenUses:
    is_cross = True

    def __init__(self, a_event, b_event, min_gap, hard, weight):
        self.a_event = a_event
        self.b_event = b_event
        self.min_gap = min_gap
        self.hard = hard
        self.weight = weight
        self.a_start = None
        self.a_end = None
        self.b_start = None
        self.b_end = None
        self._prev_a = None
        self._prev_b = None
        self.score = 0

    def reset(self):
        self.a_start = self.a_end = self.b_start = self.b_end = None
        self._prev_a = self._prev_b = None
        self.score = 0

    def reset_side(self, person):
        if person == "a":
            self.a_start = self.a_end = self._prev_a = None
        else:
            self.b_start = self.b_end = self._prev_b = None

    def accumulate(self, person, hour, event):
        if person == "a":
            if event is self.a_event and self.a_start is None:
                self.a_start = hour
            if self._prev_a is self.a_event and event is not self.a_event:
                self.a_end = hour
            self._prev_a = event
        else:
            if event is self.b_event and self.b_start is None:
                self.b_start = hour
            if self._prev_b is self.b_event and event is not self.b_event:
                self.b_end = hour
            self._prev_b = event

    def get_state(self, person):
        if person == "a":
            return {"a_start": self.a_start, "a_end": self.a_end}
        return {"b_start": self.b_start, "b_end": self.b_end}

    def load_state(self, person, state):
        for k, v in state.items():
            setattr(self, k, v)

    def compare(self):
        gaps = []
        if self.a_end is not None and self.b_start is not None:
            gaps.append(self.b_start - self.a_end)
        if self.b_end is not None and self.a_start is not None:
            gaps.append(self.a_start - self.b_end)
        if not gaps:
            self.score = 0.0
            return
        shortest = min(gaps)
        self.score = (self.min_gap - max(0, shortest)) / self.min_gap if shortest < self.min_gap else 0.0


# Cross-relational: prefer that both roommates spend roughly equal time on a shared resource.
# Score = imbalance ratio: 0 = equal, 1 = one person uses it entirely.
class ShareEqually:
    is_cross = True

    def __init__(self, a_event, b_event, hard, weight):
        self.a_event = a_event
        self.b_event = b_event
        self.hard = hard
        self.weight = weight
        self.a_hours = 0
        self.b_hours = 0
        self.score = 0

    def reset(self):
        self.a_hours = 0
        self.b_hours = 0
        self.score = 0

    def reset_side(self, person):
        if person == "a":
            self.a_hours = 0
        else:
            self.b_hours = 0

    def accumulate(self, person, hour, event):
        if person == "a" and event is self.a_event:
            self.a_hours += 1
        elif person == "b" and event is self.b_event:
            self.b_hours += 1

    def get_state(self, person):
        return {"a_hours": self.a_hours} if person == "a" else {"b_hours": self.b_hours}

    def load_state(self, person, state):
        for k, v in state.items():
            setattr(self, k, v)

    def compare(self):
        total = self.a_hours + self.b_hours
        self.score = abs(self.a_hours - self.b_hours) / total if total else 0


# ── ROOMMATE-SPECIFIC ─────────────────────────────────────────────────────────

# Cross-relational: A's noisy event should not overlap with B's sleep event.
# Score = fraction of sleep hours where the noisy event is simultaneously active.
# NOTE: Functionally equivalent to NotAtSameTime(a_event=noise_event, b_event=sleep_event).
# Kept as a separate class so the AI can output "no_noise_when_sleeping" naturally.
class NoNoiseWhenSleeping:
    is_cross = True

    def __init__(self, noise_event, sleep_event, hard, weight,
                 noise_person="a", sleep_person="b"):
        self.noise_event = noise_event
        self.sleep_event = sleep_event
        self.hard = hard
        self.weight = weight
        # noise_person / sleep_person tell us which schedule each event lives in.
        # constraint_factory derives these from actual event ownership so the
        # constraint works regardless of which roommate is "noisy" or "sleeping".
        self.noise_person = noise_person
        self.sleep_person = sleep_person
        self.noise_hours = set()
        self.sleep_hours = set()
        self.score = 0

    def reset(self):
        self.noise_hours = set()
        self.sleep_hours = set()
        self.score = 0

    def reset_side(self, person):
        if person == self.noise_person:
            self.noise_hours = set()
        if person == self.sleep_person:
            self.sleep_hours = set()

    def accumulate(self, person, hour, event):
        if person == self.noise_person and event is self.noise_event:
            self.noise_hours.add(hour)
        if person == self.sleep_person and event is self.sleep_event:
            self.sleep_hours.add(hour)

    def get_state(self, person):
        if person == self.noise_person:
            return {"noise_hours": frozenset(self.noise_hours)}
        return {"sleep_hours": frozenset(self.sleep_hours)}

    def load_state(self, person, state):
        for k, v in state.items():
            setattr(self, k, v)

    def compare(self):
        overlap = len(self.noise_hours & self.sleep_hours)
        denom = self.sleep_event.duration
        self.score = overlap / denom if denom else 0


# Cross-relational: one person's "guest" event should not occur while the other is home.
# Score = fraction of guest hours where the other person is home.
class NoGuestsWhenHome:
    is_cross = True

    def __init__(self, guest_event, person_with_guest, hard, weight):
        self.guest_event = guest_event
        self.person_with_guest = person_with_guest  # "a" or "b"
        self.hard = hard
        self.weight = weight
        # guest_hours: hours the guest event is active (on person_with_guest's schedule)
        # other_home_hours: hours the other person is home
        self.guest_hours = set()
        self.other_home_hours = set()
        self.score = 0

    def reset(self):
        self.guest_hours = set()
        self.other_home_hours = set()
        self.score = 0

    def reset_side(self, person):
        # The person_with_guest side tracks guest hours; the other tracks home hours
        is_guest_side = (person == self.person_with_guest)
        if is_guest_side:
            self.guest_hours = set()
        else:
            self.other_home_hours = set()

    def accumulate(self, person, hour, event):
        is_guest_side = (person == self.person_with_guest)
        if is_guest_side:
            if event is self.guest_event:
                self.guest_hours.add(hour)
        else:
            if event is None or event.in_dorm:
                self.other_home_hours.add(hour)

    def get_state(self, person):
        is_guest_side = (person == self.person_with_guest)
        if is_guest_side:
            return {"guest_hours": frozenset(self.guest_hours)}
        return {"other_home_hours": frozenset(self.other_home_hours)}

    def load_state(self, person, state):
        for k, v in state.items():
            setattr(self, k, v)

    def compare(self):
        overlap = len(self.guest_hours & self.other_home_hours)
        denom = self.guest_event.duration
        self.score = overlap / denom if denom else 0


# Cross-relational: prefer that both roommates spend roughly equal total hours at home.
# Score = difference in home hours normalized by 24.
class EqualHomeTime:
    is_cross = True

    def __init__(self, hard, weight):
        self.hard = hard
        self.weight = weight
        self.a_home = 0
        self.b_home = 0
        self.score = 0

    def reset(self):
        self.a_home = 0
        self.b_home = 0
        self.score = 0

    def reset_side(self, person):
        if person == "a":
            self.a_home = 0
        else:
            self.b_home = 0

    def accumulate(self, person, hour, event):
        is_home = event is None or event.in_dorm
        if person == "a" and is_home:
            self.a_home += 1
        elif person == "b" and is_home:
            self.b_home += 1

    def get_state(self, person):
        return {"a_home": self.a_home} if person == "a" else {"b_home": self.b_home}

    def load_state(self, person, state):
        for k, v in state.items():
            setattr(self, k, v)

    def compare(self):
        self.score = abs(self.a_home - self.b_home) / 24
