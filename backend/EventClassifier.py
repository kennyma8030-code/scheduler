import json
import os
from google import genai
from backend.models import EventCategory

VALID_CATEGORIES = {c.value for c in EventCategory}

SYSTEM_PROMPT = """You are an event classifier for a roommate scheduling app.

Given a list of event names, classify each into exactly one of these categories:
  sleep    — sleeping, napping, resting
  work     — job, shift, internship, meeting, office hours
  study    — class, lecture, lab, homework, studying, tutoring
  exercise — gym, run, yoga, sports, workout, walk
  personal — shower, cooking, eating, grooming, chores, laundry
  social   — guests, hanging out, party, going out, date
  errands  — groceries, commute, appointment, shopping, errands
  leisure  — gaming, TV, reading, hobbies, browsing
  other    — anything that doesn't clearly fit above

Output ONLY valid JSON with no explanation: {"event_name": "category", ...}
All category values must be lowercase and exactly as listed above."""


class EventClassifier:
    def classify(self, event_names: list[str]) -> dict[str, str]:
        if not event_names:
            return {}

        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        response = client.models.generate_content(
            model="gemini-3.1-pro-preview",
            config={"system_instruction": SYSTEM_PROMPT},
            contents=str(event_names),
        )

        if not response.text:
            return {name: "other" for name in event_names}

        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        result = json.loads(text.strip())
        return {
            name: result.get(name, "other") if result.get(name, "other") in VALID_CATEGORIES else "other"
            for name in event_names
        }
