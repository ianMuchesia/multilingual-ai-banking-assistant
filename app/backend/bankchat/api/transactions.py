"""GET /api/transactions, GET /api/transactions/{reference}/receipt"""

from typing import Annotated

from fastapi import APIRouter, Query

from bankchat.api.deps import DbDep, SettingsDep, UserDep
from bankchat.schemas import ReceiptOut, TransactionOut
from bankchat.services.receipts import receipt_for_reference
from bankchat.services.transactions import recent_transactions

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    user: UserDep,
    session: DbDep,
    settings: SettingsDep,
    account_id: Annotated[int | None, Query()] = None,
    limit: Annotated[int | None, Query(ge=1)] = None,
) -> list[TransactionOut]:
    capped = min(limit or settings.transactions_default_limit, settings.transactions_max_limit)
    rows = recent_transactions(session, user.id, account_id, capped)
    return [TransactionOut.model_validate(t) for t in rows]


@router.get("/{reference}/receipt", response_model=ReceiptOut)
def receipt(reference: str, user: UserDep, session: DbDep) -> ReceiptOut:
    return receipt_for_reference(session, user.id, reference)
