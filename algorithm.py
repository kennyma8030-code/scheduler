from itertools import product

class ScheduleOptimizer:
   
    @staticmethod
    def available_flexible(schedule):
        s = set()
        available = set()
        
        for event in schedule.fixed_events:
            for hour in range(event.start, event.finish):
                s.add(hour)
        
        available = set(range(24)) - s
        return available
    
    @staticmethod
    def fixed(schedule):
        x = {}

        for event in schedule.fixed_events:
            for hour in range(event.start, event.finish):
                x[hour] = event
        
        return x
    
    @staticmethod
    def valid_starts(event, available):
        starts = []
        for hour in available:
            s = set(range(hour, hour + event.duration))
            if s.issubset(available):
                starts.append(hour)
        return starts
   
    @staticmethod
    def generate(events, available):
        if not events:
            return [[]]
        
        event = events[0]
        remaining = events[1:]
        results = []

        for start in ScheduleOptimizer.valid_starts(event, available):
            used_hours = set(range(start, start + event.duration))
            new_available = available - used_hours 

            for sub in ScheduleOptimizer.generate(remaining, new_available):
                placement = [{"event": event, "start": start}] + sub
                results.append(placement)

        return results 
    
    @staticmethod
    def combinations(events, available, fixed_schedule):
        all_flexible_combinations = ScheduleOptimizer.generate(events, available)
        schedule_combinations = []
        
        for one_combination in all_flexible_combinations:
            d = {}
            for placement in one_combination:
                start = placement.get("start")
                finish = start + placement.get("event").duration
                for hour in range(start, finish):
                    d[hour] = placement.get("event")
            merged = fixed_schedule.copy()
            merged.update(d)    
            schedule_combinations.append(merged)
        
        return schedule_combinations
   
    @staticmethod
    def best_schedules(a, b):
        pairs = []
        results = []
        
        for x, y in product(a, b):
            score = 0
            for hour in range(24):
                check_x = x.get(hour)
                check_y = y.get(hour)
                if check_x is not None and check_y is not None and check_x.in_dorm and check_y.in_dorm:
                    score += 1
            pairs.append((score, x, y))
        
        pairs.sort(key=lambda t: t[0])
        pairs[:] = pairs[:10]
        
        for score, x, y in pairs:
            formatted_x = ScheduleOptimizer.schedule_to_blocks(x)
            formatted_y = ScheduleOptimizer.schedule_to_blocks(y)
            results.append({"score": score, "roommate_a": formatted_x, "roommate_b": formatted_y})
        
        return results
    
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
                if current.get("event") == event.name:
                    current["finish"] = current.get("finish") + 1
                    continue
                else:
                    blocks.append(current)

            current = {"event": event.name, "start": hour, "finish": hour + 1, "in_dorm": event.in_dorm}

        if current:
            blocks.append(current)
             
        return blocks





            
            

            


        
      

    

   




        





    

