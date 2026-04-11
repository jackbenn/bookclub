"""
Phragmén sequential method with temporal decay.

Each voter i has a load l_i (stored in UserLoad). Their weight is:
    w_i = 1 / (1 + l_i)

A book's score is the sum of weights of all voters who approve it.

When a book wins:
    For each approver i: l_i += w_i
    (The cost of selecting the book is distributed proportionally to each
    voter's current weight — heavier-loaded voters absorb less.)

Decay (applied after load updates, for active members only):
    l_i *= decay_rate   if user was active this month (last_active in current month)
    l_i unchanged       if user was inactive

Tiebreakers (ascending priority, applied in order):
  1. Highest weighted score (primary Phragmén score)
  2. Most raw (unweighted) approvals
  3. Fewest pages (shorter wins; None treated as infinity)
  4. Earliest nomination_at (older nominations win; None treated as latest)
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Approval, Book, BookClub, BookStatus, MonthlyResult, User, UserLoad

if TYPE_CHECKING:
    pass


async def _get_loads(club_id: int, db: AsyncSession) -> dict[int, float]:
    """Return {user_id: load_value} for all members of the club."""
    result = await db.execute(
        select(UserLoad).where(UserLoad.club_id == club_id)
    )
    return {row.user_id: row.load_value for row in result.scalars()}


async def _get_approvals(club_id: int, db: AsyncSession) -> dict[int, list[int]]:
    """Return {book_id: [user_id, ...]} for all active books in club."""
    result = await db.execute(
        select(Approval)
        .join(Book, Book.id == Approval.book_id)
        .where(Book.club_id == club_id, Book.status == BookStatus.active)
    )
    book_approvers: dict[int, list[int]] = {}
    for approval in result.scalars():
        book_approvers.setdefault(approval.book_id, []).append(approval.user_id)
    return book_approvers


def _score_books(
    book_approvers: dict[int, list[int]],
    loads: dict[int, float],
) -> dict[int, tuple[float, int]]:
    """Return {book_id: (weighted_score, raw_count)}."""
    scores: dict[int, tuple[float, int]] = {}
    for book_id, approvers in book_approvers.items():
        weighted = sum(1.0 / (1.0 + loads.get(uid, 0.0)) for uid in approvers)
        scores[book_id] = (weighted, len(approvers))
    return scores


def _tiebreak_key(book: Book, score: float, raw_count: int):
    """Lower value = better. Used for sorted() ascending then we take first."""
    pages = book.page_count if book.page_count is not None else float("inf")
    # Earlier nominated_at wins: convert to timestamp, None → very large number
    if book.nominated_at is not None:
        ts = book.nominated_at.timestamp()
    else:
        ts = float("inf")
    # Negate score and raw_count so that higher values sort first
    return (-score, -raw_count, pages, ts)


async def finalize_month(
    club: BookClub,
    year: int,
    month: int,
    db: AsyncSession,
) -> MonthlyResult:
    """
    Run the Phragmén selection for the given month:
      - Pick the winner and top-2 runners-up
      - Update loads for approvers of the winner
      - Apply decay for members active this month
      - Mark the winning book as selected
      - Persist and return a MonthlyResult
    """
    loads = await _get_loads(club.id, db)
    book_approvers = await _get_approvals(club.id, db)

    if not book_approvers:
        raise ValueError("No books with approvals to select from.")

    # Fetch all active books for tiebreaking metadata
    book_ids = list(book_approvers.keys())
    result = await db.execute(select(Book).where(Book.id.in_(book_ids)))
    books_by_id: dict[int, Book] = {b.id: b for b in result.scalars()}

    scores = _score_books(book_approvers, loads)

    # Sort all books by tiebreak key; first is winner, next two are runners-up
    ranked = sorted(
        book_ids,
        key=lambda bid: _tiebreak_key(
            books_by_id[bid], *scores[bid]
        ),
    )

    winner_id = ranked[0]
    runner_up_ids = ranked[1:3]
    winner_approvers = book_approvers[winner_id]
    winner_score, _ = scores[winner_id]

    # Update loads for winner's approvers
    for uid in winner_approvers:
        w_i = 1.0 / (1.0 + loads.get(uid, 0.0))
        loads[uid] = loads.get(uid, 0.0) + w_i

    # Decay loads for active members (active = last_active in this month)
    active_result = await db.execute(
        select(User).where(
            User.club_id == club.id,
            User.last_active >= date(year, month, 1),
            User.last_active < date(year + (month // 12), (month % 12) + 1, 1),
        )
    )
    active_user_ids = {u.id for u in active_result.scalars()}

    for uid in active_user_ids:
        loads[uid] = loads.get(uid, 0.0) * club.decay_rate

    # Persist updated loads
    load_result = await db.execute(
        select(UserLoad).where(UserLoad.club_id == club.id)
    )
    existing_loads = {row.user_id: row for row in load_result.scalars()}

    for uid, load_val in loads.items():
        if uid in existing_loads:
            existing_loads[uid].load_value = load_val
        else:
            db.add(UserLoad(user_id=uid, club_id=club.id, load_value=load_val))

    # Mark winner as selected
    winner = books_by_id[winner_id]
    winner.status = BookStatus.selected
    winner.selected_year = year
    winner.selected_month = month

    # Create result record
    monthly_result = MonthlyResult(
        club_id=club.id,
        year=year,
        month=month,
        winning_book_id=winner_id,
        runner_up_ids=",".join(str(i) for i in runner_up_ids),
        finalized_at=datetime.now(timezone.utc),
    )
    db.add(monthly_result)
    await db.commit()
    return monthly_result
