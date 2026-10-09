"""Pending actions: created by chat, executed ONLY by confirm_action.

This is the only module that moves money. confirm_action runs in one database
transaction and, before touching a balance, checks that the action:
    1. exists and belongs to the customer (else 404),
    2. is still pending and not expired (else 409),
    3. has every required slot, with valid values (else 400),
    4. debits an account the customer owns, with enough balance (else 400).
Rows are locked (SELECT ... FOR UPDATE on PostgreSQL) so two confirms of the same
action, or two transfers from the same account, cannot interleave.
"""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from bankchat.clock import as_utc, utc_now
from bankchat.db.models import Account, PendingAction, Transaction, User
from bankchat.domain import ActionStatus, Direction, Intent
from bankchat.formatting import format_money, mask_account
from bankchat.schemas import CancelResponse, ConfirmResponse, PendingActionOut, TransactionOut
from bankchat.services.action_plan import TransferPlan, build_plan, merge_slots, normalized_slots
from bankchat.services.errors import ConflictError, InvalidInputError, NotFoundError
from bankchat.services.receipts import build_receipt
from bankchat.services.references import new_unique_reference
from bankchat.settings import Settings
from bankchat.slots.action_slots import missing_slots
from bankchat.slots.bank_directory import BankDirectory

log = logging.getLogger(__name__)


# --- creation (called by chat; never moves money) ---------------------------------------

def create_pending_action(
    session: Session, settings: Settings, user_id: int, intent: str, slots: dict[str, Any], message: str
) -> PendingAction:
    now = utc_now()
    action = PendingAction(
        user_id=user_id,
        intent=intent,
        slots=slots,
        status=ActionStatus.PENDING.value,
        message=message,
        created_at=now,
        expires_at=now + settings.pending_action_ttl,
    )
    session.add(action)
    session.flush()
    return action


def to_pending_action_out(action: PendingAction) -> PendingActionOut:
    return PendingActionOut(
        id=action.id,
        intent=action.intent,
        slots=dict(action.slots),
        missing_slots=missing_slots(action.intent, action.slots),
        expires_at=action.expires_at,
    )


# --- shared checks ----------------------------------------------------------------------

def _locked_action(session: Session, user_id: int, action_id: str) -> PendingAction:
    action = session.scalar(
        select(PendingAction)
        .where(PendingAction.id == action_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if action is None or action.user_id != user_id:
        # Same answer for "doesn't exist" and "someone else's": no information leak.
        raise NotFoundError("action not found")
    return action


def _is_expired(action: PendingAction, now: datetime) -> bool:
    return as_utc(action.expires_at) <= now


def _ensure_pending(session: Session, action: PendingAction, now: datetime) -> None:
    if action.status == ActionStatus.PENDING and _is_expired(action, now):
        action.status = ActionStatus.EXPIRED.value
        action.resolved_at = now
        session.commit()
        log.info("action %s expired before confirmation", action.id)
        raise ConflictError("this action has expired; please start again")
    if action.status != ActionStatus.PENDING:
        raise ConflictError(f"this action is already {action.status}")


# --- execution --------------------------------------------------------------------------

def _lock_accounts(session: Session, numbers: list[str]) -> dict[str, Account]:
    """Lock in ascending id order so concurrent transfers can't deadlock."""
    rows = session.scalars(
        select(Account)
        .where(Account.number.in_(numbers))
        .order_by(Account.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    return {a.number: a for a in rows}


def _internal_counterparties(sender: User, source: Account, target: Account) -> tuple[str, str]:
    """(shown on the sender's row, shown on the recipient's row)."""
    if target.user_id == sender.id:
        return (
            f"Own {target.type} account {mask_account(target.number)}",
            f"Own {source.type} account {mask_account(source.number)}",
        )
    return f"{target.user.full_name} {mask_account(target.number)}", sender.full_name


def _post(
    session: Session, account: Account, direction: Direction, plan: TransferPlan,
    reference: str, counterparty: str, description: str, now: datetime,
) -> Transaction:
    if direction is Direction.OUT:
        account.balance -= plan.amount
    else:
        account.balance += plan.amount
    tx = Transaction(
        reference=reference,
        account_id=account.id,
        direction=direction.value,
        amount=plan.amount,
        channel=plan.channel.value,
        counterparty=counterparty,
        description=description,
        created_at=now,
        balance_after=account.balance,
    )
    tx.account = account
    session.add(tx)
    return tx


def _execute(session: Session, settings: Settings, user: User, plan: TransferPlan, now: datetime) -> Transaction:
    numbers = [plan.from_account] + ([plan.to_account] if plan.to_account else [])
    accounts = _lock_accounts(session, numbers)
    source = accounts.get(plan.from_account)
    if source is None or source.user_id != user.id:
        raise InvalidInputError("from_account is not one of your accounts")
    if source.balance < plan.amount:
        raise InvalidInputError(
            f"insufficient funds: {source.type} account {mask_account(source.number)} has "
            f"{format_money(source.balance, source.currency)}"
        )
    reference = new_unique_reference(session, settings.reference_prefix)

    if plan.intent != Intent.INTERNAL_TRANSFER:
        return _post(session, source, Direction.OUT, plan, reference, plan.counterparty, plan.description, now)

    target = accounts.get(plan.to_account or "")
    if target is None:
        raise InvalidInputError(f"no {settings.currency} account {plan.to_account} at this bank")
    out_party, in_party = _internal_counterparties(user, source, target)
    out_tx = _post(session, source, Direction.OUT, plan, reference, out_party, f"Transfer to {out_party}", now)
    _post(session, target, Direction.IN, plan, reference, in_party, f"Transfer from {in_party}", now)
    return out_tx


def confirm_action(
    session: Session, settings: Settings, bank: BankDirectory, user: User, action_id: str, overrides: dict[str, Any]
) -> ConfirmResponse:
    now = utc_now()
    try:
        action = _locked_action(session, user.id, action_id)
        _ensure_pending(session, action, now)
        slots = merge_slots(action.intent, action.slots, overrides)
        plan = build_plan(action.intent, slots, settings, bank)
        out_tx = _execute(session, settings, user, plan, now)

        action.slots = normalized_slots(slots, plan)
        action.status = ActionStatus.EXECUTED.value
        action.executed_reference = out_tx.reference
        action.resolved_at = now
        session.flush()
        response = ConfirmResponse(transaction=TransactionOut.model_validate(out_tx), receipt=build_receipt(out_tx))
        session.commit()
    except Exception:
        session.rollback()
        raise
    log.info(
        "executed action %s (%s) for user %s: %s %s ref %s",
        action_id, plan.intent, user.id, plan.channel, plan.amount, out_tx.reference,
    )
    return response


def cancel_action(session: Session, user: User, action_id: str) -> CancelResponse:
    now = utc_now()
    try:
        action = _locked_action(session, user.id, action_id)
        if action.status == ActionStatus.CANCELLED:
            return CancelResponse()
        _ensure_pending(session, action, now)
        action.status = ActionStatus.CANCELLED.value
        action.resolved_at = now
        session.commit()
    except Exception:
        session.rollback()
        raise
    log.info("cancelled action %s for user %s", action_id, user.id)
    return CancelResponse()

