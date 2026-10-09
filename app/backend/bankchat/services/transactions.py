"""Read-only transaction queries, always scoped to the customer's own accounts."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from bankchat.db.models import Account, Transaction
from bankchat.services.accounts import get_user_account


@dataclass(frozen=True)
class TransactionFilter:
    account_ids: list[int]
    start: datetime | None = None          # inclusive, UTC
    end: datetime | None = None            # exclusive, UTC
    amount: Decimal | None = None
    direction: str | None = None
    channels: tuple[str, ...] = ()
    reference: str | None = None


def _own_account_ids(session: Session, user_id: int) -> list[int]:
    return list(session.scalars(select(Account.id).where(Account.user_id == user_id)))


def resolve_account_ids(session: Session, user_id: int, account_id: int | None) -> list[int]:
    """One owned account (404 if it isn't theirs) or all of the customer's accounts."""
    if account_id is not None:
        return [get_user_account(session, user_id, account_id).id]
    return _own_account_ids(session, user_id)


def _apply(query: Select[tuple[Transaction]], f: TransactionFilter) -> Select[tuple[Transaction]]:
    query = query.where(Transaction.account_id.in_(f.account_ids))
    if f.start is not None:
        query = query.where(Transaction.created_at >= f.start)
    if f.end is not None:
        query = query.where(Transaction.created_at < f.end)
    if f.amount is not None:
        query = query.where(Transaction.amount == f.amount)
    if f.direction is not None:
        query = query.where(Transaction.direction == f.direction)
    if f.channels:
        query = query.where(Transaction.channel.in_(f.channels))
    if f.reference is not None:
        query = query.where(Transaction.reference == f.reference)
    return query


def query_transactions(session: Session, f: TransactionFilter, limit: int, newest_first: bool = True) -> list[Transaction]:
    if not f.account_ids:
        return []
    order = (Transaction.created_at.desc(), Transaction.id.desc()) if newest_first else (
        Transaction.created_at.asc(), Transaction.id.asc()
    )
    return list(session.scalars(_apply(select(Transaction), f).order_by(*order).limit(limit)))


def recent_transactions(session: Session, user_id: int, account_id: int | None, limit: int) -> list[Transaction]:
    return query_transactions(session, TransactionFilter(resolve_account_ids(session, user_id, account_id)), limit)


def get_by_reference(session: Session, user_id: int, reference: str) -> Transaction | None:
    """The customer's own leg of the transaction with this reference (out-leg preferred)."""
    rows = query_transactions(
        session, TransactionFilter(_own_account_ids(session, user_id), reference=reference.strip().upper()), limit=2
    )
    rows.sort(key=lambda tx: tx.direction != "out")
    return rows[0] if rows else None
