"""Request/response models: the API contract the frontend is built against. Keep these exact."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from bankchat.clock import as_utc

MAX_MESSAGE_LENGTH = 1000
MAX_USERNAME_LENGTH = 50
MAX_PASSWORD_LENGTH = 128


class _UtcModel(BaseModel):
    """Datetimes always serialised as aware UTC ISO strings (SQLite returns naive ones)."""

    model_config = ConfigDict(from_attributes=True)

    @field_validator("created_at", "expires_at", mode="after", check_fields=False)
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return as_utc(value)


# --- auth / user ------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=MAX_USERNAME_LENGTH)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserOut


# --- accounts / transactions ----------------------------------------------------------

class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str
    type: Literal["savings", "current"]
    currency: str
    balance: float


class MeResponse(UserOut):
    accounts: list[AccountOut]


class TransactionOut(_UtcModel):
    id: int
    reference: str
    account_id: int
    direction: Literal["in", "out"]
    amount: float
    channel: str
    counterparty: str
    description: str
    created_at: datetime
    balance_after: float


class ReceiptOut(_UtcModel):
    reference: str
    amount: float
    channel: str
    counterparty: str
    from_account: str
    created_at: datetime
    status: str


# --- chat ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)

    @field_validator("message")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value.strip()


class DecisionOut(BaseModel):
    intent: str
    route: Literal["direct", "confirm", "reject", "llm"]
    score: float
    margin: float
    top3: list[tuple[str, float]]
    nearest_examples: list[tuple[str, str, float]]
    reasons: list[str]
    latency_ms: float


ReplyKindLiteral = Literal[
    "balance", "mini_statement", "full_statement", "find_transaction", "view_receipt",
    "transfer_help", "confirm", "reject", "llm_pending",
]


class ReplyOut(BaseModel):
    kind: ReplyKindLiteral
    text: str
    data: dict[str, Any] | None = None


class PendingActionOut(_UtcModel):
    id: str
    intent: str
    slots: dict[str, Any]
    missing_slots: list[str]
    expires_at: datetime


class ChatResponse(BaseModel):
    decision: DecisionOut
    reply: ReplyOut
    pending_action: PendingActionOut | None = None


# --- actions ------------------------------------------------------------------------

class ConfirmRequest(BaseModel):
    slots: dict[str, Any] = Field(default_factory=dict)


class ConfirmResponse(BaseModel):
    status: Literal["executed"] = "executed"
    transaction: TransactionOut
    receipt: ReceiptOut


class CancelResponse(BaseModel):
    status: Literal["cancelled"] = "cancelled"


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    router_mode: str
