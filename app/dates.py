"""Meeting date and voting deadline calculations."""

from calendar import monthcalendar
from datetime import date, timedelta

from app.models import BookClub, MonthlySettings


def nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date | None:
    """Return the nth occurrence (1-based) of weekday (Mon=0) in the given month, or None."""
    weeks = monthcalendar(year, month)
    count = 0
    for week in weeks:
        day = week[weekday]
        if day == 0:
            continue
        count += 1
        if count == n:
            return date(year, month, day)
    return None


def compute_meeting_date(
    club: BookClub,
    year: int,
    month: int,
    override: MonthlySettings | None,
) -> date | None:
    """
    Return the meeting date for (year, month).
    - If there's an override with meeting_date=None → month is skipped, return None.
    - If there's an override with a specific date → use that.
    - Otherwise compute from club's meeting_week + meeting_weekday.
    """
    if override is not None:
        return override.meeting_date  # May be None (skipped)
    return nth_weekday_of_month(year, month, club.meeting_weekday, club.meeting_week)


def compute_voting_close(
    club: BookClub,
    meeting_date: date | None,
    override: MonthlySettings | None,
) -> date | None:
    """Return the voting close date, or None if month is skipped."""
    if meeting_date is None:
        return None
    if override is not None and override.voting_close_date is not None:
        return override.voting_close_date
    return meeting_date - timedelta(days=club.voting_close_days_before)
