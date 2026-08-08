"""Meeting date and voting deadline calculations."""

from calendar import monthcalendar
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BookClub, MonthlyResult, MonthlySettings


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


async def find_next_actionable_month(
    club: BookClub,
    db: AsyncSession,
) -> tuple[int, int, date | None, date | None]:
    """
    Return (year, month, meeting_date, voting_close_date) for the next month
    that's neither finalized nor skipped, starting from the current calendar
    month. meeting_date/voting_close_date are None only if nothing turned up
    within the search window (finalized/skipped many months in a row).
    """
    today = date.today()
    year, month = today.year, today.month
    for _ in range(12):  # look up to a year ahead
        result_row = await db.execute(
            select(MonthlyResult).where(
                MonthlyResult.club_id == club.id,
                MonthlyResult.year == year,
                MonthlyResult.month == month,
            )
        )
        if result_row.scalar_one_or_none() is None:
            settings_row = await db.execute(
                select(MonthlySettings).where(
                    MonthlySettings.club_id == club.id,
                    MonthlySettings.year == year,
                    MonthlySettings.month == month,
                )
            )
            settings = settings_row.scalar_one_or_none()
            meeting = compute_meeting_date(club, year, month, settings)
            if meeting is not None:  # not skipped
                voting_close = compute_voting_close(club, meeting, settings)
                return year, month, meeting, voting_close
        month += 1
        if month > 12:
            month = 1
            year += 1
    return year, month, None, None
