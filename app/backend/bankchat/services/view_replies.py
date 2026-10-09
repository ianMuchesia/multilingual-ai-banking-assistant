"""Replies for the read-only (view) intents. Nothing here writes to the database."""

import re
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from bankchat.clock import local_today, start_of_local_day
from bankchat.db.models import Account, Transaction, User
from bankchat.domain import Channel, ReplyKind
from bankchat.formatting import format_money, mask_account
from bankchat.schemas import AccountOut, ReplyOut, TransactionOut
from bankchat.services.accounts import list_accounts
from bankchat.services.receipts import build_receipt
from bankchat.services.transactions import TransactionFilter, get_by_reference, query_transactions
from bankchat.settings import Settings
from bankchat.slots.dates import DateRange, add_months, parse_date_range
from bankchat.slots.entities import MessageEntities

CHANNEL_KEYWORDS: dict[Channel, str] = {
    Channel.SALARY: r"\b(salary|mshahara|payslip)\b",
    Channel.MPESA: r"\bm-?pesa\b",
    Channel.TILL: r"\b(till|buy goods)\b",
    Channel.PAYBILL: r"\b(pay\s*bill|bill)\b",
    Channel.PESALINK: r"\bpesalink\b",
    Channel.DEPOSIT: r"\b(deposit|cash)\b",
    Channel.INTERNAL: r"\b(internal|savings to current|current to savings)\b",
}
# Words that never identify a counterparty, so they are not used for name matching.
STOPWORDS = frozenset(
    "the and for from with that this did my me i you your was were have has had can see show find look search "
    "money pesa transaction transactions payment payments paid pay sent send received receive came come got "
    "yesterday today last week month months account accounts savings current salary receipt proof check "
    "status where when what which how much amount kes ksh shillings bob please kindly nilituma nilipokea jana "
    "leo yangu wangu kwa ya na from into onto mpesa m-pesa till paybill bank".split()
)
MIN_NAME_TOKEN = 3
CANDIDATE_POOL = 200


def _accounts_dump(accounts: list[Account]) -> list[dict]:
    return [AccountOut.model_validate(a).model_dump(mode="json") for a in accounts]


def _tx_dump(rows: list[Transaction]) -> list[dict]:
    return [TransactionOut.model_validate(t).model_dump(mode="json") for t in rows]


def _selected_accounts(accounts: list[Account], entities: MessageEntities) -> list[Account]:
    """Accounts the message points at (by number or savings/current), else all of them."""
    by_number = [a for a in accounts if a.number in entities.account_numbers]
    if by_number:
        return by_number
    if entities.account_hint:
        by_type = [a for a in accounts if a.type == entities.account_hint]
        if by_type:
            return by_type
    return accounts


def _utc_bounds(period: DateRange, settings: Settings) -> tuple[datetime, datetime]:
    tz = settings.bank_timezone
    return start_of_local_day(period.start, tz), start_of_local_day(period.end + timedelta(days=1), tz)


def balance_reply(session: Session, settings: Settings, user: User, entities: MessageEntities) -> ReplyOut:
    accounts = _selected_accounts(list_accounts(session, user.id), entities)
    lines = [f"{a.type.title()} {mask_account(a.number)}: {format_money(a.balance, a.currency)}" for a in accounts]
    return ReplyOut(
        kind=ReplyKind.BALANCE.value,
        text="Your balance: " + "; ".join(lines) + ".",
        data={"accounts": _accounts_dump(accounts)},
    )


def mini_statement_reply(session: Session, settings: Settings, user: User, entities: MessageEntities) -> ReplyOut:
    accounts = _selected_accounts(list_accounts(session, user.id), entities)
    rows = query_transactions(session, TransactionFilter([a.id for a in accounts]), settings.mini_statement_limit)
    scope = f"{accounts[0].type} account {mask_account(accounts[0].number)}" if len(accounts) == 1 else "accounts"
    return ReplyOut(
        kind=ReplyKind.MINI_STATEMENT.value,
        text=f"Your last {len(rows)} transactions on your {scope}.",
        data={"transactions": _tx_dump(rows)},
    )


def full_statement_reply(
    session: Session, settings: Settings, user: User, entities: MessageEntities, text: str
) -> ReplyOut:
    today = local_today(settings.bank_timezone)
    period = parse_date_range(text, today) or DateRange(
        add_months(today, -settings.full_statement_default_months), today
    )
    start, end = _utc_bounds(period, settings)
    accounts = _selected_accounts(list_accounts(session, user.id), entities)
    rows = query_transactions(
        session,
        TransactionFilter([a.id for a in accounts], start=start, end=end),
        settings.full_statement_max_rows,
        newest_first=False,
    )
    return ReplyOut(
        kind=ReplyKind.FULL_STATEMENT.value,
        text=(
            f"Statement from {period.start:%d %b %Y} to {period.end:%d %b %Y}: {len(rows)} transactions. "
            "(Demo: shown here; PDF/email delivery is not part of this simulation.)"
        ),
        data={"start": period.start.isoformat(), "end": period.end.isoformat(), "transactions": _tx_dump(rows)},
    )


def _channels(text: str) -> tuple[str, ...]:
    return tuple(c.value for c, pattern in CHANNEL_KEYWORDS.items() if re.search(pattern, text, re.I))


def _name_tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z]+", text.lower())
    return [w for w in words if len(w) >= MIN_NAME_TOKEN and w not in STOPWORDS]


def _by_counterparty(rows: list[Transaction], text: str) -> tuple[list[Transaction], bool]:
    """Rows whose counterparty contains a name from the message, and True; (rows, False) if no name matches."""
    tokens = _name_tokens(text)
    matched = [t for t in rows if any(tok in t.counterparty.lower() for tok in tokens)]
    return (matched, True) if matched else (rows, False)


def _search(
    session: Session, settings: Settings, user: User, entities: MessageEntities, text: str, limit: int
) -> tuple[list[Transaction], bool]:
    """(matches, whether the message gave any search criteria)."""
    today = local_today(settings.bank_timezone)
    period = parse_date_range(text, today)
    window = period or DateRange(today - timedelta(days=settings.find_transaction_window_days), today)
    start, end = _utc_bounds(window, settings)
    accounts = _selected_accounts(list_accounts(session, user.id), entities)
    criteria = TransactionFilter(
        [a.id for a in accounts],
        start=start,
        end=end,
        amount=entities.amount,
        direction=entities.direction_hint,
        channels=_channels(text),
    )
    rows, named = _by_counterparty(query_transactions(session, criteria, CANDIDATE_POOL), text)
    has_criteria = bool(period or entities.amount or entities.direction_hint or criteria.channels or named)
    return rows[:limit], has_criteria


def find_transaction_reply(
    session: Session, settings: Settings, user: User, entities: MessageEntities, text: str
) -> ReplyOut:
    if entities.references:
        tx = get_by_reference(session, user.id, entities.references[0])
        matches = [tx] if tx else []
    else:
        matches, has_criteria = _search(session, settings, user, entities, text, settings.find_transaction_limit)
        if not has_criteria:
            matches = []
    if matches:
        reply = f"I found {len(matches)} matching transaction(s)."
    else:
        reply = "I couldn't find a matching transaction. Tell me the amount, the date, or who it was with."
    return ReplyOut(kind=ReplyKind.FIND_TRANSACTION.value, text=reply, data={"matches": _tx_dump(matches)})


def view_receipt_reply(
    session: Session, settings: Settings, user: User, entities: MessageEntities, text: str
) -> ReplyOut:
    if entities.references:
        tx = get_by_reference(session, user.id, entities.references[0])
        receipt = build_receipt(tx).model_dump(mode="json") if tx else None
        reply = "Here is your receipt." if tx else f"I couldn't find a transaction with reference {entities.references[0]}."
        return ReplyOut(kind=ReplyKind.VIEW_RECEIPT.value, text=reply, data={"receipt": receipt, "candidates": []})

    candidates, has_criteria = _search(session, settings, user, entities, text, settings.receipt_candidates_limit)
    if has_criteria and len(candidates) == 1:
        receipt = build_receipt(candidates[0]).model_dump(mode="json")
        return ReplyOut(
            kind=ReplyKind.VIEW_RECEIPT.value,
            text="Here is your receipt.",
            data={"receipt": receipt, "candidates": _tx_dump(candidates)},
        )
    if not has_criteria:
        candidates = query_transactions(
            session,
            TransactionFilter([a.id for a in list_accounts(session, user.id)], direction="out"),
            settings.receipt_candidates_limit,
        )
    return ReplyOut(
        kind=ReplyKind.VIEW_RECEIPT.value,
        text="Which transaction do you need the receipt for? Pick one below or give me its reference.",
        data={"receipt": None, "candidates": _tx_dump(candidates)},
    )
