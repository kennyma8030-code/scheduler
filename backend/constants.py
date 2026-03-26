from backend.templates import (
    EventDuring, EventNotDuring, LoudNotDuring, HomeDuring, AwayDuring,
    EventBeforeEvent, EventsBackToBack, TimeBetweenEvents, FreeTimeAroundEvent,
    KeepScheduleTight, MaxGapsInDay, GuaranteedFreeBlock, TotalHomeHours,
    MaxTimesPerDay, MyEventBeforeTheirEvent, TimeBetweenOurEvents,
    StartAtSameTime, NotAtSameTime, OverlapTheirEvents, BothHome,
    BothHomeLimits, OneAtATime, GapBetweenUses, ShareEqually,
    NoNoiseWhenSleeping, NoGuestsWhenHome, EqualHomeTime,
)

constraint_dict = {
    "event_during": EventDuring,
    "event_not_during": EventNotDuring,
    "loud_not_during": LoudNotDuring,
    "home_during": HomeDuring,
    "away_during": AwayDuring,
    "event_before_event": EventBeforeEvent,
    "events_back_to_back": EventsBackToBack,
    "time_between_events": TimeBetweenEvents,
    "free_time_around_event": FreeTimeAroundEvent,
    "keep_schedule_tight": KeepScheduleTight,
    "max_gaps_in_day": MaxGapsInDay,
    "guaranteed_free_block": GuaranteedFreeBlock,
    "total_home_hours": TotalHomeHours,
    "max_times_per_day": MaxTimesPerDay,
    "my_event_before_their_event": MyEventBeforeTheirEvent,
    "time_between_our_events": TimeBetweenOurEvents,
    "start_at_same_time": StartAtSameTime,
    "not_at_same_time": NotAtSameTime,
    "overlap_their_events": OverlapTheirEvents,
    "both_home": BothHome,
    "both_home_limits": BothHomeLimits,
    "one_at_a_time": OneAtATime,
    "gap_between_uses": GapBetweenUses,
    "share_equally": ShareEqually,
    "no_noise_when_sleeping": NoNoiseWhenSleeping,
    "no_guests_when_home": NoGuestsWhenHome,
    "equal_home_time": EqualHomeTime,
}



