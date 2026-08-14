import httpx
import recurring_ical_events
from icalendar import Calendar
from datetime import date, datetime, timedelta


class GoogleCalendarImporter:
    def _fetch_cal(self, ics_url: str) -> Calendar:
        res = httpx.get(ics_url, timeout=15, follow_redirects=True)
        res.raise_for_status()
        return Calendar.from_ical(res.content)

    def _to_minutes(self, dt: datetime) -> int:
        """Minutes since midnight, local time.

        Must not truncate to the hour: a 15:50 class has to survive the import
        intact now that the scheduler runs on a 5-minute grid.
        """
        if dt.tzinfo is not None:
            dt = dt.astimezone()
        return dt.hour * 60 + dt.minute

    def fetch_day(self, ics_url: str, target_date: str) -> list[dict]:
        d = date.fromisoformat(target_date)
        cal = self._fetch_cal(ics_url)
        result = []
        for e in recurring_ical_events.of(cal).at(d):
            start = e["DTSTART"].dt
            end   = e["DTEND"].dt
            if not isinstance(start, datetime):
                continue
            sh = self._to_minutes(start)
            fh = self._to_minutes(end)
            if fh <= sh:
                fh = sh + 5
            result.append({
                "name":    str(e.get("SUMMARY", "Event")),
                "start":   sh,
                "finish":  fh,
                "in_dorm": False,
            })
        return result

    def fetch_week(self, ics_url: str, from_date: str | None = None) -> list[dict]:
        d      = date.fromisoformat(from_date) if from_date else date.today()
        monday = d - timedelta(days=d.weekday())
        cal    = self._fetch_cal(ics_url)

        by_key: dict[tuple, set] = {}
        for day_idx in range(7):
            d = monday + timedelta(days=day_idx)
            for e in recurring_ical_events.of(cal).at(d):
                start = e["DTSTART"].dt
                end   = e["DTEND"].dt
                if not isinstance(start, datetime):
                    continue
                name = str(e.get("SUMMARY", "Event"))
                sh = self._to_minutes(start)
                fh = self._to_minutes(end)
                if fh <= sh:
                    fh = sh + 5
                by_key.setdefault((name, sh, fh), set()).add(day_idx)

        return [
            {"name": k[0], "start": k[1], "finish": k[2], "in_dorm": False, "days": sorted(days)}
            for k, days in by_key.items()
        ]
