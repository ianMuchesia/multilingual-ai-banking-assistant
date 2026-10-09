"""Domain vocabulary shared by the database, services and API: enums and intent categories."""

from enum import StrEnum


class AccountType(StrEnum):
    SAVINGS = "savings"
    CURRENT = "current"


class Direction(StrEnum):
    IN = "in"
    OUT = "out"


class Channel(StrEnum):
    INTERNAL = "internal"
    PESALINK = "pesalink"
    MPESA = "mpesa"
    TILL = "till"
    PAYBILL = "paybill"
    SALARY = "salary"
    DEPOSIT = "deposit"


class ActionStatus(StrEnum):
    PENDING = "pending"
    EXECUTED = "executed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class RouteName(StrEnum):
    DIRECT = "direct"
    CONFIRM = "confirm"
    REJECT = "reject"
    LLM = "llm"


class ReplyKind(StrEnum):
    BALANCE = "balance"
    MINI_STATEMENT = "mini_statement"
    FULL_STATEMENT = "full_statement"
    FIND_TRANSACTION = "find_transaction"
    VIEW_RECEIPT = "view_receipt"
    TRANSFER_HELP = "transfer_help"
    CONFIRM = "confirm"
    REJECT = "reject"
    LLM_PENDING = "llm_pending"


class Intent(StrEnum):
    BALANCE_INQUIRY = "balance_inquiry"
    MINI_STATEMENT = "mini_statement"
    FULL_STATEMENT = "full_statement"
    FIND_TRANSACTION = "find_transaction"
    VIEW_RECEIPT = "view_receipt"
    INTERNAL_TRANSFER = "internal_transfer"
    EXTERNAL_TRANSFER = "external_transfer"
    LIPA_NA_MPESA = "lipa_na_mpesa"
    TRANSFER_HELP = "transfer_help"
    UNSUPPORTED = "unsupported"


class Category(StrEnum):
    VIEW = "view"
    ACTION = "action"
    INFO = "info"
    NONE = "none"


# Mirrors intent-router/data/intents.json (a test checks they agree).
INTENT_CATEGORY: dict[Intent, Category] = {
    Intent.BALANCE_INQUIRY: Category.VIEW,
    Intent.MINI_STATEMENT: Category.VIEW,
    Intent.FULL_STATEMENT: Category.VIEW,
    Intent.FIND_TRANSACTION: Category.VIEW,
    Intent.VIEW_RECEIPT: Category.VIEW,
    Intent.INTERNAL_TRANSFER: Category.ACTION,
    Intent.EXTERNAL_TRANSFER: Category.ACTION,
    Intent.LIPA_NA_MPESA: Category.ACTION,
    Intent.TRANSFER_HELP: Category.INFO,
    Intent.UNSUPPORTED: Category.NONE,
}

ACTION_INTENTS: frozenset[str] = frozenset(i.value for i, c in INTENT_CATEGORY.items() if c is Category.ACTION)


def category_of(intent: str) -> Category | None:
    try:
        return INTENT_CATEGORY[Intent(intent)]
    except ValueError:
        return None


class DestinationType(StrEnum):
    BANK = "bank"
    MOBILE = "mobile"


class PaymentType(StrEnum):
    TILL = "till"
    PAYBILL = "paybill"
