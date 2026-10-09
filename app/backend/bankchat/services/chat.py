"""POST /api/chat: route the message, answer view/info intents, PREPARE (never execute) actions.

    message -> router -> route
        direct   view/info intent  -> read-only reply
        confirm  action intent     -> pending action (slots + missing slots), customer must confirm
        reject                     -> polite decline
        llm                        -> "llm_pending": the LLM step is not built yet, ask to rephrase

SAFETY: nothing in this module changes a balance. Money moves only in
services/actions.confirm_action, called from POST /api/actions/{id}/confirm.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from bankchat.db.models import User
from bankchat.domain import ACTION_INTENTS, Intent, ReplyKind, RouteName
from bankchat.formatting import format_money, mask_account
from bankchat.router_client.base import RouterClient, RouterDecision
from bankchat.schemas import ChatResponse, DecisionOut, PendingActionOut, ReplyOut
from bankchat.services import view_replies
from bankchat.services.accounts import accounts_by_type, list_accounts
from bankchat.services.actions import create_pending_action, to_pending_action_out
from bankchat.services.audit import record_decision
from bankchat.services.payees import find_internal_payee_account
from bankchat.services.transfer_help import TransferFaq, transfer_help_reply
from bankchat.settings import Settings
from bankchat.slots.action_slots import build_action_slots, missing_slots
from bankchat.slots.bank_directory import BankDirectory
from bankchat.slots.entities import MessageEntities, extract_entities

log = logging.getLogger(__name__)

LLM_PENDING_TEXT = (
    "I'm not sure I understood that. Could you rephrase it? For example: \"what's my balance\", "
    "\"show my last transactions\", or \"send 2,000 to 0712 345 678\"."
)
REJECT_TEXT = (
    "Sorry, I can't help with that here. I can show balances and statements, find transactions and "
    "receipts, explain transfer limits and charges, and prepare transfers and payments for you to confirm."
)
INTENT_LABELS: dict[str, str] = {
    Intent.INTERNAL_TRANSFER: "transfer",
    Intent.EXTERNAL_TRANSFER: "send",
    Intent.LIPA_NA_MPESA: "pay",
}


@dataclass(frozen=True)
class ChatContext:
    settings: Settings
    router: RouterClient
    bank: BankDirectory
    faq: TransferFaq


@dataclass(frozen=True)
class _Request:
    session: Session
    ctx: ChatContext
    user: User
    message: str
    entities: MessageEntities


ViewHandler = Callable[[_Request], ReplyOut]

VIEW_HANDLERS: dict[str, ViewHandler] = {
    Intent.BALANCE_INQUIRY: lambda r: view_replies.balance_reply(r.session, r.ctx.settings, r.user, r.entities),
    Intent.MINI_STATEMENT: lambda r: view_replies.mini_statement_reply(r.session, r.ctx.settings, r.user, r.entities),
    Intent.FULL_STATEMENT: lambda r: view_replies.full_statement_reply(
        r.session, r.ctx.settings, r.user, r.entities, r.message
    ),
    Intent.FIND_TRANSACTION: lambda r: view_replies.find_transaction_reply(
        r.session, r.ctx.settings, r.user, r.entities, r.message
    ),
    Intent.VIEW_RECEIPT: lambda r: view_replies.view_receipt_reply(
        r.session, r.ctx.settings, r.user, r.entities, r.message
    ),
    Intent.TRANSFER_HELP: lambda r: transfer_help_reply(r.ctx.faq, r.message),
}


def _decision_out(decision: RouterDecision) -> DecisionOut:
    return DecisionOut(
        intent=decision.intent,
        route=decision.route,
        score=decision.score,
        margin=decision.margin,
        top3=decision.top3,
        nearest_examples=decision.nearest_examples,
        reasons=decision.reasons,
        latency_ms=decision.latency_ms,
    )


def _describe_destination(slots: dict[str, Any]) -> str:
    if "to_account" in slots:
        return f"account {mask_account(str(slots['to_account']))}"
    if "destination" in slots:
        bank = f" at {str(slots['bank']).upper()}" if slots.get("bank") else ""
        return f"{slots['destination']}{bank}"
    if "till_or_paybill" in slots:
        account = f" account {slots['account_number']}" if slots.get("account_number") else ""
        return f"{slots.get('payment_type', 'till/paybill')} {slots['till_or_paybill']}{account}"
    return "the recipient"


def _confirm_text(intent: str, slots: dict[str, Any], missing: list[str], currency: str) -> str:
    verb = INTENT_LABELS.get(intent, intent)
    amount = format_money(slots["amount"], currency) if "amount" in slots else "an amount"
    source = f" from account {mask_account(str(slots['from_account']))}" if "from_account" in slots else ""
    summary = f"You want to {verb} {amount}{source} to {_describe_destination(slots)}."
    if missing:
        return f"{summary} To continue I need: {', '.join(missing)}."
    return f"{summary} Please confirm to proceed. Nothing is sent until you confirm."


def _prepare_action(req: _Request, intent: str) -> tuple[ReplyOut, PendingActionOut]:
    accounts = list_accounts(req.session, req.user.id)
    slots = build_action_slots(intent, req.entities, accounts_by_type(accounts), req.user.phone)
    if intent == Intent.INTERNAL_TRANSFER and "to_account" not in slots:
        payee = find_internal_payee_account(req.session, req.user.id, req.message)
        if payee:
            slots["to_account"] = payee
    action = create_pending_action(req.session, req.ctx.settings, req.user.id, intent, slots, req.message)
    missing = missing_slots(intent, slots)
    reply = ReplyOut(
        kind=ReplyKind.CONFIRM.value,
        text=_confirm_text(intent, slots, missing, req.ctx.settings.currency),
        data=None,
    )
    return reply, to_pending_action_out(action)


def _reply(req: _Request, decision: RouterDecision) -> tuple[ReplyOut, PendingActionOut | None]:
    if decision.route == RouteName.CONFIRM and decision.intent in ACTION_INTENTS:
        return _prepare_action(req, decision.intent)
    if decision.route == RouteName.DIRECT and decision.intent in VIEW_HANDLERS:
        return VIEW_HANDLERS[decision.intent](req), None
    if decision.route == RouteName.REJECT:
        return ReplyOut(kind=ReplyKind.REJECT.value, text=REJECT_TEXT), None
    if decision.route != RouteName.LLM:
        log.warning("unexpected decision route=%s intent=%s; treating as llm", decision.route, decision.intent)
    log.info("llm fallback pending (not built): user=%s intent=%s score=%.3f", req.user.id, decision.intent, decision.score)
    return ReplyOut(kind=ReplyKind.LLM_PENDING.value, text=LLM_PENDING_TEXT), None


def handle_chat(session: Session, ctx: ChatContext, user: User, message: str) -> ChatResponse:
    decision = ctx.router.route(message)
    req = _Request(session, ctx, user, message, extract_entities(message, ctx.bank))
    reply, pending = _reply(req, decision)
    record_decision(
        session,
        user_id=user.id,
        message=message,
        router_mode=ctx.router.mode,
        decision=decision,
        reply_kind=reply.kind,
        pending_action_id=pending.id if pending else None,
    )
    session.commit()
    return ChatResponse(decision=_decision_out(decision), reply=reply, pending_action=pending)
