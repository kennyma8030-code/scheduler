import heapq
from itertools import product
from backend.constants import constraint_dict
from backend.templates import CrossEventBeforeEvent
from collections import defaultdict


class ScoredSchedule:
    """
    Wraps a raw schedule dict with precomputed metadata from the first pass:
      - single_penalty: sum of (weight * score) for all single-person constraints
      - hard_fail:      True if any hard single-person constraint was violated
      - cross_states:   per-constraint state snapshot {id(constraint): state_dict}
      - blocks:         precomputed timeline blocks for API output
    """
    schedule: dict
    single_penalty: float
    hard_fail: bool
    cross_states: dict
    blocks: list

    def __init__(self, schedule):
        self.schedule = schedule
        self.single_penalty = 0.0
        self.hard_fail = False
        self.cross_states = {}
        self.blocks = []


class ScheduleOptimizer:

    @staticmethod
    def available_flexible(schedule):
        occupied = set()
        for event in schedule.fixed_events:
            for hour in range(event.start, event.start + event.duration):
                occupied.add(hour)
        return set(range(24)) - occupied
    
    @staticmethod
    def available_flexible_weekly(day_fixed_dict, day):
        occupied = set()
        for event in day_fixed_dict[day]:
            for hour in range(event.start, event.start + event.duration):
                occupied.add(hour)
        return set(range(24)) - occupied

    @staticmethod
    def fixed(schedule):
        hour_map = {}
        for event in schedule.fixed_events:
            for hour in range(event.start, event.start + event.duration):
                hour_map[hour] = event
        return hour_map
    
    @staticmethod
    def fixed_weekly(day_fixed_dict, day):
        hour_map = {}
        for event in day_fixed_dict[day]:
            for hour in range(event.start, event.start + event.duration):
                hour_map[hour] = event
        return hour_map

    @staticmethod
    def valid_starts(event, free_hours):
        return [
            h for h in free_hours
            if set(range(h, h + event.duration)).issubset(free_hours)
        ]

    @staticmethod
    def generate(events, free_hours):
        if not events:
            return [[]]
        event = events[0]
        remaining = events[1:]
        results = []
        for start in ScheduleOptimizer.valid_starts(event, free_hours):
            used = set(range(start, start + event.duration))
            for sub in ScheduleOptimizer.generate(remaining, free_hours - used):
                results.append([{"event": event, "start": start}] + sub)
        return results

    @staticmethod
    def combinations_weekly(schedule_weekly):
        day_flexible_dict = defaultdict(list)
        for event in schedule_weekly.flexible_events:
            for day in event.days:
                day_flexible_dict[day].append(event)

        day_fixed_dict = defaultdict(list)
        for event in schedule_weekly.fixed_events:
            for day in event.days:
                day_fixed_dict[day].append(event)
        
        schedules = {}
        
        for day in range(7):
            fixed_schedule = ScheduleOptimizer.fixed_weekly(day_fixed_dict, day)
            events = day_flexible_dict[day]
            free_hours = ScheduleOptimizer.available_flexible_weekly(day_fixed_dict, day)
            schedules[day] = ScheduleOptimizer.combinations(events, free_hours, fixed_schedule)
        
        return schedules

    @staticmethod
    def combinations(events, free_hours, fixed_schedule):
        schedules = []
        for placement in ScheduleOptimizer.generate(events, free_hours):
            flex_map = {}
            for p in placement:
                for hour in range(p["start"], p["start"] + p["event"].duration):
                    flex_map[hour] = p["event"]
            full = fixed_schedule.copy()
            full.update(flex_map)
            schedules.append(full)
        return schedules

    @staticmethod
    def first_pass(schedules, person, single_constraints, cross_constraints):
        """
        Phase 1: process each schedule individually.

        For single-person constraints: runs the full process/finalize cycle and
        accumulates the weighted penalty. Hard failures are flagged immediately.

        For cross-relational constraints: accumulates per-person state (e.g. which
        hours an event is active) without pairing. The state is snapshotted and
        stored on the ScoredSchedule so phase 2 can compare pairs without
        re-looping 24 hours.

        Timeline blocks are precomputed here since the schedule never changes.
        """
        scored = []
        for sched in schedules:
            scored_schedule = ScoredSchedule(sched)

            for c in single_constraints:
                c.reset()
            for c in cross_constraints:
                c.reset_side(person)

            for hour in range(24):
                event = sched.get(hour)
                # Single constraints expect (hour, a_event, b_event); pass None
                # for the unused slot — the constraint picks the right one via self.person
                a_ev = event if person == "a" else None
                b_ev = event if person == "b" else None
                for c in single_constraints:
                    c.process(hour, a_ev, b_ev)
                for c in cross_constraints:
                    c.accumulate(person, hour, event)

            for c in single_constraints:
                c.finalize()
                if c.hard and c.score > 0:
                    scored_schedule.hard_fail = True
                scored_schedule.single_penalty += c.weight * c.score

            # Snapshot cross-constraint state for this person's side
            for c in cross_constraints:
                scored_schedule.cross_states[id(c)] = c.get_state(person)

            scored_schedule.blocks = ScheduleOptimizer.schedule_to_blocks(sched)
            scored.append(scored_schedule)

        return scored
    
    @staticmethod
    def best_schedules_weekly(schedules_a_dict, schedules_b_dict, active_constraints):
        results = []
        for day in range(7):
            curr_schedule_a = schedules_a_dict[day]
            curr_schedule_b = schedules_b_dict[day]
            results.append(ScheduleOptimizer.best_schedules(curr_schedule_a, curr_schedule_b, active_constraints))
        return results

    @staticmethod
    def best_schedules(schedules_a, schedules_b, active_constraints):
        # Partition into single-person (by side) and cross-relational
        single_a = [c for c in active_constraints if not c.is_cross and c.person == "a"]
        single_b = [c for c in active_constraints if not c.is_cross and c.person == "b"]
        cross    = [c for c in active_constraints if c.is_cross]

        total_weight = sum(c.weight for c in active_constraints) or 1.0

        # Phase 1: score individuals, accumulate cross states
        scored_a = ScheduleOptimizer.first_pass(schedules_a, "a", single_a, cross)
        scored_b = ScheduleOptimizer.first_pass(schedules_b, "b", single_b, cross)

        # Prune schedules that already violate a hard single person constraint —
        # no pairing can save them
        valid_a = [s for s in scored_a if not s.hard_fail]
        valid_b = [s for s in scored_b if not s.hard_fail]

        # Phase 2: pair and score cross-relational constraints
        # Use a min-heap of size MAX_RESULTS to keep only the top scores
        MAX_RESULTS = 1
        heap = []   # (score, tiebreak_idx, sa, sb)
        idx = 0
        passing_pairs = 0
        all_scores = []

        for sa, sb in product(valid_a, valid_b):
            pair_penalty = 0.0
            hard_fail = False

            for c in cross:
                c.load_state("a", sa.cross_states[id(c)])
                c.load_state("b", sb.cross_states[id(c)])
                c.compare()
                # Early exit: no point scoring further once a hard constraint fires
                if c.hard and c.score > 0:
                    hard_fail = True
                    break
                pair_penalty += c.weight * c.score

            if hard_fail:
                continue

            passing_pairs += 1
            total_penalty = sa.single_penalty + sb.single_penalty + pair_penalty
            final_score = (1 - total_penalty / total_weight) * 100
            all_scores.append(final_score)

            heapq.heappush(heap, (final_score, idx, sa, sb))
            idx += 1
            if len(heap) > MAX_RESULTS:
                heapq.heappop(heap)  # drop the lowest score

        results = [
            {"score": score, "roommate_a": sa.blocks, "roommate_b": sb.blocks}
            for score, _, sa, sb in sorted(heap, key=lambda x: -x[0])
        ]

        stats: dict[str, object] = {
            "schedules_a":    len(schedules_a),
            "schedules_b":    len(schedules_b),
            "hard_pruned_a":  sum(1 for s in scored_a if s.hard_fail),
            "hard_pruned_b":  sum(1 for s in scored_b if s.hard_fail),
            "valid_pairs":    len(valid_a) * len(valid_b),
            "passing_pairs":  passing_pairs,
        }
        if all_scores:
            n = len(all_scores)
            mean = sum(all_scores) / n
            sorted_s = sorted(all_scores)
            median = sorted_s[n // 2] if n % 2 else (sorted_s[n // 2 - 1] + sorted_s[n // 2]) / 2
            stdev  = (sum((s - mean) ** 2 for s in all_scores) / n) ** 0.5
            stats["score_min"]    = round(min(all_scores), 2)
            stats["score_max"]    = round(max(all_scores), 2)
            stats["score_mean"]   = round(mean, 2)
            stats["score_median"] = round(median, 2)
            stats["score_stdev"]  = round(stdev, 2)

        return {"results": results, "stats": stats}

    @staticmethod
    def constraint_factory(ai_output, events_a, events_b):
        # Per-person maps so shared event names resolve to the right object
        event_map_a = {e.name: e for e in events_a}
        event_map_b = {e.name: e for e in events_b}
        event_map   = {**event_map_a, **event_map_b}   # fallback (b wins on collision)
        events_a_ids = {id(e) for e in events_a}
        constraints = []

        def person_of(event):
            return "a" if id(event) in events_a_ids else "b"

        for item in ai_output:
            cls = constraint_dict.get(item["type"])
            if cls is None:
                continue
            params = {k: v for k, v in item.items() if k != "type"}
            person_hint = item.get("person")  # "a", "b", or None
            for key in ["event", "first_event", "second_event",
                        "noise_event", "sleep_event", "guest_event"]:
                if key in params and isinstance(params[key], str):
                    name = params[key]
                    if person_hint == "a":
                        params[key] = event_map_a.get(name) or event_map.get(name, name)
                    elif person_hint == "b":
                        params[key] = event_map_b.get(name) or event_map.get(name, name)
                    else:
                        params[key] = event_map.get(name, name)
            # Cross constraints: a_event from A's map, b_event from B's map
            for key, emap in [("a_event", event_map_a), ("b_event", event_map_b)]:
                if key in params and isinstance(params[key], str):
                    name = params[key]
                    params[key] = emap.get(name) or event_map.get(name, name)

            # Auto-correct person for single-person constraints using event ownership
            if "person" in params:
                anchor = (params.get("event")
                          or params.get("first_event")
                          or params.get("second_event"))
                if anchor is not None and not isinstance(anchor, str):
                    params["person"] = person_of(anchor)

            # Auto-swap a_event/b_event if they're provably assigned to the wrong person
            ae = params.get("a_event")
            be = params.get("b_event")
            if (ae is not None and be is not None
                    and not isinstance(ae, str) and not isinstance(be, str)
                    and person_of(ae) == "b" and person_of(be) == "a"):
                params["a_event"], params["b_event"] = be, ae

            # Inject noise_person/sleep_person for NoNoiseWhenSleeping
            if item["type"] == "no_noise_when_sleeping":
                ne = params.get("noise_event")
                se = params.get("sleep_event")
                if ne is not None and not isinstance(ne, str):
                    params.setdefault("noise_person", person_of(ne))
                if se is not None and not isinstance(se, str):
                    params.setdefault("sleep_person", person_of(se))

            # Promote event_before_event to CrossEventBeforeEvent when the two
            # events belong to different people's schedules
            if item["type"] == "event_before_event":
                fe = params.get("first_event")
                se = params.get("second_event")
                if (fe is not None and se is not None
                        and not isinstance(fe, str) and not isinstance(se, str)
                        and person_of(fe) != person_of(se)):
                    constraints.append(CrossEventBeforeEvent(
                        first_event=fe,
                        first_person=person_of(fe),
                        second_event=se,
                        second_person=person_of(se),
                        hard=params["hard"],
                        weight=params["weight"],
                    ))
                    continue

            # Drop constraint if any event param is still an unresolved string
            event_keys = ["event", "first_event", "second_event",
                          "noise_event", "sleep_event", "guest_event",
                          "a_event", "b_event"]
            if any(isinstance(params.get(k), str) for k in event_keys if k in params):
                continue

            constraints.append(cls(**params))
        return constraints

    @staticmethod
    def schedule_to_blocks(schedule):
        blocks = []
        current = None
        for hour in range(24):
            event = schedule.get(hour)
            if event is None:
                if current:
                    blocks.append(current)
                    current = None
                continue
            if current is not None:
                if current["event"] == event.name:
                    current["finish"] += 1
                    continue
                blocks.append(current)
            current = {"event": event.name, "start": hour, "finish": hour + 1, "in_dorm": event.in_dorm}
        if current:
            blocks.append(current)
        return blocks
