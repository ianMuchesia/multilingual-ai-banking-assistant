"""Find another Benki Yetu customer named in a message ("send 2000 to Grace")."""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from bankchat.db.models import Account, User
from bankchat.domain import AccountType


def _name_parts(user: User) -> set[str]:
    return {user.username.lower(), *(part.lower() for part in user.full_name.split())}


def find_internal_payee_account(session: Session, sender_id: int, text: str) -> str | None:
    """The current account number of the one other customer whose name appears in `text`, else None.

    Ambiguous (two customers match) returns None, so the customer is asked for the account number.
    """
    words = set(re.findall(r"[a-z]+", text.lower()))
    if not words:
        return None
    others = session.scalars(select(User).where(User.id != sender_id)).all()
    matches = [u for u in others if _name_parts(u) & words]
    if len(matches) != 1:
        return None
    accounts = session.scalars(
        select(Account).where(Account.user_id == matches[0].id).order_by(Account.id)
    ).all()
    current = [a for a in accounts if a.type == AccountType.CURRENT]
    chosen = current or list(accounts)
    return chosen[0].number if chosen else None
