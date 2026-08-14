"""Client for the Rutgers Schedule of Classes (SOC) API.

The SOC exposes exactly two JSON endpoints. Both take ``year``, ``term`` and
``campus`` and both return the *entire* campus dump — there is no server-side
filtering, so we download once and filter locally.

    GET /soc/api/courses.json?year=&term=&campus=      full catalog (Cache-Control: max-age=900)
    GET /soc/api/openSections.json?year=&term=&campus= list of open registration indexes (max-age=30)

See API_NOTES.md for the full endpoint survey and field reference.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

BASE_URL = "https://classes.rutgers.edu/soc/api"

# sis.rutgers.edu/soc/api/* still works but 302s here, costing a round trip.
LEGACY_BASE_URL = "https://sis.rutgers.edu/soc/api"

# Server-advertised max-age for each endpoint; we mirror it on disk.
COURSES_TTL = 900
OPEN_SECTIONS_TTL = 30

CACHE_DIR = Path(__file__).parent / ".soc_cache"

TERMS = {"winter": "0", "spring": "1", "summer": "7", "fall": "9"}
CAMPUSES = {"NB": "New Brunswick", "NK": "Newark", "CM": "Camden"}


class SOCError(RuntimeError):
    pass


class SOCClient:
    """Fetches and disk-caches SOC payloads.

    The courses dump is ~21 MB of JSON (~0.9 MB gzipped) for New Brunswick, so
    the cache is not optional in practice — a cold fetch takes ~3 s.
    """

    def __init__(self, cache_dir: Path | None = None, session: requests.Session | None = None):
        self.cache_dir = Path(cache_dir) if cache_dir else CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = session or requests.Session()
        # The API always gzips; requests negotiates and decodes this for us.
        self.session.headers.update({"Accept-Encoding": "gzip"})

    def _get(self, endpoint: str, year: int, term: str, campus: str, ttl: int) -> Any:
        cache_path = self.cache_dir / f"{endpoint}_{year}_{term}_{campus}.json"
        if cache_path.exists() and time.time() - cache_path.stat().st_mtime < ttl:
            return json.loads(cache_path.read_text())

        url = f"{BASE_URL}/{endpoint}.json"
        params = {"year": year, "term": term, "campus": campus}
        try:
            response = self.session.get(url, params=params, timeout=60)
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            # Serve stale rather than fail — SOC goes down during registration peaks.
            if cache_path.exists():
                return json.loads(cache_path.read_text())
            raise SOCError(f"{url} failed: {exc}") from exc

        cache_path.write_text(json.dumps(data))
        return data

    def courses(self, year: int, term: str, campus: str = "NB") -> list[dict]:
        """Every course offered on ``campus`` that term, sections included."""
        data = self._get("courses", year, term, campus, COURSES_TTL)
        if not isinstance(data, list):
            raise SOCError(f"expected a list of courses, got {type(data).__name__}")
        return data

    def open_section_indexes(self, year: int, term: str, campus: str = "NB") -> set[str]:
        """Registration indexes currently open.

        Fresher than the ``openStatus`` flag baked into ``courses.json``: the
        catalog is cached for 15 minutes while this is cached for 30 seconds.
        Prefer this set when deciding whether a section is actually open.
        """
        data = self._get("openSections", year, term, campus, OPEN_SECTIONS_TTL)
        if not isinstance(data, list):
            raise SOCError(f"expected a list of indexes, got {type(data).__name__}")
        return set(data)


def resolve_term(name: str) -> str:
    """'fall' -> '9'. Accepts a raw code ('9') unchanged."""
    key = name.strip().lower()
    if key in TERMS:
        return TERMS[key]
    if key in TERMS.values():
        return key
    raise ValueError(f"unknown term {name!r}; expected one of {sorted(TERMS)}")
