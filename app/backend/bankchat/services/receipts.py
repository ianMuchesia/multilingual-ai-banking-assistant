"""Receipts are derived from the customer's transaction row: one source of truth, nothing to drift."""

from sqlalchemy.orm import Session

from bankchat.db.models import Transaction
from bankchat.schemas import ReceiptOut
from bankchat.services.errors import NotFoundError
from bankchat.services.transactions import get_by_reference

RECEIPT_STATUS = "completed"


def build_receipt(tx: Transaction) -> ReceiptOut:
    return ReceiptOut(
        reference=tx.reference,
        amount=float(tx.amount),
        channel=tx.channel,
        counterparty=tx.counterparty,
        from_account=tx.account.number,
        created_at=tx.created_at,
        status=RECEIPT_STATUS,
    )


def receipt_for_reference(session: Session, user_id: int, reference: str) -> ReceiptOut:
    tx = get_by_reference(session, user_id, reference)
    if tx is None:
        raise NotFoundError("transaction not found")
    return build_receipt(tx)
