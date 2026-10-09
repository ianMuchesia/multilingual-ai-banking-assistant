"""FastAPI dependencies: settings, DB session, current user, chat context (all from app.state)."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from bankchat.db.models import User
from bankchat.services.auth import InvalidTokenError, user_id_from_token
from bankchat.services.chat import ChatContext
from bankchat.settings import Settings

_bearer = HTTPBearer(auto_error=False)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Iterator[Session]:
    session: Session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_chat_context(request: Request) -> ChatContext:
    return request.app.state.chat_context


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"}
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("not authenticated")
    try:
        user_id = user_id_from_token(credentials.credentials, settings)
    except InvalidTokenError as exc:
        raise _unauthorized("invalid or expired token") from exc
    user = session.get(User, user_id)
    if user is None or user.password_hash is None:
        raise _unauthorized("invalid or expired token")
    return user


SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[Session, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_user)]
ChatContextDep = Annotated[ChatContext, Depends(get_chat_context)]
