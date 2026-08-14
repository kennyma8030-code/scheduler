from backend.class_scheduler.models import (
    CAMPUS_LOCATIONS,
    DAY_CODES,
    DAY_NAMES,
    Course,
    Meeting,
    Section,
    merge_split_courses,
    parse_courses,
)
from backend.class_scheduler.soc import (
    CAMPUSES,
    TERMS,
    SOCClient,
    SOCError,
    resolve_term,
)

__all__ = [
    "CAMPUSES",
    "CAMPUS_LOCATIONS",
    "DAY_CODES",
    "DAY_NAMES",
    "Course",
    "Meeting",
    "SOCClient",
    "SOCError",
    "Section",
    "TERMS",
    "merge_split_courses",
    "parse_courses",
    "resolve_term",
]

# schema/sync are not imported here on purpose: they pull in SQLAlchemy and a
# database driver, and the API client is useful without either.
