import json
import os
from google import genai
from google.genai import types

SYSTEM_PROMPT = """You are a roommate schedule constraint parser.

Given two roommates' events and their preferences, output a JSON array
of constraints. Output ONLY valid JSON, no other text.

Available events for Person A: {events_a}
Available events for Person B: {events_b}

Available constraint types:

event_during:
  event: str (event name)
  person: "a" or "b"
  hours: list of ints (0-23)
  hard: bool
  weight: float (0.3-1.0)

event_not_during:
  event: str
  person: "a" or "b"
  hours: list of ints (0-23)
  hard: bool
  weight: float (0.3-1.0)

not_at_same_time:
  a_event: str
  b_event: str
  hard: bool
  weight: float (0.3-1.0)

both_home:
  minimize: bool
  hard: bool
  weight: float (0.3-1.0)

... (all 27 types)

Weight guidelines:
  0.3-0.4: "it would be nice", "if possible"
  0.5-0.6: "I prefer", "I'd rather"
  0.7-0.8: "I really need", "it's important"
  0.9-1.0: "I can't stand", "this is critical"
  hard=true: "absolutely not", "never", "non-negotiable"

Do not activate overlapping constraints for the same preference.
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
