"""Account lookups, always scoped to the customer who asks."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from bankchat.db.models import Account
from bankchat.domain import AccountType
from bankchat.services.errors import NotFoundError


def list_accounts(session: Session, user_id: int) -> list[Account]:
    return list(session.scalars(select(Account).where(Account.user_id == user_id).order_by(Account.id)))


def get_user_account(session: Session, user_id: int, account_id: int) -> Account:
    account = session.get(Account, account_id)
    if account is None or account.user_id != user_id:
        raise NotFoundError("account not found")
    return account


def accounts_by_type(accounts: list[Account]) -> dict[AccountType, str]:
    """{savings: number, current: number} for slot filling (first account of each type)."""
    result: dict[AccountType, str] = {}
    for account in accounts:
        result.setdefault(AccountType(account.type), account.number)
    return result


def get_account_by_number(session: Session, number: str, *, for_update: bool = False) -> Account | None:
    query = select(Account).where(Account.number == number)
    if for_update:
        query = query.with_for_update()
    return session.scalar(query)
