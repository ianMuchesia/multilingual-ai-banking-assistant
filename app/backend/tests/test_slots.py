"""Slot extraction: amounts, phones, account numbers, till/paybill, banks, account hints, dates."""

import json
from datetime import date
from decimal import Decimal

import pytest

from bankchat.domain import INTENT_CATEGORY, AccountType
from bankchat.settings import Settings
from bankchat.slots.action_slots import build_action_slots, missing_slots
from bankchat.slots.bank_directory import BankDirectory
from bankchat.slots.dates import DateRange, parse_date_range
from bankchat.slots.entities import extract_entities, normalize_phone

SAVINGS = "110000000001"
CURRENT = "120000000001"
OWN = {AccountType.SAVINGS: SAVINGS, AccountType.CURRENT: CURRENT}
OWN_PHONE = "254712000101"
TODAY = date(2026, 10, 9)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("send 5k to brian", "5000"),
        ("transfer 5,000 to savings", "5000"),
        ("pay 1.5M to KCB", "1500000"),
        ("KES 2,400 to till 512345", "2400"),
        ("kes2400 please", "2400"),
        ("Ksh. 300 to mama", "300"),
        ("tuma 5 thao", "5000"),
        ("tuma elfu tano kwa brian", "5000"),
        ("tuma laki moja", "100000"),
        ("send 250.50 to savings", "250.50"),
        ("send 2 million to equity", "2000000"),
        ("send 0712345678 1000", "1000"),
        ("send 1000 to 0712 345 678", "1000"),
        ("pay till 512345 750", "750"),
    ],
)
def test_amounts(bank: BankDirectory, text: str, expected: str) -> None:
    assert extract_entities(text, bank).amount == Decimal(expected)


@pytest.mark.parametrize(
    "text",
    ["what is my balance", "statement for the last 3 months", "send money to 0712345678", "receipt for BY12AB34CD"],
)
def test_no_amount(bank: BankDirectory, text: str) -> None:
    assert extract_entities(text, bank).amount is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0712345678", "254712345678"),
        ("0112345678", "254112345678"),
        ("+254712345678", "254712345678"),
        ("254 712 345 678", "254712345678"),
        ("0712-345-678", "254712345678"),
        ("0812345678", None),
        ("071234567", None),
    ],
)
def test_normalize_phone(raw: str, expected: str | None) -> None:
    assert normalize_phone(raw) == expected


def test_phone_in_message(bank: BankDirectory) -> None:
    entities = extract_entities("send 1,500 to +254 712 345 678 on mpesa", bank)
    assert entities.phones == ["254712345678"]
    assert entities.wallets == ["mpesa"]
    assert entities.amount == Decimal("1500")


def test_labelled_bank_account_is_not_a_phone(bank: BankDirectory) -> None:
    entities = extract_entities("send 10000 to equity account 0123456789", bank)
    assert entities.account_numbers == ["0123456789"]
    assert entities.phones == []
    assert entities.other_banks == ["equity"]
    assert entities.amount == Decimal("10000")


def test_account_numbers(bank: BankDirectory) -> None:
    entities = extract_entities("move 2000 from 110000000001 to 120000000002", bank)
    assert entities.account_numbers == ["110000000001", "120000000002"]
    assert entities.amount == Decimal("2000")


def test_till(bank: BankDirectory) -> None:
    entities = extract_entities("pay till number 512345 KES 750", bank)
    assert entities.till == "512345"
    assert entities.amount == Decimal("750")


def test_paybill_with_account(bank: BankDirectory) -> None:
    entities = extract_entities("pay paybill 888880 account 12345678 1500", bank)
    assert entities.paybill == "888880"
    assert entities.paybill_account == "12345678"
    assert entities.amount == Decimal("1500")
    assert entities.account_numbers == []


def test_reference(bank: BankDirectory) -> None:
    assert extract_entities("receipt for BY4K7Q2M9X please", bank).references == ["BY4K7Q2M9X"]


def test_other_banks_come_from_bank_json(bank: BankDirectory, settings: Settings) -> None:
    raw = json.loads(settings.bank_config_path.read_text(encoding="utf-8"))
    assert set(bank.other_banks) == {b.lower() for b in raw["other_banks"]}
    assert extract_entities("send 5k to my KCB account", bank).other_banks == ["kcb"]
    assert extract_entities("tuma 5k hapa hapa benki yetu", bank).own_bank


@pytest.mark.parametrize(
    ("text", "from_hint", "to_hint"),
    [
        ("move 5k from savings to current", AccountType.SAVINGS, AccountType.CURRENT),
        ("transfer 5000 current to savings", AccountType.CURRENT, AccountType.SAVINGS),
        ("put 3000 into my savings", None, AccountType.SAVINGS),
        ("hamisha 2000 kutoka akiba", AccountType.SAVINGS, None),
    ],
)
def test_account_hints(bank: BankDirectory, text: str, from_hint: AccountType | None, to_hint: AccountType | None) -> None:
    entities = extract_entities(text, bank)
    assert (entities.from_hint, entities.to_hint) == (from_hint, to_hint)


@pytest.mark.parametrize(
    ("text", "direction"),
    [("did the money brian sent me arrive", "in"), ("the 5000 I paid yesterday", "out"), ("find my transaction", None)],
)
def test_direction(bank: BankDirectory, text: str, direction: str | None) -> None:
    assert extract_entities(text, bank).direction_hint == direction


# --- slots for action intents ------------------------------------------------------------

def _slots(bank: BankDirectory, intent: str, text: str) -> dict:
    return build_action_slots(intent, extract_entities(text, bank), OWN, OWN_PHONE)


def test_internal_transfer_slots(bank: BankDirectory) -> None:
    slots = _slots(bank, "internal_transfer", "transfer 5000 from current to savings")
    assert slots == {"from_account": CURRENT, "to_account": SAVINGS, "amount": 5000}
    assert missing_slots("internal_transfer", slots) == []


def test_internal_transfer_to_current_comes_from_savings(bank: BankDirectory) -> None:
    slots = _slots(bank, "internal_transfer", "move 5k to current")
    assert slots == {"from_account": SAVINGS, "to_account": CURRENT, "amount": 5000}


def test_from_account_defaults_to_current(bank: BankDirectory) -> None:
    slots = _slots(bank, "internal_transfer", "send 2000 to 120000000002")
    assert slots == {"from_account": CURRENT, "to_account": "120000000002", "amount": 2000}


def test_external_mobile_slots(bank: BankDirectory) -> None:
    slots = _slots(bank, "external_transfer", "send 1,500 to 0712345678")
    assert slots == {
        "from_account": CURRENT, "destination_type": "mobile", "destination": "254712345678", "amount": 1500,
    }


def test_external_to_own_mpesa(bank: BankDirectory) -> None:
    slots = _slots(bank, "external_transfer", "withdraw 3000 to my mpesa")
    assert slots["destination"] == OWN_PHONE
    assert slots["destination_type"] == "mobile"


def test_external_bank_missing_destination(bank: BankDirectory) -> None:
    slots = _slots(bank, "external_transfer", "send 20k to my KCB account")
    assert slots == {"from_account": CURRENT, "destination_type": "bank", "bank": "kcb", "amount": 20000}
    assert missing_slots("external_transfer", slots) == ["destination"]


def test_lipa_till_slots(bank: BankDirectory) -> None:
    slots = _slots(bank, "lipa_na_mpesa", "pay till 512345 KES 750 from savings")
    assert slots == {"from_account": SAVINGS, "payment_type": "till", "till_or_paybill": "512345", "amount": 750}


def test_paybill_needs_account_number(bank: BankDirectory) -> None:
    slots = _slots(bank, "lipa_na_mpesa", "pay paybill 888880 2000")
    assert missing_slots("lipa_na_mpesa", slots) == ["account_number"]


def test_nothing_known_means_everything_missing(bank: BankDirectory) -> None:
    slots = _slots(bank, "lipa_na_mpesa", "lipa na mpesa")
    assert missing_slots("lipa_na_mpesa", slots) == ["payment_type", "till_or_paybill", "amount"]


# --- dates ---------------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("statement for the last 3 months", DateRange(date(2026, 7, 9), TODAY)),
        ("statement for last month", DateRange(date(2026, 9, 1), date(2026, 9, 30))),
        ("what did I pay yesterday", DateRange(date(2026, 10, 8), date(2026, 10, 8))),
        ("nilituma jana", DateRange(date(2026, 10, 8), date(2026, 10, 8))),
        ("statement from 1/3/2026 to 31/3/2026", DateRange(date(2026, 3, 1), date(2026, 3, 31))),
        ("statement ya miezi sita", DateRange(date(2026, 4, 9), TODAY)),
        ("statement for march", DateRange(date(2026, 3, 1), date(2026, 3, 31))),
        ("payment on 5th October", DateRange(date(2026, 10, 5), date(2026, 10, 5))),
        ("my balance", None),
    ],
)
def test_date_ranges(text: str, expected: DateRange | None) -> None:
    assert parse_date_range(text, TODAY) == expected


def test_intent_categories_match_intent_router(settings: Settings) -> None:
    raw = json.loads(settings.intents_path.read_text(encoding="utf-8"))
    assert {i["id"]: i["category"] for i in raw["intents"]} == {k.value: v.value for k, v in INTENT_CATEGORY.items()}
