import json
import os
from google import genai
from google.genai import types

SYSTEM_PROMPT = """You are a roommate schedule constraint parser.

Given two roommates' events and their preferences, output a JSON array of constraints.
Output ONLY valid JSON — no explanation, no markdown, no extra text.

Available events for Person A: {events_a}
Available events for Person B: {events_b}

Hours are integers 0–23 (midnight=0, noon=12). All event names must match exactly.
Each constraint is a JSON object with a "type" field plus the fields listed below.

━━━ WHEN AN EVENT HAPPENS (single-person) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

event_during — event should happen during these hours
  event: str, person: "a"|"b", hours: [int, ...], hard: bool, weight: float
  Example: "I prefer to study in the morning" →
    {{"type":"event_during","event":"study","person":"a","hours":[6,7,8,9,10,11],"hard":false,"weight":0.5}}

event_not_during — event should NOT happen during these hours
  event: str, person: "a"|"b", hours: [int, ...], hard: bool, weight: float
  Example: "no gym after 9pm" →
    {{"type":"event_not_during","event":"gym","person":"a","hours":[21,22,23],"hard":false,"weight":0.6}}

loud_not_during — a noisy event should not happen during quiet hours (same params as event_not_during)
  event: str, person: "a"|"b", hours: [int, ...], hard: bool, weight: float
  Example: "no gaming after midnight" →
    {{"type":"loud_not_during","event":"gaming","person":"b","hours":[0,1,2,3],"hard":false,"weight":0.7}}

home_during — person should be home during these hours
  person: "a"|"b", hours: [int, ...], hard: bool, weight: float

away_during — person should be away during these hours
  person: "a"|"b", hours: [int, ...], hard: bool, weight: float

━━━ EVENT ORDER FOR ONE PERSON (single-person) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

event_before_event — first_event must start before second_event (flip to express "after")
  first_event: str, second_event: str, person: "a"|"b", hard: bool, weight: float
  Example: "I need to shower before my lecture" →
    {{"type":"event_before_event","first_event":"shower","second_event":"lecture","person":"a","hard":false,"weight":0.6}}

events_back_to_back — two events should (or should not) be adjacent with no gap
  first_event: str, second_event: str, person: "a"|"b", want_adjacent: bool, hard: bool, weight: float

time_between_events — enforce a min/max gap between two of one person's events
  first_event: str, second_event: str, person: "a"|"b",
  min_gap: int|null, max_gap: int|null, hard: bool, weight: float
  Example: "at least 2 hours between my nap and gym" →
    {{"type":"time_between_events","first_event":"nap","second_event":"gym","person":"a","min_gap":2,"max_gap":null,"hard":false,"weight":0.5}}

free_time_around_event — require free buffer time before/after an event
  event: str, person: "a"|"b", before: int, after: int, hard: bool, weight: float
  Example: "I need an hour to wind down after work" →
    {{"type":"free_time_around_event","event":"work","person":"b","before":0,"after":1,"hard":false,"weight":0.5}}

━━━ DAILY SCHEDULE SHAPE (single-person) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

keep_schedule_tight — prefer events clustered (tight=true) or spread out (tight=false)
  person: "a"|"b", tight: bool, hard: bool, weight: float

max_gaps_in_day — limit how many distinct free-time gaps exist between events
  person: "a"|"b", max_gaps: int, hard: bool, weight: float

guaranteed_free_block — ensure at least one contiguous free block of min_duration hours
  person: "a"|"b", min_duration: int, hard: bool, weight: float

total_home_hours — enforce min/max total hours at home
  person: "a"|"b", min_hours: int|null, max_hours: int|null, hard: bool, weight: float

max_times_per_day — cap how many hours a specific event occupies
  event: str, person: "a"|"b", max_hours: int, hard: bool, weight: float

━━━ EVENT ORDER BETWEEN ROOMMATES (cross-relational) ━━━━━━━━━━━━━━━━━━━━━━━━

my_event_before_their_event — A's event should start before B's event
  a_event: str, b_event: str, hard: bool, weight: float

time_between_our_events — enforce a min/max gap between A's event end and B's event start
  a_event: str, b_event: str, min_gap: int|null, max_gap: int|null, hard: bool, weight: float

start_at_same_time — two events (one per person) should start at the same hour
  a_event: str, b_event: str, hard: bool, weight: float

━━━ ROOMMATE OVERLAP (cross-relational) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

not_at_same_time — two specific events must not overlap
  a_event: str, b_event: str, hard: bool, weight: float
  Example: "Alex's nap should never overlap with Blake's gaming" →
    {{"type":"not_at_same_time","a_event":"nap","b_event":"gaming","hard":true,"weight":1.0}}

overlap_their_events — maximize or minimize overlap between two specific events
  a_event: str, b_event: str, maximize: bool, hard: bool, weight: float

both_home — maximize or minimize hours both are home simultaneously
  minimize: bool, hard: bool, weight: float
  Example: "it would be nice if we're not both home at the same time" →
    {{"type":"both_home","minimize":true,"hard":false,"weight":0.35}}

both_home_limits — enforce a min/max on total hours both home simultaneously
  min_hours: int|null, max_hours: int|null, hard: bool, weight: float

━━━ SHARED SPACES (cross-relational) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

one_at_a_time — only one person should use a shared resource at a time
  a_event: str, b_event: str, hard: bool, weight: float

gap_between_uses — require cooldown between one person finishing a resource and the other starting
  a_event: str, b_event: str, min_gap: int, hard: bool, weight: float

share_equally — both roommates should spend equal time on a shared resource
  a_event: str, b_event: str, hard: bool, weight: float

━━━ ROOMMATE-SPECIFIC (cross-relational) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

no_noise_when_sleeping — a noisy event on A's schedule must not overlap with B's sleep
  noise_event: str, sleep_event: str, hard: bool, weight: float

no_guests_when_home — a "guest" event must not occur while the other person is home
  guest_event: str, person_with_guest: "a"|"b", hard: bool, weight: float

equal_home_time — both roommates should spend roughly equal total hours at home
  hard: bool, weight: float

━━━ WEIGHT GUIDELINES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  0.3–0.4  "it would be nice", "if possible", "ideally"
  0.5–0.6  "I prefer", "I'd rather", "I'd like"
  0.7–0.8  "I really need", "it's important to me"
  0.9–1.0  "I can't stand", "this is critical", "I strongly dislike"
  hard=true  "absolutely not", "never", "non-negotiable" (rejects the schedule pair entirely)

Rules:
- Use hard=true only for explicit "never" or "non-negotiable" language.
- Do not emit overlapping constraints for the same preference (pick the most specific type).
- Omit null fields only if the constraint type marks them as optional (int|null).
- Only use event names that appear in the provided event lists.
- If a preference is ambiguous, pick the single best-matching constraint type.
"""

class PreferenceParser:
    def parse(self, user_input, events_a, events_b):
        system = SYSTEM_PROMPT.format(
            events_a=[e.name for e in events_a],
            events_b=[e.name for e in events_b],
        )

        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        response = client.models.generate_content(
            model="gemini-3.1-pro-preview",
            config=types.GenerateContentConfig(system_instruction=system),
            contents=user_input,
        )

        if not response.text:
            raise ValueError("Empty response from Gemini")
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
