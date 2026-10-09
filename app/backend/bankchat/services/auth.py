"""Passwords (bcrypt) and access tokens (JWT, HS256)."""

import logging
from datetime import timedelta

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from bankchat.clock import utc_now
from bankchat.db.models import User
from bankchat.settings import Settings

log = logging.getLogger(__name__)

TOKEN_SUBJECT_CLAIM = "sub"


class InvalidTokenError(Exception):
    pass


def hash_password(password: str, rounds: int) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=rounds)).decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def authenticate(session: Session, username: str, password: str) -> User | None:
    user = session.scalar(select(User).where(User.username == username.strip().lower()))
    if user is None or not verify_password(password, user.password_hash):
        log.info("failed login for username=%r", username)
        return None
    return user


def create_access_token(user_id: int, settings: Settings) -> str:
    now = utc_now()
    claims = {
        TOKEN_SUBJECT_CLAIM: str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def user_id_from_token(token: str, settings: Settings) -> int:
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return int(claims[TOKEN_SUBJECT_CLAIM])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise InvalidTokenError("invalid or expired token") from exc
