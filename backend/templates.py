# MINIMIZE EVENT OVERLAP
# CONSIDER SCORE REFERENCE POINT BETWEEN CONSTRAINTS
# CONSIDER OVERCONSTRAINING/UNDERCONSTRAINING

#single
class EventBeforeEvent: #first event shouldn't be right before second event
    def __init__(self, first_event, second_event, hard, weight):
        self.first_event = first_event
        self.second_event = second_event
        self.hard = hard
        self.weight = weight
        self.first_hour = None
        self.second_hour = None
        self.score = 0

    def reset(self):
        self.first_hour = None
        self.second_hour = None
        self.score = 0

    def process(self, hour, event, schedule):
        if (event is self.first_event):
            self.first_hour = hour

        if (event == self.second_event and schedule[hour + 1] is not self.second_event):
            self.second_hour = hour

    def finalize(self):
        if (self.first_hour is not None and self.second_hour is not None
        and self.first_hour + 1 is self.second_hour):
            self.score = 1 # binary score

#cross relational
class NotAtSameTime: #minimize certain events at the same time
    def __init__(self, a_event, b_event, hard, weight):
        self.a_event = a_event
        self.b_event = b_event
        self.hard = hard 
        self.weight = weight
        self.overlap = 0
        self.score = 0

    def reset(self):
        self.overlap = 0
        self.score = 0

    def process(self, hour, a_event, b_event):
        if (a_event == self.a_event and b_event == self.b_event):
            self.overlap += 1

    def finalize(self):
        self.score = self.overlap / min(self.a_event.duration, self.b_event.duration) # normalized score

#cross relational
class BothHome: #min/max time spent in dorm with roommate
    def __init__(self, minimize, hard, weight): #minimize is a bool, true = minimize time, false = maximize time
        self.minimize = minimize
        self.hard = hard
        self.weight = weight
        self.overlap = 0
        self.score = 0

    def reset(self):
        self.overlap = 0
        self.score = 0

    def process(self, hour, a_event, b_event):
        if a_event and b_event and a_event.in_dorm and b_event.in_dorm:
            self.overlap += 1

    def finalize(self):
        if self.minimize: 
            self.score = self.overlap / 24
        else:
            self.score = 1 - (self.overlap / 24)

#single
class EventDuring: #hour preferences for an event  
    def __init__(self, event, hours, hard, weight): # hours is set
        self.event = event
        self.hours = hours
        self.hard = hard
        self.weight = weight
        self.overlap = 0
        self.score = 0

    def reset(self):
        self.overlap = 0
        self.score = 0

    def process(self, hour, event):
        if hour in self.hours:
            self.overlap += 1

    def finalize(self):
        self.score = 1 - self.overlap / min(len(self.hours), self.event.duration)


    
    
                            
            



class TimeBetweenEvents:
    def __init__(self, *args, hard=False, weight=1.0, **kwargs):
        self.hard = hard
        self.weight = weight
        self.score = 0

    def reset(self): self.score = 0
    def process(self, hour, a_event, b_event): pass
    def finalize(self): pass


class EventNotDuring:
    def __init__(self, *args, hard=False, weight=1.0, **kwargs):
        self.hard = hard
        self.weight = weight
        self.score = 0

    def reset(self): self.score = 0
    def process(self, hour, a_event, b_event): pass
    def finalize(self): pass


class LoudNotDuring:
    def __init__(self, *args, hard=False, weight=1.0, **kwargs):
        self.hard = hard
        self.weight = weight
        self.score = 0

    def reset(self): self.score = 0
    def process(self, hour, a_event, b_event): pass
    def finalize(self): pass


class HomeDuring:
    def __init__(self, *args, hard=False, weight=1.0, **kwargs):
        self.hard = hard
        self.weight = weight
        self.score = 0

    def reset(self): self.score = 0
    def process(self, hour, a_event, b_event): pass
    def finalize(self): pass


class AwayDuring:
    def __init__(self, *args, hard=False, weight=1.0, **kwargs):
        self.hard = hard
        self.weight = weight
        self.score = 0

    def reset(self): self.score = 0
    def process(self, hour, a_event, b_event): pass
    def finalize(self): pass


class EventsBackToBack:
    def __init__(self, *args, hard=False, weight=1.0, **kwargs):
        self.hard = hard
        self.weight = weight
        self.score = 0

    def reset(self): self.score = 0
    def process(self, hour, a_event, b_event): pass
    def finalize(self): pass


class FreeTimeAroundEvent:
    def __init__(self, *args, hard=False, weight=1.0, **kwargs):
        self.hard = hard
        self.weight = weight
        self.score = 0

    def reset(self): self.score = 0
    def process(self, hour, a_event, b_event): pass
    def finalize(self): pass


class KeepScheduleTight:
    def __init__(self, *args, hard=False, weight=1.0, **kwargs):
        self.hard = hard
        self.weight = weight
        self.score = 0

    def reset(self): self.score = 0
    def process(self, hour, a_event, b_event): pass
    def finalize(self): pass


class MaxGapsInDay:
    def __init__(self, *args, hard=False, weight=1.0, **kwargs):
        self.hard = hard
        self.weight = weight
        self.score = 0

    def reset(self): self.score = 0
    def process(self, hour, a_event, b_event): pass
    def finalize(self): pass


class GuaranteedFreeBlock:
    def __init__(self, *args, hard=False, weight=1.0, **kwargs):
        self.hard = hard
        self.weight = weight
        self.score = 0

    def reset(self): self.score = 0
    def process(self, hour, a_event, b_event): pass
    def finalize(self): pass


class TotalHomeHours:
    def __init__(self, *args, hard=False, weight=1.0, **kwargs):
        self.hard = hard
        self.weight = weight
        self.score = 0

    def reset(self): self.score = 0
    def process(self, hour, a_event, b_event): pass
    def finalize(self): pass


class MaxTimesPerDay:
    def __init__(self, *args, hard=False, weight=1.0, **kwargs):
        self.hard = hard
        self.weight = weight
        self.score = 0

    def reset(self): self.score = 0
    def process(self, hour, a_event, b_event): pass
    def finalize(self): pass


class MyEventBeforeTheirEvent:
    def __init__(self, *args, hard=False, weight=1.0, **kwargs):
        self.hard = hard
        self.weight = weight
        self.score = 0

    def reset(self): self.score = 0
    def process(self, hour, a_event, b_event): pass
    def finalize(self): pass


class TimeBetweenOurEvents:
    def __init__(self, *args, hard=False, weight=1.0, **kwargs):
        self.hard = hard
        self.weight = weight
        self.score = 0

    def reset(self): self.score = 0
    def process(self, hour, a_event, b_event): pass
    def finalize(self): pass


class StartAtSameTime:
    def __init__(self, *args, hard=False, weight=1.0, **kwargs):
        self.hard = hard
        self.weight = weight
        self.score = 0

    def reset(self): self.score = 0
    def process(self, hour, a_event, b_event): pass
    def finalize(self): pass


class OverlapTheirEvents:
    def __init__(self, *args, hard=False, weight=1.0, **kwargs):
        self.hard = hard
        self.weight = weight
        self.score = 0

    def reset(self): self.score = 0
    def process(self, hour, a_event, b_event): pass
    def finalize(self): pass


class BothHomeLimits:
    def __init__(self, *args, hard=False, weight=1.0, **kwargs):
        self.hard = hard
        self.weight = weight
        self.score = 0

    def reset(self): self.score = 0
    def process(self, hour, a_event, b_event): pass
    def finalize(self): pass


class OneAtATime:
    def __init__(self, *args, hard=False, weight=1.0, **kwargs):
        self.hard = hard
        self.weight = weight
        self.score = 0

    def reset(self): self.score = 0
    def process(self, hour, a_event, b_event): pass
    def finalize(self): pass


class GapBetweenUses:
    def __init__(self, *args, hard=False, weight=1.0, **kwargs):
        self.hard = hard
        self.weight = weight
        self.score = 0

    def reset(self): self.score = 0
    def process(self, hour, a_event, b_event): pass
    def finalize(self): pass


class ShareEqually:
    def __init__(self, *args, hard=False, weight=1.0, **kwargs):
        self.hard = hard
        self.weight = weight
        self.score = 0

    def reset(self): self.score = 0
    def process(self, hour, a_event, b_event): pass
    def finalize(self): pass


class NoNoiseWhenSleeping:
    def __init__(self, *args, hard=False, weight=1.0, **kwargs):
        self.hard = hard
        self.weight = weight
        self.score = 0

    def reset(self): self.score = 0
    def process(self, hour, a_event, b_event): pass
    def finalize(self): pass


class NoGuestsWhenHome:
    def __init__(self, *args, hard=False, weight=1.0, **kwargs):
        self.hard = hard
        self.weight = weight
        self.score = 0

    def reset(self): self.score = 0
    def process(self, hour, a_event, b_event): pass
    def finalize(self): pass


class EqualHomeTime:
    def __init__(self, *args, hard=False, weight=1.0, **kwargs):
        self.hard = hard
        self.weight = weight
        self.score = 0

    def reset(self): self.score = 0
    def process(self, hour, a_event, b_event): pass
    def finalize(self): pass
