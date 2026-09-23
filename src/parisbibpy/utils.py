"""Utility functions for parisbibpy (Syracuse date parsing and helpers)."""

import re
from datetime import datetime, timedelta, timezone

# Regex matches /Date(1790373600000+0200)/ or \/Date(1790373600000+0200)\/
_DATE_REGEX = re.compile(r"/Date\((\d+)(?:([+-]\d{2})(\d{2}))?\)/")


def parse_syracuse_date(raw_date: str | None) -> datetime | None:
    """Parse a Syracuse / Microsoft JSON date string into a datetime object.

    Examples:
        - '/Date(1790373600000+0200)/' -> datetime(2026, 9, 26, 12, 0, tzinfo=timezone(timedelta(hours=2)))
        - '/Date(1573896067877)/' -> datetime with UTC timezone
    """
    if not raw_date:
        return None

    # Normalize escaped backslashes if present
    cleaned = raw_date.replace(r"\/", "/")
    match = _DATE_REGEX.search(cleaned)
    if not match:
        return None

    timestamp_ms = int(match.group(1))
    tz_hour = match.group(2)
    tz_min = match.group(3)

    if tz_hour is not None and tz_min is not None:
        sign = 1 if tz_hour.startswith("+") else -1
        hours = abs(int(tz_hour))
        minutes = int(tz_min)
        tz = timezone(timedelta(hours=sign * hours, minutes=sign * minutes))
    else:
        tz = timezone.utc

    timestamp_s = timestamp_ms / 1000.0
    return datetime.fromtimestamp(timestamp_s, tz=tz)
