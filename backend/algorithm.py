from itertools import product
from backend.constants import constraint_dict

class ScheduleOptimizer:
   
    @staticmethod
    def available_flexible(schedule):
        occupied_hours = set()

        for event in schedule.fixed_events:
            duration = event.duration
            for hour in range(event.start, event.start + duration):
                occupied_hours.add(hour)

        free_hours = set(range(24)) - occupied_hours
        return free_hours

    @staticmethod
    def fixed(schedule):
        hour_to_event = {}

        for event in schedule.fixed_events:
            duration = event.duration
            for hour in range(event.start, event.start + duration):
                hour_to_event[hour] = event

        return hour_to_event

    @staticmethod
    def valid_starts(event, free_hours):
        valid_start_hours = []
        for hour in free_hours:
            required_hours = set(range(hour, hour + event.duration))
            if required_hours.issubset(free_hours):
                valid_start_hours.append(hour)
        return valid_start_hours

    @staticmethod
    def generate(events, free_hours):
        if not events:
            return [[]]

        event = events[0]
        remaining_events = events[1:]
        results = []

        for start in ScheduleOptimizer.valid_starts(event, free_hours):
            used_hours = set(range(start, start + event.duration))
            remaining_free_hours = free_hours - used_hours

            for sub_placements in ScheduleOptimizer.generate(remaining_events, remaining_free_hours):
                event_placement = [{"event": event, "start": start}] + sub_placements
                results.append(event_placement)

        return results

    @staticmethod
    def combinations(events, free_hours, fixed_schedule):
        all_flexible_combinations = ScheduleOptimizer.generate(events, free_hours)
        schedule_combinations = []

        for flexible_placement in all_flexible_combinations:
            flexible_hour_map = {}
            for placed_event in flexible_placement:
                start = placed_event.get("start")
                finish = start + placed_event.get("event").duration
                for hour in range(start, finish):
                    flexible_hour_map[hour] = placed_event.get("event")
            full_schedule = fixed_schedule.copy()
            full_schedule.update(flexible_hour_map)
            schedule_combinations.append(full_schedule)

        return schedule_combinations

    @staticmethod
    def best_schedules(schedules_a, schedules_b, active_constraints): #make sure to add active constraint logic
        results = []

        scored_pairs = []

        for schedule_a, schedule_b in product(schedules_a, schedules_b):
            for constraint in active_constraints:
                constraint.reset()

            for hour in range(24):
                a_event = schedule_a.get(hour)
                b_event = schedule_b.get(hour)

                for constraint in active_constraints:
                    constraint.process(hour, a_event, b_event)

            for constraint in active_constraints:
                constraint.finalize()

            if any(c.hard and c.score > 0 for c in active_constraints):
                continue

            total_deducted = sum(c.weight * c.score for c in active_constraints)
            final_score = (1 - total_deducted) * 100
            scored_pairs.append((final_score, schedule_a, schedule_b))

        for score, schedule_a, schedule_b in scored_pairs:
            blocks_a = ScheduleOptimizer.schedule_to_blocks(schedule_a)
            blocks_b = ScheduleOptimizer.schedule_to_blocks(schedule_b)
            results.append({"score": score, "roommate_a": blocks_a, "roommate_b": blocks_b})

        return results
    
    @staticmethod
    def constraint_factory(ai_output, events_a, events_b):
        event_map = {e.name: e for e in events_a + events_b}
        constraints = []
        for item in ai_output:
            cls = constraint_dict[item["type"]]
            params = {k: v for k, v in item.items() if k != "type"}
            for key in ["event", "a_event", "b_event", "first_event", "second_event"]:
                if key in params and isinstance(params[key], str):
                    params[key] = event_map.get(params[key], params[key])
            instance = cls(**params)
            constraints.append(instance)
        return constraints

    
    @staticmethod
    def schedule_to_blocks(schedule):
        blocks = []
        current_block = None

        for hour in range(24):
            event = schedule.get(hour)

            if event is None:
                if current_block:
                    blocks.append(current_block)
                    current_block = None
                continue

            if current_block is not None:
                if current_block.get("event") == event.name:
                    current_block["finish"] = current_block["finish"] + 1
                    continue
                else:
                    blocks.append(current_block)

            current_block = {"event": event.name, "start": hour, "finish": hour + 1, "in_dorm": event.in_dorm}

        if current_block:
            blocks.append(current_block)

        return blocks





            
            

            


        
      

    

   




        





    

