"""Slots for the money-moving intents: which ones exist, which are required, and how to fill
them from the entities found in a message.

    internal_transfer   from_account, to_account, amount
    external_transfer   from_account, destination_type (bank|mobile), destination, amount,
                        bank (required when destination_type is bank)
    lipa_na_mpesa       from_account, payment_type (till|paybill), till_or_paybill, amount,
                        account_number (required when payment_type is paybill)

from_account defaults to the customer's current account. Slot values are JSON-friendly
(strings, and a number for amount) because they are stored in pending_actions.slots.
"""

from decimal import Decimal
from typing import Any

from bankchat.domain import AccountType, DestinationType, Intent, PaymentType
from bankchat.slots.entities import MessageEntities

BASE_REQUIRED: dict[str, tuple[str, ...]] = {
    Intent.INTERNAL_TRANSFER: ("from_account", "to_account", "amount"),
    Intent.EXTERNAL_TRANSFER: ("from_account", "destination_type", "destination", "amount"),
    Intent.LIPA_NA_MPESA: ("from_account", "payment_type", "till_or_paybill", "amount"),
}
CONDITIONAL_REQUIRED: dict[str, tuple[str, str, str]] = {
    # intent: (slot, when this slot..., ...has this value)
    Intent.EXTERNAL_TRANSFER: ("bank", "destination_type", DestinationType.BANK),
    Intent.LIPA_NA_MPESA: ("account_number", "payment_type", PaymentType.PAYBILL),
}


def allowed_slots(intent: str) -> frozenset[str]:
    names = set(BASE_REQUIRED.get(intent, ()))
    if intent in CONDITIONAL_REQUIRED:
        names.add(CONDITIONAL_REQUIRED[intent][0])
    return frozenset(names)


def missing_slots(intent: str, slots: dict[str, Any]) -> list[str]:
    """Required slots that are absent or empty, in a stable order."""
    required = list(BASE_REQUIRED.get(intent, ()))
    if intent in CONDITIONAL_REQUIRED:
        slot, when, value = CONDITIONAL_REQUIRED[intent]
        if slots.get(when) == value:
            required.append(slot)
    return [name for name in required if slots.get(name) in (None, "")]


def amount_to_json(amount: Decimal) -> int | float:
    return int(amount) if amount == amount.to_integral_value() else float(amount)


def _from_account(entities: MessageEntities, own: dict[AccountType, str]) -> str | None:
    if entities.from_hint and entities.from_hint in own:
        return own[entities.from_hint]
    return own.get(AccountType.CURRENT) or next(iter(own.values()), None)


def _internal(entities: MessageEntities, own: dict[AccountType, str]) -> dict[str, Any]:
    from_account = _from_account(entities, own)
    to_account = None
    numbers = entities.account_numbers
    if len(numbers) >= 2 and numbers[0] in own.values():
        from_account, to_account = numbers[0], numbers[1]
    elif numbers:
        to_account = numbers[0]
    elif entities.to_hint and entities.to_hint in own:
        to_account = own[entities.to_hint]
        if to_account == from_account and not entities.from_hint:
            # "move 5k to current": the money must come from the other own account.
            others = [n for t, n in own.items() if t != entities.to_hint]
            from_account = others[0] if others else from_account
    return {"from_account": from_account, "to_account": to_account}


def _external(entities: MessageEntities, own_phone: str | None) -> dict[str, Any]:
    if entities.phones:
        return {"destination_type": DestinationType.MOBILE.value, "destination": entities.phones[0]}
    if entities.wallets and entities.own_wallet and own_phone:
        return {"destination_type": DestinationType.MOBILE.value, "destination": own_phone}
    if entities.other_banks or entities.account_numbers:
        return {
            "destination_type": DestinationType.BANK.value,
            "destination": entities.account_numbers[0] if entities.account_numbers else None,
            "bank": entities.other_banks[0] if entities.other_banks else None,
        }
    if entities.wallets:
        return {"destination_type": DestinationType.MOBILE.value, "destination": None}
    return {"destination_type": None, "destination": None}


def _lipa(entities: MessageEntities) -> dict[str, Any]:
    if entities.paybill:
        return {
            "payment_type": PaymentType.PAYBILL.value,
            "till_or_paybill": entities.paybill,
            "account_number": entities.paybill_account,
        }
    if entities.till:
        return {"payment_type": PaymentType.TILL.value, "till_or_paybill": entities.till}
    return {"payment_type": None, "till_or_paybill": None}


def build_action_slots(
    intent: str, entities: MessageEntities, own_accounts: dict[AccountType, str], own_phone: str | None
) -> dict[str, Any]:
    """Slots for a money-moving intent; unknown values are left out (they show up as missing)."""
    if intent == Intent.INTERNAL_TRANSFER:
        slots = _internal(entities, own_accounts)
    elif intent == Intent.EXTERNAL_TRANSFER:
        slots = {"from_account": _from_account(entities, own_accounts), **_external(entities, own_phone)}
    elif intent == Intent.LIPA_NA_MPESA:
        slots = {"from_account": _from_account(entities, own_accounts), **_lipa(entities)}
    else:
        raise ValueError(f"{intent!r} is not a money-moving intent")
    if entities.amount is not None:
        slots["amount"] = amount_to_json(entities.amount)
    return {name: value for name, value in slots.items() if value not in (None, "")}
