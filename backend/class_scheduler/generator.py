"""Course schedule generation: selection search over section candidates.

Nothing is ever *placed* — section times come fixed from the catalog, so the
search chooses one section per requirement group and the work is pruning the
Cartesian product. The shape of a run:

    0. skeleton validation   exact-section locks checked against each other
    1. hard filters          hard section constraints delete candidates
    2. skeleton pre-filter   candidates clashing with locked picks deleted
    3. conflict matrix       pairwise bitmask: time overlap OR 35-min campus
                             rule OR same course twice
    4. DFS                   fail-first group order, best-first candidates,
                             branch-and-bound on precomputed soft penalties
    5. leaf scoring          schedule + selection constraints over ~15 blocks
    6. result shaping        course combinations x section variants

The 35-minute cross-campus rule (travel.MIN_CAMPUS_TRANSFER_MIN, which
exempts the short Busch/Livingston hop) is enforced at the earliest possible
stage everywhere: steps 0, 2, and (via the mask) 4.

Execution is hybrid: sequential DFS below SEQUENTIAL_RAW_LIMIT estimated raw
combinations, a multiprocessing worker pool above it (the largest group's
candidates are partitioned across workers; each runs the same sequential
search on its slice). Never per-branch threads — a branch step is a
microsecond bitmask test, and pruning depends on a fresh shared bound.
"""

from __future__ import annotations

import heapq
import math
import os
import time
from dataclasses import dataclass

from backend.timegrid import SLOT_MINUTES
from backend.class_scheduler.models import Course, DAY_NAMES, Section
from backend.class_scheduler import travel
from backend.class_scheduler.constraints import (
    BaseConstraint,
    CreditRange,
    ScheduleConstraint,
    SectionConstraint,
    SelectionConstraint,
)

# Above this estimated raw product, the worker pool takes over.
SEQUENTIAL_RAW_LIMIT = 1_000_000
MAX_WORKERS = 8

# Per-group candidate caps (after hard filtering, best soft penalty kept).
GROUP_CANDIDATE_CAP = 60
FLEXIBLE_GROUP_CAP = 40  # groups spanning many courses (core / one_of fillers)

DEFAULT_BUDGET_S = 5.0
FROM_SCRATCH_BUDGET_S = 60.0
_BUDGET_CHECK_EVERY = 1024  # search nodes between clock checks


@dataclass(frozen=True)
class Block:
    """One timed weekly meeting, flattened for constraint math."""

    day: int            # 0=Monday .. 6=Sunday
    start: int          # minutes since midnight
    end: int
    campus_code: str    # "1".."5", "O", "Z", "S"
    mode: str


@dataclass
class Candidate:
    """One (course, section) choice with everything precomputed once."""

    course: Course
    section: Section
    group_idx: int
    cand_id: int = -1                     # global index, assigned after capping
    blocks: tuple[Block, ...] = ()
    day_masks: tuple[int, ...] = ()       # 7 x 288-bit occupancy ints
    is_fully_async: bool = False
    credits: float | None = None
    section_penalty: float = 0.0          # Σ w·s over soft section constraints
    conflict_mask: int = 0                # bit j set ⇒ conflicts with cand_id j
    group_label: str = ""                 # requirement label, survives reordering

    @classmethod
    def build(cls, course: Course, section: Section, group_idx: int) -> "Candidate":
        blocks = sorted(
            (
                Block(
                    day=m.day, start=m.start, end=m.end,
                    campus_code=m.campus_code, mode=m.mode,
                )
                for m in section.meetings
                if not m.is_async and m.end is not None
            ),
            key=lambda b: (b.day, b.start),
        )
        masks = [0] * 7
        for b in blocks:
            first = b.start // SLOT_MINUTES
            last = -(-b.end // SLOT_MINUTES)  # ceil: end minute is exclusive
            masks[b.day] |= ((1 << (last - first)) - 1) << first
        return cls(
            course=course,
            section=section,
            group_idx=group_idx,
            blocks=tuple(blocks),
            day_masks=tuple(masks),
            is_fully_async=not blocks,
            credits=course.credits,
        )


@dataclass
class Group:
    label: str
    candidates: list[Candidate]
    locked: bool = False                  # exact-section requirement (skeleton)
    flexible: bool = False                # spans many courses (core / one_of)
    min_section_penalty: float = 0.0


@dataclass
class WeekOccupancy:
    """Merged view of a full selection: 7 sorted per-day block lists."""

    days: list[list[Block]]
    selection: list[Candidate]

    @classmethod
    def build(cls, selection: list[Candidate]) -> "WeekOccupancy":
        days: list[list[Block]] = [[] for _ in range(7)]
        for cand in selection:
            for b in cand.blocks:
                days[b.day].append(b)
        for day in days:
            day.sort(key=lambda b: b.start)
        return cls(days=days, selection=selection)


# ---------------------------------------------------------------------------
# pairwise conflict logic


def _same_offering(a: Candidate, b: Candidate) -> bool:
    if (a.course.course_string, a.course.supplement) == (
        b.course.course_string, b.course.supplement
    ):
        return True
    return (
        a.section.index in b.section.cross_listed
        or b.section.index in a.section.cross_listed
    )


def _pair_conflicts(a: Candidate, b: Candidate) -> bool:
    """Time overlap, 35-minute campus violation, or the same class twice."""
    if _same_offering(a, b):
        return True
    if any(ma & mb for ma, mb in zip(a.day_masks, b.day_masks)):
        return True
    for ba in a.blocks:
        for bb in b.blocks:
            if ba.day != bb.day:
                continue
            if ba.end <= bb.start:
                if travel.transfer_violation(ba.end, bb.start, ba.campus_code, bb.campus_code):
                    return True
            elif bb.end <= ba.start:
                if travel.transfer_violation(bb.end, ba.start, bb.campus_code, ba.campus_code):
                    return True
    return False


def _describe_pair_conflict(a: Candidate, b: Candidate) -> str:
    if _same_offering(a, b):
        return (
            f"{a.course.course_string} idx {a.section.index} and "
            f"{b.course.course_string} idx {b.section.index} are the same class"
        )
    for ba in a.blocks:
        for bb in b.blocks:
            if ba.day != bb.day:
                continue
            first, second = (ba, bb) if ba.start <= bb.start else (bb, ba)
            day = DAY_NAMES[ba.day]
            if first.end > second.start:
                return (
                    f"idx {a.section.index} and idx {b.section.index} overlap on {day}"
                )
            if travel.transfer_violation(
                first.end, second.start, first.campus_code, second.campus_code
            ):
                gap = second.start - first.end
                return (
                    f"idx {a.section.index} and idx {b.section.index}: campus "
                    f"transfer with only a {gap}-minute gap on {day} "
                    f"(minimum {travel.MIN_CAMPUS_TRANSFER_MIN})"
                )
    return f"idx {a.section.index} and idx {b.section.index} conflict"


# ---------------------------------------------------------------------------
# the generator


class CourseScheduleGenerator:
    def __init__(
        self,
        groups: list[Group],
        constraints: list[BaseConstraint],
        *,
        max_course_combos: int = 5,
        max_sections_per_combo: int = 5,
        assumed_credits: float = 3.0,
        time_budget_s: float | None = None,
        sequential_raw_limit: int = SEQUENTIAL_RAW_LIMIT,
    ):
        self.groups = groups
        self.constraints = constraints
        self.max_course_combos = max_course_combos
        self.max_sections_per_combo = max_sections_per_combo
        self.assumed_credits = assumed_credits
        self.time_budget_s = time_budget_s
        self.sequential_raw_limit = sequential_raw_limit

        self.section_constraints = [c for c in constraints if isinstance(c, SectionConstraint)]
        self.schedule_constraints = [c for c in constraints if isinstance(c, ScheduleConstraint)]
        self.selection_constraints = [c for c in constraints if isinstance(c, SelectionConstraint)]
        # Hard constraints never contribute penalty (they reject), so only
        # soft weights normalize the final score.
        self.total_weight = sum(c.weight for c in constraints if not c.hard) or 1.0
        self.hard_max_credits = next(
            (
                c.max_credits
                for c in self.selection_constraints
                if isinstance(c, CreditRange) and c.hard and c.max_credits is not None
            ),
            None,
        )

        self.warnings: list[str] = []
        self.stats: dict = {
            "pruned_hard_filter": 0,
            "pruned_skeleton": 0,
            "pruned_conflict": 0,
            "pruned_bound": 0,
            "pruned_credit": 0,
            "pruned_hard": 0,
            "leaves_scored": 0,
            "truncated": False,
            "workers": 1,
        }

    # -- public entry -------------------------------------------------------

    def run(self) -> dict:
        started = time.monotonic()

        infeasible = self._prepare()
        if infeasible is not None:
            return self._result([], infeasible, started)

        raw = 1
        for g in self.groups:
            raw *= len(g.candidates)
        self.stats["raw_product"] = raw
        self.stats["candidates_per_group"] = {
            g.label: len(g.candidates) for g in self.groups
        }

        budget = self.time_budget_s
        if budget is None:
            budget = DEFAULT_BUDGET_S if raw <= self.sequential_raw_limit else FROM_SCRATCH_BUDGET_S

        if raw > self.sequential_raw_limit and len(self.groups) > 1:
            leaves = self._run_pool(budget)
        else:
            search = _Search(self, self.groups, budget)
            leaves = search.run()
            self._merge_search_stats(search)

        return self._result(leaves, None, started)

    # -- pipeline steps 0-4 -------------------------------------------------

    def _prepare(self) -> dict | None:
        # Step 0: skeleton validation, cheapest and loudest failure first.
        skeleton = [g.candidates[0] for g in self.groups if g.locked and g.candidates]
        for i, a in enumerate(skeleton):
            for b in skeleton[i + 1:]:
                if _pair_conflicts(a, b):
                    return {
                        "pair": [a.section.index, b.section.index],
                        "reason": _describe_pair_conflict(a, b),
                    }

        # Step 1: hard section constraints delete candidates.
        hard_section = [c for c in self.section_constraints if c.hard]
        for group in self.groups:
            if group.locked:
                continue
            survivors = []
            kills: dict[str, int] = {}
            for cand in group.candidates:
                killer = next(
                    (c for c in hard_section if c.score_section(cand) > 0), None
                )
                if killer is None:
                    survivors.append(cand)
                else:
                    kills[killer.type_name] = kills.get(killer.type_name, 0) + 1
                    self.stats["pruned_hard_filter"] += 1
            if not survivors:
                # Name the actual killers with counts, worst first.
                parts = ", ".join(
                    f"{name} ({count} sections)"
                    for name, count in sorted(kills.items(), key=lambda kv: -kv[1])
                )
                return {
                    "group": group.label,
                    "reason": f"no sections survive: {parts}" if parts
                    else "no sections exist",
                }
            group.candidates = survivors

        # Step 2: pre-filter against the skeleton.
        if skeleton:
            for group in self.groups:
                if group.locked:
                    continue
                survivors = [
                    cand
                    for cand in group.candidates
                    if not any(_pair_conflicts(cand, s) for s in skeleton)
                ]
                self.stats["pruned_skeleton"] += len(group.candidates) - len(survivors)
                if not survivors:
                    return {
                        "group": group.label,
                        "reason": "every section clashes with your locked classes "
                        "(time overlap or the 35-minute campus rule)",
                    }
                group.candidates = survivors

        # Step 3: soft precompute, caps, group ordering.
        n_groups = len(self.groups)
        soft_section = [c for c in self.section_constraints if not c.hard]
        for group in self.groups:
            for cand in group.candidates:
                # Per-candidate share of the schedule-level mean, so summing
                # over the selection reproduces w * mean(scores).
                cand.section_penalty = sum(
                    c.weight * c.score_section(cand) for c in soft_section
                ) / n_groups
            cap = FLEXIBLE_GROUP_CAP if group.flexible else GROUP_CANDIDATE_CAP
            if len(group.candidates) > cap:
                group.candidates.sort(key=lambda c: (not c.section.open, c.section_penalty))
                group.candidates = group.candidates[:cap]
                self.warnings.append(
                    f"group '{group.label}' capped at {cap} sections "
                    "(best preference fit kept) — narrow it to search everything"
                )
            group.candidates.sort(key=lambda c: c.section_penalty)
            group.min_section_penalty = min(
                (c.section_penalty for c in group.candidates), default=0.0
            )

        # Fail-first: smallest groups first (locked skeleton effectively free).
        self.groups.sort(key=lambda g: len(g.candidates))

        # Step 4: global ids + pairwise conflict bitmasks.
        all_cands: list[Candidate] = []
        for gi, group in enumerate(self.groups):
            for cand in group.candidates:
                cand.group_idx = gi
                cand.group_label = group.label
                cand.cand_id = len(all_cands)
                cand.conflict_mask = 0
                all_cands.append(cand)
        warned_same: set[frozenset[str]] = set()
        for i, a in enumerate(all_cands):
            for b in all_cands[i + 1:]:
                if a.group_idx == b.group_idx:
                    continue
                if _pair_conflicts(a, b):
                    a.conflict_mask |= 1 << b.cand_id
                    b.conflict_mask |= 1 << a.cand_id
                    if _same_offering(a, b):
                        key = frozenset({
                            a.course.course_string, b.course.course_string,
                            a.group_label or self.groups[a.group_idx].label,
                            b.group_label or self.groups[b.group_idx].label,
                        })
                        if key in warned_same:
                            continue
                        warned_same.add(key)
                        la = self.groups[a.group_idx].label
                        lb = self.groups[b.group_idx].label
                        if a.course.course_string == b.course.course_string:
                            self.warnings.append(
                                f"{a.course.course_string} appears in both "
                                f"'{la}' and '{lb}' — it can satisfy either, never both"
                            )
                        else:
                            self.warnings.append(
                                f"{a.course.course_string} and {b.course.course_string} "
                                "are the same class (cross-listed) — never chosen together"
                            )
        return None

    # -- leaf scoring (shared by sequential and pool paths) -----------------

    def score_leaf(self, selection: list[Candidate]) -> tuple[float, list[dict]] | None:
        """Returns (total_penalty, breakdown) or None on a hard rejection."""
        week = WeekOccupancy.build(selection)
        penalty = sum(c.section_penalty for c in selection)
        breakdown: list[dict] = []

        for c in self.schedule_constraints:
            s = c.score_schedule(week)
            if s > 0 and c.hard:
                return None
            if not c.hard and s > 0:
                penalty += c.weight * s
                breakdown.append({**c.describe(), "score": round(s, 4)})
        for c in self.selection_constraints:
            s = c.score_selection(selection)
            if s > 0 and c.hard:
                return None
            if not c.hard and s > 0:
                penalty += c.weight * s
                breakdown.append({**c.describe(), "score": round(s, 4)})
        return penalty, breakdown

    def final_score(self, penalty: float) -> float:
        return (1.0 - penalty / self.total_weight) * 100.0

    # -- worker pool --------------------------------------------------------

    def _run_pool(self, budget: float) -> list["_Leaf"]:
        import concurrent.futures

        # Split the largest group; it must lead the DFS for the split to
        # actually partition the tree.
        largest = max(range(len(self.groups)), key=lambda i: len(self.groups[i].candidates))
        self.groups.insert(0, self.groups.pop(largest))

        workers = min(os.cpu_count() or 1, MAX_WORKERS, len(self.groups[0].candidates))
        if workers <= 1:
            search = _Search(self, self.groups, budget)
            leaves = search.run()
            self._merge_search_stats(search)
            return leaves

        slices: list[list[Candidate]] = [[] for _ in range(workers)]
        for i, cand in enumerate(self.groups[0].candidates):
            slices[i % workers].append(cand)

        payloads = [
            (self, [Group(self.groups[0].label, sl, flexible=self.groups[0].flexible)]
             + self.groups[1:], budget)
            for sl in slices
        ]
        leaves: list[_Leaf] = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
            for worker_leaves, worker_stats in pool.map(_run_slice, payloads):
                leaves.extend(worker_leaves)
                for key, value in worker_stats.items():
                    if isinstance(value, bool):
                        self.stats[key] = self.stats.get(key) or value
                    else:
                        self.stats[key] = self.stats.get(key, 0) + value
        self.stats["workers"] = workers
        leaves.sort(key=lambda leaf: leaf.penalty)
        return leaves[: self._keep_capacity()]

    def _keep_capacity(self) -> int:
        # Flat kept-set sized generously above combos x variants so a dominant
        # course combination can't evict every alternative combination.
        return max(50, self.max_course_combos * self.max_sections_per_combo * 2)

    def _merge_search_stats(self, search: "_Search") -> None:
        for key, value in search.stats.items():
            if isinstance(value, bool):
                self.stats[key] = self.stats.get(key) or value
            else:
                self.stats[key] = self.stats.get(key, 0) + value

    # -- result shaping -----------------------------------------------------

    def _result(self, leaves: list["_Leaf"], infeasible: dict | None, started: float) -> dict:
        leaves = sorted(leaves, key=lambda leaf: leaf.penalty)

        combos: dict[tuple, dict] = {}
        for leaf in leaves:
            key = tuple(sorted(
                (c.course.course_string, c.course.supplement) for c in leaf.selection
            ))
            bucket = combos.setdefault(key, {"courses": sorted({k[0] for k in key}), "results": []})
            if len(bucket["results"]) < self.max_sections_per_combo:
                bucket["results"].append(self._leaf_dict(leaf))

        combo_list = sorted(
            combos.values(), key=lambda b: -b["results"][0]["score"]
        )[: self.max_course_combos]

        flat = [self._leaf_dict(leaf) for leaf in leaves[:10]]

        self.stats["elapsed_ms"] = round((time.monotonic() - started) * 1000, 1)
        return {
            "course_combos": combo_list,
            "results": flat,
            "stats": self.stats,
            "warnings": self.warnings,
            "infeasible": infeasible,
        }

    def _leaf_dict(self, leaf: "_Leaf") -> dict:
        selection = leaf.selection
        week: list[list[dict]] = [[] for _ in range(7)]
        for cand in selection:
            for b in cand.blocks:
                week[b.day].append({
                    "start": b.start, "end": b.end, "index": cand.section.index,
                    "course_string": cand.course.course_string,
                    "campus_code": b.campus_code, "mode": b.mode,
                })
        for day in week:
            day.sort(key=lambda blk: blk["start"])

        credits_assumed = any(c.credits is None for c in selection)
        credits_total = sum(
            c.credits if c.credits is not None else self.assumed_credits
            for c in selection
        )
        return {
            "score": round(self.final_score(leaf.penalty), 2),
            "indexes": [c.section.index for c in selection],
            "credits_total": credits_total,
            "credits_assumed": credits_assumed,
            "selections": [
                {
                    "requirement_label": c.group_label,
                    "course_string": c.course.course_string,
                    "title": c.course.title,
                    "credits": c.credits,
                    "section": {
                        "index": c.section.index,
                        "number": c.section.number,
                        "open": c.section.open,
                        "instructors": c.section.instructors,
                        "honors": c.section.honors,
                        "exam_code": c.section.exam_code,
                        "final_exam": c.section.final_exam,
                        "meetings": [
                            {
                                "day": b.day, "start": b.start, "end": b.end,
                                "mode": b.mode, "campus_code": b.campus_code,
                            }
                            for b in c.blocks
                        ] + ([] if not c.is_fully_async else [{"day": None, "mode": "ASYNC"}]),
                    },
                }
                for c in selection
            ],
            "week": week,
            "penalties": leaf.breakdown,
        }


@dataclass
class _Leaf:
    penalty: float
    selection: list[Candidate]
    breakdown: list[dict]


class _Search:
    """One sequential DFS over a set of groups. Also the unit of work a pool
    worker executes on its slice."""

    def __init__(self, gen: CourseScheduleGenerator, groups: list[Group], budget: float):
        self.gen = gen
        self.groups = groups
        self.budget = budget
        self.capacity = gen._keep_capacity()
        self.heap: list[tuple[float, int, _Leaf]] = []  # (-penalty, seq, leaf)
        self.seq = 0
        self.nodes = 0
        self.deadline = 0.0
        self.stats = {
            "pruned_conflict": 0, "pruned_bound": 0, "pruned_credit": 0,
            "pruned_hard": 0, "leaves_scored": 0, "truncated": False,
        }
        # Suffix sums of per-group minimum soft penalty, for the bound.
        self.suffix_min = [0.0] * (len(groups) + 1)
        for i in range(len(groups) - 1, -1, -1):
            self.suffix_min[i] = self.suffix_min[i + 1] + groups[i].min_section_penalty

    def run(self) -> list[_Leaf]:
        self.deadline = time.monotonic() + self.budget
        try:
            self._dfs(0, [], 0, 0.0, 0.0)
        except _Timeout:
            self.stats["truncated"] = True
        return [entry[2] for entry in self.heap]

    def _worst_kept(self) -> float:
        if len(self.heap) < self.capacity:
            return math.inf
        return -self.heap[0][0]

    def _dfs(self, gi: int, chosen: list[Candidate], conflicts: int,
             penalty: float, credits: float) -> None:
        self.nodes += 1
        if self.nodes % _BUDGET_CHECK_EVERY == 0 and time.monotonic() > self.deadline:
            raise _Timeout

        if gi == len(self.groups):
            self.stats["leaves_scored"] += 1
            scored = self.gen.score_leaf(chosen)
            if scored is None:
                self.stats["pruned_hard"] += 1
                return
            total_penalty, breakdown = scored
            if total_penalty >= self._worst_kept():
                return
            leaf = _Leaf(total_penalty, list(chosen), breakdown)
            entry = (-total_penalty, self.seq, leaf)
            self.seq += 1
            if len(self.heap) < self.capacity:
                heapq.heappush(self.heap, entry)
            else:
                heapq.heappushpop(self.heap, entry)
            return

        hard_max = self.gen.hard_max_credits
        assumed = self.gen.assumed_credits
        for cand in self.groups[gi].candidates:
            if conflicts >> cand.cand_id & 1:
                self.stats["pruned_conflict"] += 1
                continue
            new_penalty = penalty + cand.section_penalty
            if new_penalty + self.suffix_min[gi + 1] >= self._worst_kept():
                self.stats["pruned_bound"] += 1
                # Candidates are penalty-sorted, so every later one prunes too.
                break
            new_credits = credits + (cand.credits if cand.credits is not None else assumed)
            if hard_max is not None and new_credits > hard_max:
                self.stats["pruned_credit"] += 1
                continue
            chosen.append(cand)
            self._dfs(gi + 1, chosen, conflicts | cand.conflict_mask,
                      new_penalty, new_credits)
            chosen.pop()


class _Timeout(Exception):
    pass


def _run_slice(payload) -> tuple[list[_Leaf], dict]:
    """Top-level so ProcessPoolExecutor can pickle it (Windows spawn)."""
    gen, groups, budget = payload
    search = _Search(gen, groups, budget)
    leaves = search.run()
    return leaves, search.stats
