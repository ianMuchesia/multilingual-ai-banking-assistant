"""Turn a pending action's slots into a validated transfer plan. Pure: no database access.

Everything a customer (or the chat extractor) put into the slots is untrusted here and is
re-validated: required slots present, amount positive and within the limit, phone numbers,
till/paybill numbers and bank names well formed.
"""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from bankchat.domain import Channel, DestinationType, Intent, PaymentType
from bankchat.formatting import format_money
from bankchat.services.errors import InvalidInputError
from bankchat.settings import Settings
from bankchat.slots.action_slots import allowed_slots, amount_to_json, missing_slots
from bankchat.slots.bank_directory import BankDirectory
from bankchat.slots.entities import normalize_phone

ACCOUNT_NUMBER = re.compile(r"\d{6,20}")
TILL_NUMBER = re.compile(r"\d{5,8}")
PAYBILL_NUMBER = re.compile(r"\d{5,7}")
PAYBILL_ACCOUNT = re.compile(r"[A-Za-z0-9-]{1,30}")
CENTS = Decimal("0.01")
SHORT_BANK_NAME = 4


@dataclass(frozen=True)
class TransferPlan:
    intent: str
    from_account: str
    amount: Decimal
    channel: Channel
    counterparty: str             # shown on the sender's row; internal transfers fill it in from the DB
    description: str
    to_account: str | None = None  # internal transfers only


def merge_slots(intent: str, stored: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Stored slots updated with the customer's values. Unknown slot names are rejected."""
    unknown = sorted(set(overrides) - allowed_slots(intent))
    if unknown:
        raise InvalidInputError(f"unknown slot(s) for {intent}: {', '.join(unknown)}")
    merged = dict(stored)
    for name, value in overrides.items():
        if isinstance(value, str):
            value = value.strip()
        if value is None or value == "":
            merged.pop(name, None)
        else:
            merged[name] = value
    return merged


def parse_amount(value: Any, settings: Settings) -> Decimal:
    if isinstance(value, bool):
        raise InvalidInputError("amount must be a number")
    try:
        amount = Decimal(str(value).replace(",", "").strip())
    except InvalidOperation as exc:
        raise InvalidInputError("amount must be a number") from exc
    if not amount.is_finite() or amount <= 0:
        raise InvalidInputError("amount must be greater than zero")
    if amount != amount.quantize(CENTS):
        raise InvalidInputError("amount can have at most 2 decimal places")
    if amount > Decimal(str(settings.max_transfer_amount)):
        raise InvalidInputError(
            f"amount exceeds the limit of {format_money(settings.max_transfer_amount, settings.currency)}"
        )
    return amount.quantize(CENTS)


def _require(pattern: re.Pattern[str], value: Any, name: str) -> str:
    text = str(value).strip()
    if not pattern.fullmatch(text):
        raise InvalidInputError(f"{name} is not valid: {text!r}")
    return text


def _bank_label(name: str) -> str:
    return name.upper() if len(name) <= SHORT_BANK_NAME else name.title()


def _internal(slots: dict[str, Any], amount: Decimal) -> TransferPlan:
    from_account = _require(ACCOUNT_NUMBER, slots["from_account"], "from_account")
    to_account = _require(ACCOUNT_NUMBER, slots["to_account"], "to_account")
    if from_account == to_account:
        raise InvalidInputError("from_account and to_account must be different")
    return TransferPlan(
        intent=Intent.INTERNAL_TRANSFER,
        from_account=from_account,
        amount=amount,
        channel=Channel.INTERNAL,
        counterparty="",
        description="Internal transfer",
        to_account=to_account,
    )


def _external(slots: dict[str, Any], amount: Decimal, bank: BankDirectory) -> TransferPlan:
    from_account = _require(ACCOUNT_NUMBER, slots["from_account"], "from_account")
    destination_type = str(slots["destination_type"]).strip().lower()
    if destination_type == DestinationType.MOBILE:
        phone = normalize_phone(str(slots["destination"]))
        if phone is None:
            raise InvalidInputError("destination is not a valid Kenyan mobile number")
        return TransferPlan(
            intent=Intent.EXTERNAL_TRANSFER,
            from_account=from_account,
            amount=amount,
            channel=Channel.MPESA,
            counterparty=f"M-Pesa {phone}",
            description=f"Bank to M-Pesa {phone}",
        )
    if destination_type == DestinationType.BANK:
        destination = _require(ACCOUNT_NUMBER, slots["destination"], "destination")
        bank_name = str(slots["bank"]).strip().lower()
        if not bank.is_other_bank(bank_name):
            raise InvalidInputError(
                f"{slots['bank']!r} is not a supported destination bank (use an internal transfer for {bank.name})"
            )
        label = _bank_label(bank_name)
        return TransferPlan(
            intent=Intent.EXTERNAL_TRANSFER,
            from_account=from_account,
            amount=amount,
            channel=Channel.PESALINK,
            counterparty=f"{label} a/c {destination}",
            description=f"PesaLink to {label} a/c {destination}",
        )
    raise InvalidInputError("destination_type must be 'bank' or 'mobile'")


def _lipa(slots: dict[str, Any], amount: Decimal) -> TransferPlan:
    from_account = _require(ACCOUNT_NUMBER, slots["from_account"], "from_account")
    payment_type = str(slots["payment_type"]).strip().lower()
    if payment_type == PaymentType.TILL:
        till = _require(TILL_NUMBER, slots["till_or_paybill"], "till_or_paybill")
        return TransferPlan(
            intent=Intent.LIPA_NA_MPESA,
            from_account=from_account,
            amount=amount,
            channel=Channel.TILL,
            counterparty=f"Till {till}",
            description=f"Lipa na M-Pesa Buy Goods till {till}",
        )
    if payment_type == PaymentType.PAYBILL:
        paybill = _require(PAYBILL_NUMBER, slots["till_or_paybill"], "till_or_paybill")
        account = _require(PAYBILL_ACCOUNT, slots["account_number"], "account_number")
        return TransferPlan(
            intent=Intent.LIPA_NA_MPESA,
            from_account=from_account,
            amount=amount,
            channel=Channel.PAYBILL,
            counterparty=f"Paybill {paybill} a/c {account}",
            description=f"Lipa na M-Pesa Paybill {paybill} account {account}",
        )
    raise InvalidInputError("payment_type must be 'till' or 'paybill'")


def build_plan(intent: str, slots: dict[str, Any], settings: Settings, bank: BankDirectory) -> TransferPlan:
    missing = missing_slots(intent, slots)
    if missing:
        raise InvalidInputError(f"missing slots: {', '.join(missing)}")
    amount = parse_amount(slots["amount"], settings)
    if intent == Intent.INTERNAL_TRANSFER:
        return _internal(slots, amount)
    if intent == Intent.EXTERNAL_TRANSFER:
        return _external(slots, amount, bank)
    if intent == Intent.LIPA_NA_MPESA:
        return _lipa(slots, amount)
    raise InvalidInputError(f"{intent} cannot be executed")


def normalized_slots(slots: dict[str, Any], plan: TransferPlan) -> dict[str, Any]:
    """The slots as executed (amount as a JSON number), stored on the action for the audit trail."""
    return {**slots, "amount": amount_to_json(plan.amount)}
