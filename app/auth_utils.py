"""Auth helpers: token generation, email sending, session management."""

import hashlib
import json
import random
import string
from datetime import datetime, timedelta, timezone

import resend
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import (
    BASE_URL,
    EMAIL_FROM,
    MAGIC_LINK_EXPIRE_MINUTES,
    RESEND_API_KEY,
    SECRET_KEY,
    SESSION_COOKIE_NAME,
)
from app.models import BookClub, MagicToken, User

resend.api_key = RESEND_API_KEY

_serializer = URLSafeTimedSerializer(SECRET_KEY)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def create_signed_token(user_id: int) -> str:
    return _serializer.dumps(user_id, salt="magic-link")


def verify_signed_token(token: str) -> int | None:
    try:
        user_id = _serializer.loads(
            token, salt="magic-link", max_age=MAGIC_LINK_EXPIRE_MINUTES * 60
        )
        return int(user_id)
    except Exception:
        return None


async def issue_magic_token(user: User, db: AsyncSession) -> tuple[str, str]:
    """Create a MagicToken row. Returns (signed_token, otp_code)."""
    signed = create_signed_token(user.id)
    otp = _generate_otp()
    expires = datetime.now(timezone.utc) + timedelta(minutes=MAGIC_LINK_EXPIRE_MINUTES)
    token_row = MagicToken(
        user_id=user.id,
        token_hash=_hash_token(signed),
        otp_code=otp,
        expires_at=expires,
    )
    db.add(token_row)
    await db.commit()
    return signed, otp


async def consume_magic_token(token: str, db: AsyncSession) -> User | None:
    """Verify a signed token, mark it used, return the User or None."""
    user_id = verify_signed_token(token)
    if user_id is None:
        return None
    token_hash = _hash_token(token)
    result = await db.execute(
        select(MagicToken).where(
            MagicToken.token_hash == token_hash,
            MagicToken.used_at.is_(None),
            MagicToken.expires_at > datetime.now(timezone.utc),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    row.used_at = datetime.now(timezone.utc)
    await db.commit()
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def consume_otp(email: str, club_id: int, otp: str, db: AsyncSession) -> User | None:
    """Verify an OTP code for a user, mark token used, return User or None."""
    result = await db.execute(
        select(User).where(User.email == email, User.club_id == club_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        return None
    result = await db.execute(
        select(MagicToken).where(
            MagicToken.user_id == user.id,
            MagicToken.otp_code == otp,
            MagicToken.used_at.is_(None),
            MagicToken.expires_at > datetime.now(timezone.utc),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    row.used_at = datetime.now(timezone.utc)
    await db.commit()
    return user


def is_email_allowed(email: str, club: BookClub) -> bool:
    allowed_emails = json.loads(club.allowed_emails)
    allowed_domains = json.loads(club.allowed_domains)
    domain = email.split("@")[-1].lower()
    return email.lower() in allowed_emails or domain in allowed_domains


async def send_magic_email(email: str, display_name: str, club_slug: str, token: str, otp: str) -> None:
    magic_link = f"{BASE_URL}/{club_slug}/auth/verify?token={token}"
    resend.Emails.send({
        "from": EMAIL_FROM,
        "to": email,
        "subject": "Your Book Club login link",
        "html": f"""
        <p>Hi {display_name},</p>
        <p>Click the link below to log in to Book Club (expires in {MAGIC_LINK_EXPIRE_MINUTES} minutes):</p>
        <p><a href="{magic_link}">{magic_link}</a></p>
        <p>Or enter this code on the verification page: <strong>{otp}</strong></p>
        <p>If you didn't request this, you can ignore it.</p>
        """,
    })


def get_session_user_id(request) -> int | None:
    return request.session.get("user_id")


def set_session(request, user_id: int) -> None:
    request.session["user_id"] = user_id


def clear_session(request) -> None:
    request.session.clear()
