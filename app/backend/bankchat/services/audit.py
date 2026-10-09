"""router_audit: one row per chat message with the routing decision and what we replied."""

from sqlalchemy.orm import Session

from bankchat.db.models import RouterAudit
from bankchat.router_client.base import RouterDecision


def record_decision(
    session: Session,
    *,
    user_id: int,
    message: str,
    router_mode: str,
    decision: RouterDecision,
    reply_kind: str,
    pending_action_id: str | None,
) -> RouterAudit:
    row = RouterAudit(
        user_id=user_id,
        message=message,
        router_mode=router_mode,
        intent=decision.intent,
        route=decision.route,
        score=decision.score,
        margin=decision.margin,
        reasons=list(decision.reasons),
        latency_ms=decision.latency_ms,
        reply_kind=reply_kind,
        pending_action_id=pending_action_id,
    )
    session.add(row)
    return row
